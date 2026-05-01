from __future__ import annotations

import re
import uuid
from typing import Any

from .contracts import AXLMessage
from .transport import AXLMeshTransport
from .inference_client import InferenceClient


TOKEN_BY_SYMBOL_AND_CHAIN = {
    "1": {
        "USDC": "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    },
    "8453": {
        "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "USDT": "0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2",
    },
    "84532": {
        # Base Sepolia testnet
        "USDC": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    },
    "42161": {
        "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "USDT": "0xFd086bC7CD5C481DCC9C85ebe478A1C0b69FCbb9",
    },
}


class ReasoningAgent:
    def __init__(self, transport: AXLMeshTransport, zg: InferenceClient):
        self.transport = transport
        self.zg = zg

    _GOODBYE_WORDS = {"bye", "goodbye", "hang up", "end call", "that's all", "thats all", "done", "quit", "exit", "stop", "nothing", "no thanks", "no thank you"}

    def _is_goodbye(self, text: str) -> bool:
        lower = text.lower().strip()
        return any(word in lower for word in self._GOODBYE_WORDS)

    def handle(self, message: AXLMessage) -> dict[str, Any]:
        import logging
        log = logging.getLogger("reasoning_agent")
        transcript = str(message.payload.get("transcript", ""))
        caller = str(message.payload.get("caller", "unknown"))
        wallet_address = str(message.payload.get("walletAddress", ""))
        sub_org_id = str(message.payload.get("subOrgId", ""))
        log.warning("[reasoning] transcript=%r", transcript)

        if self._is_goodbye(transcript):
            return {
                "ok": True,
                "intent": "goodbye",
                "entities": {},
                "spokenText": "Goodbye! Have a great day.",
                "hangup": True,
            }

        try:
            intent_data = self.zg.infer_intent(transcript)
        except Exception as exc:
            log.error("[reasoning] LLM infer_intent failed: %s", exc)
            return {"ok": False, "error": f"LLM failed: {exc}"}
        log.warning("[reasoning] intent_data=%s", intent_data)
        intent = str(intent_data.get("intent", "check_token_balance"))
        entities = dict(intent_data.get("entities", {}))

        # General questions — answer directly, skip execution pipeline
        if intent == "general_query":
            answer = str(entities.get("answer", "I'm not sure about that, but I'm here to help with your crypto wallet."))
            return {
                "ok": True,
                "intent": "general_query",
                "entities": entities,
                "spokenText": answer,
            }
        addresses = re.findall(r"0x[a-fA-F0-9]{40}", transcript)
        if addresses:
            entities.setdefault("address", addresses[0])
        if len(addresses) > 1:
            entities.setdefault("toAddress", addresses[1])

        # Extract phone numbers (e.g. "+917382120692" or spoken digits grouped as phone)
        phones = re.findall(r"\+?\d[\d\s\-]{7,14}\d", transcript)
        phones = ["".join(filter(str.isdigit, p)) for p in phones]
        phones = ["+" + p if not p.startswith("+") else p for p in phones if len(p) >= 8]
        if phones and intent == "transfer_erc20" and not entities.get("toAddress"):
            entities.setdefault("toPhone", phones[0])

        execution_input = self._build_execution_input(intent, entities, wallet_address, sub_org_id)

        exec_msg = AXLMessage(
            trace_id=message.trace_id,
            from_agent="reasoning",
            to_agent="execution",
            intent="execute_workflow",
            payload={
                "intent": intent,
                "caller": caller,
                "entities": entities,
                "executionInput": execution_input,
            },
        )
        exec_result = self.transport.send(exec_msg)
        log.warning("[reasoning] exec_result=%s", exec_result)
        if not exec_result.get("ok"):
            log.error("[reasoning] execution failed: %s", exec_result.get("error"))
            return {
                "ok": False,
                "intent": intent,
                "entities": entities,
                "error": exec_result.get("error", "Execution failed"),
            }

        response_msg = AXLMessage(
            trace_id=message.trace_id,
            from_agent="reasoning",
            to_agent="response",
            intent="phrase_response",
            payload={
                "intent": intent,
                "execution": exec_result.get("execution", {}),
            },
        )
        response_result = self.transport.send(response_msg)

        return {
            "ok": True,
            "intent": intent,
            "entities": entities,
            "selectedWorkflow": exec_result.get("selectedWorkflow"),
            "execution": exec_result.get("execution"),
            "spokenText": response_result.get("spokenText", "Request completed."),
        }

    def _build_execution_input(self, intent: str, entities: dict[str, Any], wallet_address: str = "", sub_org_id: str = "") -> dict[str, Any]:
        chain_id = str(entities.get("chainId", "8453"))
        token = str(entities.get("token", "USDC")).upper()
        default_addr = "0x0000000000000000000000000000000000000000"
        token_addr = TOKEN_BY_SYMBOL_AND_CHAIN.get(chain_id, TOKEN_BY_SYMBOL_AND_CHAIN["1"]).get(token)
        if not token_addr:
            token_addr = TOKEN_BY_SYMBOL_AND_CHAIN["1"]["USDC"]

        if intent == "check_token_balance":
            return {
                "chainId": chain_id,
                "address": entities.get("address") or wallet_address or default_addr,
                "tokenAddress": token_addr,
            }
        if intent == "transfer_erc20":
            return {
                "chainId": chain_id,
                "fromAddress": wallet_address,
                "subOrgId": sub_org_id,
                "toAddress": entities.get("toAddress", ""),
                "toPhone": entities.get("toPhone", ""),
                "tokenAddress": token_addr,
                "amount": entities.get("amount", "1"),
            }
        if intent == "check_aave_health":
            return {
                "chainId": chain_id,
                "walletAddress": entities.get("address", default_addr),
            }
        if intent == "monitor_aave_health":
            return {
                "chainId": chain_id,
                "walletAddress": entities.get("address", default_addr),
                "healthThreshold": float(entities.get("healthThreshold", 1.5)),
            }
        return {
            "chainId": chain_id,
            "address": entities.get("address", default_addr),
            "tokenAddress": token_addr,
        }
