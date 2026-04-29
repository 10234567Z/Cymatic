"""
Twilio voice webhook routes.

Flow:
  POST /voice/inbound  — Twilio rings → detect new/existing user → ask for PIN
  POST /voice/pin      — DTMF digits arrive → verify or create user + wallet → start stream
  WS   /voice/stream   — Twilio Media Stream → forward to platform_agents → TTS back
"""

import json
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Form, Query, WebSocket
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


def _stream_url(call_sid: str) -> str:
    """Build the wss:// URL for Twilio to connect the Media Stream."""
    base = settings.BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
    return f"{base}/voice/stream?callSid={call_sid}"


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
            vr.say(
                "Your vault is ready. "
                "You can now check your balance, transfer tokens, or monitor your positions. "
                "Please speak your request after the tone."
            )
            vr.connect().stream(url=_stream_url(CallSid))
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
            vr.say(
                "Authenticated. "
                "Please speak your request after the tone."
            )
            vr.connect().stream(url=_stream_url(CallSid))
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


@router.websocket("/stream")
async def stream(websocket: WebSocket, callSid: str = Query(...)) -> None:
    """
    Twilio Media Stream WebSocket.

    Twilio sends JSON frames (start / media / stop).
    We forward each frame to platform_agents, then on stop we play back
    the TTS audio payloads Twilio-style over the same socket.
    """
    await websocket.accept()
    stream_sid: str | None = None

    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            try:
                raw = await websocket.receive_text()
            except Exception:
                break

            event: dict = json.loads(raw)
            event_type = event.get("event")

            if event_type == "start":
                stream_sid = (event.get("start") or {}).get("streamSid")

            sess = session_store.get(callSid)
            if not sess or sess.state != CallState.AUTHENTICATED:
                if event_type == "stop":
                    break
                continue

            try:
                resp = await client.post(
                    f"{settings.PLATFORM_AGENTS_URL}/agents/voice/process-twilio-event",
                    json={
                        "callSid": callSid,
                        "caller": sess.phone_number,
                        "event": event,
                    },
                )
                resp.raise_for_status()
                result = resp.json()
            except Exception:
                if event_type == "stop":
                    break
                continue

            # On stop: play back TTS audio then close
            if event_type == "stop" and stream_sid:
                payloads = (result.get("result") or {}).get("twilioMediaPayloads", [])
                for payload in payloads:
                    await websocket.send_text(
                        json.dumps({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": payload},
                        })
                    )
                await websocket.send_text(
                    json.dumps({"event": "stop", "streamSid": stream_sid})
                )
                session_store.destroy(callSid)
                break

    await websocket.close()
