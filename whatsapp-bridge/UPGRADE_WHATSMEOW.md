## Update guide: Fix “Client outdated (405)” by upgrading whatsmeow

This guide documents the minimal changes needed to build and connect the bridge after updating `go.mau.fi/whatsmeow`. Newer versions are context-aware and require `context.Context` in several APIs.

Reference: `whatsapp-mcp` README on GitHub: [`lharries/whatsapp-mcp`](https://github.com/lharries/whatsapp-mcp)

### Symptoms

- On `go run main.go` you may see:
  - `Client outdated (405) connect failure (client version: ...)`
  - Build errors like “not enough arguments” for `sqlstore.New`, `GetFirstDevice`, `Download`, `GetContact`.

### Steps

1) Upgrade the dependency

```bash
go get go.mau.fi/whatsmeow@latest
go mod tidy
```

2) Apply code edits in `whatsapp-bridge/main.go`

- Add `context.Background()` to the updated whatsmeow APIs:

```diff
- container, err := sqlstore.New("sqlite3", "file:store/whatsapp.db?_foreign_keys=on", dbLog)
+ container, err := sqlstore.New(context.Background(), "sqlite3", "file:store/whatsapp.db?_foreign_keys=on", dbLog)

- deviceStore, err := container.GetFirstDevice()
+ deviceStore, err := container.GetFirstDevice(context.Background())

- mediaData, err := client.Download(downloader)
+ mediaData, err := client.Download(context.Background(), downloader)

- contact, err := client.Store.Contacts.GetContact(jid)
+ contact, err := client.Store.Contacts.GetContact(context.Background(), jid)
```

3) Rebuild and run

```bash
go build -o whatsapp-bridge
./whatsapp-bridge
```

You should see output including:

```
Successfully authenticated
Connected to WhatsApp
Starting REST API server on :8080...
```

### Verify and send a test message (optional)

With the bridge running (port 8080):

```bash
# Find a chat (replace pattern as needed)
sqlite3 store/messages.db "SELECT jid, name FROM chats WHERE name LIKE '%<name-part>%';"

# Send a message by phone (no @server) or by full JID
curl -sS -X POST http://localhost:8080/api/send \
  -H 'Content-Type: application/json' \
  -d '{"recipient":"<phone-or-jid>","message":"hello from bridge"}'
```

### Notes

- Keep the bridge process running to maintain connection and the REST API.
- For MCP usage in Cursor/Claude, configure the MCP JSON as described in the project README and restart the client.


