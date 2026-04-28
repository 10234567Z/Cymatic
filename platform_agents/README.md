# Platform Agents (4-Agent Runtime)

This service implements 4 distinct agents and wires them through AXL-style envelopes.

## Agents

1. Voice Agent
- Accepts Twilio media stream events.
- Converts inbound media to transcript via 0G STT.
- Sends transcript to Reasoning Agent.
- Converts response text into Twilio-compatible base64 mulaw payloads via 0G TTS.

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

### Run MCP Adapter

```bash
cd platform_agents
uvicorn mcp_server:app --host 127.0.0.1 --port 7101
```

### Run A2A Adapter

```bash
cd platform_agents
uvicorn a2a_server:app --host 127.0.0.1 --port 7102
```

### Run All Local Services (One Command)

```bash
cd platform_agents
chmod +x scripts/run_protocol_stack.sh
./scripts/run_protocol_stack.sh
```

These adapters expose your local agent runtime as protocol endpoints that an AXL
node can forward to.

## Required Env

`platform_agents/main.py` loads env in this order:

1. `platform_agents/.env`
2. `backend/.env`

So yes, the service can run with only `backend/.env`, but `platform_agents/.env.example` is now provided for local clarity.

- Required: `KEEPERHUB_API_KEY`
- Optional: `KEEPERHUB_BASE_URL` (default `https://app.keeperhub.com`)
- Required: `OPENAI_BASE_URL`, `OPENAI_API_KEY`
- Optional: `OPENAI_LLM_MODEL` (default `gpt-4o-mini`)
- Optional: `OPENAI_STT_MODEL` (default `whisper-1`)
- Optional: `OPENAI_TTS_MODEL` (default `tts-1`)
- Optional: `OPENAI_TTS_VOICE` (default `alloy`)
- Optional: `AXL_TRANSPORT_MODE` (`local`, `mcp`, or `axl`; default `local`)
- Optional: `AXL_NODE_URL` (default `http://127.0.0.1:9002`)
- Optional: `AXL_PROTOCOL_DEFAULT` (`mcp` or `a2a`, default `mcp`)
- Optional per-agent protocol overrides:
	- `AXL_PROTOCOL_REASONING`
	- `AXL_PROTOCOL_EXECUTION`
	- `AXL_PROTOCOL_RESPONSE`
	- `AXL_PROTOCOL_VOICE`
- Optional peer wiring for remote MCP over AXL:
	- `AXL_PEER_REASONING`, `AXL_SERVICE_REASONING`
	- `AXL_PEER_EXECUTION`, `AXL_SERVICE_EXECUTION`
	- `AXL_PEER_RESPONSE`, `AXL_SERVICE_RESPONSE`
	- `AXL_PEER_VOICE`, `AXL_SERVICE_VOICE`
- Optional CallerINFT integration on 0G:
	- `CALLER_INFT_ADDRESS`
	- `OG_RPC_URL` (default `https://evmrpc-testnet.0g.ai`)
	- `DEPLOYER_PRIVATE_KEY` (needed for write ops)
	- `CALLER_INFT_DEPLOYER_ADDRESS`

## AXL-Doc-Aligned Usage

When `AXL_TRANSPORT_MODE=mcp`, inter-agent calls use the documented AXL MCP bridge path:

- `POST http://127.0.0.1:9002/mcp/{peer_id}/{service_name}`

When using A2A protocol for a target agent (`AXL_PROTOCOL_* = a2a`), calls go through:

- `POST http://127.0.0.1:9002/a2a/{peer_id}/{service_name}`

This matches the Gensyn AXL examples (`tools/list` / `tools/call` JSON-RPC over MCP).

You can inspect current mode/topology via:

- `GET /agents/axl/status`

## Public Node + Service Setup

To act as a public AXL node, you must run the external Gensyn AXL `node` binary
with `Listen` enabled on a public peering port (for example `tls://0.0.0.0:9001`).

Recommended split:

1. AXL node peering port exposed publicly (for routing/peering)
2. AXL HTTP bridge (`:9002`) bound to localhost only
3. MCP adapter running locally (`mcp_server.py`)
4. A2A adapter running locally (`a2a_server.py`)
5. Main app running locally (`main.py`)

Then register your local adapter URLs with your local AXL integration layer.

Quick checks:

```bash
# Local AXL node identity and peers
curl -s http://127.0.0.1:9002/topology | python3 -m json.tool

# MCP adapter tools list
curl -s -X POST http://127.0.0.1:7101/mcp \
	-H "Content-Type: application/json" \
	-d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python3 -m json.tool

# A2A adapter request
curl -s -X POST http://127.0.0.1:7102/a2a \
	-H "Content-Type: application/json" \
	-d '{"trace_id":"demo-1","from_agent":"remote","intent":"phrase_response","to_agent":"response","payload":{"intent":"check_aave_health","execution":{"output":{"healthFactor":"1.75"}}}}' | python3 -m json.tool

# Local adapter smoke suite
./.venv/bin/python platform_agents/scripts/smoke_protocols.py
```

## Official Library Notes

- 0G Compute official SDK path is TypeScript (`@0glabs/0g-serving-broker`).
- 0G Storage official SDK path is TypeScript (`@0gfoundation/0g-ts-sdk`) and Go (`0g-storage-client`).
- Gensyn AXL official integration is the node binary + local HTTP API bridge (`/topology`, `/send`, `/recv`, `/mcp/...`, `/a2a/...`).

This project now uses the official AXL HTTP pattern directly, and can use official 0G compute stack through a broker-backed endpoint when env vars are set.
