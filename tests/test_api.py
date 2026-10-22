from fastapi.testclient import TestClient
import app.main as main
from app.main import app
from app.models import LanguageTrack, TranscriptResult, TranscriptSegment


class FakeProvider:
    def fetch(self, value, languages):
        return TranscriptResult(video_id="yTwvX2RJ80Q", language="Vietnamese", language_code="vi", is_generated=False, is_translatable=True, segments=[TranscriptSegment(text="Xin chào", start=0, duration=1)], text="Xin chào")

    def list_languages(self, value):
        return [LanguageTrack(language="Vietnamese", language_code="vi", is_generated=False, is_translatable=True)]


def test_health():
    assert TestClient(app).get("/health").status_code == 200


def test_transcript_contract(monkeypatch):
    monkeypatch.setattr(main, "provider", FakeProvider())
    response = TestClient(app).post("/transcript", json={"url": "https://youtu.be/yTwvX2RJ80Q", "languages": ["vi", "en"]})
    assert response.status_code == 200
    assert response.json()["language_code"] == "vi"
    assert response.json()["segments"][0]["start"] == 0


def test_languages_contract(monkeypatch):
    monkeypatch.setattr(main, "provider", FakeProvider())
    response = TestClient(app).get("/transcript/yTwvX2RJ80Q/languages")
    assert response.status_code == 200
    assert response.json()[0]["language_code"] == "vi"


def test_requires_exactly_one_source():
    assert TestClient(app).post("/transcript", json={"languages": ["vi"]}).status_code == 422
