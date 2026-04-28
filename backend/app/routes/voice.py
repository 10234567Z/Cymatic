"""
Twilio voice webhook routes.

Flow:
  POST /voice/inbound  — Twilio rings → detect new/existing user → ask for PIN
  POST /voice/pin      — DTMF digits arrive → verify or create user + wallet → greet
"""

from typing import Annotated

from fastapi import APIRouter, Form
from fastapi.responses import Response
from twilio.twiml.voice_response import Gather, VoiceResponse

from app.config import settings
from app.core import auth
from app.core import session as session_store
from app.models.session import CallState
from app.models.user import NewUserInput
from app.services import supabase_client
from app.services.turnkey import create_wallet

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_PIN_ATTEMPTS = 3


def _xml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="application/xml")


@router.post("/inbound")
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

