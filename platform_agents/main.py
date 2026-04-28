from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from agents.contracts import AXLMessage
try:
    from agent_runtime import build_runtime
except ImportError:  # pragma: no cover
    from platform_agents.agent_runtime import build_runtime

app = FastAPI(title="Cymatic Platform Agents", version="0.2.0")
runtime = build_runtime(force_local_transport=False)
transport = runtime.transport
voice_agent = runtime.voice
reasoning_agent = runtime.reasoning
execution_agent = runtime.execution


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


@app.get("/agents/axl/status")
def axl_status() -> dict[str, Any]:
    return {"ok": True, "axl": transport.status()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8100, reload=True)
