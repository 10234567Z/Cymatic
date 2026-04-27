from __future__ import annotations

import base64
import os
from typing import Any

import httpx


class ZeroGInferenceClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("ZERO_G_INFERENCE_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("ZERO_G_INFERENCE_API_KEY", "")
        self.llm_model = os.getenv("ZERO_G_LLM_MODEL", "")
        self.stt_model = os.getenv("ZERO_G_STT_MODEL", "")
        self.tts_model = os.getenv("ZERO_G_TTS_MODEL", "")
        # Optional direct integration path via official 0G compute broker-style API.
        self.broker_base_url = os.getenv("ZERO_G_BROKER_BASE_URL", "").rstrip("/")
        self.provider_llm = os.getenv("ZERO_G_PROVIDER_ADDRESS_LLM", "")
        self.provider_stt = os.getenv("ZERO_G_PROVIDER_ADDRESS_STT", "")
        self.provider_tts = os.getenv("ZERO_G_PROVIDER_ADDRESS_TTS", "")
        self.client = httpx.Client(timeout=30.0)

    def _query_broker(self, provider_address: str, query: str) -> str | None:
        if not self.broker_base_url:
            raise RuntimeError("ZERO_G_BROKER_BASE_URL is required")
        if not provider_address:
            raise RuntimeError("0G provider address is required")

        try:
            response = self.client.post(
                f"{self.broker_base_url}/api/services/query",
                json={
                    "providerAddress": provider_address,
                    "query": query,
                    "fallbackFee": 0.000001,
                },
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("response") if isinstance(payload, dict) else None
            if isinstance(result, dict):
                content = result.get("content")
                if isinstance(content, str) and content.strip():
                    return content
            raise RuntimeError("0G broker returned empty response content")
        except Exception as exc:
            raise RuntimeError(f"0G broker query failed: {exc}") from exc

    def infer_intent(self, text: str) -> dict[str, Any]:
        broker_reply = self._query_broker(
            self.provider_llm,
            (
                "Extract intent and entities as compact JSON with keys intent, entities, confidence. "
                "Supported intents: check_token_balance, transfer_erc20, check_aave_health, monitor_aave_health. "
                f"User text: {text}"
            ),
        )
        try:
            import json

            parsed = json.loads(broker_reply)
            if isinstance(parsed, dict) and isinstance(parsed.get("intent"), str):
                parsed.setdefault("entities", {})
                parsed.setdefault("confidence", 0.75)
                return parsed
        except Exception as exc:
            raise RuntimeError(f"0G intent response parse failed: {exc}") from exc

        raise RuntimeError("0G intent response missing required fields")

    def transcribe_mulaw_base64(self, b64_audio: str) -> str:
        if not b64_audio:
            raise RuntimeError("Audio payload is empty")
        broker_reply = self._query_broker(
            self.provider_stt,
            (
                "Transcribe this base64-encoded mulaw 8kHz audio payload. "
                "Return only the transcription text. "
                f"payload={b64_audio[:16000]}"
            ),
        )
        if not isinstance(broker_reply, str) or not broker_reply.strip():
            raise RuntimeError("0G STT returned empty transcription")
        return broker_reply.strip()

    def render_voice_reply(self, intent: str, execution_result: dict[str, Any]) -> str:
        if intent == "check_token_balance":
            output = (execution_result.get("output") or {}).get("balance") or {}
            symbol = output.get("symbol", "token")
            amount = output.get("balance", "unknown")
            return f"Your {symbol} balance is {amount}."
        if intent == "check_aave_health":
            output = execution_result.get("output") or {}
            hf = output.get("healthFactor") or output.get("health_factor")
            if hf is None:
                return "I could not fetch your Aave health factor right now."
            return f"Your Aave health factor is {hf}."
        if intent == "monitor_aave_health":
            return "Aave health monitoring is now active."
        if intent == "transfer_erc20":
            tx_hash = (execution_result.get("output") or {}).get("txHash")
            if tx_hash:
                return f"Transfer complete. Transaction hash starts with {tx_hash[:10]}."
            return "Transfer request submitted."
        return "Request completed."

    def text_to_twilio_mulaw_payloads(self, text: str) -> list[str]:
        tts_reply = self._query_broker(
            self.provider_tts,
            (
                "Convert this text to base64 mulaw 8kHz audio frame payloads for Twilio media stream. "
                "Return JSON array of base64 frame strings only. "
                f"text={text}"
            ),
        )
        try:
            import json

            parsed = json.loads(tts_reply)
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                return parsed
        except Exception as exc:
            raise RuntimeError(f"0G TTS response parse failed: {exc}") from exc

        raise RuntimeError("0G TTS response missing base64 frame list")
