from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional


class CallState(str, Enum):
    NEW_USER = "new_user"          # first time caller, collecting PIN
    EXISTING_USER = "existing_user" # known caller, verifying PIN
    AUTHENTICATED = "authenticated" # PIN verified, streaming to agent


class CallSession(BaseModel):
    call_sid: str
    phone_number: str
    state: CallState
    user_id: Optional[str] = None        # set once user is found/created
    wallet_address: Optional[str] = None # set once user is found/created
    sub_org_id: Optional[str] = None     # Turnkey sub-org for signing
    pin_attempts: int = 0
    conversation: list[dict] = Field(default_factory=list)  # {"role": "user"|"agent", "text": "..."}
