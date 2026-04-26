from fastapi import APIRouter, Depends

from app.dependencies import get_execution_service
from app.services import ExecutionService
from app.services.workflow_contracts import (
    CheckAaveHealthInput,
    CheckTokenBalanceInput,
    MonitorAaveHealthInput,
    TransferErc20Input,
    WorkflowExecutionResult,
)

router = APIRouter(prefix="/execution", tags=["execution"])


@router.post("/transfer", response_model=WorkflowExecutionResult)
def transfer_erc20(
    payload: TransferErc20Input,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowExecutionResult:
    return service.transfer_erc20(payload)


@router.post("/balance", response_model=WorkflowExecutionResult)
def check_token_balance(
    payload: CheckTokenBalanceInput,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowExecutionResult:
    return service.check_token_balance(payload)


@router.post("/aave-health", response_model=WorkflowExecutionResult)
def check_aave_health(
    payload: CheckAaveHealthInput,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowExecutionResult:
    return service.check_aave_health(payload)


@router.post("/aave-health/monitor", response_model=WorkflowExecutionResult)
def monitor_aave_health(
    payload: MonitorAaveHealthInput,
    service: ExecutionService = Depends(get_execution_service),
) -> WorkflowExecutionResult:
    return service.monitor_aave_health(payload)
