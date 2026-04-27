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
        self.client = httpx.Client(timeout=30.0)

    def _query_broker(self, provider_address: str, query: str) -> str | None:
        if not self.broker_base_url or not provider_address:
            return None

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
            return None
        except Exception:
            return None

    def infer_intent(self, text: str) -> dict[str, Any]:
        broker_reply = self._query_broker(
            self.provider_llm,
            (
                "Extract intent and entities as compact JSON with keys intent, entities, confidence. "
                "Supported intents: check_token_balance, transfer_erc20, check_aave_health, monitor_aave_health. "
                f"User text: {text}"
            ),
        )
        if broker_reply:
            try:
                import json

                parsed = json.loads(broker_reply)
                if isinstance(parsed, dict) and isinstance(parsed.get("intent"), str):
                    parsed.setdefault("entities", {})
                    parsed.setdefault("confidence", 0.75)
                    return parsed
            except Exception:
                pass

        normalized = text.lower()
        intent = "check_token_balance"
        if any(x in normalized for x in ["send", "transfer", "pay"]):
            intent = "transfer_erc20"
        elif "aave" in normalized and any(x in normalized for x in ["monitor", "alert", "watch"]):
            intent = "monitor_aave_health"
        elif "aave" in normalized:
            intent = "check_aave_health"

        entities: dict[str, Any] = {}
        if "base" in normalized:
            entities["chainId"] = "8453"
        elif "arbitrum" in normalized:
            entities["chainId"] = "42161"
        elif "polygon" in normalized:
            entities["chainId"] = "137"
        else:
            entities["chainId"] = "1"

        for token in ["USDC", "USDT", "DAI", "WETH", "ETH"]:
            if token.lower() in normalized:
                entities["token"] = token
                break

        return {"intent": intent, "entities": entities, "confidence": 0.72}

    def transcribe_mulaw_base64(self, b64_audio: str) -> str:
        if not b64_audio:
            return ""
        broker_reply = self._query_broker(
            self.provider_stt,
            (
                "Transcribe this base64-encoded mulaw 8kHz audio payload. "
                "Return only the transcription text. "
                f"payload={b64_audio[:16000]}"
            ),
        )
        if isinstance(broker_reply, str) and broker_reply.strip():
            return broker_reply.strip()

        # If a real 0G STT endpoint is configured, this is where the API call should go.
        # We keep a deterministic fallback so backend integration can proceed now.
        raw = base64.b64decode(b64_audio)
        if len(raw) < 160:
            return ""
        return "voice input received"

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
        # Fallback: u-law silence frames (0xFF) that Twilio can stream.
        # Replace with real 0G TTS audio bytes when TTS endpoint is configured.
        duration_s = min(2.0, max(0.5, len(text) / 35.0))
        frame_size = 160  # 20ms at 8kHz for ulaw
        total_frames = max(1, int((duration_s * 1000) / 20))
        frames = [bytes([0xFF] * frame_size) for _ in range(total_frames)]
        return [base64.b64encode(frame).decode("ascii") for frame in frames if frame]
