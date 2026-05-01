from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import httpx

from .contracts import AXLMessage
from .keeperhub_client import KeeperHubWorkflowClient

_BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# USDC = 6 decimals, most others = 18
_TOKEN_DECIMALS: dict[str, int] = {
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": 6,  # ETH USDC
    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": 6,  # Base USDC
    "0xaf88d065e77c8cc2239327c5edb3a432268e5831": 6,  # Arb USDC
    "0x036cbd53842c5426634e7929541ec2318f3dcf7e": 6,  # Base Sepolia USDC
    "0xdac17f958d2ee523a2206206994597c13d831ec7": 6,  # ETH USDT
}


INTENT_TO_MATCH = {
    "check_token_balance": {
        "patterns": ["*balance*", "*token*"],
        "action": "web3/check-token-balance",
    },
    "transfer_erc20": {
        "patterns": ["*transfer*", "*send*"],
        "action": "web3/transfer-token",
    },
    "check_aave_health": {
        "patterns": ["*aave*", "*health*"],
        "action": "web3/read-contract",
    },
    "monitor_aave_health": {
        "patterns": ["*monitor*", "*alert*"],
        "action": "web3/read-contract",
    },
}


class ExecutionAgent:
    def __init__(self, keeperhub: KeeperHubWorkflowClient):
        self.keeperhub = keeperhub

    def handle(self, message: AXLMessage) -> dict[str, Any]:
        payload = message.payload
        intent = str(payload.get("intent", "check_token_balance"))

        # Transfer is handled directly via backend Turnkey signing
        if intent == "transfer_erc20":
            return self._handle_transfer(payload.get("executionInput", {}))

        # Balance check is handled directly via backend RPC call
        if intent == "check_token_balance":
            return self._handle_balance(payload.get("executionInput", {}))

        workflow_meta = INTENT_TO_MATCH.get(intent, INTENT_TO_MATCH["check_token_balance"])

        selected = self.keeperhub.select_workflow(
            wildcard_patterns=workflow_meta["patterns"],
            action_hint=workflow_meta["action"],
        )
        if not selected:
            return {
                "ok": False,
                "error": f"No workflow matched for intent {intent}",
                "intent": intent,
                "selectedWorkflow": None,
            }

        execution_input = payload.get("executionInput", {})
        result = self.keeperhub.execute(selected["id"], execution_input)
        return {
            "ok": True,
            "intent": intent,
            "selectedWorkflow": {
                "id": selected.get("id"),
                "name": selected.get("name"),
                "description": selected.get("description", ""),
            },
            "execution": result,
        }

    def _handle_balance(self, execution_input: dict[str, Any]) -> dict[str, Any]:
        address = execution_input.get("address", "")
        token_address = execution_input.get("tokenAddress", "")
        chain_id = int(execution_input.get("chainId", 8453))

        if not address or not token_address:
            return {"ok": False, "intent": "check_token_balance", "error": "Missing address or tokenAddress in executionInput"}

        # KeeperHub's web3/check-token-balance action does not support dynamic address
        # resolution via API — template vars are not interpolated at runtime. We route
        # directly through the backend RPC endpoint which accepts dynamic params from code.
        workflow_id = os.getenv("KEEPERHUB_WORKFLOW_ID_CHECK_TOKEN_BALANCE", "erd67zvt366dk0jkkshgz")
        try:
            resp = httpx.post(
                f"{_BACKEND_URL}/execution/internal/balance",
                json={"address": address, "token_address": token_address, "chain_id": chain_id},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "ok": True,
                "intent": "check_token_balance",
                "selectedWorkflow": {
                    "id": workflow_id,
                    "name": "check_token_balance",
                    "description": "ERC-20 balance via direct RPC (Base Sepolia)",
                },
                "execution": {
                    "workflowId": workflow_id,
                    "executionId": None,
                    "status": "success",
                    "output": data,
                    "error": None,
                },
            }
        except Exception as e:
            return {"ok": False, "intent": "check_token_balance", "error": str(e)}

    def _resolve_to_address(self, to_phone: str) -> str | None:
        """Look up a Cymatic user's wallet address by phone number."""
        try:
            resp = httpx.get(f"{_BACKEND_URL}/execution/users/wallet/{to_phone}", timeout=10)
            if resp.status_code == 200:
                return resp.json().get("walletAddress")
        except Exception:
            pass
        return None

    def _resolve_key_id(self, wallet_address: str) -> tuple[str, str] | None:
        """Look up a Cymatic user's private key ID and sub_org_id by wallet address."""
        try:
            resp = httpx.get(f"{_BACKEND_URL}/execution/users/key-id/{wallet_address}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return (data.get("privateKeyId"), data.get("subOrgId"))
        except Exception:
            pass
        return None

    def _handle_transfer(self, execution_input: dict[str, Any]) -> dict[str, Any]:
        sub_org_id = execution_input.get("subOrgId", "")
        from_address = execution_input.get("fromAddress", "")
        to_address = execution_input.get("toAddress", "")
        to_phone = execution_input.get("toPhone", "")
        token_address = execution_input.get("tokenAddress", "")

        # Resolve phone → wallet address if toAddress not provided
        if not to_address and to_phone:
            resolved = self._resolve_to_address(to_phone)
            if not resolved:
                return {
                    "ok": False,
                    "intent": "transfer_erc20",
                    "error": f"No Cymatic wallet found for {to_phone}. They need to register first.",
                }
            to_address = resolved
        amount_str = str(execution_input.get("amount", "1"))
        chain_id = int(execution_input.get("chainId", 8453))

        if not from_address:
            return {
                "ok": False,
                "intent": "transfer_erc20",
                "error": "Wallet not set up for signing. Please call back and re-register.",
            }

        # Resolve wallet address → private key ID and sub_org_id
        key_info = self._resolve_key_id(from_address)
        if not key_info:
            return {
                "ok": False,
                "intent": "transfer_erc20",
                "error": "Could not retrieve signing credentials. Please call back.",
            }
        private_key_id, resolved_sub_org_id = key_info
        if not sub_org_id:
            sub_org_id = resolved_sub_org_id

        if not to_address:
            return {
                "ok": False,
                "intent": "transfer_erc20",
                "error": "No destination address or phone number provided.",
            }

        decimals = _TOKEN_DECIMALS.get(token_address.lower(), 18)
        try:
            amount_units = int(Decimal(amount_str) * Decimal(10 ** decimals))
        except Exception:
            amount_units = 10 ** decimals  # default 1 token

        try:
            resp = httpx.post(
                f"{_BACKEND_URL}/execution/internal/transfer",
                json={
                    "sub_org_id": sub_org_id,
                    "from_address": from_address,
                    "to_address": to_address,
                    "token_address": token_address,
                    "amount_units": amount_units,
                    "chain_id": chain_id,
                    "private_key_id": private_key_id,
                },
                timeout=45.0,
            )
            if not resp.is_success:
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text or f"HTTP {resp.status_code}"
                return {"ok": False, "intent": "transfer_erc20", "error": detail}
            data = resp.json()
            return {
                "ok": True,
                "intent": "transfer_erc20",
                "selectedWorkflow": {"name": "direct-turnkey-transfer"},
                "execution": {"output": data},
            }
        except Exception as exc:
            return {
                "ok": False,
                "intent": "transfer_erc20",
                "error": str(exc),
            }
