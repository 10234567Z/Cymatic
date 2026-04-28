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


@router.post("/pin")
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
                "What would you like to do?"
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
            vr.say(
                "Authenticated. "
                "What would you like to do? "
                "You can check your balance, transfer tokens, or check your Aave health."
            )
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
