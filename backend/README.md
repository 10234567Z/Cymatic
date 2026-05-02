# Cymatic Backend

## Environment

Create backend environment variables in a shell or `.env` file:

```bash
export SUPABASE_URL="https://<project>.supabase.co"
export SUPABASE_SECRET_KEY="<service_role_key>"
export TURNKEY_API_PUBLIC_KEY="..."
export TURNKEY_API_PRIVATE_KEY="..."
export TURNKEY_ORG_ID="..."
export TWILIO_ACCOUNT_SID="..."
export TWILIO_AUTH_TOKEN="..."
export TWILIO_PHONE_NUMBER="+1..."
export BASE_URL="https://<public-backend-url>"
export PLATFORM_AGENTS_URL="http://127.0.0.1:8100"

# Optional, but recommended for higher Base Sepolia scan limits
export BASESCAN_API_KEY="..."
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
