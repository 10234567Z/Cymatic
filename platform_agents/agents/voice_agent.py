from __future__ import annotations

import base64
import uuid
from typing import Any

from .contracts import AXLMessage
from .transport import AXLMeshTransport
from .inference_client import InferenceClient
from .inft_client import CallerINFTClient


class VoiceAgent:
    def __init__(self, transport: AXLMeshTransport, zg: InferenceClient, inft: CallerINFTClient | None = None):
        self.transport = transport
        self.zg = zg
        self.inft = inft or CallerINFTClient()
        self._sessions: dict[str, dict[str, Any]] = {}

    def process_text(self, call_sid: str, caller: str, text: str, wallet_address: str = "", sub_org_id: str = "") -> dict[str, Any]:
        import logging
        log = logging.getLogger("voice_agent")
        log.warning("[process_text] transcript=%r caller=%s", text, caller)
        trace_id = str(uuid.uuid4())
        caller_profile = self.inft.get_caller_profile_summary(caller)
        reasoning_result = self.transport.send(
            AXLMessage(
                trace_id=trace_id,
                from_agent="voice",
                to_agent="reasoning",
                intent="reason_over_transcript",
                payload={
                    "callSid": call_sid,
                    "caller": caller,
                    "transcript": text,
                    "callerProfile": caller_profile,
                    "walletAddress": wallet_address,
                    "subOrgId": sub_org_id,
                },
            )
        )
        log.warning("[process_text] reasoning_result=%s", reasoning_result)
        if not reasoning_result.get("ok"):
            log.error("[process_text] reasoning failed: %s", reasoning_result.get("error"))
            return {
                "ok": False,
                "traceId": trace_id,
                "transcript": text,
                "error": reasoning_result.get("error", "Reasoning failed"),
                "twilioMediaPayloads": [],
            }

        spoken_text = reasoning_result.get("spokenText", "Request completed.")
        hangup = reasoning_result.get("hangup", False)
        log.warning("[process_text] spoken_text=%r hangup=%s", spoken_text, hangup)
        try:
            media_payloads = self.zg.text_to_twilio_mulaw_payloads(spoken_text)
        except Exception as exc:
            log.error("[process_text] TTS failed: %s", exc)
            media_payloads = []
        return {
            "ok": True,
            "traceId": trace_id,
            "transcript": text,
            "intent": reasoning_result.get("intent"),
            "selectedWorkflow": reasoning_result.get("selectedWorkflow"),
            "execution": reasoning_result.get("execution"),
            "responseText": spoken_text,
            "hangup": hangup,
            "twilioMediaPayloads": media_payloads,
        }

    def process_twilio_event(self, call_sid: str, caller: str, event: dict[str, Any]) -> dict[str, Any]:
        session = self._sessions.setdefault(call_sid, {"audio": bytearray(), "streamSid": None})
        event_type = event.get("event")

        if event_type == "start":
            start = event.get("start") or {}
            session["streamSid"] = start.get("streamSid")
            return {"ok": True, "event": "start", "callSid": call_sid}

        if event_type == "media":
            payload = ((event.get("media") or {}).get("payload"))
            if not isinstance(payload, str):
                return {"ok": False, "error": "Invalid media payload"}
            session["audio"].extend(base64.b64decode(payload))
            return {"ok": True, "event": "media", "bytesBuffered": len(session["audio"])}

        if event_type == "stop":
            audio = bytes(session["audio"])
            audio_b64 = base64.b64encode(audio).decode("ascii") if audio else ""
            transcript = self.zg.transcribe_mulaw_base64(audio_b64)
            # Ensure caller has an iNFT (register on first call)
            if not self.inft.is_registered(caller):
                self.inft.register_caller_web3(caller_id=caller, profile={"callSid": call_sid})
            result = self.process_text(call_sid=call_sid, caller=caller, text=transcript)
            # Update on-chain profile summary after the call completes
            token_id = self.inft.get_token_id(caller)
            if token_id is not None:
                self.inft.update_profile_web3(
                    token_id=token_id,
                    profile={
                        "callSid": call_sid,
                        "intent": (result.get("result") or {}).get("intent"),
                        "workflow": (result.get("result") or {}).get("selectedWorkflow"),
                    },
                )
            self._sessions.pop(call_sid, None)
            return {
                "ok": result.get("ok", False),
                "event": "stop",
                "transcript": transcript,
                "result": result,
            }

        return {"ok": False, "error": f"Unsupported Twilio event: {event_type}"}
