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
        self.created_workflows = []

        self._workflow_details = {}
        for wf in workflows:
            name = wf.get("name")
            wf_id = wf.get("id")
            details = {
                "id": wf_id,
                "name": name,
                "description": "test workflow",
                "nodes": [
                    {
                        "id": "trigger-1",
                        "type": "trigger",
                        "data": {"config": {"triggerType": "Manual"}},
                    }
                ],
                "edges": [],
            }

            if name == "check_token_balance":
                details["nodes"].append(
                    {
                        "id": "check-token-balance-1",
                        "type": "action",
                        "data": {"config": {"actionType": "web3/check-token-balance"}},
                    }
                )
                details["edges"] = [{"id": "edge-1", "source": "trigger-1", "target": "check-token-balance-1"}]

            if name == "check_aave_health":
                details["nodes"].append(
                    {
                        "id": "aave-health-1",
                        "type": "action",
                        "data": {"config": {"actionType": "web3/read-contract"}},
                    }
                )
                details["edges"] = [{"id": "edge-1", "source": "trigger-1", "target": "aave-health-1"}]

            if name == "transfer_erc20":
                details["nodes"].append(
                    {
                        "id": "transfer-token-1",
                        "type": "action",
                        "data": {"config": {"actionType": "web3/transfer-token"}},
                    }
                )
                details["edges"] = [{"id": "edge-1", "source": "trigger-1", "target": "transfer-token-1"}]

            self._workflow_details[wf_id] = details

    def list_workflows(self):
        return self._workflows

    def execute_workflow(self, workflow_id):
        return self._execution

    def get_execution_status(self, execution_id):
        return self._status

    def get_execution_logs(self, execution_id):
        return self._logs

    def list_executions(self, workflow_id):
        return [
            {
                "id": self._execution.get("executionId", "exec_1"),
                "status": self._status.get("status", "success"),
                "output": self._logs.get("output", {}),
            }
        ]

    def get_workflow(self, workflow_id):
        return self._workflow_details[workflow_id]

    def update_workflow(self, workflow_id, **kwargs):
        details = self._workflow_details[workflow_id]
        for key, value in kwargs.items():
            details[key] = value
        return details

    def create_workflow(self, name, description="", project_id=None):
        created = {
            "id": f"wf_created_{len(self.created_workflows) + 1}",
            "name": name,
            "description": description,
        }
        self.created_workflows.append(created)
        self._workflows.append(created)
        return created


class ExecutionServiceTests(unittest.TestCase):
    def test_list_workflow_deployments_marks_missing(self):
        client = FakeKeeperHubClient(workflows=[{"id": "wf_1", "name": "transfer_erc20"}])
        service = ExecutionService(client)

        report = service.list_workflow_deployments()
        by_name = {record.workflow.value: record for record in report.records}

        self.assertTrue(by_name["transfer_erc20"].exists)
        self.assertFalse(by_name["check_token_balance"].exists)
        self.assertFalse(by_name["check_aave_health"].exists)
        self.assertFalse(by_name["monitor_aave_health"].exists)

    def test_ensure_workflow_deployments_creates_missing(self):
        client = FakeKeeperHubClient(workflows=[{"id": "wf_1", "name": "transfer_erc20"}])
        service = ExecutionService(client)

        report = service.ensure_workflow_deployments()
        by_name = {record.workflow.value: record for record in report.records}

        self.assertFalse(by_name["transfer_erc20"].created)
        self.assertTrue(by_name["check_token_balance"].created)
        self.assertTrue(by_name["check_aave_health"].created)
        self.assertTrue(by_name["monitor_aave_health"].created)
        self.assertEqual(len(client.created_workflows), 3)

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
