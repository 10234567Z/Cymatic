from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from agents.contracts import AXLMessage
from agents.execution_agent import ExecutionAgent
from agents.keeperhub_client import KeeperHubWorkflowClient
from agents.reasoning_agent import ReasoningAgent
from agents.response_agent import ResponseAgent
from agents.transport import AXLMeshTransport
from agents.voice_agent import VoiceAgent
from agents.zero_g_client import ZeroGInferenceClient


def load_env() -> None:
    candidates = [
        Path.cwd() / ".env",
        Path.cwd() / "backend" / ".env",
        Path(__file__).resolve().parents[1] / "backend" / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate, override=False)


load_env()

app = FastAPI(title="Cymatic Platform Agents", version="0.2.0")
transport = AXLMeshTransport()
zg_client = ZeroGInferenceClient()
keeperhub_client = KeeperHubWorkflowClient()

execution_agent = ExecutionAgent(keeperhub_client)
response_agent = ResponseAgent(zg_client)
reasoning_agent = ReasoningAgent(transport, zg_client)
voice_agent = VoiceAgent(transport, zg_client)

transport.register("execution", execution_agent.handle)
transport.register("response", response_agent.handle)
transport.register("reasoning", reasoning_agent.handle)


class ProcessTextRequest(BaseModel):
    callSid: str
    caller: str
    text: str


class ProcessTwilioEventRequest(BaseModel):
    callSid: str
    caller: str
    event: dict[str, Any]


class RouteReasoningRequest(BaseModel):
    transcript: str
    caller: str


class ExecuteIntentRequest(BaseModel):
    intent: str
    executionInput: dict[str, Any]


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/agents/voice/process-text")
def voice_process_text(request: ProcessTextRequest) -> dict[str, Any]:
    return voice_agent.process_text(
        call_sid=request.callSid,
        caller=request.caller,
        text=request.text,
    )


@app.post("/agents/voice/process-twilio-event")
def voice_process_twilio_event(request: ProcessTwilioEventRequest) -> dict[str, Any]:
    return voice_agent.process_twilio_event(
        call_sid=request.callSid,
        caller=request.caller,
        event=request.event,
    )


@app.post("/agents/reasoning/route")
def reasoning_route(request: RouteReasoningRequest) -> dict[str, Any]:
    return reasoning_agent.handle(
        AXLMessage(
            trace_id="manual-reasoning-call",
            from_agent="backend",
            to_agent="reasoning",
            intent="reason_over_transcript",
            payload={"transcript": request.transcript, "caller": request.caller},
        )
    )


@app.post("/agents/execution/execute")
def execution_execute(request: ExecuteIntentRequest) -> dict[str, Any]:
    return execution_agent.handle(
        AXLMessage(
            trace_id="manual-execution-call",
            from_agent="backend",
            to_agent="execution",
            intent="execute_workflow",
            payload={"intent": request.intent, "executionInput": request.executionInput},
        )
    )


@app.get("/agents/workflows")
def list_workflows() -> dict[str, Any]:
    try:
        workflows = keeperhub_client.list_workflows()
        return {"ok": True, "count": len(workflows), "workflows": workflows}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "workflows": []}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8100, reload=True)
