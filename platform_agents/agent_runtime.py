from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    from agents.contracts import AXLMessage
    from agents.execution_agent import ExecutionAgent
    from agents.inference_client import InferenceClient
    from agents.keeperhub_client import KeeperHubWorkflowClient
    from agents.reasoning_agent import ReasoningAgent
    from agents.response_agent import ResponseAgent
    from agents.transport import AXLMeshTransport
    from agents.voice_agent import VoiceAgent
except ImportError:  # pragma: no cover
    from platform_agents.agents.contracts import AXLMessage
    from platform_agents.agents.execution_agent import ExecutionAgent
    from platform_agents.agents.inference_client import InferenceClient
    from platform_agents.agents.keeperhub_client import KeeperHubWorkflowClient
    from platform_agents.agents.reasoning_agent import ReasoningAgent
    from platform_agents.agents.response_agent import ResponseAgent
    from platform_agents.agents.transport import AXLMeshTransport
    from platform_agents.agents.voice_agent import VoiceAgent


_TOOL_TO_AGENT: dict[str, str] = {
    "reason_over_transcript": "reasoning",
    "execute_workflow": "execution",
    "phrase_response": "response",
}


@dataclass
class AgentRuntime:
    transport: AXLMeshTransport
    voice: VoiceAgent
    reasoning: ReasoningAgent
    execution: ExecutionAgent
    response: ResponseAgent

    def _dispatch(self, to_agent: str, intent: str, payload: dict[str, Any], trace_id: str, from_agent: str) -> dict[str, Any]:
        message = AXLMessage(
            trace_id=trace_id,
            from_agent=from_agent,
            to_agent=to_agent,
            intent=intent,
            payload=payload,
        )
        if to_agent == "reasoning":
            return self.reasoning.handle(message)
        if to_agent == "execution":
            return self.execution.handle(message)
        if to_agent == "response":
            return self.response.handle(message)
        return {
            "ok": False,
            "error": f"Unsupported target agent '{to_agent}'",
            "trace_id": trace_id,
        }

    def call_tool(self, tool_name: str, arguments: dict[str, Any], request_id: str) -> dict[str, Any]:
        if tool_name == "voice_process_text":
            return self.voice.process_text(
                call_sid=str(arguments.get("callSid", "")),
                caller=str(arguments.get("caller", "")),
                text=str(arguments.get("text", "")),
            )
        if tool_name == "voice_process_twilio_event":
            event = arguments.get("event")
            if not isinstance(event, dict):
                return {"ok": False, "error": "voice_process_twilio_event requires event object"}
            return self.voice.process_twilio_event(
                call_sid=str(arguments.get("callSid", "")),
                caller=str(arguments.get("caller", "")),
                event=event,
            )

        target = _TOOL_TO_AGENT.get(tool_name)
        if not target:
            return {"ok": False, "error": f"Unknown tool '{tool_name}'"}
        return self._dispatch(
            to_agent=target,
            intent=tool_name,
            payload=arguments,
            trace_id=str(request_id),
            from_agent="remote",
        )

    def dispatch_a2a(self, envelope: dict[str, Any]) -> dict[str, Any]:
        trace_id = str(envelope.get("trace_id", "a2a-call"))
        from_agent = str(envelope.get("from_agent", "remote"))
        intent = str(envelope.get("intent", ""))

        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        to_agent = str(envelope.get("to_agent", ""))
        if not to_agent:
            to_agent = _TOOL_TO_AGENT.get(intent, "")

        if not to_agent and intent in {"voice_process_text", "voice_process_twilio_event"}:
            to_agent = "voice"

        if to_agent == "voice":
            return self.call_tool(intent, payload, trace_id)

        return self._dispatch(
            to_agent=to_agent,
            intent=intent,
            payload=payload,
            trace_id=trace_id,
            from_agent=from_agent,
        )


def load_env() -> None:
    candidates = [
        Path.cwd() / ".env",
        Path.cwd() / "backend" / ".env",
        Path(__file__).resolve().parents[1] / "backend" / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate, override=False)


def build_runtime(force_local_transport: bool = False) -> AgentRuntime:
    load_env()

    transport = AXLMeshTransport()
    if force_local_transport:
        transport.mode = "local"

    zg_client = InferenceClient()
    keeperhub_client = KeeperHubWorkflowClient()

    execution = ExecutionAgent(keeperhub_client)
    response = ResponseAgent(zg_client)
    reasoning = ReasoningAgent(transport, zg_client)
    voice = VoiceAgent(transport, zg_client)

    transport.register("execution", execution.handle)
    transport.register("response", response.handle)
    transport.register("reasoning", reasoning.handle)

    return AgentRuntime(
        transport=transport,
        voice=voice,
        reasoning=reasoning,
        execution=execution,
        response=response,
    )


def list_mcp_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "reason_over_transcript",
            "description": "Reason over transcript and route execution + response",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "transcript": {"type": "string"},
                    "caller": {"type": "string"},
                    "callSid": {"type": "string"},
                    "callerProfile": {"type": "object"},
                },
                "required": ["transcript", "caller"],
            },
        },
        {
            "name": "execute_workflow",
            "description": "Select and execute KeeperHub workflow",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string"},
                    "executionInput": {"type": "object"},
                },
                "required": ["intent"],
            },
        },
        {
            "name": "phrase_response",
            "description": "Build voice-safe response text",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string"},
                    "execution": {"type": "object"},
                },
                "required": ["intent"],
            },
        },
        {
            "name": "voice_process_text",
            "description": "Process a text utterance end-to-end via voice agent",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "callSid": {"type": "string"},
                    "caller": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["callSid", "caller", "text"],
            },
        },
        {
            "name": "voice_process_twilio_event",
            "description": "Handle Twilio media stream event",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "callSid": {"type": "string"},
                    "caller": {"type": "string"},
                    "event": {"type": "object"},
                },
                "required": ["callSid", "caller", "event"],
            },
        },
    ]
