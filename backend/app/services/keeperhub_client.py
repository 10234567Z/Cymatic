import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


class KeeperHubClientError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class KeeperHubClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://app.keeperhub.com",
        timeout_seconds: float = 30.0,
    ):
        if not api_key:
            raise ValueError("KeeperHub API key is required")

        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    @classmethod
    def from_env(cls) -> "KeeperHubClient":
        backend_root = Path(__file__).resolve().parents[2]
        load_dotenv(dotenv_path=backend_root / ".env", override=False)
        api_key = os.getenv("KEEPERHUB_API_KEY", "")
        base_url = os.getenv("KEEPERHUB_BASE_URL", "https://app.keeperhub.com")
        return cls(api_key=api_key, base_url=base_url)

    def close(self) -> None:
        self._client.close()

    def list_workflows(
        self,
        project_id: str | None = None,
        tag_id: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if project_id:
            params["projectId"] = project_id
        if tag_id:
            params["tagId"] = tag_id
        return self._request("GET", "/api/workflows", params=params)

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/workflows/{workflow_id}")

    def create_workflow(
        self,
        name: str,
        description: str = "",
        project_id: str | None = None,
        nodes: list[dict[str, Any]] | None = None,
        edges: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "nodes": nodes or [
                {
                    "id": "trigger-1",
                    "type": "trigger",
                    "data": {
                        "label": "Manual Trigger",
                        "type": "trigger",
                        "config": {"triggerType": "Manual"},
                        "status": "idle",
                    },
                }
            ],
            "edges": edges or [],
        }
        if project_id:
            payload["projectId"] = project_id
        return self._request("POST", "/api/workflows/create", json=payload)

    def update_workflow(
        self,
        workflow_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        nodes: list[dict[str, Any]] | None = None,
        edges: list[dict[str, Any]] | None = None,
        visibility: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if nodes is not None:
            payload["nodes"] = nodes
        if edges is not None:
            payload["edges"] = edges
        if visibility is not None:
            payload["visibility"] = visibility
        return self._request("PATCH", f"/api/workflows/{workflow_id}", json=payload)

    def execute_workflow(self, workflow_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/workflow/{workflow_id}/execute")

    def get_execution_status(self, execution_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/workflows/executions/{execution_id}/status")

    def get_execution_logs(self, execution_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/workflows/executions/{execution_id}/logs")

    def get_wallet_integration(self) -> dict[str, Any]:
        return self._request("GET", "/api/integrations/wallet")

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        response = self._client.request(method, path, params=params, json=json)
        if response.status_code >= 400:
            raise KeeperHubClientError(
                message=f"KeeperHub request failed: {response.text}",
                status_code=response.status_code,
            )

        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}
