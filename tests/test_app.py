import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_tmp = tempfile.NamedTemporaryFile(delete=False)
_tmp.close()
os.environ["JARVIS_API_KEY"] = "test-secret-key"
os.environ["MACRODROID_OPEN_WHATSAPP_URL"] = "https://example.invalid/whatsapp"
os.environ["MACRODROID_OPEN_CAMERA_URL"] = "https://example.invalid/camera"
os.environ["MACRODROID_OPEN_INSTAGRAM_URL"] = "https://example.invalid/instagram"
os.environ["MACRODROID_OPEN_GMAIL_URL"] = "https://example.invalid/gmail"
os.environ["MACRODROID_OPEN_SETTINGS_URL"] = "https://example.invalid/settings"
os.environ["JARVIS_IDEMPOTENCY_DB"] = _tmp.name

import app
from fastapi.testclient import TestClient
client = TestClient(app.app)
AUTH = {"Authorization": "Bearer test-secret-key"}

def test_health_reports_actions_without_secrets():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert set(r.json()["configured_actions"]) == {
        "open_whatsapp", "open_camera", "open_instagram", "open_gmail", "open_settings"
    }
    assert "example.invalid" not in r.text

def test_requires_auth():
    r = client.post("/v1/actions/execute", json={"action":"open_whatsapp","request_id":"auth-test"})
    assert r.status_code == 401

def test_rejects_unallowlisted_action():
    r = client.post("/v1/actions/execute", headers=AUTH,
                    json={"action":"open_arbitrary_url","request_id":"bad-action"})
    assert r.status_code == 422

def test_missing_webhook_is_503(monkeypatch):
    monkeypatch.delenv("MACRODROID_OPEN_CAMERA_URL")
    r = client.post("/v1/actions/execute", headers=AUTH,
                    json={"action":"open_camera","request_id":"missing-hook"})
    assert r.status_code == 503

def test_request_id_cannot_be_reused_for_different_action():
    first = client.post("/v1/actions/execute", headers=AUTH,
                        json={"action":"open_whatsapp","request_id":"same-id"})
    # This test only checks conflict if first call can be sent; network is intentionally invalid,
    # so the request is reserved before it fails. Reuse must still not dispatch a second action.
    second = client.post("/v1/actions/execute", headers=AUTH,
                         json={"action":"open_camera","request_id":"same-id"})
    assert second.status_code == 409
