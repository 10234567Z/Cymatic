"""
Twilio voice webhook routes.

Flow:
  POST /voice/inbound  — Twilio rings → detect new/existing user → ask for PIN
  POST /voice/pin      — DTMF digits arrive → verify or create user + wallet
  POST /voice/chat     — Twilio posts speech transcript → call agents → speak reply → listen again
  POST /voice/status   — Twilio call-status callback → send SMS summary on call end
"""

import logging
import traceback
import threading
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Form
from fastapi.responses import Response
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import Gather, VoiceResponse

from app.config import settings
from app.core import auth
from app.core import session as session_store
from app.core.twilio_security import validate_twilio_signature
from app.models.session import CallSession, CallState
from app.models.user import NewUserInput
from app.services import supabase_client
from app.services.turnkey import create_wallet
from app.services.inft import mint_caller_inft

log = logging.getLogger("voice")
router = APIRouter(prefix="/voice", tags=["voice"])

MAX_PIN_ATTEMPTS = 3


def _send_call_summary(sess: CallSession) -> None:
    """Send an SMS to the caller with their wallet address + conversation recap."""
    try:
        lines = [
            "-- Cymatic Call Summary --",
            f"Wallet: {sess.wallet_address or 'not set'}",
            "",
        ]
        if sess.conversation:
            for turn in sess.conversation:
                prefix = "You" if turn["role"] == "user" else "Cymatic"
                lines.append(f"{prefix}: {turn['text']}")
        else:
            lines.append("No conversation recorded.")

        body = "\n".join(lines)
        # Twilio SMS has a 1600-char limit — truncate gracefully
        if len(body) > 1580:
            body = body[:1577] + "..."

        client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            to=sess.phone_number,
            from_=settings.TWILIO_PHONE_NUMBER,
            body=body,
        )
        log.warning("[sms] summary sent to %s", sess.phone_number)
    except Exception as exc:
        log.error("[sms] failed to send summary: %s", exc)


def _chat_gather(vr: VoiceResponse, prompt: str) -> None:
    """Append a speech Gather to vr, speaking prompt while listening."""
    gather = Gather(
        input="speech",
        action=f"{settings.BASE_URL}/voice/chat",
        method="POST",
        speechTimeout="1",       # wait 3 s of silence before cutting off (was "auto" ~1 s)
        speechModel="phone_call",
        timeout=10,               # wait up to 10 s for the user to start speaking
        actionOnEmptyResult=True, # still POST to /chat even if nothing heard (so we re-prompt)
        language="en-US",
    )
    gather.say(prompt)
    vr.append(gather)


def _xml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="application/xml")


@router.post("/inbound", dependencies=[Depends(validate_twilio_signature)])
async def inbound(
    CallSid: Annotated[str, Form()],
    From: Annotated[str, Form()],
) -> Response:
    """Twilio calls this on every inbound call."""
    user = await supabase_client.get_user_by_phone(From)

    if user:
        state = CallState.EXISTING_USER
        prompt = "Welcome back to Cymatic. Please enter your PIN, then press hash."
    else:
        state = CallState.NEW_USER
        prompt = (
            "Welcome to Cymatic. "
            "Please enter a PIN to secure your vault, then press hash."
        )

    session_store.create(CallSid, From, state)

    vr = VoiceResponse()
    gather = Gather(
        input="dtmf",
        action=f"{settings.BASE_URL}/voice/pin",
        method="POST",
        finish_on_key="#",
        timeout=15,
    )
    gather.say(prompt)
    vr.append(gather)
    # Fallback if the caller doesn't press anything
    vr.say("We didn't receive your PIN. Please call back.")
    vr.hangup()

    return _xml(vr)


@router.post("/pin", dependencies=[Depends(validate_twilio_signature)])
async def pin(
    CallSid: Annotated[str, Form()],
    Digits: Annotated[str, Form()] = "",
) -> Response:
    """Twilio posts here after the caller finishes entering DTMF digits."""
    sess = session_store.get(CallSid)
    vr = VoiceResponse()

    if not sess or not Digits:
        vr.say("Something went wrong. Please call back.")
        vr.hangup()
        return _xml(vr)

    # ── New user: hash PIN, provision wallet, create DB record ───────────────
    if sess.state == CallState.NEW_USER:
        try:
            pin_hash = auth.hash_pin(Digits)
            wallet = create_wallet(sess.phone_number)
            user = await supabase_client.create_user(
                NewUserInput(
                    phone_number=sess.phone_number,
                    pin_hash=pin_hash,
                    turnkey_wallet_id=wallet["wallet_id"],
                    wallet_address=wallet["address"],
                    sub_org_id=wallet["sub_org_id"],
                    private_key_id="",
                )
            )
            session_store.update(
                CallSid,
                state=CallState.AUTHENTICATED,
                user_id=user.id,
                wallet_address=wallet["address"],
                sub_org_id=wallet["sub_org_id"],
            )
            # Mint iNFT in background — don't block the call
            threading.Thread(
                target=mint_caller_inft,
                args=(wallet["address"], sess.phone_number, user.id),
                daemon=True,
            ).start()
            _chat_gather(
                vr,
                "Your vault is ready. "
                "What would you want me to do?",
            )
        except Exception as exc:
            traceback.print_exc()
            print(f"[vault setup error] {exc}")
            vr.say("We couldn't set up your vault right now. Please call back.")
            vr.hangup()

        return _xml(vr)

    # ── Existing user: verify PIN ─────────────────────────────────────────────
    if sess.state == CallState.EXISTING_USER:
        user = await supabase_client.get_user_by_phone(sess.phone_number)

        if user and auth.verify_pin(Digits, user.pin_hash):
            session_store.update(
                CallSid,
                state=CallState.AUTHENTICATED,
                user_id=user.id,
                wallet_address=user.wallet_address,
                sub_org_id=user.sub_org_id,
            )
            _chat_gather(vr, "Authenticated. What would you like to do?")
            return _xml(vr)

        # Wrong PIN
        attempts = sess.pin_attempts + 1
        session_store.update(CallSid, pin_attempts=attempts)

        if attempts >= MAX_PIN_ATTEMPTS:
            session_store.destroy(CallSid)
            vr.say("Too many incorrect attempts. Goodbye.")
            vr.hangup()
            return _xml(vr)

        remaining = MAX_PIN_ATTEMPTS - attempts
        gather = Gather(
            input="dtmf",
            action=f"{settings.BASE_URL}/voice/pin",
            method="POST",
            finish_on_key="#",
            timeout=15,
        )
        gather.say(
            f"Incorrect PIN. {remaining} attempt{'s' if remaining > 1 else ''} remaining. "
            "Please try again, then press hash."
        )
        vr.append(gather)
        vr.say("No input received. Goodbye.")
        vr.hangup()
        return _xml(vr)

    # Shouldn't reach here but be safe
    vr.say("Unexpected session state. Please call back.")
    vr.hangup()
    return _xml(vr)


@router.post("/chat", dependencies=[Depends(validate_twilio_signature)])
async def chat(
    CallSid: Annotated[str, Form()],
    SpeechResult: Annotated[str, Form()] = "",
) -> Response:
    """
    Twilio posts here after the caller finishes speaking.
    SpeechResult contains the transcript. We call platform_agents,
    speak the reply, then listen again for the next turn.
    """
    sess = session_store.get(CallSid)
    vr = VoiceResponse()

    if not sess or sess.state != CallState.AUTHENTICATED:
        vr.say("Session expired. Please call back.")
        vr.hangup()
        return _xml(vr)

    if not SpeechResult.strip():
        _chat_gather(vr, "I didn't catch that. What would you like to do?")
        return _xml(vr)

    # Log user's turn
    conversation = list(sess.conversation)
    conversation.append({"role": "user", "text": SpeechResult.strip()})
    session_store.update(CallSid, conversation=conversation)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.PLATFORM_AGENTS_URL}/agents/voice/process-text",
                json={
                    "callSid": CallSid,
                    "caller": sess.phone_number,
                    "text": SpeechResult,
                    "walletAddress": sess.wallet_address or "",
                    "subOrgId": sess.sub_org_id or "",
                },
            )
            resp.raise_for_status()
            result = resp.json()
        log.warning("[chat] platform_agents result: %s", {k: v for k, v in result.items() if k != "twilioMediaPayloads"})
        spoken = result.get("responseText") or "Request completed."
        hangup = result.get("hangup", False)
    except Exception as exc:
        log.error("[chat] platform_agents call failed: %s\n%s", exc, traceback.format_exc())
        spoken = "Sorry, I had trouble processing that. Please try again."
        hangup = False

    # Get or re-initialize session
    sess = session_store.get(CallSid)
    if not sess:
        vr.say("Your session has expired. Please call back.")
        vr.hangup()
        return _xml(vr)

    # Log agent's reply
    conversation = list(sess.conversation)
    conversation.append({"role": "agent", "text": spoken})
    session_store.update(CallSid, conversation=conversation)

    if hangup:
        vr.say(spoken)
        final_sess = session_store.get(CallSid)
        session_store.destroy(CallSid)
        if final_sess:
            threading.Thread(
                target=_send_call_summary,
                args=(final_sess,),
                daemon=True,
            ).start()
        vr.hangup()
    else:
        _chat_gather(vr, f"{spoken}  Anything else I can help you with?")
    return _xml(vr)


@router.post("/status")
async def call_status(
    CallSid: Annotated[str, Form()],
    CallStatus: Annotated[str, Form()] = "",
) -> Response:
    """
    Twilio status callback — fired when call ends for any reason (hangup, drop, etc.).
    Sends SMS summary if a session is still in memory (i.e. call ended without saying bye).
    Configure in Twilio console: Voice → Phone Number → Call Status Callback URL
    → {BASE_URL}/voice/status
    """
    terminal_statuses = {"completed", "busy", "failed", "no-answer", "canceled"}
    if CallStatus.lower() in terminal_statuses:
        sess = session_store.get(CallSid)
        if sess:
            session_store.destroy(CallSid)
            if sess.state == CallState.AUTHENTICATED and sess.conversation:
                threading.Thread(
                    target=_send_call_summary,
                    args=(sess,),
                    daemon=True,
                ).start()
    return Response(status_code=204)
