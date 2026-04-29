"""
Twilio voice webhook routes.

Flow:
  POST /voice/inbound  — Twilio rings → detect new/existing user → ask for PIN
  POST /voice/pin      — DTMF digits arrive → verify or create user + wallet
  POST /voice/chat     — Twilio posts speech transcript → call agents → speak reply → listen again
"""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Form
from fastapi.responses import Response
from twilio.twiml.voice_response import Gather, VoiceResponse

from app.config import settings
from app.core import auth
from app.core import session as session_store
from app.core.twilio_security import validate_twilio_signature
from app.models.session import CallState
from app.models.user import NewUserInput
from app.services import supabase_client
from app.services.turnkey import create_wallet

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_PIN_ATTEMPTS = 3


def _chat_gather(vr: VoiceResponse, prompt: str) -> None:
    """Append a speech Gather to vr, speaking prompt while listening."""
    gather = Gather(
        input="speech",
        action=f"{settings.BASE_URL}/voice/chat",
        method="POST",
        speechTimeout="auto",
        language="en-US",
    )
    gather.say(prompt)
    vr.append(gather)
    # Fallback if nothing was heard
    vr.say("I didn't catch that. Goodbye.")
    vr.hangup()


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
                )
            )
            session_store.update(
                CallSid,
                state=CallState.AUTHENTICATED,
                user_id=user.id,
                wallet_address=wallet["address"],
            )
            _chat_gather(
                vr,
                "Your vault is ready. "
                "You can check your balance, transfer tokens, or monitor your Aave position. "
                "What would you like to do?",
            )
        except Exception:
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

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.PLATFORM_AGENTS_URL}/agents/voice/process-text",
                json={
                    "callSid": CallSid,
                    "caller": sess.phone_number,
                    "text": SpeechResult,
                },
            )
            resp.raise_for_status()
            result = resp.json()
        spoken = result.get("responseText") or "Request completed."
    except Exception:
        spoken = "Sorry, I had trouble processing that. Please try again."

    _chat_gather(vr, f"{spoken}  Anything else I can help you with?")
    return _xml(vr)
