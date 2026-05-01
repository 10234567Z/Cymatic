"""
CallerINFT minting service.

Mints an ERC-7857 iNFT on the 0G testnet for each new Cymatic user.
The MockVerifier accepts any bytes as proof, so we pass a SHA-256 hash
of the phone number as the proof data.
"""

import asyncio
import hashlib
import logging
import os

log = logging.getLogger("inft")

_MINT_ABI = [
    {
        "name": "mint",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [
            {"name": "proofs", "type": "bytes[]"},
            {"name": "dataDescriptions", "type": "string[]"},
            {"name": "to", "type": "address"},
        ],
        "outputs": [{"name": "tokenId", "type": "uint256"}],
    }
]


_OG_CHAIN_ID = 16602


def mint_caller_inft(wallet_address: str, phone_number: str, user_id: str = "") -> dict:
    """
    Mint a CallerINFT for a new user. Runs synchronously — call from a background thread.

    Returns:
        {"ok": True, "txHash": "0x...", "tokenId": 1} on success
        {"ok": False, "reason": "..."} on failure / misconfiguration
    """
    contract_address = os.getenv("CALLER_INFT_ADDRESS", "").strip()
    private_key = os.getenv("DEPLOYER_PRIVATE_KEY", "").strip()
    rpc_url = os.getenv("OG_RPC_URL", "https://evmrpc-testnet.0g.ai").strip()

    if not contract_address:
        log.error("[inft] CALLER_INFT_ADDRESS not set — skipping mint")
        return {"ok": False, "reason": "CALLER_INFT_ADDRESS not configured"}
    if not private_key:
        log.error("[inft] DEPLOYER_PRIVATE_KEY not set — cannot mint iNFT. "
                  "Set it to the private key of %s (the wallet that deployed the contract).",
                  os.getenv("CALLER_INFT_DEPLOYER_ADDRESS", "the deployer"))
        return {"ok": False, "reason": "DEPLOYER_PRIVATE_KEY not configured"}

    try:
        from web3 import Web3
        from eth_account import Account
    except ImportError:
        log.error("[inft] web3 not installed — run: uv sync")
        return {"ok": False, "reason": "web3 not installed"}

    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=_MINT_ABI,
        )

        # MockVerifier accepts any bytes as proof — use SHA-256 of phone as identity proof
        proof_bytes = hashlib.sha256(phone_number.encode()).digest()

        acct = Account.from_key(private_key)
        tx = contract.functions.mint(
            [proof_bytes],
            ["cymatic caller identity"],
            Web3.to_checksum_address(wallet_address),
        ).build_transaction({
            "from": acct.address,
            "nonce": w3.eth.get_transaction_count(acct.address),
            "chainId": _OG_CHAIN_ID,
            "gas": 300_000,
            "gasPrice": w3.eth.gas_price,
        })
        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        log.warning("[inft] tx broadcast: %s — waiting for receipt...", tx_hash.hex())
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        # Parse tokenId from Minted event — first indexed topic after event sig
        token_id = None
        for log_entry in receipt.logs:
            if len(log_entry["topics"]) >= 2:
                token_id = int(log_entry["topics"][1].hex(), 16)
                break

        result = {
            "ok": receipt.status == 1,
            "txHash": tx_hash.hex(),
            "tokenId": token_id,
            "walletAddress": wallet_address,
            "userId": user_id,
        }
        log.warning("[inft] mint result: %s", result)

        # Persist tokenId + contract address back to Supabase
        if result["ok"] and token_id is not None and result.get("userId"):
            from app.services.supabase_client import update_inft
            contract_addr = os.getenv("CALLER_INFT_ADDRESS", "")
            asyncio.run(update_inft(result["userId"], str(token_id), contract_addr))
            log.warning("[inft] saved tokenId=%s to user %s", token_id, result["userId"])

        return result

    except Exception as exc:
        log.error("[inft] mint failed: %s", exc, exc_info=True)
        return {"ok": False, "reason": str(exc)}
