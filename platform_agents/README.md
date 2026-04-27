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
- Optional: `ZERO_G_INFERENCE_BASE_URL`
- Optional: `ZERO_G_INFERENCE_API_KEY`
- Optional: `ZERO_G_LLM_MODEL`, `ZERO_G_STT_MODEL`, `ZERO_G_TTS_MODEL`

Note: If 0G inference endpoints are not set, deterministic fallbacks keep end-to-end integration testable.
