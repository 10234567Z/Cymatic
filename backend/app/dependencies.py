from fastapi import HTTPException

from app.services import ExecutionService, KeeperHubClient


def get_execution_service() -> ExecutionService:
    try:
        client = KeeperHubClient.from_env()
        return ExecutionService(keeperhub_client=client)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
