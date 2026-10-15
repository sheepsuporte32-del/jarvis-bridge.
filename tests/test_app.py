import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient

_tmp = tempfile.NamedTemporaryFile(delete=False)
_tmp.close()
os.environ['JARVIS_API_KEY'] = 'test-secret-key'
os.environ['MACRODROID_OPEN_WHATSAPP_URL'] = 'https://example.invalid/hook'
os.environ['JARVIS_IDEMPOTENCY_DB'] = _tmp.name
import app
client = TestClient(app.app)

def test_health():
    r = client.get('/health')
    assert r.status_code == 200 and r.json()['status'] == 'ok'

def test_requires_auth():
    r = client.post('/v1/actions/execute', json={'action':'open_whatsapp','confirmation':True,'request_id':'test-1'})
    assert r.status_code == 401

def test_rejects_unallowlisted_action():
    r = client.post('/v1/actions/execute', headers={'Authorization':'Bearer test-secret-key'},
                    json={'action':'open_camera','confirmation':True,'request_id':'test-2'})
    assert r.status_code == 422
