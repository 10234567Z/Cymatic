from __future__ import annotations

import base64
import io
import json
import os
import struct
from typing import Any

import httpx

try:
    import audioop  # Python < 3.13
except ModuleNotFoundError:
    try:
        import audioop_lts as audioop  # audioop-lts backport for Python 3.13+
    except ModuleNotFoundError:
        audioop = None  # type: ignore[assignment]


def _mulaw_wav_bytes(mulaw_data: bytes, sample_rate: int = 8000) -> bytes:
    """Wrap raw mulaw bytes in a RIFF WAV container (format tag 7 = MULAW)."""
    num_channels = 1
    bits_per_sample = 8
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = len(mulaw_data)
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))
    buf.write(struct.pack("<H", 7))  # MULAW
    buf.write(struct.pack("<H", num_channels))
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", byte_rate))
    buf.write(struct.pack("<H", block_align))
    buf.write(struct.pack("<H", bits_per_sample))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(mulaw_data)
    return buf.getvalue()


def _pcm24k_to_mulaw8k_frames(pcm_bytes: bytes) -> list[bytes]:
    """Downsample 24kHz 16-bit mono PCM → 8kHz mulaw, return 20ms frames."""
    if audioop is None:
        raise RuntimeError(
            "audioop or audioop-lts is required for audio conversion. "
            "Install it: pip install audioop-lts"
        )
    # Downsample 24000→8000 (factor 3)
    pcm8k, _ = audioop.ratecv(pcm_bytes, 2, 1, 24000, 8000, None)
    mulaw = audioop.lin2ulaw(pcm8k, 2)
    frame_size = 160  # 20ms at 8kHz
    return [mulaw[i : i + frame_size] for i in range(0, len(mulaw), frame_size) if mulaw[i : i + frame_size]]


class InferenceClient:
    """Plain OpenAI-compatible inference client (LLM, STT, TTS)."""

    def __init__(self) -> None:
        base = os.environ["OPENAI_BASE_URL"].rstrip("/")
        # Strip trailing /v1 so we can append it consistently below
        self.base_url = base[:-3] if base.endswith("/v1") else base
        self.api_key = os.environ["OPENAI_API_KEY"]
        self.llm_model = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
        self.stt_model = os.getenv("OPENAI_STT_MODEL", "whisper-1")
        self.tts_model = os.getenv("OPENAI_TTS_MODEL", "tts-1")
        self.tts_voice = os.getenv("OPENAI_TTS_VOICE", "alloy")
        self._http = httpx.Client(timeout=60.0)

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def infer_intent(self, text: str) -> dict[str, Any]:
        resp = self._http.post(
            f"{self.base_url}/v1/chat/completions",
            headers=self._auth_headers(),
            json={
                "model": self.llm_model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful voice assistant for Cymatic, a crypto wallet app. "
                            "Extract intent and entities from the user text. "
                            "Reply with compact JSON: {intent, entities, confidence}. "
                            "Supported intents: check_token_balance, transfer_erc20, "
                            "check_aave_health, monitor_aave_health, general_query. "
                            "Use general_query for anything not related to the above crypto actions "
                            "(e.g. weather, trivia, greetings, jokes, recommendations). "
                            "For general_query, include an 'answer' field in entities with a concise, "
                            "friendly, voice-appropriate response to the question."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                "temperature": 0,
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not isinstance(parsed.get("intent"), str):
            raise RuntimeError("LLM response missing intent field")
        parsed.setdefault("entities", {})
        parsed.setdefault("confidence", 0.9)
        return parsed

    def transcribe_mulaw_base64(self, b64_audio: str) -> str:
        if not b64_audio:
            raise RuntimeError("Audio payload is empty")
        raw_mulaw = base64.b64decode(b64_audio)
        wav_bytes = _mulaw_wav_bytes(raw_mulaw)
        resp = self._http.post(
            f"{self.base_url}/v1/audio/transcriptions",
            headers=self._auth_headers(),
            files={"file": ("audio.wav", wav_bytes, "audio/wav")},
            data={"model": self.stt_model},
        )
        resp.raise_for_status()
        text = resp.json().get("text", "").strip()
        if not text:
            raise RuntimeError("STT returned empty transcription")
        return text

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
            output = (execution_result.get("output") or {})
            tx_hash = output.get("txHash")
            if tx_hash:
                return f"Transfer complete. Transaction hash starts with {tx_hash[:10]}."
            return "Transfer submitted."
        return "Request completed."

    def text_to_twilio_mulaw_payloads(self, text: str) -> list[str]:
        resp = self._http.post(
            f"{self.base_url}/v1/audio/speech",
            headers=self._auth_headers(),
            json={
                "model": self.tts_model,
                "voice": self.tts_voice,
                "input": text,
                "response_format": "pcm",  # 24kHz 16-bit mono PCM
            },
        )
        resp.raise_for_status()
        pcm_bytes = resp.content
        frames = _pcm24k_to_mulaw8k_frames(pcm_bytes)
        return [base64.b64encode(f).decode("ascii") for f in frames]
