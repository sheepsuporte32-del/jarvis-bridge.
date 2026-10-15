import os
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

VERSION = "1.1.0"
app = FastAPI(
    title="JARVIS Bridge",
    version=VERSION,
    description="Authenticated allowlisted bridge to preconfigured MacroDroid webhooks.",
)
JARVIS_API_KEY = os.getenv("JARVIS_API_KEY", "")
bearer_scheme = HTTPBearer(auto_error=False)
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "8"))
IDEMPOTENCY_DB = os.getenv("JARVIS_IDEMPOTENCY_DB", "/data/jarvis.sqlite3")

# Each action maps only to a server-side secret. Clients can never submit arbitrary URLs.
ACTION_WEBHOOK_ENVS = {
    "open_whatsapp": "MACRODROID_OPEN_WHATSAPP_URL",
    "open_camera": "MACRODROID_OPEN_CAMERA_URL",
    "open_instagram": "MACRODROID_OPEN_INSTAGRAM_URL",
    "open_gmail": "MACRODROID_OPEN_GMAIL_URL",
    "open_settings": "MACRODROID_OPEN_SETTINGS_URL",
}
ActionName = Literal["open_whatsapp", "open_camera", "open_instagram", "open_gmail", "open_settings"]

class ActionRequest(BaseModel):
    action: ActionName
    # Legacy clients may continue sending confirmation=true. The allowlisted commands
    # are treated as pre-authorized by the owner; no per-launch confirmation is needed.
    confirmation: Literal[True] | None = None
    request_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")

class ActionResult(BaseModel):
    status: Literal["request_sent", "already_processed"]
    action: str
    request_id: str
    detail: str

@contextmanager
def db_connection():
    path = Path(IDEMPOTENCY_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS requests (request_id TEXT PRIMARY KEY, action TEXT NOT NULL, status TEXT NOT NULL)")
        conn.commit()
        yield conn
    finally:
        conn.close()

def authorize(credentials: HTTPAuthorizationCredentials | None) -> None:
    if not JARVIS_API_KEY:
        raise HTTPException(status_code=503, detail="Server not configured: JARVIS_API_KEY is missing.")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    if not secrets.compare_digest(credentials.credentials.strip(), JARVIS_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid bearer token.")

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"status": "ok", "service": "jarvis-bridge", "health": "/health"}

@app.get("/health")
async def health():
    configured = [action for action, env_name in ACTION_WEBHOOK_ENVS.items() if os.getenv(env_name, "").strip()]
    return {"status": "ok", "service": "jarvis-bridge", "version": VERSION,
            "configured_actions": configured}

@app.post("/v1/actions/execute", response_model=ActionResult)
async def execute_action(payload: ActionRequest, credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)):
    authorize(credentials)
    env_name = ACTION_WEBHOOK_ENVS[payload.action]
    webhook_url = os.getenv(env_name, "").strip()
    if not webhook_url:
        raise HTTPException(status_code=503, detail=f"Action is not configured on the server: {payload.action}.")

    # Reserve the request ID before the external call to prevent duplicate execution.
    try:
        with db_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT action, status FROM requests WHERE request_id = ?", (payload.request_id,)).fetchone()
            if existing:
                conn.commit()
                if existing[0] != payload.action:
                    raise HTTPException(status_code=409, detail="request_id was already used for a different action.")
                return ActionResult(status="already_processed", action=payload.action, request_id=payload.request_id,
                                    detail="Request ID was already processed; no second action was sent.")
            conn.execute("INSERT INTO requests(request_id, action, status) VALUES (?, ?, ?)",
                         (payload.request_id, payload.action, "pending"))
            conn.commit()
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail="Idempotency storage unavailable.")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False) as client:
            response = await client.get(webhook_url)
            response.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="MacroDroid webhook timed out. Check the phone before retrying.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="MacroDroid webhook request failed.")

    with db_connection() as conn:
        conn.execute("UPDATE requests SET status = ? WHERE request_id = ?", ("sent", payload.request_id))
        conn.commit()

    return ActionResult(status="request_sent", action=payload.action, request_id=payload.request_id,
                        detail="MacroDroid webhook responded successfully; this does not prove the app visibly opened.")
