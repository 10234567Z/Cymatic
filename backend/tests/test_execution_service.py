import unittest

from app.services.execution_service import ExecutionService
from app.services.workflow_contracts import (
    CheckAaveHealthInput,
    CheckTokenBalanceInput,
    ExecutionStatus,
    TransferErc20Input,
)


class FakeKeeperHubClient:
    def __init__(self, workflows, execution=None, status=None, logs=None):
        self._workflows = workflows
        self._execution = execution or {"executionId": "exec_1"}
        self._status = status or {"status": "success"}
        self._logs = logs or {"data": []}

    def list_workflows(self):
        return self._workflows

    def execute_workflow(self, workflow_id):
        return self._execution

    def get_execution_status(self, execution_id):
        return self._status

    def get_execution_logs(self, execution_id):
        return self._logs


class ExecutionServiceTests(unittest.TestCase):
    def test_transfer_returns_not_found_when_workflow_missing(self):
        service = ExecutionService(FakeKeeperHubClient(workflows=[]))
        result = service.transfer_erc20(
            TransferErc20Input(
                wallet_id="wid",
                chain_id="8453",
                token_address="0xtoken",
                to_address="0xto",
                amount="10",
                idempotency_key="idem-1",
            )
        )

        self.assertEqual(result.status, ExecutionStatus.ERROR)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "WORKFLOW_NOT_FOUND")

    def test_check_token_balance_extracts_value_payload(self):
        client = FakeKeeperHubClient(
            workflows=[{"id": "wf_1", "name": "check_token_balance"}],
            logs={
                "data": [
                    {
                        "output": {
                            "value": "123456",
                            "formatted": "0.123456",
                            "decimals": 6,
                            "symbol": "USDC",
                        }
                    }
                ]
            },
        )
        service = ExecutionService(client)

        result = service.check_token_balance(
            CheckTokenBalanceInput(
                chain_id="8453",
                wallet_address="0xwallet",
                token_address="0xtoken",
            )
        )

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertIsNotNone(result.output)
        self.assertEqual(result.output.raw_balance, "123456")
        self.assertEqual(result.output.symbol, "USDC")

    def test_check_aave_health_extracts_metrics(self):
        client = FakeKeeperHubClient(
            workflows=[{"id": "wf_2", "name": "check_aave_health"}],
            logs={
                "data": [
                    {
                        "output": {
                            "healthFactor": "1.82",
                            "suppliedValueUsd": "5000",
                            "borrowedValueUsd": "2500",
                        }
                    }
                ]
            },
        )
        service = ExecutionService(client)

        result = service.check_aave_health(
            CheckAaveHealthInput(chain_id="42161", wallet_address="0xwallet")
        )

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertIsNotNone(result.output)
        self.assertEqual(result.output.health_factor, 1.82)
        self.assertEqual(result.output.supplied_value_usd, 5000.0)
        self.assertEqual(result.output.borrowed_value_usd, 2500.0)


if __name__ == "__main__":
    unittest.main()
