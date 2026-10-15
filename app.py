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

app = FastAPI(
    title="JARVIS Bridge",
    version="1.0.0",
    description="Authenticated, allowlisted bridge from ChatGPT Actions or an Alexa skill to approved MacroDroid webhooks.",
)
JARVIS_API_KEY = os.getenv("JARVIS_API_KEY", "")
bearer_scheme = HTTPBearer(auto_error=False)
OPEN_WHATSAPP_URL = os.getenv("MACRODROID_OPEN_WHATSAPP_URL", "")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "8"))
IDEMPOTENCY_DB = os.getenv("JARVIS_IDEMPOTENCY_DB", "/data/jarvis.sqlite3")

class ActionRequest(BaseModel):
    action: Literal["open_whatsapp"]
    confirmation: Literal[True]
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
    supplied = credentials.credentials.strip()
    if not secrets.compare_digest(supplied, JARVIS_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid bearer token.")

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"status": "ok", "service": "jarvis-bridge", "health": "/health"}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "jarvis-bridge", "version": "1.0.0"}

@app.post("/v1/actions/execute", response_model=ActionResult)
async def execute_action(payload: ActionRequest, credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)):
    authorize(credentials)
    if not payload.confirmation:
        raise HTTPException(status_code=403, detail="Explicit confirmation is required.")
    if not OPEN_WHATSAPP_URL:
        raise HTTPException(status_code=503, detail="MacroDroid webhook is not configured on the server.")

    # Reserve the request ID before making the external call. Repeated calls won't repeat the action.
    try:
        with db_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT status FROM requests WHERE request_id = ?", (payload.request_id,)).fetchone()
            if existing:
                conn.commit()
                return ActionResult(status="already_processed", action=payload.action, request_id=payload.request_id,
                                    detail="This request ID was already processed; no second action was sent.")
            conn.execute("INSERT INTO requests(request_id, action, status) VALUES (?, ?, ?)",
                         (payload.request_id, payload.action, "pending"))
            conn.commit()
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail="Idempotency storage unavailable.")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False) as client:
            response = await client.get(OPEN_WHATSAPP_URL)
            response.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="MacroDroid webhook timed out. Use a new request_id only after checking the phone.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="MacroDroid webhook request failed.")
    else:
        with db_connection() as conn:
            conn.execute("UPDATE requests SET status = ? WHERE request_id = ?", ("sent", payload.request_id))
            conn.commit()

    return ActionResult(status="request_sent", action=payload.action, request_id=payload.request_id,
                        detail="Webhook responded successfully; confirm on the phone that WhatsApp opened.")
