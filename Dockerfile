# Multi-service container for Railway: Go WhatsApp bridge + FastAPI (uv)

# --- Build Go bridge ---
FROM golang:1.22-bullseye AS go-builder
WORKDIR /src/whatsapp-bridge
COPY whatsapp-bridge/go.mod whatsapp-bridge/go.sum ./
RUN go mod download
COPY whatsapp-bridge/ .
# Build binary (CGO needed for sqlite3)
RUN CGO_ENABLED=1 GOOS=linux GOARCH=amd64 go build -o /out/whatsapp-bridge

# --- Final runtime with uv preinstalled ---
FROM ghcr.io/astral-sh/uv:python3.11-bookworm
WORKDIR /app

# Install Python deps via uv (respect lock)
COPY whatsapp-mcp-server/pyproject.toml whatsapp-mcp-server/uv.lock ./whatsapp-mcp-server/
RUN cd whatsapp-mcp-server && uv sync --frozen --no-dev

# Copy Python server code
COPY whatsapp-mcp-server/ ./whatsapp-mcp-server/

# Copy Go bridge binary and store DBs
COPY --from=go-builder /out/whatsapp-bridge ./whatsapp-bridge/whatsapp-bridge
COPY whatsapp-bridge/store/ ./whatsapp-bridge/store/

# Railway exposes $PORT; FastAPI will bind to it
EXPOSE 8000

# Entrypoint launches both services
COPY start.sh ./start.sh
RUN chmod +x ./start.sh
CMD ["./start.sh"]
