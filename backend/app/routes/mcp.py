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
    private_key_id: str


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
            private_key_id=req.private_key_id,
        )
        return {"txHash": tx_hash, "status": "submitted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users/wallet/{phone}")
async def get_wallet_by_phone(phone: str):
    """Look up a Cymatic user's wallet address by phone number."""
    from app.services.supabase_client import get_user_by_phone
    # Normalise: ensure leading +
    if not phone.startswith("+"):
        phone = "+" + phone
    user = await get_user_by_phone(phone)
    if not user or not user.wallet_address:
        raise HTTPException(status_code=404, detail=f"No Cymatic user found for {phone}")
    return {"phone": phone, "walletAddress": user.wallet_address}


class InternalBalanceRequest(BaseModel):
    address: str
    token_address: str
    chain_id: int


@router.post("/internal/balance")
def internal_balance(req: InternalBalanceRequest):
    """Check ERC20 token balance directly via RPC (no KeeperHub required)."""
    import httpx as _httpx

    rpc_urls = {
        1: "https://cloudflare-eth.com",
        8453: "https://mainnet.base.org",
        84532: "https://sepolia.base.org",
        42161: "https://arb1.arbitrum.io/rpc",
        137: "https://polygon-rpc.com",
    }
    rpc_url = rpc_urls.get(req.chain_id)
    if not rpc_url:
        raise HTTPException(status_code=400, detail=f"Unsupported chain_id: {req.chain_id}")

    def rpc_call(method: str, params: list, call_id: int) -> dict:
        r = _httpx.post(rpc_url, json={"jsonrpc": "2.0", "id": call_id, "method": method, "params": params}, timeout=15)
        r.raise_for_status()
        return r.json()

    padded = req.address.lower().replace("0x", "").zfill(64)

    try:
        bal_res = rpc_call("eth_call", [{"to": req.token_address, "data": "0x70a08231" + padded}, "latest"], 1)
        balance_raw = int(bal_res["result"], 16)

        dec_res = rpc_call("eth_call", [{"to": req.token_address, "data": "0x313ce567"}, "latest"], 2)
        decimals = int(dec_res["result"], 16)

        sym_res = rpc_call("eth_call", [{"to": req.token_address, "data": "0x95d89b41"}, "latest"], 3)
        sym_hex = sym_res["result"][2:]
        # ABI-decode dynamic string: offset(32) + length(32) + data
        try:
            str_len = int(sym_hex[64:128], 16)
            symbol = bytes.fromhex(sym_hex[128:128 + str_len * 2]).decode("utf-8", errors="replace").rstrip("\x00")
        except Exception:
            symbol = bytes.fromhex(sym_hex[:64]).decode("utf-8", errors="replace").rstrip("\x00").strip()

        divisor = 10 ** decimals
        formatted = f"{balance_raw / divisor:.{decimals}f}".rstrip("0").rstrip(".")

        return {
            "address": req.address,
            "balance": {
                "balanceRaw": str(balance_raw),
                "balance": formatted,
                "decimals": decimals,
                "symbol": symbol,
                "tokenAddress": req.token_address,
            },
            "success": True,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
