from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import httpx


# Minimal ABI — only the functions we call from Python.
CALLER_INFT_ABI = [
    {
        "name": "registerCaller",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "callerId", "type": "string"},
            {"name": "encryptedURI", "type": "string"},
            {"name": "metadataHash", "type": "bytes32"},
        ],
        "outputs": [{"name": "tokenId", "type": "uint256"}],
    },
    {
        "name": "updateMetadata",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "tokenId", "type": "uint256"},
            {"name": "newEncryptedURI", "type": "string"},
            {"name": "newMetadataHash", "type": "bytes32"},
        ],
        "outputs": [],
    },
    {
        "name": "authorizeUsage",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "tokenId", "type": "uint256"},
            {"name": "executor", "type": "address"},
            {"name": "permissions", "type": "bytes"},
        ],
        "outputs": [],
    },
    {
        "name": "isRegistered",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "callerId", "type": "string"}],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "getTokenId",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "callerId", "type": "string"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "getEncryptedURI",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "outputs": [{"name": "", "type": "string"}],
    },
    {
        "name": "getMetadataHash",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "outputs": [{"name": "", "type": "bytes32"}],
    },
    {
        "name": "isAuthorized",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "tokenId", "type": "uint256"},
            {"name": "executor", "type": "address"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
]


def _profile_hash(profile: dict[str, Any]) -> bytes:
    """Deterministic keccak256-like hash of profile JSON (using sha3_256 as a stand-in)."""
    raw = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha3_256(raw).digest()


class CallerINFTClient:
    """Python client for CallerINFT contract on 0G network.

    Uses JSON-RPC directly so the platform agent service doesn't need web3.py as a
    hard runtime dependency (web3 is optional). When CALLER_INFT_ADDRESS is not set,
    all methods are no-ops that return sensible defaults so the rest of the platform
    keeps working locally.
    """

    def __init__(self) -> None:
        self.contract_address = os.getenv("CALLER_INFT_ADDRESS", "")
        self.rpc_url = os.getenv("OG_RPC_URL", "https://evmrpc-testnet.0g.ai")
        self.deployer_address = os.getenv("CALLER_INFT_DEPLOYER_ADDRESS", "")
        self._http = httpx.Client(timeout=30.0)
        self._enabled = bool(self.contract_address and self.deployer_address)

    # ── Internal JSON-RPC helpers ────────────────────────────────────────────

    def _call(self, data: str) -> str:
        """eth_call (read-only) — returns hex result string."""
        resp = self._http.post(
            self.rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_call",
                "params": [
                    {"to": self.contract_address, "data": data},
                    "latest",
                ],
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        if "error" in payload:
            raise RuntimeError(f"eth_call error: {payload['error']}")
        return payload["result"]

    def _send_transaction(self, data: str) -> str:
        """eth_sendRawTransaction placeholder.

        In production, sign transactions with the deployer private key using
        eth_account (web3.py) before broadcasting. Here we raise to make the
        boundary explicit.
        """
        raise NotImplementedError(
            "Transaction signing requires web3.py + DEPLOYER_PRIVATE_KEY. "
            "Call _send_transaction_signed() after installing web3."
        )

    @staticmethod
    def _encode_string(s: str) -> str:
        """ABI-encode a single dynamic string argument (simplified, ASCII-safe)."""
        enc = s.encode("utf-8")
        length_hex = f"{len(enc):064x}"
        data_hex = enc.hex().ljust((len(enc) + 31) // 32 * 64, "0")
        # offset 32 (0x20) + length + data
        return "0000000000000000000000000000000000000000000000000000000000000020" + length_hex + data_hex

    @staticmethod
    def _decode_bool(hex_result: str) -> bool:
        return int(hex_result, 16) != 0

    @staticmethod
    def _decode_uint256(hex_result: str) -> int:
        return int(hex_result, 16)

    # ── Function selectors (keccak256 first 4 bytes) ─────────────────────────

    _SEL_IS_REGISTERED = "c4d66de8"   # isRegistered(string)
    _SEL_GET_TOKEN_ID = "35a89f0f"    # getTokenId(string)

    # ── Public API ────────────────────────────────────────────────────────────

    def is_registered(self, caller_id: str) -> bool:
        """Return True if a caller already has an iNFT."""
        if not self._enabled:
            return False
        data = "0x" + self._SEL_IS_REGISTERED + self._encode_string(caller_id)
        try:
            result = self._call(data)
            return self._decode_bool(result)
        except Exception:
            return False

    def get_token_id(self, caller_id: str) -> int | None:
        """Return the tokenId for a registered caller, or None."""
        if not self._enabled:
            return None
        data = "0x" + self._SEL_GET_TOKEN_ID + self._encode_string(caller_id)
        try:
            result = self._call(data)
            token_id = self._decode_uint256(result)
            return token_id if token_id > 0 else None
        except Exception:
            return None

    def register_caller_web3(
        self,
        caller_id: str,
        profile: dict[str, Any],
        encrypted_uri: str = "",
    ) -> dict[str, Any]:
        """Register a new caller iNFT using web3.py (requires web3 installed).

        This is the production path. It signs + broadcasts `registerCaller`.
        Returns a summary dict with txHash and tokenId.
        """
        if not self._enabled:
            return {"ok": False, "reason": "iNFT disabled (CALLER_INFT_ADDRESS not set)"}

        try:
            from web3 import Web3  # type: ignore[import]
            from eth_account import Account  # type: ignore[import]
        except ImportError:
            return {"ok": False, "reason": "web3 not installed — pip install web3"}

        private_key = os.environ.get("DEPLOYER_PRIVATE_KEY", "")
        if not private_key:
            return {"ok": False, "reason": "DEPLOYER_PRIVATE_KEY not set"}

        w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(self.contract_address),
            abi=CALLER_INFT_ABI,
        )

        metadata_hash_bytes = _profile_hash(profile)
        metadata_hash = bytes(metadata_hash_bytes).ljust(32, b"\x00")[:32]

        acct = Account.from_key(private_key)
        tx = contract.functions.registerCaller(
            acct.address,
            caller_id,
            encrypted_uri or f"cymatic://profile/{caller_id}",
            metadata_hash,
        ).build_transaction(
            {
                "from": acct.address,
                "nonce": w3.eth.get_transaction_count(acct.address),
                "gas": 300_000,
                "gasPrice": w3.eth.gas_price,
            }
        )
        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        # Parse tokenId from Transfer event logs (topic[3] = tokenId for ERC-721).
        token_id: int | None = None
        for log in receipt.logs:
            if len(log["topics"]) >= 4:
                token_id = int(log["topics"][3].hex(), 16)
                break

        return {
            "ok": receipt.status == 1,
            "txHash": tx_hash.hex(),
            "tokenId": token_id,
            "callerId": caller_id,
        }

    def update_profile_web3(
        self,
        token_id: int,
        profile: dict[str, Any],
        encrypted_uri: str = "",
    ) -> dict[str, Any]:
        """Update caller profile metadata on-chain after a call."""
        if not self._enabled:
            return {"ok": False, "reason": "iNFT disabled"}

        try:
            from web3 import Web3
            from eth_account import Account
        except ImportError:
            return {"ok": False, "reason": "web3 not installed — pip install web3"}

        private_key = os.environ.get("DEPLOYER_PRIVATE_KEY", "")
        if not private_key:
            return {"ok": False, "reason": "DEPLOYER_PRIVATE_KEY not set"}

        w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(self.contract_address),
            abi=CALLER_INFT_ABI,
        )

        metadata_hash = bytes(_profile_hash(profile)).ljust(32, b"\x00")[:32]
        acct = Account.from_key(private_key)

        tx = contract.functions.updateMetadata(
            token_id,
            encrypted_uri or f"cymatic://profile/updated/{token_id}",
            metadata_hash,
        ).build_transaction(
            {
                "from": acct.address,
                "nonce": w3.eth.get_transaction_count(acct.address),
                "gas": 150_000,
                "gasPrice": w3.eth.gas_price,
            }
        )
        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        return {
            "ok": receipt.status == 1,
            "txHash": tx_hash.hex(),
            "tokenId": token_id,
        }

    def get_caller_profile_summary(self, caller_id: str) -> dict[str, Any]:
        """Return on-chain profile info for a caller (read-only, no web3 needed)."""
        if not self._enabled:
            return {"registered": False, "reason": "iNFT disabled"}

        registered = self.is_registered(caller_id)
        if not registered:
            return {"registered": False, "callerId": caller_id}

        token_id = self.get_token_id(caller_id)
        return {
            "registered": True,
            "callerId": caller_id,
            "tokenId": token_id,
            "contractAddress": self.contract_address,
            "network": self.rpc_url,
        }
