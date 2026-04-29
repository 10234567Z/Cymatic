"""
FastAPI dependency that validates the X-Twilio-Signature header.

Twilio signs every webhook request with HMAC-SHA1 using your Auth Token.
If the signature is missing or invalid we reject with 403.

Usage:
    @router.post("/inbound", dependencies=[Depends(validate_twilio_signature)])
"""

from fastapi import Depends, HTTPException, Request
from twilio.request_validator import RequestValidator

from app.config import settings

_validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)


async def validate_twilio_signature(request: Request) -> None:
    signature = request.headers.get("X-Twilio-Signature", "")

    # Full URL Twilio signed — must match exactly what Twilio saw
    url = str(request.url)

    # For form-encoded webhooks Twilio signs the POST params too
    form_data: dict[str, str] = {}
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        raw_form = await request.form()
        form_data = dict(raw_form)

    if not _validator.validate(url, form_data, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
