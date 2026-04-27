from __future__ import annotations

import os
import json
from typing import Callable, Any

import httpx

from .contracts import AXLMessage


class AXLMeshTransport:
    """AXL transport with two modes:

    - local: in-process handler dispatch (dev and single-process runtime)
    - mcp: remote dispatch over AXL node HTTP bridge (/mcp/{peer}/{service})
    """

    def __init__(self) -> None:
        self.mode = os.getenv("AXL_TRANSPORT_MODE", "local").strip().lower()
        self.axl_node_url = os.getenv("AXL_NODE_URL", "http://127.0.0.1:9002").rstrip("/")
        self._http = httpx.Client(timeout=30.0)
        self._handlers: dict[str, Callable[[AXLMessage], dict[str, Any]]] = {}
        self._remote_map: dict[str, tuple[str, str]] = {
            "voice": (
                os.getenv("AXL_PEER_VOICE", ""),
                os.getenv("AXL_SERVICE_VOICE", "voice"),
            ),
            "reasoning": (
                os.getenv("AXL_PEER_REASONING", ""),
                os.getenv("AXL_SERVICE_REASONING", "reasoning"),
            ),
            "execution": (
                os.getenv("AXL_PEER_EXECUTION", ""),
                os.getenv("AXL_SERVICE_EXECUTION", "execution"),
            ),
            "response": (
                os.getenv("AXL_PEER_RESPONSE", ""),
                os.getenv("AXL_SERVICE_RESPONSE", "response"),
            ),
        }

    def register(self, agent_name: str, handler: Callable[[AXLMessage], dict[str, Any]]) -> None:
        self._handlers[agent_name] = handler

    def status(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "mode": self.mode,
            "axlNodeUrl": self.axl_node_url,
        }
        if self.mode == "mcp":
            try:
                resp = self._http.get(f"{self.axl_node_url}/topology")
                if resp.status_code == 200:
                    payload = resp.json()
                    info["topology"] = {
                        "ourPublicKey": payload.get("our_public_key"),
                        "ourIpv6": payload.get("our_ipv6"),
                    }
                else:
                    info["topologyError"] = f"HTTP {resp.status_code}"
            except Exception as exc:  # pragma: no cover
                info["topologyError"] = str(exc)
        return info

    def send(self, message: AXLMessage) -> dict[str, Any]:
        if self.mode == "mcp":
            return self._send_over_axl_mcp(message)

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

    def _send_over_axl_mcp(self, message: AXLMessage) -> dict[str, Any]:
        peer_id, service_name = self._remote_map.get(message.to_agent, ("", message.to_agent))
        if not peer_id:
            # If no remote peer configured for this target, fall back to local handler.
            handler = self._handlers.get(message.to_agent)
            if not handler:
                return {
                    "ok": False,
                    "error": f"AXL peer not configured for '{message.to_agent}'",
                    "trace_id": message.trace_id,
                }
            result = handler(message)
            result.setdefault("ok", True)
            result.setdefault("trace_id", message.trace_id)
            result.setdefault("transport", "local-fallback")
            return result

        request_payload = {
            "jsonrpc": "2.0",
            "id": message.trace_id,
            "method": "tools/call",
            "params": {
                "name": message.intent,
                "arguments": message.payload,
            },
        }

        try:
            resp = self._http.post(
                f"{self.axl_node_url}/mcp/{peer_id}/{service_name}",
                headers={"Content-Type": "application/json"},
                json=request_payload,
            )
            resp.raise_for_status()
            payload = resp.json()

            result = payload.get("result") if isinstance(payload, dict) else None
            if isinstance(result, dict):
                content = result.get("content")
                if isinstance(content, list) and content:
                    first = content[0]
                    if isinstance(first, dict) and isinstance(first.get("text"), str):
                        try:
                            decoded = json.loads(first["text"])
                            if isinstance(decoded, dict):
                                decoded.setdefault("trace_id", message.trace_id)
                                decoded.setdefault("ok", True)
                                decoded.setdefault("transport", "axl-mcp")
                                return decoded
                        except Exception:
                            pass

                merged = dict(result)
                merged.setdefault("trace_id", message.trace_id)
                merged.setdefault("ok", True)
                merged.setdefault("transport", "axl-mcp")
                return merged

            return {
                "ok": True,
                "trace_id": message.trace_id,
                "transport": "axl-mcp",
                "raw": payload,
            }
        except Exception as exc:  # pragma: no cover
            return {
                "ok": False,
                "error": f"AXL MCP send failed: {exc}",
                "trace_id": message.trace_id,
                "transport": "axl-mcp",
            }
