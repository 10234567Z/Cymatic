"""
Simple KeeperHub MCP wrapper - call KeeperHub's MCP tools directly
No workflow management, no complexity. Just execute MCP tools.
"""

import httpx
import os
from typing import Any


class KeeperHubMCP:
    """Lightweight wrapper for KeeperHub MCP tools"""

    def __init__(self, api_key: str, base_url: str = "https://app.keeperhub.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    @classmethod
    def from_env(cls) -> "KeeperHubMCP":
        """Create from environment variables"""
        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.getenv("KEEPERHUB_API_KEY", "")
        base_url = os.getenv("KEEPERHUB_BASE_URL", "https://app.keeperhub.com")
        return cls(api_key=api_key, base_url=base_url)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _list_workflows(self) -> list[dict[str, Any]]:
        response = self.client.get(f"{self.base_url}/api/workflows", headers=self._headers())
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("workflows"), list):
            return payload["workflows"]
        if isinstance(payload, list):
            return payload
        return []

    def _workflow_id_for_tool(self, tool_name: str) -> tuple[str, str]:
        env_keys = {
            "web3/check_token_balance": "KEEPERHUB_WORKFLOW_ID_CHECK_TOKEN_BALANCE",
            "web3/check_aave_health": "KEEPERHUB_WORKFLOW_ID_CHECK_AAVE_HEALTH",
            "web3/transfer_erc20": "KEEPERHUB_WORKFLOW_ID_TRANSFER_ERC20",
            "web3/monitor_aave_health": "KEEPERHUB_WORKFLOW_ID_MONITOR_AAVE_HEALTH",
        }
        configured_env_key = env_keys.get(tool_name)
        if configured_env_key:
            configured_workflow_id = os.getenv(configured_env_key)
            if configured_workflow_id:
                return configured_workflow_id, tool_name

        name_candidates = {
            "web3/check_token_balance": {"check_token_balance", "check-token-balance"},
            "web3/check_aave_health": {"check_aave_health", "check-aave-health"},
            "web3/transfer_erc20": {"transfer_erc20", "transfer-erc20"},
            "web3/monitor_aave_health": {"monitor_aave_health", "monitor-aave-health"},
        }
        action_type_by_tool = {
            "web3/check_token_balance": "web3/check-token-balance",
            "web3/check_aave_health": "web3/read-contract",
            "web3/transfer_erc20": "web3/transfer-token",
            "web3/monitor_aave_health": "web3/read-contract",
        }

        workflows = self._list_workflows()

        for workflow in workflows:
            workflow_name = str(workflow.get("name", "")).strip().lower()
            if workflow_name in name_candidates.get(tool_name, set()):
                workflow_id = workflow.get("id")
                if isinstance(workflow_id, str) and workflow_id:
                    return workflow_id, workflow_name

        expected_action_type = action_type_by_tool.get(tool_name)
        for workflow in workflows:
            nodes = workflow.get("nodes")
            if not isinstance(nodes, list):
                continue
            for node in nodes:
                if not isinstance(node, dict) or node.get("type") != "action":
                    continue
                data = node.get("data") or {}
                config = data.get("config") if isinstance(data, dict) else {}
                if isinstance(config, dict) and config.get("actionType") == expected_action_type:
                    workflow_id = workflow.get("id")
                    if isinstance(workflow_id, str) and workflow_id:
                        return workflow_id, str(workflow.get("name", tool_name))

        raise ValueError(f"Workflow not found for tool: {tool_name}")

    def _execute_workflow(self, tool_name: str, input_payload: dict[str, Any]) -> dict[str, Any]:
        workflow_id, resolved_name = self._workflow_id_for_tool(tool_name)
        execute_response = self.client.post(
            f"{self.base_url}/api/workflow/{workflow_id}/execute",
            headers=self._headers(),
            json={"input": input_payload},
        )
        execute_response.raise_for_status()
        execute_payload = execute_response.json()
        execution_id = execute_payload.get("executionId") or execute_payload.get("id")
        if not isinstance(execution_id, str) or not execution_id:
            raise ValueError("Execution id missing from KeeperHub response")

        # Keep polling short. If still running, caller gets pending state.
        status = "pending"
        for _ in range(5):
            status_response = self.client.get(
                f"{self.base_url}/api/workflows/executions/{execution_id}/status",
                headers=self._headers(),
            )
            status_response.raise_for_status()
            status_payload = status_response.json()
            status = str(status_payload.get("status", "pending")).lower()
            if status in {"success", "error", "cancelled"}:
                break

        executions_response = self.client.get(
            f"{self.base_url}/api/workflows/{workflow_id}/executions",
            headers=self._headers(),
        )
        executions_response.raise_for_status()
        executions_payload = executions_response.json()
        entries = (
            executions_payload.get("executions")
            if isinstance(executions_payload, dict)
            else executions_payload
        )

        if isinstance(entries, list):
            for item in entries:
                if isinstance(item, dict) and item.get("id") == execution_id:
                    return {
                        "workflow": resolved_name,
                        "tool": tool_name,
                        "workflowId": workflow_id,
                        "executionId": execution_id,
                        "status": item.get("status", status),
                        "output": item.get("output"),
                        "error": item.get("error"),
                    }

        return {
            "workflow": resolved_name,
            "tool": tool_name,
            "workflowId": workflow_id,
            "executionId": execution_id,
            "status": status,
            "output": None,
            "error": None,
        }

    def call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a KeeperHub-managed workflow by logical tool name."""
        supported_tools = {
            "web3/check_token_balance",
            "web3/check_aave_health",
            "web3/transfer_erc20",
            "web3/monitor_aave_health",
        }
        if tool_name not in supported_tools:
            raise ValueError(f"Unsupported tool: {tool_name}")
        return self._execute_workflow(tool_name, arguments)

    def check_token_balance(
        self,
        chain_id: int,
        address: str,
        token_address: str,
    ) -> dict[str, Any]:
        """Check ERC20 token balance - calls KeeperHub's check_token_balance MCP tool"""
        return self.call_mcp_tool(
            "web3/check_token_balance",
            {
                "chainId": chain_id,
                "address": address,
                "tokenAddress": token_address,
            },
        )

    def check_aave_health(
        self,
        chain_id: int,
        wallet_address: str,
    ) -> dict[str, Any]:
        """Check Aave health factor - calls KeeperHub's check_aave_health MCP tool"""
        return self.call_mcp_tool(
            "web3/check_aave_health",
            {
                "chainId": chain_id,
                "walletAddress": wallet_address,
            },
        )

    def transfer_erc20(
        self,
        chain_id: int,
        to_address: str,
        token_address: str,
        amount: str,
        wallet_id: str,
    ) -> dict[str, Any]:
        """Transfer ERC20 token - calls KeeperHub's transfer_erc20 MCP tool"""
        return self.call_mcp_tool(
            "web3/transfer_erc20",
            {
                "chainId": chain_id,
                "toAddress": to_address,
                "tokenAddress": token_address,
                "amount": amount,
                "walletId": wallet_id,
            },
        )

    def monitor_aave_health(
        self,
        chain_id: int,
        wallet_address: str,
        health_threshold: float = 1.5,
    ) -> dict[str, Any]:
        """Monitor Aave health factor - calls KeeperHub's monitor_aave_health MCP tool"""
        return self.call_mcp_tool(
            "web3/monitor_aave_health",
            {
                "chainId": chain_id,
                "walletAddress": wallet_address,
                "healthThreshold": health_threshold,
            },
        )
