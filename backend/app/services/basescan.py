import httpx

from app.config import settings


def _to_eth(value_wei_str: str) -> str:
    try:
        value = int(value_wei_str)
    except Exception:
        return "0 ETH"

    whole = value // 10**18
    frac = value % 10**18
    if frac == 0:
        return f"{whole} ETH"

    frac_short = str(frac).rjust(18, "0")[:6].rstrip("0")
    return f"{whole}.{frac_short or '0'} ETH"


async def fetch_wallet_transactions(address: str, page: int = 1, offset: int = 25) -> list[dict]:
    params = {
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": "0",
        "endblock": "99999999",
        "page": str(page),
        "offset": str(offset),
        "sort": "desc",
    }

    if settings.BASESCAN_API_KEY:
        params["apikey"] = settings.BASESCAN_API_KEY

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(settings.BASESCAN_BASE_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()

    result = payload.get("result", [])
    if not isinstance(result, list):
        return []

    normalized = []
    wallet_lower = address.lower()

    for tx in result:
        tx_from = (tx.get("from") or "").lower()
        tx_to = (tx.get("to") or "").lower()

        if tx_from == wallet_lower:
            direction = "out"
        elif tx_to == wallet_lower:
            direction = "in"
        else:
            direction = "out"

        normalized.append(
            {
                "wallet": wallet_lower,
                "direction": direction,
                "txHash": tx.get("hash", ""),
                "blockNumber": int(tx.get("blockNumber", "0") or "0"),
                "timestamp": int(tx.get("timeStamp", "0") or "0"),
                "from": tx_from,
                "to": tx_to,
                "valueEth": _to_eth(tx.get("value", "0")),
                "network": "base-sepolia",
            }
        )

    return normalized
