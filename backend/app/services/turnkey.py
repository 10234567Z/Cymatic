"""
Turnkey wallet service.

Creates one sub-organization (= one isolated wallet) per phone number.
The parent-org API key controls all sub-orgs, so no user passkeys are needed.
"""

import base64
import json
import time
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from app.config import settings

_BASE_URL = "https://api.turnkey.com"


def _stamp(body_json: str) -> str:
    """
    Build a Turnkey API stamp — a base64url-encoded JSON envelope containing
    the API public key and a P-256 signature over the raw request body bytes.
    """
    raw_key = bytes.fromhex(settings.TURNKEY_API_PRIVATE_KEY)
    private_key = ec.derive_private_key(
        int.from_bytes(raw_key, "big"),
        ec.SECP256R1(),
        default_backend(),
    )

    sig_der = private_key.sign(body_json.encode("utf-8"), ec.ECDSA(hashes.SHA256()))

    # DER → fixed-width (r || s) so the server can verify it
    r, s = decode_dss_signature(sig_der)
    sig_bytes = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    sig_b64 = base64.urlsafe_b64encode(sig_bytes).rstrip(b"=").decode()

    envelope = {
        "publicKey": settings.TURNKEY_API_PUBLIC_KEY,
        "signature": sig_b64,
        "scheme": "SIGNATURE_SCHEME_TK_API_P256",
    }
    envelope_json = json.dumps(envelope, separators=(",", ":"))
    return base64.urlsafe_b64encode(envelope_json.encode()).rstrip(b"=").decode()


def create_wallet(phone_number: str) -> dict[str, str]:
    """
    Create a Turnkey sub-organization with one Ethereum wallet account.

    Each phone number gets its own isolated sub-org so keys are never
    mixed across users.

    Returns:
        {"sub_org_id": "...", "wallet_id": "...", "address": "0x..."}

    Raises:
        httpx.HTTPStatusError: on non-2xx from Turnkey
        RuntimeError: if the response is missing expected fields
    """
    body: dict[str, Any] = {
        "type": "ACTIVITY_TYPE_CREATE_SUB_ORGANIZATION_V7",
        "timestampMs": str(int(time.time() * 1000)),
        "organizationId": settings.TURNKEY_ORG_ID,
        "parameters": {
            "subOrganizationName": f"cymatic-{phone_number}",
            "rootUsers": [],
            "rootQuorumThreshold": 1,
            "wallet": {
                "walletName": "Default Wallet",
                "accounts": [
                    {
                        "curve": "CURVE_SECP256K1",
                        "pathFormat": "PATH_FORMAT_BIP32",
                        "path": "m/44'/60'/0'/0/0",
                        "addressFormat": "ADDRESS_FORMAT_ETHEREUM",
                    }
                ],
            },
            "disableEmailRecovery": True,
            "disableEmailAuth": True,
        },
    }

    body_json = json.dumps(body, separators=(",", ":"))
    stamp = _stamp(body_json)

    resp = httpx.post(
        f"{_BASE_URL}/public/v1/submit/create_sub_organization",
        content=body_json,
        headers={
            "Content-Type": "application/json",
            "X-Stamp": stamp,
        },
        timeout=30.0,
    )
    resp.raise_for_status()

    data = resp.json()
    v7 = (
        data.get("activity", {})
        .get("result", {})
        .get("createSubOrganizationResultV7", {})
    )

    sub_org_id = v7.get("subOrganizationId", "")
    wallet = v7.get("wallet", {})
    wallet_id = wallet.get("walletId", "")
    addresses = wallet.get("addresses", [])
    address = addresses[0] if addresses else ""

    if not wallet_id or not address:
        raise RuntimeError(f"Turnkey wallet creation failed: {data}")

    return {
        "sub_org_id": sub_org_id,
        "wallet_id": wallet_id,
        "address": address,
    }
