from __future__ import annotations

from typing import Any

from .contracts import AXLMessage
from .inference_client import InferenceClient


class ResponseAgent:
    def __init__(self, zg: InferenceClient):
        self.zg = zg

    def handle(self, message: AXLMessage) -> dict[str, Any]:
        intent = str(message.payload.get("intent", "check_token_balance"))
        execution_result = message.payload.get("execution", {})
        spoken_text = self.zg.render_voice_reply(intent, execution_result)
        return {
            "ok": True,
            "intent": intent,
            "spokenText": spoken_text,
        }
