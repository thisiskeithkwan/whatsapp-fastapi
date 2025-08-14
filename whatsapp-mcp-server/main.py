from typing import Any, Dict, List, Optional
from dataclasses import asdict, is_dataclass
import os

from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

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


# Local dev entrypoint (optional)
# Run with: uvicorn fastapi_app:app --reload --port 8000
