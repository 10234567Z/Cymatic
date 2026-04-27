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
    WorkflowDeploymentRecord,
    WorkflowDeploymentReport,
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

        if not self._configure_action_node(
            workflow_id=workflow["id"],
            action_type="web3/transfer-token",
            config_updates={
                "network": payload.chain_id,
                "toAddress": payload.to_address,
                "tokenAddress": payload.token_address,
                "amount": payload.amount,
                "walletId": payload.wallet_id,
                "idempotencyKey": payload.idempotency_key,
            },
            fallback=self._default_transfer_workflow(),
            description="Cymatic managed workflow: transfer_erc20",
        ):
            return WorkflowExecutionResult(
                workflow=WorkflowName.TRANSFER_ERC20,
                status=ExecutionStatus.ERROR,
                output_type="transfer_erc20",
                error=WorkflowError(
                    code="WORKFLOW_CONFIG_INVALID",
                    message="transfer_erc20 missing transfer action node",
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

        execution_entry = self._get_execution_entry(workflow["id"], execution_id)
        execution_output = (execution_entry or {}).get("output") or {}
        logs = self._keeperhub.get_execution_logs(execution_id)
        tx_hash = self._extract_tx_hash_from_output(execution_output) or self._extract_tx_hash(logs)

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

    def list_workflow_deployments(self) -> WorkflowDeploymentReport:
        workflows = self._keeperhub.list_workflows()
        records = [
            self._deployment_record_for_name(workflows, workflow_name)
            for workflow_name in WorkflowName
        ]
        return WorkflowDeploymentReport(records=records)

    def ensure_workflow_deployments(self) -> WorkflowDeploymentReport:
        workflows = self._keeperhub.list_workflows()
        existing_by_name = {item.get("name"): item for item in workflows}
        records: list[WorkflowDeploymentRecord] = []

        for workflow_name in WorkflowName:
            existing = existing_by_name.get(workflow_name.value)
            if existing:
                records.append(
                    WorkflowDeploymentRecord(
                        workflow=workflow_name,
                        exists=True,
                        created=False,
                        workflow_id=existing.get("id"),
                    )
                )
                continue

            created = self._keeperhub.create_workflow(
                name=workflow_name.value,
                description=f"Cymatic managed workflow: {workflow_name.value}",
            )
            records.append(
                WorkflowDeploymentRecord(
                    workflow=workflow_name,
                    exists=True,
                    created=True,
                    workflow_id=created.get("id"),
                )
            )

        return WorkflowDeploymentReport(records=records)

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

        if not self._configure_action_node(
            workflow_id=workflow["id"],
            action_type="web3/check-token-balance",
            config_updates={
                "network": payload.chain_id,
                "address": payload.wallet_address,
                "tokenAddress": payload.token_address,
            },
            fallback=self._default_check_token_balance_workflow(),
            description="Cymatic managed workflow: check_token_balance",
        ):
            return WorkflowExecutionResult(
                workflow=WorkflowName.CHECK_TOKEN_BALANCE,
                status=ExecutionStatus.ERROR,
                output_type="check_token_balance",
                error=WorkflowError(
                    code="WORKFLOW_CONFIG_INVALID",
                    message="check_token_balance missing token balance action node",
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

        execution_entry = self._get_execution_entry(workflow["id"], execution_id)
        execution_output = (execution_entry or {}).get("output") or {}
        logs = self._keeperhub.get_execution_logs(execution_id)
        extracted = self._extract_balance_payload_from_output(execution_output)
        if not extracted:
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

        if not self._configure_action_node(
            workflow_id=workflow["id"],
            action_type="web3/read-contract",
            config_updates={
                "network": payload.chain_id,
                "args": [payload.wallet_address],
                "abi": self._aave_user_account_data_abi(),
            },
            fallback=self._default_check_aave_health_workflow(),
            description="Cymatic managed workflow: check_aave_health",
        ):
            return WorkflowExecutionResult(
                workflow=WorkflowName.CHECK_AAVE_HEALTH,
                status=ExecutionStatus.ERROR,
                output_type="check_aave_health",
                error=WorkflowError(
                    code="WORKFLOW_CONFIG_INVALID",
                    message="check_aave_health missing read action node",
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

        execution_entry = self._get_execution_entry(workflow["id"], execution_id)
        execution_output = (execution_entry or {}).get("output") or {}
        logs = self._keeperhub.get_execution_logs(execution_id)
        extracted = self._extract_aave_health_payload_from_output(execution_output)
        if not extracted:
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

        if not self._configure_action_node(
            workflow_id=workflow["id"],
            action_type="web3/read-contract",
            config_updates={
                "network": payload.chain_id,
                "args": [payload.wallet_address],
                "abi": self._aave_user_account_data_abi(),
            },
            fallback=self._default_monitor_aave_health_workflow(),
            description="Cymatic managed workflow: monitor_aave_health",
        ):
            return WorkflowExecutionResult(
                workflow=WorkflowName.MONITOR_AAVE_HEALTH,
                status=ExecutionStatus.ERROR,
                output_type="monitor_aave_health",
                error=WorkflowError(
                    code="WORKFLOW_CONFIG_INVALID",
                    message="monitor_aave_health missing monitor action node",
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

    def _configure_action_node(
        self,
        *,
        workflow_id: str,
        action_type: str,
        config_updates: dict[str, Any],
        fallback: tuple[list[dict[str, Any]], list[dict[str, Any]]],
        description: str,
    ) -> bool:
        full = self._keeperhub.get_workflow(workflow_id)
        nodes = full.get("nodes", [])
        edges = full.get("edges", [])

        action_found = False
        for node in nodes:
            if node.get("type") != "action":
                continue
            cfg = node.setdefault("data", {}).setdefault("config", {})
            if cfg.get("actionType") == action_type:
                cfg.update(config_updates)
                action_found = True
                break

        if not action_found:
            nodes, edges = fallback
            for node in nodes:
                if node.get("type") == "action":
                    cfg = node.setdefault("data", {}).setdefault("config", {})
                    if cfg.get("actionType") == action_type:
                        cfg.update(config_updates)
                        action_found = True

        if not action_found:
            return False

        self._keeperhub.update_workflow(
            workflow_id,
            nodes=nodes,
            edges=edges,
            description=description,
        )
        return True

    def _get_execution_entry(self, workflow_id: str, execution_id: str) -> dict[str, Any] | None:
        executions = self._keeperhub.list_executions(workflow_id)
        return next((item for item in executions if item.get("id") == execution_id), None)

    @staticmethod
    def _deployment_record_for_name(
        workflows: list[dict[str, Any]],
        workflow_name: WorkflowName,
    ) -> WorkflowDeploymentRecord:
        existing = next((item for item in workflows if item.get("name") == workflow_name.value), None)
        if not existing:
            return WorkflowDeploymentRecord(workflow=workflow_name, exists=False)

        return WorkflowDeploymentRecord(
            workflow=workflow_name,
            exists=True,
            created=False,
            workflow_id=existing.get("id"),
        )

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
        entries = ExecutionService._extract_log_entries(logs_payload)
        for entry in entries:
            output = entry.get("output") or {}
            if isinstance(output, dict):
                for key in ("txHash", "transactionHash", "hash"):
                    value = output.get(key)
                    if isinstance(value, str) and value.startswith("0x"):
                        return value
        return None

    @staticmethod
    def _extract_tx_hash_from_output(output: dict[str, Any]) -> str | None:
        for key in ("txHash", "transactionHash", "hash"):
            value = output.get(key)
            if isinstance(value, str) and value.startswith("0x"):
                return value
        return None

    @staticmethod
    def _extract_log_entries(logs_payload: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(logs_payload.get("logs"), list):
            return logs_payload.get("logs", [])
        if isinstance(logs_payload.get("data"), list):
            return logs_payload.get("data", [])
        return []

    @staticmethod
    def _extract_balance_payload(logs_payload: dict[str, Any]) -> dict[str, Any]:
        entries = ExecutionService._extract_log_entries(logs_payload)
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
    def _extract_balance_payload_from_output(output: dict[str, Any]) -> dict[str, Any]:
        balance = output.get("balance")
        if not isinstance(balance, dict):
            return {}

        return {
            "raw_balance": str(balance.get("balanceRaw", "0")),
            "formatted_balance": str(balance.get("balance")) if balance.get("balance") is not None else None,
            "decimals": balance.get("decimals"),
            "symbol": balance.get("symbol"),
        }

    @staticmethod
    def _extract_aave_health_payload(logs_payload: dict[str, Any]) -> dict[str, Any]:
        entries = ExecutionService._extract_log_entries(logs_payload)
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
    def _extract_aave_health_payload_from_output(output: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(output, dict):
            return {}

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

        result = output.get("result")
        if isinstance(result, list) and len(result) >= 6:
            collateral_base = ExecutionService._to_float(result[0])
            debt_base = ExecutionService._to_float(result[1])
            health_raw = ExecutionService._to_float(result[5])
            health_factor = None
            if health_raw is not None:
                health_factor = health_raw / 1e18 if health_raw > 1e9 else health_raw
            return {
                "health_factor": health_factor,
                "supplied_value_usd": collateral_base,
                "borrowed_value_usd": debt_base,
            }

        return {}

    @staticmethod
    def _default_transfer_workflow() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        nodes = [
            {
                "id": "trigger-1",
                "type": "trigger",
                "data": {
                    "label": "Manual Trigger",
                    "type": "trigger",
                    "config": {"triggerType": "Manual"},
                    "status": "idle",
                },
            },
            {
                "id": "transfer-token-1",
                "type": "action",
                "data": {
                    "label": "Transfer Token",
                    "type": "action",
                    "config": {
                        "actionType": "web3/transfer-token",
                        "network": "8453",
                        "toAddress": "0x0000000000000000000000000000000000000000",
                        "tokenAddress": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                        "amount": "0",
                        "walletId": "",
                    },
                    "status": "idle",
                },
            },
        ]
        edges = [{"id": "edge-1", "source": "trigger-1", "target": "transfer-token-1"}]
        return nodes, edges

    @staticmethod
    def _default_check_token_balance_workflow() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        nodes = [
            {
                "id": "trigger-1",
                "type": "trigger",
                "data": {
                    "label": "Manual Trigger",
                    "type": "trigger",
                    "config": {"triggerType": "Manual"},
                    "status": "idle",
                },
            },
            {
                "id": "check-token-balance-1",
                "type": "action",
                "data": {
                    "label": "Check Token Balance",
                    "type": "action",
                    "config": {
                        "actionType": "web3/check-token-balance",
                        "network": "8453",
                        "address": "0x0000000000000000000000000000000000000000",
                        "tokenAddress": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                    },
                    "status": "idle",
                },
            },
        ]
        edges = [{"id": "edge-1", "source": "trigger-1", "target": "check-token-balance-1"}]
        return nodes, edges

    @staticmethod
    def _default_check_aave_health_workflow() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        nodes = [
            {
                "id": "trigger-1",
                "type": "trigger",
                "data": {
                    "label": "Manual Trigger",
                    "type": "trigger",
                    "config": {"triggerType": "Manual"},
                    "status": "idle",
                },
            },
            {
                "id": "aave-health-1",
                "type": "action",
                "data": {
                    "label": "Read Aave Account Data",
                    "type": "action",
                    "config": {
                        "actionType": "web3/read-contract",
                        "network": "42161",
                        "contractAddress": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
                        "functionName": "getUserAccountData",
                        "args": ["0x0000000000000000000000000000000000000000"],
                        "abi": ExecutionService._aave_user_account_data_abi(),
                    },
                    "status": "idle",
                },
            },
        ]
        edges = [{"id": "edge-1", "source": "trigger-1", "target": "aave-health-1"}]
        return nodes, edges

    @staticmethod
    def _default_monitor_aave_health_workflow() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return ExecutionService._default_check_aave_health_workflow()

    @staticmethod
    def _aave_user_account_data_abi() -> str:
        return (
            '[{"inputs":[{"internalType":"address","name":"user","type":"address"}],'
            '"name":"getUserAccountData","outputs":[{"internalType":"uint256",'
            '"name":"totalCollateralBase","type":"uint256"},{"internalType":"uint256",'
            '"name":"totalDebtBase","type":"uint256"},{"internalType":"uint256",'
            '"name":"availableBorrowsBase","type":"uint256"},{"internalType":"uint256",'
            '"name":"currentLiquidationThreshold","type":"uint256"},{"internalType":"uint256",'
            '"name":"ltv","type":"uint256"},{"internalType":"uint256",'
            '"name":"healthFactor","type":"uint256"}],"stateMutability":"view",'
            '"type":"function"}]'
        )

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
