## whatsapp-mcp FastAPI API

Comprehensive guide to interacting with the FastAPI server.

## Base URL and Authentication

- Base URL: your public URL (e.g., `https://<your-ngrok>.ngrok-free.app`)
- Auth header required on all endpoints except those listed under Exemptions:
  - Header: `X-Webhook-Api-Key: <your_key>`
- Exemptions (no auth required): `/health`, `/docs`, `/redoc`, `/openapi.json`
- Content type: `application/json` for all request bodies

### Quick start

```bash
# Load key from .env (if present next to main.py)
KEY=$(grep -E '^WEBHOOK_API_KEY=' whatsapp-mcp-server/.env | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//')
BASE_URL="https://ebe91886e4a6.ngrok-free.app"

# Health (no auth)
curl -sS "$BASE_URL/health" | cat

# Example authorized request
curl -sS -H "X-Webhook-Api-Key: $KEY" "$BASE_URL/chats?limit=5" | cat
```

## Data Models

### Contact

```json
{
  "phone_number": "string",     
  "name": "string|null",
  "jid": "string"              
}
```

### Chat

```json
{
  "jid": "string",                       
  "name": "string|null",
  "last_message_time": "ISO-8601|null",
  "last_message": "string|null",
  "last_sender": "string|null",
  "last_is_from_me": true
}
```

### Message

```json
{
  "timestamp": "ISO-8601",
  "sender": "string",
  "content": "string",
  "is_from_me": true,
  "chat_jid": "string",
  "id": "string",
  "chat_name": "string|null",
  "media_type": "string|null"
}
```

## Endpoints

### Health

- GET `/health` (no auth)
- Response: `{ "status": "ok" }`

### Contacts

- GET `/contacts/search?query=string`
  - Response: `Contact[]`

- GET `/contacts/{jid}/chats?limit=int&page=int`
  - Response: `Chat[]`

- GET `/contacts/{jid}/last-interaction`
  - Response: `{ "output": string|null }`

### Chats

- GET `/chats?query=string&limit=int&page=int&include_last_message=bool&sort_by=last_active|name`
  - Response: `Chat[]`

- GET `/chats/{chat_jid}?include_last_message=bool`
  - Response: `Chat|null`

- GET `/chats/direct-by-contact?sender_phone_number=string`
  - Response: `Chat|null`

### Messages

- GET `/messages`
  - Query params:
    - `after`: ISO-8601 datetime
    - `before`: ISO-8601 datetime
    - `sender_phone_number`: string
    - `chat_jid`: string (full JID)
    - `query`: string
    - `limit`: int (default 20)
    - `page`: int (default 0)
    - `include_context`: bool (default true)
    - `context_before`: int (default 1)
    - `context_after`: int (default 1)
  - Response when `include_context=true` (default): `{ "output": string }`
  - Response when `include_context=false`: `{ "messages": Message[] }`

- GET `/messages/{message_id}/context?before=int&after=int`
  - Response: `{ "message": Message, "before": Message[], "after": Message[] }`

### Sending

- POST `/messages/send-text`
  - Body: `{ "recipient": string, "message": string }`
  - Notes: `recipient` can be a phone number (auto-converted) or a full JID
  - Response: `{ "success": bool, "message": string }`

- POST `/messages/send-file`
  - Body: `{ "recipient": string, "media_path": string }`
  - Notes: `media_path` must exist on the server filesystem
  - Response: `{ "success": bool, "message": string }`

- POST `/messages/send-audio`
  - Body: `{ "recipient": string, "media_path": string }`
  - Notes: non-`.ogg` inputs are auto-converted to Ogg/Opus if possible
  - Response: `{ "success": bool, "message": string }`

### Media

- POST `/media/download`
  - Body: `{ "message_id": string, "chat_jid": string }`
  - Response on success: `{ "success": true, "message": string, "file_path": string }`
  - Response on failure: `{ "success": false, "message": string }`

## Identifier Notes

- `chat_jid` must be a full JID:
  - Direct: `<phone>@s.whatsapp.net` (e.g., `85257037164@s.whatsapp.net`)
  - Group: `<id>@g.us`
- To resolve a phone number to a direct chat JID, call:
  - GET `/chats/direct-by-contact?sender_phone_number=<number>`

## Example Calls

```bash
# Search contacts
curl -sS -H "X-Webhook-Api-Key: $KEY" \
  "$BASE_URL/contacts/search?query=852" | cat

# Get direct chat by phone number
curl -sS -H "X-Webhook-Api-Key: $KEY" \
  "$BASE_URL/chats/direct-by-contact?sender_phone_number=85257037164" | cat

# Get chat details
curl -sS -H "X-Webhook-Api-Key: $KEY" \
  "$BASE_URL/chats/85257037164@s.whatsapp.net" | cat

# Send a text message
curl -sS -X POST -H 'Content-Type: application/json' -H "X-Webhook-Api-Key: $KEY" \
  "$BASE_URL/messages/send-text" \
  -d '{"recipient":"85267436242","message":"hi"}' | cat

# List messages (formatted output)
curl -sS -H "X-Webhook-Api-Key: $KEY" \
  "$BASE_URL/messages?chat_jid=85267436242@s.whatsapp.net&limit=10" | cat

# Message context
curl -sS -H "X-Webhook-Api-Key: $KEY" \
  "$BASE_URL/messages/<MESSAGE_ID>/context?before=3&after=3" | cat

# Download media
curl -sS -X POST -H 'Content-Type: application/json' -H "X-Webhook-Api-Key: $KEY" \
  "$BASE_URL/media/download" \
  -d '{"message_id":"<MESSAGE_ID>","chat_jid":"85267436242@s.whatsapp.net"}' | cat
```

## Behavior Notes

- When `include_context=true` on `/messages`, the server returns a single formatted string under `output` combining messages and context windows for readability.
- API key is loaded from `.env` near `main.py` (`WEBHOOK_API_KEY`). If not present, the server will respond with a 500 on protected endpoints to avoid accidental exposure.



