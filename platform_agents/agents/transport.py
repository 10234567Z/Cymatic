from __future__ import annotations

from typing import Callable, Any

from .contracts import AXLMessage


class AXLMeshTransport:
    """In-process AXL-style router. Replace with network transport in deployment."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[AXLMessage], dict[str, Any]]] = {}

    def register(self, agent_name: str, handler: Callable[[AXLMessage], dict[str, Any]]) -> None:
        self._handlers[agent_name] = handler

    def send(self, message: AXLMessage) -> dict[str, Any]:
        handler = self._handlers.get(message.to_agent)
        if not handler:
            return {
                "ok": False,
                "error": f"No route for agent '{message.to_agent}'",
                "trace_id": message.trace_id,
            }
        try:
            result = handler(message)
            result.setdefault("trace_id", message.trace_id)
            result.setdefault("ok", True)
            return result
        except Exception as exc:  # pragma: no cover
            return {
                "ok": False,
                "error": str(exc),
                "trace_id": message.trace_id,
            }
