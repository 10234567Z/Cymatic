"""
Simple KeeperHub MCP wrapper - call KeeperHub's MCP tools directly
No workflow management, no complexity. Just execute MCP tools.
"""

import httpx
import os
from typing import Any
from pydantic import BaseModel


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

    def call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a KeeperHub MCP tool directly"""
        url = f"{self.base_url}/mcp/tools/{tool_name}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        response = self.client.post(url, json=arguments, headers=headers)
        response.raise_for_status()
        return response.json()

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
