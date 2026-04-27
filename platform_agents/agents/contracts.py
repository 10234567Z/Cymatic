from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class AXLMessage(BaseModel):
    trace_id: str
    from_agent: str
    to_agent: str
    intent: str
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowSelection(BaseModel):
    workflow_id: str
    workflow_name: str
    score: float


class ExecutionResult(BaseModel):
    workflow_id: str
    execution_id: str
    status: str
    output: dict[str, Any] | None = None
    error: Any = None


class VoiceProcessTextRequest(BaseModel):
    call_sid: str
    caller: str
    text: str


class VoiceProcessTextResponse(BaseModel):
    transcript: str
    response_text: str
    twilio_media_payloads: list[str]


class TwilioStartEvent(BaseModel):
    event: Literal["start"]
    start: dict[str, Any]


class TwilioMediaEvent(BaseModel):
    event: Literal["media"]
    media: dict[str, Any]


class TwilioStopEvent(BaseModel):
    event: Literal["stop"]
    stop: dict[str, Any] | None = None
