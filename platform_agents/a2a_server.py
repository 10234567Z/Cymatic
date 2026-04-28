from __future__ import annotations

from typing import Any

from fastapi import FastAPI

try:
    from agent_runtime import build_runtime
except ImportError:  # pragma: no cover
    from platform_agents.agent_runtime import build_runtime


runtime = build_runtime(force_local_transport=True)
app = FastAPI(title="Cymatic A2A Adapter", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "a2a-adapter"}


@app.post("/")
@app.post("/a2a")
def a2a_message(body: dict[str, Any]) -> dict[str, Any]:
    result = runtime.dispatch_a2a(body)
    return {
        "ok": bool(result.get("ok", True)),
        "result": result,
    }
