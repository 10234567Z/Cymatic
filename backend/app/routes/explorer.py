from fastapi import APIRouter, Query

from app.services.basescan import fetch_wallet_transactions
from app.services.supabase_client import list_wallet_users, list_inft_users

router = APIRouter(prefix="/explorer", tags=["explorer"])


@router.get("/wallet-transactions")
async def wallet_transactions(
    limit_wallets: int = Query(default=100, ge=1, le=500),
    tx_per_wallet: int = Query(default=25, ge=1, le=100),
) -> dict:
    users = await list_wallet_users(limit=limit_wallets)
    inft_users = await list_inft_users(limit=limit_wallets)

    wallets = []
    all_txs = []

    for user in users:
        wallet = (user.get("wallet_address") or "").strip().lower()
        if not wallet:
            continue

        wallets.append(
            {
                "userId": user.get("id"),
                "phoneNumber": user.get("phone_number"),
                "walletAddress": wallet,
            }
        )

        txs = await fetch_wallet_transactions(wallet, page=1, offset=tx_per_wallet)
        for tx in txs:
            tx["userId"] = user.get("id")
            tx["phoneNumber"] = user.get("phone_number")
        all_txs.extend(txs)

    all_txs.sort(key=lambda tx: tx.get("timestamp", 0), reverse=True)

    account_created = []
    for user in inft_users:
        account_created.append(
            {
                "userId": user.get("id"),
                "phoneNumber": user.get("phone_number"),
                "owner": (user.get("wallet_address") or "").strip().lower(),
                "tokenId": str(user.get("inft_token_id") or ""),
                "contract": (user.get("inft_contract") or "").strip().lower(),
                "createdAt": user.get("created_at"),
                "source": "supabase",
            }
        )

    return {
        "wallets": wallets,
        "transactions": all_txs,
        "accountCreated": account_created,
        "walletsScanned": len(wallets),
        "network": "base-sepolia",
    }
