# Platform Agents (4-Agent Runtime)

This service implements 4 distinct agents and wires them through AXL-style envelopes.

## Agents

1. Voice Agent
- Accepts Twilio media stream events.
- Converts inbound media to transcript (0G STT hook + deterministic fallback).
- Sends transcript to Reasoning Agent.
- Converts response text into Twilio-compatible base64 mulaw payloads.

2. Reasoning Agent
- Uses 0G LLM hook for intent/entity extraction.
- Requests execution from Execution Agent.
- Requests natural spoken phrasing from Response Agent.

3. Execution Agent
- Lists existing KeeperHub workflows.
- Matches with wildcard + action type hints.
- Executes selected workflow and returns normalized result.

4. Response Agent
- Builds short, voice-safe response text from execution output.

## API Endpoints

- `GET /healthz`
- `POST /agents/voice/process-text`
- `POST /agents/voice/process-twilio-event`
- `POST /agents/reasoning/route`
- `POST /agents/execution/execute`
- `GET /agents/workflows`

## Run

```bash
cd platform_agents
python -m pip install -e .
uvicorn main:app --reload --port 8100
```

## Required Env

- `KEEPERHUB_API_KEY`
- Optional: `KEEPERHUB_BASE_URL` (default `https://app.keeperhub.com`)
- Optional: `AXL_TRANSPORT_MODE` (`local` or `mcp`, default `local`)
- Optional: `AXL_NODE_URL` (default `http://127.0.0.1:9002`)
- Optional peer wiring for remote MCP over AXL:
	- `AXL_PEER_REASONING`, `AXL_SERVICE_REASONING`
	- `AXL_PEER_EXECUTION`, `AXL_SERVICE_EXECUTION`
	- `AXL_PEER_RESPONSE`, `AXL_SERVICE_RESPONSE`
	- `AXL_PEER_VOICE`, `AXL_SERVICE_VOICE`
- Optional: `ZERO_G_INFERENCE_BASE_URL`
- Optional: `ZERO_G_INFERENCE_API_KEY`
- Optional: `ZERO_G_LLM_MODEL`, `ZERO_G_STT_MODEL`, `ZERO_G_TTS_MODEL`
- Optional direct official 0G compute broker integration:
	- `ZERO_G_BROKER_BASE_URL` (example: `http://127.0.0.1:4000`)
	- `ZERO_G_PROVIDER_ADDRESS_LLM`
	- `ZERO_G_PROVIDER_ADDRESS_STT`

Note: If 0G inference endpoints are not set, deterministic fallbacks keep end-to-end integration testable.

## AXL-Doc-Aligned Usage

When `AXL_TRANSPORT_MODE=mcp`, inter-agent calls use the documented AXL MCP bridge path:

- `POST http://127.0.0.1:9002/mcp/{peer_id}/{service_name}`

This matches the Gensyn AXL examples (`tools/list` / `tools/call` JSON-RPC over MCP).

You can inspect current mode/topology via:

- `GET /agents/axl/status`

## Official Library Notes

- 0G Compute official SDK path is TypeScript (`@0glabs/0g-serving-broker`).
- 0G Storage official SDK path is TypeScript (`@0gfoundation/0g-ts-sdk`) and Go (`0g-storage-client`).
- Gensyn AXL official integration is the node binary + local HTTP API bridge (`/topology`, `/send`, `/recv`, `/mcp/...`, `/a2a/...`).

This project now uses the official AXL HTTP pattern directly, and can use official 0G compute stack through a broker-backed endpoint when env vars are set.
