from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

# Safe local defaults for runtime initialization in test context.
os.environ.setdefault("OPENAI_BASE_URL", "http://localhost")
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("KEEPERHUB_API_KEY", "test")

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from platform_agents.a2a_server import app as a2a_app  # noqa: E402
from platform_agents.mcp_server import app as mcp_app  # noqa: E402


def main() -> None:
    mcp = TestClient(mcp_app)
    a2a = TestClient(a2a_app)

    tools = mcp.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert tools.status_code == 200
    payload = tools.json()
    assert "result" in payload and "tools" in payload["result"]

    phrase = mcp.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "smoke-1",
            "method": "tools/call",
            "params": {
                "name": "phrase_response",
                "arguments": {
                    "intent": "check_aave_health",
                    "execution": {"output": {"healthFactor": "1.91"}},
                },
            },
        },
    )
    assert phrase.status_code == 200
    assert "1.91" in phrase.json()["result"]["content"][0]["text"]

    a2a = a2a.post(
        "/a2a",
        json={
            "trace_id": "smoke-a2a-1",
            "from_agent": "remote",
            "to_agent": "response",
            "intent": "phrase_response",
            "payload": {
                "intent": "monitor_aave_health",
                "execution": {},
            },
        },
    )
    assert a2a.status_code == 200
    assert a2a.json()["result"]["spokenText"] == "Aave health monitoring is now active."

    print("SMOKE_OK")


if __name__ == "__main__":
    main()
