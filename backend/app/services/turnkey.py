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

_CHAIN_RPC: dict[str, str] = {
    "1": "https://cloudflare-eth.com",
    "8453": "https://mainnet.base.org",
    "84532": "https://sepolia.base.org",
    "11155111": "https://rpc.sepolia.org",
    "42161": "https://arb1.arbitrum.io/rpc",
}

_ERC20_TRANSFER_SELECTOR = bytes.fromhex("a9059cbb")


def _rlp_encode(item: Any) -> bytes:
    if isinstance(item, int):
        item = b"" if item == 0 else item.to_bytes((item.bit_length() + 7) // 8, "big")
    if isinstance(item, bytes):
        if len(item) == 1 and item[0] < 0x80:
            return item
        length = len(item)
        if length <= 55:
            return bytes([0x80 + length]) + item
        lb = length.to_bytes((length.bit_length() + 7) // 8, "big")
        return bytes([0xb7 + len(lb)]) + lb + item
    if isinstance(item, list):
        encoded = b"".join(_rlp_encode(i) for i in item)
        length = len(encoded)
        if length <= 55:
            return bytes([0xc0 + length]) + encoded
        lb = length.to_bytes((length.bit_length() + 7) // 8, "big")
        return bytes([0xf7 + len(lb)]) + lb + encoded
    raise TypeError(f"Cannot RLP encode {type(item)}")


def _rpc_call(rpc_url: str, method: str, params: list) -> Any:
    resp = httpx.post(
        rpc_url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data["result"]


def sign_and_broadcast_erc20(
    sub_org_id: str,
    from_address: str,
    to_address: str,
    token_address: str,
    amount_units: int,
    chain_id: int,
    private_key_id: str = "",
) -> str:
    """Sign an ERC20 transfer via Turnkey and broadcast it. Returns tx hash."""
    rpc_url = _CHAIN_RPC.get(str(chain_id))
    if not rpc_url:
        raise ValueError(f"Unsupported chain_id: {chain_id}")

    nonce = int(_rpc_call(rpc_url, "eth_getTransactionCount", [from_address, "latest"]), 16)

    try:
        fee_history = _rpc_call(rpc_url, "eth_feeHistory", [1, "latest", [50]])
        base_fee = int(fee_history["baseFeePerGas"][-1], 16)
        max_priority = 1_000_000_000  # 1 gwei
        max_fee = base_fee * 2 + max_priority
    except Exception:
        gp = int(_rpc_call(rpc_url, "eth_gasPrice", []), 16)
        max_priority = gp
        max_fee = gp

    calldata = (
        _ERC20_TRANSFER_SELECTOR
        + bytes.fromhex(to_address[2:].lower().zfill(64))
        + amount_units.to_bytes(32, "big")
    )

    unsigned_tx = b"\x02" + _rlp_encode([
        chain_id, nonce, max_priority, max_fee, 100_000,
        bytes.fromhex(token_address[2:].lower()), 0, calldata, [],
    ])

    body: dict[str, Any] = {
        "type": "ACTIVITY_TYPE_SIGN_TRANSACTION_V2",
        "timestampMs": str(int(time.time() * 1000)),
        "organizationId": sub_org_id,
        "parameters": {
            "signWith": from_address,
            "unsignedTransaction": unsigned_tx.hex(),
            "type": "TRANSACTION_TYPE_ETHEREUM",
        },
    }
    body_json = json.dumps(body, separators=(",", ":"))
    stamp = _stamp(body_json)

    resp = httpx.post(
        f"{_BASE_URL}/public/v1/submit/sign_transaction",
        content=body_json,
        headers={"Content-Type": "application/json", "X-Stamp": stamp},
        timeout=30.0,
    )
    if not resp.is_success:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Turnkey sign_transaction {resp.status_code}: {detail}")
    data = resp.json()
    signed_tx = (
        data.get("activity", {})
        .get("result", {})
        .get("signTransactionResult", {})
        .get("signedTransaction", "")
    )
    if not signed_tx:
        raise RuntimeError(f"Turnkey signing failed: {data}")

    tx_hash = _rpc_call(rpc_url, "eth_sendRawTransaction", [f"0x{signed_tx}"])
    return tx_hash


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

    # Hex-encode the DER signature bytes for Turnkey
    sig_hex = sig_der.hex()

    envelope = {
        "publicKey": settings.TURNKEY_API_PUBLIC_KEY,
        "signature": sig_hex,
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
            "rootUsers": [
                {
                    "userName": "backend-api",
                    "userEmail": "api@cymatic.local",
                    "apiKeys": [
                        {
                            "apiKeyName": "parent-key",
                            "publicKey": settings.TURNKEY_API_PUBLIC_KEY,
                            "curveType": "API_KEY_CURVE_P256",
                        }
                    ],
                    "authenticators": [],
                    "oauthProviders": [],
                }
            ],
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
        raise RuntimeError(f"Turnkey wallet creation failed: missing wallet_id/address. {data}")

    return {
        "sub_org_id": sub_org_id,
        "wallet_id": wallet_id,
        "address": address,
        "private_key_id": "",  # Not used — we sign with address instead
    }
