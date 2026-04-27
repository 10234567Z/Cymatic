from __future__ import annotations

from typing import Any

from .contracts import AXLMessage
from .keeperhub_client import KeeperHubWorkflowClient


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
