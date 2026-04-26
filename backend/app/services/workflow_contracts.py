from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class WorkflowName(str, Enum):
    TRANSFER_ERC20 = "transfer_erc20"
    CHECK_TOKEN_BALANCE = "check_token_balance"
    CHECK_AAVE_HEALTH = "check_aave_health"
    MONITOR_AAVE_HEALTH = "monitor_aave_health"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


class TransferErc20Input(BaseModel):
    wallet_id: str = Field(min_length=1)
    chain_id: str = Field(min_length=1)
    token_address: str = Field(min_length=1)
    to_address: str = Field(min_length=1)
    amount: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class TransferErc20Output(BaseModel):
    tx_hash: str | None = None
    explorer_url: str | None = None
    execution_id: str
    workflow_id: str


class CheckTokenBalanceInput(BaseModel):
    chain_id: str = Field(min_length=1)
    wallet_address: str = Field(min_length=1)
    token_address: str = Field(min_length=1)


class CheckTokenBalanceOutput(BaseModel):
    raw_balance: str
    formatted_balance: str | None = None
    decimals: int | None = None
    symbol: str | None = None
    execution_id: str
    workflow_id: str


class CheckAaveHealthInput(BaseModel):
    chain_id: str = Field(min_length=1)
    wallet_address: str = Field(min_length=1)
    market: str = Field(default="aave-v3", min_length=1)


class CheckAaveHealthOutput(BaseModel):
    health_factor: float | None = None
    supplied_value_usd: float | None = None
    borrowed_value_usd: float | None = None
    execution_id: str
    workflow_id: str


class MonitorAaveHealthInput(BaseModel):
    chain_id: str = Field(min_length=1)
    wallet_address: str = Field(min_length=1)
    threshold: float = Field(gt=0)
    alert_target: str = Field(min_length=1)
    schedule: str = Field(default="*/5 * * * *", min_length=1)


class MonitorAaveHealthOutput(BaseModel):
    monitor_enabled: bool
    workflow_id: str


class WorkflowError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    provider_status: int | None = None


class WorkflowExecutionResult(BaseModel):
    workflow: WorkflowName
    status: ExecutionStatus
    output_type: Literal[
        "transfer_erc20",
        "check_token_balance",
        "check_aave_health",
        "monitor_aave_health",
    ]
    output: (
        TransferErc20Output
        | CheckTokenBalanceOutput
        | CheckAaveHealthOutput
        | MonitorAaveHealthOutput
        | None
    ) = None
    error: WorkflowError | None = None
