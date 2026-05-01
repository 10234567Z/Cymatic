import asyncio

from supabase import create_client, Client
from app.config import settings
from app.models.user import UserRecord, NewUserInput

_client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY)


async def get_user_by_phone(phone_number: str) -> UserRecord | None:
    response = await asyncio.to_thread(
        lambda: _client.table("users")
        .select("*")
        .eq("phone_number", phone_number)
        .maybe_single()
        .execute()
    )
    if response is None or not response.data:
        return None
    return UserRecord(**response.data)


async def get_user_by_wallet_address(wallet_address: str) -> UserRecord | None:
    response = await asyncio.to_thread(
        lambda: _client.table("users")
        .select("*")
        .eq("wallet_address", wallet_address)
        .maybe_single()
        .execute()
    )
    if response is None or not response.data:
        return None
    return UserRecord(**response.data)


async def create_user(payload: NewUserInput) -> UserRecord:
    response = await asyncio.to_thread(
        lambda: _client.table("users")
        .insert(payload.model_dump())
        .execute()
    )
    data = response.data[0]
    # sub_org_id column may not exist in older DB schemas — ignore gracefully
    if "sub_org_id" not in data:
        data["sub_org_id"] = payload.sub_org_id
    return UserRecord(**data)


async def update_inft(user_id: str, token_id: str, contract: str) -> None:
    await asyncio.to_thread(
        lambda: _client.table("users").update({
            "inft_token_id": token_id,
            "inft_contract": contract,
        }).eq("id", user_id).execute()
    )
