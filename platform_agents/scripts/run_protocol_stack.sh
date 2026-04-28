#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

: "${OPENAI_BASE_URL:=http://localhost}"
: "${OPENAI_API_KEY:=test}"
: "${KEEPERHUB_API_KEY:=test}"

export OPENAI_BASE_URL OPENAI_API_KEY KEEPERHUB_API_KEY

echo "Starting MCP adapter on :7101"
uvicorn mcp_server:app --host 127.0.0.1 --port 7101 &
MCP_PID=$!

echo "Starting A2A adapter on :7102"
uvicorn a2a_server:app --host 127.0.0.1 --port 7102 &
A2A_PID=$!

echo "Starting main agents API on :8100"
uvicorn main:app --host 0.0.0.0 --port 8100 &
MAIN_PID=$!

cleanup() {
  kill "$MCP_PID" "$A2A_PID" "$MAIN_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

wait
