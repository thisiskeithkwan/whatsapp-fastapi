from typing import Any, Dict, List, Optional, Literal
from dataclasses import asdict, is_dataclass
import os
import json
from datetime import datetime
from collections import deque

from fastapi import FastAPI, Query, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx

from whatsapp import (
    search_contacts as whatsapp_search_contacts,
    list_messages as whatsapp_list_messages,
    list_chats as whatsapp_list_chats,
    get_chat as whatsapp_get_chat,
    get_direct_chat_by_contact as whatsapp_get_direct_chat_by_contact,
    get_contact_chats as whatsapp_get_contact_chats,
    get_last_interaction as whatsapp_get_last_interaction,
    get_message_context as whatsapp_get_message_context,
    send_message as whatsapp_send_message,
    send_file as whatsapp_send_file,
    send_audio_message as whatsapp_send_audio_message,
    download_media as whatsapp_download_media,
)

app = FastAPI(title="whatsapp-mcp-fastapi", version="0.1.0")

# Load environment variables from local .env
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
WEBHOOK_API_KEY = os.environ.get("WEBHOOK_API_KEY")
OUTGOING_WEBHOOK_URL = os.environ.get("OUTGOING_WEBHOOK_URL")
OUTGOING_WEBHOOK_HEADERS = os.environ.get("OUTGOING_WEBHOOK_HEADERS")  # JSON string of default headers
# Default outgoing header aligns with incoming protection
OUTGOING_WEBHOOK_SECRET_HEADER = os.environ.get("OUTGOING_WEBHOOK_SECRET_HEADER", "X-Webhook-Api-Key")
# Reuse WEBHOOK_API_KEY by default if a separate outgoing secret is not provided
OUTGOING_WEBHOOK_SECRET = os.environ.get("OUTGOING_WEBHOOK_SECRET") or WEBHOOK_API_KEY

try:
    DEFAULT_OUTGOING_HEADERS = json.loads(OUTGOING_WEBHOOK_HEADERS) if OUTGOING_WEBHOOK_HEADERS else {}
    if not isinstance(DEFAULT_OUTGOING_HEADERS, dict):
        DEFAULT_OUTGOING_HEADERS = {}
except Exception:
    DEFAULT_OUTGOING_HEADERS = {}

# In-memory received events buffer (for quick inspection)
RECEIVED_EVENTS: deque = deque(maxlen=200)


# ---------- Security Middleware ----------

EXEMPT_PATHS = {"/docs", "/redoc", "/openapi.json", "/health"}

@app.middleware("http")
async def require_webhook_api_key(request: Request, call_next):
    # Skip protection for docs and health
    if request.url.path in EXEMPT_PATHS:
        return await call_next(request)

    if not WEBHOOK_API_KEY:
        # If not configured, block by default to avoid accidental exposure
        return JSONResponse(status_code=500, content={"detail": "Server misconfiguration: WEBHOOK_API_KEY not set"})

    header_value = request.headers.get("x-webhook-api-key")
    if header_value is None:
        return JSONResponse(status_code=401, content={"detail": "Missing X-Webhook-Api-Key header"})
    if header_value != WEBHOOK_API_KEY:
        return JSONResponse(status_code=403, content={"detail": "Invalid webhook API key"})

    return await call_next(request)


# ---------- Helpers ----------

def dataclass_to_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, list):
        return [dataclass_to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {key: dataclass_to_dict(value) for key, value in obj.items()}
    return obj


# ---------- Request Models ----------

class SendTextRequest(BaseModel):
    recipient: str
    message: str


class SendMediaRequest(BaseModel):
    recipient: str
    media_path: str


class DownloadMediaRequest(BaseModel):
    message_id: str
    chat_jid: str


class WebhookTriggerRequest(BaseModel):
    target_url: Optional[str] = None
    method: Literal["POST", "GET"] = "POST"
    payload: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    query: Optional[Dict[str, str]] = None
    async_mode: bool = True
    timeout_seconds: float = 10.0

class IngestResponse(BaseModel):
    received: bool
    stored_events: int


# ---------- Endpoints (replicating tools) ----------

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}

@app.get("/contacts/search")
def search_contacts(query: str = Query(..., description="Search name or phone number")) -> List[Dict[str, Any]]:
    contacts = whatsapp_search_contacts(query)
    return dataclass_to_dict(contacts)


@app.get("/messages")
def list_messages(
    after: Optional[str] = None,
    before: Optional[str] = None,
    sender_phone_number: Optional[str] = None,
    chat_jid: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 20,
    page: int = 0,
    include_context: bool = True,
    context_before: int = 1,
    context_after: int = 1,
) -> Dict[str, Any]:
    # whatsapp_list_messages returns a formatted string when include_context is True
    messages_output = whatsapp_list_messages(
        after=after,
        before=before,
        sender_phone_number=sender_phone_number,
        chat_jid=chat_jid,
        query=query,
        limit=limit,
        page=page,
        include_context=include_context,
        context_before=context_before,
        context_after=context_after,
    )
    if isinstance(messages_output, str):
        return {"output": messages_output}
    # Fallback for potential list of dataclasses
    return {"messages": dataclass_to_dict(messages_output)}


@app.get("/chats")
def list_chats(
    query: Optional[str] = None,
    limit: int = 20,
    page: int = 0,
    include_last_message: bool = True,
    sort_by: str = "last_active",
) -> List[Dict[str, Any]]:
    chats = whatsapp_list_chats(
        query=query,
        limit=limit,
        page=page,
        include_last_message=include_last_message,
        sort_by=sort_by,
    )
    return dataclass_to_dict(chats)


@app.get("/chats/{chat_jid}")
def get_chat(chat_jid: str, include_last_message: bool = True) -> Optional[Dict[str, Any]]:
    chat = whatsapp_get_chat(chat_jid, include_last_message)
    return dataclass_to_dict(chat)


@app.get("/chats/direct-by-contact")
def get_direct_chat_by_contact(sender_phone_number: str) -> Optional[Dict[str, Any]]:
    chat = whatsapp_get_direct_chat_by_contact(sender_phone_number)
    return dataclass_to_dict(chat)


@app.get("/contacts/{jid}/chats")
def get_contact_chats(jid: str, limit: int = 20, page: int = 0) -> List[Dict[str, Any]]:
    chats = whatsapp_get_contact_chats(jid, limit, page)
    return dataclass_to_dict(chats)


@app.get("/contacts/{jid}/last-interaction")
def get_last_interaction(jid: str) -> Dict[str, Optional[str]]:
    message = whatsapp_get_last_interaction(jid)
    return {"output": message}


@app.get("/messages/{message_id}/context")
def get_message_context(message_id: str, before: int = 5, after: int = 5) -> Dict[str, Any]:
    context = whatsapp_get_message_context(message_id, before, after)
    return dataclass_to_dict(context)


@app.post("/messages/send-text")
def send_message(payload: SendTextRequest) -> Dict[str, Any]:
    success, status_message = whatsapp_send_message(payload.recipient, payload.message)
    return {"success": success, "message": status_message}


@app.post("/messages/send-file")
def send_file(payload: SendMediaRequest) -> Dict[str, Any]:
    success, status_message = whatsapp_send_file(payload.recipient, payload.media_path)
    return {"success": success, "message": status_message}


@app.post("/messages/send-audio")
def send_audio_message(payload: SendMediaRequest) -> Dict[str, Any]:
    success, status_message = whatsapp_send_audio_message(payload.recipient, payload.media_path)
    return {"success": success, "message": status_message}


@app.post("/media/download")
def download_media(payload: DownloadMediaRequest) -> Dict[str, Any]:
    file_path = whatsapp_download_media(payload.message_id, payload.chat_jid)
    if file_path:
        return {"success": True, "message": "Media downloaded successfully", "file_path": file_path}
    return {"success": False, "message": "Failed to download media"}


def _build_outgoing_headers(override_headers: Optional[Dict[str, str]]) -> Dict[str, str]:
    headers: Dict[str, str] = dict(DEFAULT_OUTGOING_HEADERS)
    if OUTGOING_WEBHOOK_SECRET:
        headers[OUTGOING_WEBHOOK_SECRET_HEADER] = OUTGOING_WEBHOOK_SECRET
    if override_headers:
        headers.update({k: v for k, v in override_headers.items() if isinstance(k, str) and isinstance(v, str)})
    # Ensure JSON content-type by default for POST
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"
    return headers


def _send_webhook_sync(
    url: str,
    method: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]],
    query: Optional[Dict[str, str]],
    timeout_seconds: float,
) -> None:
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        if method == "GET":
            client.get(url, params=query, headers=headers)
        else:
            client.post(url, params=query, headers=headers, json=(payload or {}))


@app.post("/webhook/trigger")
async def webhook_trigger(payload: WebhookTriggerRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Trigger a configurable outgoing webhook call.

    - If `target_url` is omitted, uses `OUTGOING_WEBHOOK_URL` from env.
    - Adds default headers from `OUTGOING_WEBHOOK_HEADERS` (JSON) and optional secret header.
    - When `async_mode=true` (default), dispatches in background and returns immediately.
    """
    url = payload.target_url or OUTGOING_WEBHOOK_URL
    if not url:
        raise HTTPException(status_code=400, detail="No target_url provided and OUTGOING_WEBHOOK_URL not configured")

    headers = _build_outgoing_headers(payload.headers)
    method = payload.method.upper()

    if payload.async_mode:
        background_tasks.add_task(
            _send_webhook_sync,
            url,
            method,
            headers,
            payload.payload,
            payload.query,
            payload.timeout_seconds,
        )
        return {"scheduled": True}

    # Synchronous dispatch: await result and return status
    try:
        async with httpx.AsyncClient(timeout=payload.timeout_seconds, follow_redirects=True) as client:
            if method == "GET":
                resp = await client.get(url, params=payload.query, headers=headers)
            else:
                resp = await client.post(url, params=payload.query, headers=headers, json=(payload.payload or {}))
        text_excerpt = (resp.text or "")[:1000]
        return {
            "scheduled": False,
            "status_code": resp.status_code,
            "ok": resp.is_success,
            "response_excerpt": text_excerpt,
        }
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Webhook request error: {str(e)}")


@app.post("/webhook/ingest", response_model=IngestResponse)
async def webhook_ingest(request: Request) -> IngestResponse:
    """Receive webhook events (e.g., from the Go bridge) and store briefly in memory.

    Requires the same `X-Webhook-Api-Key` header as other protected endpoints.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {"_raw": await request.body()}
    RECEIVED_EVENTS.append({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "headers": dict(request.headers),
        "body": payload,
    })
    return IngestResponse(received=True, stored_events=len(RECEIVED_EVENTS))


@app.get("/webhook/events")
def list_ingested_events(limit: int = 20) -> Dict[str, Any]:
    events = list(RECEIVED_EVENTS)[-max(0, min(limit, len(RECEIVED_EVENTS))):]
    return {"events": events}


# Local dev entrypoint (optional)
# Run with: uvicorn fastapi_app:app --reload --port 8000
