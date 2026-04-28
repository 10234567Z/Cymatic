from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

try:
    from agent_runtime import build_runtime, list_mcp_tools
except ImportError:  # pragma: no cover
    from platform_agents.agent_runtime import build_runtime, list_mcp_tools


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Any = None
    method: str
    params: dict[str, Any] = {}


runtime = build_runtime(force_local_transport=True)
app = FastAPI(title="Cymatic MCP Adapter", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "mcp-adapter"}


@app.post("/")
@app.post("/mcp")
def mcp_rpc(request: JsonRpcRequest) -> dict[str, Any]:
    if request.method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {"tools": list_mcp_tools()},
        }

    if request.method == "tools/call":
        name = str((request.params or {}).get("name", ""))
        arguments = (request.params or {}).get("arguments") or {}
        if not isinstance(arguments, dict):
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {"code": -32602, "message": "arguments must be an object"},
            }

        result = runtime.call_tool(name, arguments, str(request.id))
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result),
                    }
                ]
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": request.id,
        "error": {"code": -32601, "message": f"Method not found: {request.method}"},
    }
