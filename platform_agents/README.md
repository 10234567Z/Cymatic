# Platform Agents

This module implements the call reasoning behavior for Cymatic.

## What It Does

The reasoning agent follows this exact flow:

1. Parse caller sentence and infer intent.
2. List workflows from KeeperHub (`GET /api/workflows`).
3. Wildcard-match best workflow by intent keywords.
4. Build execution input from extracted entities.
5. Execute that workflow (`POST /api/workflow/{id}/execute`).
6. Poll status and return final output.

No workflow creation is done here. It only uses existing workflows.

## Supported Intents

- `check_token_balance`
- `transfer_erc20`
- `check_aave_health`
- `monitor_aave_health`

## Run

```bash
cd platform_agents
python main.py "check usdc balance on base for 0x646D1FEd1dB30e6d8dEd0e0097a27c5d38c4c32F"
```

## Required Environment

- `KEEPERHUB_API_KEY`
- Optional: `KEEPERHUB_BASE_URL` (defaults to `https://app.keeperhub.com`)
- Optional: `KEEPERHUB_WALLET_ID` (used for transfer intent)

The script auto-loads `.env` from:

- `platform_agents/.env`
- `backend/.env`
- repo root `.env`
