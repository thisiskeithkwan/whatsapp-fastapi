#!/usr/bin/env bash
set -euo pipefail

# Default values
export PORT="${PORT:-8000}"
export GO_BRIDGE_PORT="${GO_BRIDGE_PORT:-8080}"

# If not provided, point Go's outgoing webhook to FastAPI inside the same container
export OUTGOING_WEBHOOK_URL="${OUTGOING_WEBHOOK_URL:-http://127.0.0.1:${PORT}/webhook/ingest}"
export OUTGOING_WEBHOOK_SECRET_HEADER="${OUTGOING_WEBHOOK_SECRET_HEADER:-X-Webhook-Api-Key}"
# Reuse WEBHOOK_API_KEY for the outgoing secret if not separately provided
if [ -n "${WEBHOOK_API_KEY:-}" ] && [ -z "${OUTGOING_WEBHOOK_SECRET:-}" ]; then
  export OUTGOING_WEBHOOK_SECRET="$WEBHOOK_API_KEY"
fi

# Start the Go WhatsApp bridge
./whatsapp-bridge/whatsapp-bridge >/proc/1/fd/1 2>/proc/1/fd/2 &

# Start FastAPI using uv and the locked environment
cd whatsapp-mcp-server
uv run uvicorn main:app --host 0.0.0.0 --port "$PORT"
