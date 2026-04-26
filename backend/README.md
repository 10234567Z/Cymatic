# Cymatic Backend

## Environment

Create backend environment variables in a shell or `.env` file:

```bash
export KEEPERHUB_API_KEY="kh_..."
export KEEPERHUB_BASE_URL="https://app.keeperhub.com"
```

## Run API

```bash
cd backend
uv run uvicorn main:app --reload --port 8000
```

Health check:

```bash
curl -sS http://127.0.0.1:8000/healthz
```

## KeeperHub: List Existing Workflows

```bash
curl -sS \
	-H "Authorization: Bearer $KEEPERHUB_API_KEY" \
	"https://app.keeperhub.com/api/workflows"
```

## KeeperHub: Create a Workflow Draft

```bash
curl -sS -X POST \
	-H "Authorization: Bearer $KEEPERHUB_API_KEY" \
	-H "Content-Type: application/json" \
	"https://app.keeperhub.com/api/workflows/create" \
	-d '{"name":"transfer_erc20","description":"Cymatic transfer workflow"}'
```

## KeeperHub: Execute a Workflow

```bash
curl -sS -X POST \
	-H "Authorization: Bearer $KEEPERHUB_API_KEY" \
	"https://app.keeperhub.com/api/workflow/<WORKFLOW_ID>/execute"
```

## Run Tests

```bash
cd backend
uv run python -m unittest discover -s tests -p "test_*.py"
```
