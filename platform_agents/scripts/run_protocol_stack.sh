#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Load backend .env so all vars are available to child processes
if [ -f "$ROOT_DIR/../backend/.env" ]; then
  set -a; source "$ROOT_DIR/../backend/.env"; set +a
fi

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
