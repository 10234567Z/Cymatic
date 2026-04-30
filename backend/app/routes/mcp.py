"""
FastAPI routes for KeeperHub MCP tools
Direct MCP calls - no workflow management complexity
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.keeperhub_mcp import KeeperHubMCP

router = APIRouter(prefix="/execution", tags=["execution"])
mcp = KeeperHubMCP.from_env()


class TokenBalanceRequest(BaseModel):
    chain_id: int
    address: str
    token_address: str


class AaveHealthRequest(BaseModel):
    chain_id: int
    wallet_address: str


class TransferRequest(BaseModel):
    chain_id: int
    to_address: str
    token_address: str
    amount: str
    wallet_id: str


class MonitorRequest(BaseModel):
    chain_id: int
    wallet_address: str
    health_threshold: float = 1.5


@router.post("/balance")
async def check_balance(req: TokenBalanceRequest):
    """Check ERC20 token balance via KeeperHub MCP"""
    try:
        result = mcp.check_token_balance(
            chain_id=req.chain_id,
            address=req.address,
            token_address=req.token_address,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/aave-health")
async def check_aave(req: AaveHealthRequest):
    """Check Aave health factor via KeeperHub MCP"""
    try:
        result = mcp.check_aave_health(
            chain_id=req.chain_id,
            wallet_address=req.wallet_address,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/transfer")
async def transfer(req: TransferRequest):
    """Transfer ERC20 token via KeeperHub MCP"""
    try:
        result = mcp.transfer_erc20(
            chain_id=req.chain_id,
            to_address=req.to_address,
            token_address=req.token_address,
            amount=req.amount,
            wallet_id=req.wallet_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/monitor")
async def monitor(req: MonitorRequest):
    """Monitor Aave health via KeeperHub MCP"""
    try:
        result = mcp.monitor_aave_health(
            chain_id=req.chain_id,
            wallet_address=req.wallet_address,
            health_threshold=req.health_threshold,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class InternalTransferRequest(BaseModel):
    sub_org_id: str
    from_address: str
    to_address: str
    token_address: str
    amount_units: int
    chain_id: int


@router.post("/internal/transfer")
def internal_transfer(req: InternalTransferRequest):
    """Sign and broadcast an ERC20 transfer via Turnkey (called by platform_agents)."""
    from app.services.turnkey import sign_and_broadcast_erc20
    try:
        tx_hash = sign_and_broadcast_erc20(
            sub_org_id=req.sub_org_id,
            from_address=req.from_address,
            to_address=req.to_address,
            token_address=req.token_address,
            amount_units=req.amount_units,
            chain_id=req.chain_id,
        )
        return {"txHash": tx_hash, "status": "submitted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
