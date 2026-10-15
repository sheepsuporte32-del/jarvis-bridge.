import os
import sys
import tempfile
from pathlib import Path

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
AUTH = {"Authorization": "Bearer test-secret-key"}
client = TestClient(app.app)

class FakeResponse:
    def raise_for_status(self):
        return None

class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False
    async def get(self, url):
        assert url.startswith("https://example.invalid/")
        return FakeResponse()

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

def test_each_allowed_action_routes_to_its_private_webhook(monkeypatch):
    monkeypatch.setattr(app.httpx, "AsyncClient", FakeAsyncClient)
    for action in ("open_whatsapp", "open_camera", "open_instagram", "open_gmail", "open_settings"):
        r = client.post("/v1/actions/execute", headers=AUTH,
                        json={"action": action, "request_id": f"route-{action}"})
        assert r.status_code == 200, r.text
        assert r.json()["action"] == action
        assert r.json()["status"] == "request_sent"

def test_duplicate_request_is_not_dispatched_twice(monkeypatch):
    monkeypatch.setattr(app.httpx, "AsyncClient", FakeAsyncClient)
    body = {"action": "open_whatsapp", "request_id": "duplicate-test"}
    first = client.post("/v1/actions/execute", headers=AUTH, json=body)
    second = client.post("/v1/actions/execute", headers=AUTH, json=body)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "already_processed"

def test_request_id_cannot_be_reused_for_different_action(monkeypatch):
    monkeypatch.setattr(app.httpx, "AsyncClient", FakeAsyncClient)
    first = client.post("/v1/actions/execute", headers=AUTH,
                        json={"action":"open_whatsapp","request_id":"same-id"})
    second = client.post("/v1/actions/execute", headers=AUTH,
                         json={"action":"open_camera","request_id":"same-id"})
    assert first.status_code == 200
    assert second.status_code == 409
