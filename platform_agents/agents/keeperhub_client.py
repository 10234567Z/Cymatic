from __future__ import annotations

import fnmatch
import os
import time
from typing import Any

import httpx


class KeeperHubWorkflowClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("KEEPERHUB_API_KEY", "")
        self.base_url = os.getenv("KEEPERHUB_BASE_URL", "https://app.keeperhub.com").rstrip("/")
        self.client = httpx.Client(timeout=30.0)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Cymatic-Platform-Agent/0.2",
        }

    def list_workflows(self) -> list[dict[str, Any]]:
        response = self.client.get(f"{self.base_url}/api/workflows", headers=self._headers())
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("workflows"), list):
            return payload["workflows"]
        return []

    def select_workflow(self, wildcard_patterns: list[str], action_hint: str | None = None) -> dict[str, Any] | None:
        workflows = self.list_workflows()
        best: tuple[int, dict[str, Any]] | None = None

        for workflow in workflows:
            name = str(workflow.get("name", ""))
            description = str(workflow.get("description", ""))
            searchable = f"{name} {description}".lower()
            score = 0

            for pattern in wildcard_patterns:
                if fnmatch.fnmatch(name.lower(), pattern.lower()):
                    score += 10
                elif fnmatch.fnmatch(searchable, pattern.lower()):
                    score += 6

            if action_hint:
                nodes = workflow.get("nodes")
                if isinstance(nodes, list):
                    for node in nodes:
                        if not isinstance(node, dict) or node.get("type") != "action":
                            continue
                        data = node.get("data") or {}
                        config = data.get("config") if isinstance(data, dict) else {}
                        if isinstance(config, dict) and config.get("actionType") == action_hint:
                            score += 10
                            break

            if best is None or score > best[0]:
                best = (score, workflow)

        if not best:
            return None
        # If no pattern matched but only one workflow exists, use it
        if best[0] <= 0 and len(workflows) > 1:
            return None
        return best[1]

    def execute(self, workflow_id: str, input_payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(
            f"{self.base_url}/api/workflow/{workflow_id}/execute",
            headers=self._headers(),
            json={"input": input_payload},
        )
        response.raise_for_status()
        payload = response.json()
        execution_id = payload.get("executionId") or payload.get("id")
        if not execution_id:
            raise RuntimeError("Execution ID missing")

        status = "pending"
        for _ in range(10):
            status_response = self.client.get(
                f"{self.base_url}/api/workflows/executions/{execution_id}/status",
                headers=self._headers(),
            )
            status_response.raise_for_status()
            status_payload = status_response.json()
            status = str(status_payload.get("status", "pending")).lower()
            if status in {"success", "error", "cancelled"}:
                break
            time.sleep(1)

        executions_response = self.client.get(
            f"{self.base_url}/api/workflows/{workflow_id}/executions",
            headers=self._headers(),
        )
        executions_response.raise_for_status()
        executions_payload = executions_response.json()
        entries = executions_payload.get("executions") if isinstance(executions_payload, dict) else executions_payload

        if isinstance(entries, list):
            for item in entries:
                if isinstance(item, dict) and item.get("id") == execution_id:
                    return {
                        "workflowId": workflow_id,
                        "executionId": execution_id,
                        "status": item.get("status", status),
                        "output": item.get("output"),
                        "error": item.get("error"),
                    }

        return {
            "workflowId": workflow_id,
            "executionId": execution_id,
            "status": status,
            "output": None,
            "error": None,
        }
