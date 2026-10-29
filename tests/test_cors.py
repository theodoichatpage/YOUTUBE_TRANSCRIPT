import pytest
from fastapi.testclient import TestClient
import app.main as main
from app.main import app
from tests.test_api import FakeProvider

ORIGINS = [
    'https://video-image-studio.vercel.app',
    'https://video-image-studio-git-phase3-manager-presence-image-studio1.vercel.app',
    'https://video-image-studio-git-phase3-identity-monitor-preview-image-studio1.vercel.app',
    'http://localhost:5173',
    'http://127.0.0.1:5173',
]

@pytest.mark.parametrize('origin', ORIGINS)
def test_studio_preflight_and_transcript(origin, monkeypatch):
    monkeypatch.setattr(main, 'provider', FakeProvider())
    client = TestClient(app)
    response = client.options('/transcript', headers={
        'Origin': origin,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type',
    })
    assert response.status_code == 200, response.text
    assert response.headers['access-control-allow-origin'] == origin
    result = client.post('/transcript', headers={'Origin': origin}, json={
        'url': 'https://www.youtube.com/watch?v=6q9bXFVMaqc',
        'languages': ['vi', 'en'],
    })
    assert result.status_code == 200
    assert result.json()['text'] == 'Xin chào'
    assert result.headers['access-control-allow-origin'] == origin
    health = client.get('/health', headers={'Origin': origin})
    assert health.headers['access-control-allow-origin'] == origin

@pytest.mark.parametrize('origin', [
    'https://unrelated.vercel.app',
    'https://video-image-studio.vercel.app.attacker.example',
    'https://attacker.example',
])
def test_unrelated_origins_remain_blocked(origin):
    response = TestClient(app).options('/transcript', headers={
        'Origin': origin,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type',
    })
    assert response.status_code == 400
    assert 'access-control-allow-origin' not in response.headers
