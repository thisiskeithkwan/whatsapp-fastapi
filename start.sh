#!/usr/bin/env bash
set -euo pipefail

# Default values
export PORT="${PORT:-8000}"
export GO_BRIDGE_PORT="${GO_BRIDGE_PORT:-8080}"

# Start the Go WhatsApp bridge
./whatsapp-bridge/whatsapp-bridge >/proc/1/fd/1 2>/proc/1/fd/2 &

# Start FastAPI using uv and the locked environment
cd whatsapp-mcp-server
uv run uvicorn main:app --host 0.0.0.0 --port "$PORT"
