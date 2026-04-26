from typing import Any

from app.services.keeperhub_client import KeeperHubClient
from app.services.workflow_contracts import (
    CheckAaveHealthInput,
    CheckAaveHealthOutput,
    CheckTokenBalanceInput,
    CheckTokenBalanceOutput,
    ExecutionStatus,
    MonitorAaveHealthInput,
    MonitorAaveHealthOutput,
    TransferErc20Input,
    TransferErc20Output,
    WorkflowError,
    WorkflowExecutionResult,
    WorkflowName,
)


class ExecutionService:
    def __init__(self, keeperhub_client: KeeperHubClient):
        self._keeperhub = keeperhub_client

    def transfer_erc20(self, payload: TransferErc20Input) -> WorkflowExecutionResult:
        workflow = self._find_workflow_by_name(WorkflowName.TRANSFER_ERC20.value)
        if not workflow:
            return WorkflowExecutionResult(
                workflow=WorkflowName.TRANSFER_ERC20,
                status=ExecutionStatus.ERROR,
                output_type="transfer_erc20",
                error=WorkflowError(
                    code="WORKFLOW_NOT_FOUND",
                    message="transfer_erc20 workflow is not deployed",
                ),
            )

        execution = self._keeperhub.execute_workflow(workflow["id"])
        execution_id = execution.get("executionId", "")
        status_payload = self._keeperhub.get_execution_status(execution_id)
        status = self._to_status(status_payload.get("status", "pending"))

        if status in {ExecutionStatus.PENDING, ExecutionStatus.RUNNING}:
            return WorkflowExecutionResult(
                workflow=WorkflowName.TRANSFER_ERC20,
                status=status,
                output_type="transfer_erc20",
                output=TransferErc20Output(
                    tx_hash=None,
                    explorer_url=None,
                    execution_id=execution_id,
                    workflow_id=workflow["id"],
                ),
            )

        logs = self._keeperhub.get_execution_logs(execution_id)
        tx_hash = self._extract_tx_hash(logs)

        if status == ExecutionStatus.SUCCESS:
            return WorkflowExecutionResult(
                workflow=WorkflowName.TRANSFER_ERC20,
                status=status,
                output_type="transfer_erc20",
                output=TransferErc20Output(
                    tx_hash=tx_hash,
                    explorer_url=self._build_explorer_url(payload.chain_id, tx_hash),
                    execution_id=execution_id,
                    workflow_id=workflow["id"],
                ),
            )

        return WorkflowExecutionResult(
            workflow=WorkflowName.TRANSFER_ERC20,
            status=status,
            output_type="transfer_erc20",
            output=TransferErc20Output(
                tx_hash=tx_hash,
                explorer_url=self._build_explorer_url(payload.chain_id, tx_hash),
                execution_id=execution_id,
                workflow_id=workflow["id"],
            ),
            error=WorkflowError(
                code="WORKFLOW_EXECUTION_FAILED",
                message="transfer_erc20 workflow failed",
                retryable=False,
            ),
        )

    def check_token_balance(
        self,
        payload: CheckTokenBalanceInput,
    ) -> WorkflowExecutionResult:
        workflow = self._find_workflow_by_name(WorkflowName.CHECK_TOKEN_BALANCE.value)
        if not workflow:
            return WorkflowExecutionResult(
                workflow=WorkflowName.CHECK_TOKEN_BALANCE,
                status=ExecutionStatus.ERROR,
                output_type="check_token_balance",
                error=WorkflowError(
                    code="WORKFLOW_NOT_FOUND",
                    message="check_token_balance workflow is not deployed",
                ),
            )

        execution = self._keeperhub.execute_workflow(workflow["id"])
        execution_id = execution.get("executionId", "")
        status_payload = self._keeperhub.get_execution_status(execution_id)
        status = self._to_status(status_payload.get("status", "pending"))

        if status in {ExecutionStatus.PENDING, ExecutionStatus.RUNNING}:
            return WorkflowExecutionResult(
                workflow=WorkflowName.CHECK_TOKEN_BALANCE,
                status=status,
                output_type="check_token_balance",
                output=CheckTokenBalanceOutput(
                    raw_balance="0",
                    execution_id=execution_id,
                    workflow_id=workflow["id"],
                ),
            )

        logs = self._keeperhub.get_execution_logs(execution_id)
        extracted = self._extract_balance_payload(logs)
        output = CheckTokenBalanceOutput(
            raw_balance=extracted.get("raw_balance", "0"),
            formatted_balance=extracted.get("formatted_balance"),
            decimals=extracted.get("decimals"),
            symbol=extracted.get("symbol"),
            execution_id=execution_id,
            workflow_id=workflow["id"],
        )

        if status == ExecutionStatus.SUCCESS:
            return WorkflowExecutionResult(
                workflow=WorkflowName.CHECK_TOKEN_BALANCE,
                status=status,
                output_type="check_token_balance",
                output=output,
            )

        return WorkflowExecutionResult(
            workflow=WorkflowName.CHECK_TOKEN_BALANCE,
            status=status,
            output_type="check_token_balance",
            output=output,
            error=WorkflowError(
                code="WORKFLOW_EXECUTION_FAILED",
                message="check_token_balance workflow failed",
                retryable=False,
            ),
        )

    def check_aave_health(self, payload: CheckAaveHealthInput) -> WorkflowExecutionResult:
        workflow = self._find_workflow_by_name(WorkflowName.CHECK_AAVE_HEALTH.value)
        if not workflow:
            return WorkflowExecutionResult(
                workflow=WorkflowName.CHECK_AAVE_HEALTH,
                status=ExecutionStatus.ERROR,
                output_type="check_aave_health",
                error=WorkflowError(
                    code="WORKFLOW_NOT_FOUND",
                    message="check_aave_health workflow is not deployed",
                ),
            )

        execution = self._keeperhub.execute_workflow(workflow["id"])
        execution_id = execution.get("executionId", "")
        status_payload = self._keeperhub.get_execution_status(execution_id)
        status = self._to_status(status_payload.get("status", "pending"))

        if status in {ExecutionStatus.PENDING, ExecutionStatus.RUNNING}:
            return WorkflowExecutionResult(
                workflow=WorkflowName.CHECK_AAVE_HEALTH,
                status=status,
                output_type="check_aave_health",
                output=CheckAaveHealthOutput(
                    health_factor=None,
                    supplied_value_usd=None,
                    borrowed_value_usd=None,
                    execution_id=execution_id,
                    workflow_id=workflow["id"],
                ),
            )

        logs = self._keeperhub.get_execution_logs(execution_id)
        extracted = self._extract_aave_health_payload(logs)
        output = CheckAaveHealthOutput(
            health_factor=extracted.get("health_factor"),
            supplied_value_usd=extracted.get("supplied_value_usd"),
            borrowed_value_usd=extracted.get("borrowed_value_usd"),
            execution_id=execution_id,
            workflow_id=workflow["id"],
        )

        if status == ExecutionStatus.SUCCESS:
            return WorkflowExecutionResult(
                workflow=WorkflowName.CHECK_AAVE_HEALTH,
                status=status,
                output_type="check_aave_health",
                output=output,
            )

        return WorkflowExecutionResult(
            workflow=WorkflowName.CHECK_AAVE_HEALTH,
            status=status,
            output_type="check_aave_health",
            output=output,
            error=WorkflowError(
                code="WORKFLOW_EXECUTION_FAILED",
                message="check_aave_health workflow failed",
                retryable=False,
            ),
        )

    def monitor_aave_health(
        self,
        payload: MonitorAaveHealthInput,
    ) -> WorkflowExecutionResult:
        workflow = self._find_workflow_by_name(WorkflowName.MONITOR_AAVE_HEALTH.value)
        if not workflow:
            return WorkflowExecutionResult(
                workflow=WorkflowName.MONITOR_AAVE_HEALTH,
                status=ExecutionStatus.ERROR,
                output_type="monitor_aave_health",
                error=WorkflowError(
                    code="WORKFLOW_NOT_FOUND",
                    message="monitor_aave_health workflow is not deployed",
                ),
            )

        execution = self._keeperhub.execute_workflow(workflow["id"])
        execution_id = execution.get("executionId", "")
        status_payload = self._keeperhub.get_execution_status(execution_id)
        status = self._to_status(status_payload.get("status", "pending"))

        output = MonitorAaveHealthOutput(
            monitor_enabled=status in {ExecutionStatus.SUCCESS, ExecutionStatus.RUNNING},
            workflow_id=workflow["id"],
        )

        if status in {ExecutionStatus.SUCCESS, ExecutionStatus.RUNNING, ExecutionStatus.PENDING}:
            return WorkflowExecutionResult(
                workflow=WorkflowName.MONITOR_AAVE_HEALTH,
                status=status,
                output_type="monitor_aave_health",
                output=output,
            )

        return WorkflowExecutionResult(
            workflow=WorkflowName.MONITOR_AAVE_HEALTH,
            status=status,
            output_type="monitor_aave_health",
            output=output,
            error=WorkflowError(
                code="WORKFLOW_EXECUTION_FAILED",
                message="monitor_aave_health workflow failed",
                retryable=False,
            ),
        )

    def _find_workflow_by_name(self, workflow_name: str) -> dict[str, Any] | None:
        workflows = self._keeperhub.list_workflows()
        return next((item for item in workflows if item.get("name") == workflow_name), None)

    @staticmethod
    def _to_status(value: str) -> ExecutionStatus:
        normalized = value.lower()
        if normalized == "running":
            return ExecutionStatus.RUNNING
        if normalized == "success":
            return ExecutionStatus.SUCCESS
        if normalized == "error":
            return ExecutionStatus.ERROR
        if normalized == "cancelled":
            return ExecutionStatus.CANCELLED
        return ExecutionStatus.PENDING

    @staticmethod
    def _extract_tx_hash(logs_payload: dict[str, Any]) -> str | None:
        entries = logs_payload.get("data", [])
        for entry in entries:
            output = entry.get("output") or {}
            if isinstance(output, dict):
                for key in ("txHash", "transactionHash", "hash"):
                    value = output.get(key)
                    if isinstance(value, str) and value.startswith("0x"):
                        return value
        return None

    @staticmethod
    def _extract_balance_payload(logs_payload: dict[str, Any]) -> dict[str, Any]:
        entries = logs_payload.get("data", [])
        for entry in entries:
            output = entry.get("output") or {}
            if not isinstance(output, dict):
                continue

            if "balance" in output:
                value = output.get("balance")
                if isinstance(value, str):
                    return {"raw_balance": value}

            if "value" in output:
                value = output.get("value")
                if isinstance(value, str):
                    return {
                        "raw_balance": value,
                        "formatted_balance": output.get("formatted"),
                        "decimals": output.get("decimals"),
                        "symbol": output.get("symbol"),
                    }

        return {"raw_balance": "0"}

    @staticmethod
    def _extract_aave_health_payload(logs_payload: dict[str, Any]) -> dict[str, Any]:
        entries = logs_payload.get("data", [])
        for entry in entries:
            output = entry.get("output") or {}
            if not isinstance(output, dict):
                continue

            if "healthFactor" in output or "health_factor" in output:
                return {
                    "health_factor": ExecutionService._to_float(
                        output.get("healthFactor", output.get("health_factor"))
                    ),
                    "supplied_value_usd": ExecutionService._to_float(
                        output.get("suppliedValueUsd", output.get("supplied_value_usd"))
                    ),
                    "borrowed_value_usd": ExecutionService._to_float(
                        output.get("borrowedValueUsd", output.get("borrowed_value_usd"))
                    ),
                }

        return {}

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_explorer_url(chain_id: str, tx_hash: str | None) -> str | None:
        if not tx_hash:
            return None

        explorers = {
            "1": "https://etherscan.io/tx/",
            "8453": "https://basescan.org/tx/",
            "42161": "https://arbiscan.io/tx/",
            "137": "https://polygonscan.com/tx/",
            "11155111": "https://sepolia.etherscan.io/tx/",
        }
        prefix = explorers.get(chain_id)
        if not prefix:
            return None
        return f"{prefix}{tx_hash}"
