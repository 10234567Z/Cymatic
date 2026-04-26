from pydantic import BaseModel
from typing import Optional


class UserRecord(BaseModel):
    id: str
    phone_number: str
    pin_hash: str
    turnkey_wallet_id: str
    wallet_address: str
    inft_token_id: Optional[str] = None
    inft_contract: Optional[str] = None
    is_active: bool = True
    failed_pin_attempts: int = 0


class NewUserInput(BaseModel):
    phone_number: str
    pin_hash: str
    turnkey_wallet_id: str
    wallet_address: str
