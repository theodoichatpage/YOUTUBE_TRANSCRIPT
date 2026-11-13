import os
import threading
import time

from fastapi.testclient import TestClient

import app.main as main
from app.errors import TranscriptServiceError
from app.main import app
from app.media import MediaJobs, clean_title


class FakeBackend:
    def __init__(self, fail=None, segments=None, gate=None):
        self.fail = fail
        self.segments = segments if segments is not None else [{"text": "Xin chào", "start": 0.0, "duration": 1.5}, {"text": "các bạn", "start": 1.5, "duration": 1.0}]
        self.gate = gate
        self.downloads = 0

    def download(self, url, folder, progress):
        self.downloads += 1
        if self.gate:
            self.gate.wait(5)
        if self.fail:
            raise self.fail
        progress(1.0)
        path = os.path.join(folder, "media.m4a")
        open(path, "wb").close()
        return {"path": path, "id": "facebook:1415564201644332", "title": "Reel", "thumbnail": "https://x/t.jpg", "duration": 2.5, "uploader": "A"}

    def transcribe(self, path, language, loading, progress):
        assert os.path.exists(path)
        loading()
        progress(0.5)
        progress(1.0)
        return self.segments, language or "vi", 2.5


def wait_done(jobs, job_id):
    for _ in range(200):
        job = jobs.get(job_id)
        if job["status"] in {"done", "error"}:
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_job_turns_speech_into_transcript_and_cleans_up():
    jobs = MediaJobs(FakeBackend())
    job = jobs.submit("https://www.facebook.com/reel/1415564201644332", "vi")
    done = wait_done(jobs, job["id"])
    assert done["status"] == "done" and done["progress"] == 1.0
    result = done["result"]
    assert result["text"] == "Xin chào các bạn"
    assert result["video_id"] == "facebook:1415564201644332"
    assert result["is_generated"] is True and result["source"] == "speech"
    assert result["segments"][1]["start"] == 1.5


def test_same_link_is_not_downloaded_twice():
    backend = FakeBackend()
    jobs = MediaJobs(backend)
    first = jobs.submit("https://www.facebook.com/reel/1", "vi")
    wait_done(jobs, first["id"])
    again = jobs.submit("https://www.facebook.com/reel/1", "vi")
    assert again["id"] == first["id"] and backend.downloads == 1


def test_failed_link_reports_reason_and_can_be_retried():
    backend = FakeBackend(fail=TranscriptServiceError("MEDIA_LOGIN_REQUIRED", "cần đăng nhập", 403))
    jobs = MediaJobs(backend)
    job = wait_done(jobs, jobs.submit("https://www.facebook.com/reel/2", "vi")["id"])
    assert job["status"] == "error" and job["error"]["code"] == "MEDIA_LOGIN_REQUIRED"
    backend.fail = None
    retry = jobs.submit("https://www.facebook.com/reel/2", "vi")
    assert retry["id"] != job["id"]
    assert wait_done(jobs, retry["id"])["status"] == "done"


def test_unexpected_error_keeps_worker_alive():
    backend = FakeBackend(fail=RuntimeError("boom"))
    jobs = MediaJobs(backend)
    assert wait_done(jobs, jobs.submit("https://a.example/v/1", None)["id"])["error"]["code"] == "MEDIA_FAILED"
    backend.fail = None
    assert wait_done(jobs, jobs.submit("https://a.example/v/2", None)["id"])["status"] == "done"


def test_no_speech_is_an_error():
    jobs = MediaJobs(FakeBackend(segments=[]))
    assert wait_done(jobs, jobs.submit("https://a.example/v/3", "vi")["id"])["error"]["code"] == "NO_SPEECH"


def test_jobs_run_one_at_a_time_in_order():
    gate = threading.Event()
    jobs = MediaJobs(FakeBackend(gate=gate))
    a = jobs.submit("https://a.example/v/a", "vi")
    b = jobs.submit("https://a.example/v/b", "vi")
    time.sleep(0.1)
    assert jobs.get(b["id"])["status"] == "queued"
    gate.set()
    assert wait_done(jobs, a["id"])["status"] == "done"
    assert wait_done(jobs, b["id"])["status"] == "done"


def test_api_contract(monkeypatch):
    monkeypatch.setattr(main, "media_jobs", MediaJobs(FakeBackend()))
    client = TestClient(app)
    health = client.get("/health").json()
    assert "media_link" in health["features"]
    started = client.post("/media/jobs", json={"url": "https://www.facebook.com/reel/1415564201644332", "language": "vi"})
    assert started.status_code == 202
    job_id = started.json()["id"]
    for _ in range(200):
        body = client.get(f"/media/jobs/{job_id}").json()
        if body["status"] == "done":
            break
        time.sleep(0.02)
    assert body["result"]["text"] == "Xin chào các bạn"
    assert client.get("/media/jobs/nope").status_code == 404


def test_rejects_non_web_links(monkeypatch):
    monkeypatch.setattr(main, "media_jobs", MediaJobs(FakeBackend()))
    client = TestClient(app)
    assert client.post("/media/jobs", json={"url": "file:///C:/x.mp4"}).json()["error"]["code"] == "INVALID_MEDIA_URL"
    assert client.post("/media/jobs", json={"url": "http://127.0.0.1:8765/api"}).status_code == 400


def test_facebook_title_drops_view_counts():
    assert clean_title("7.2K views · 63 reactions | Mẹ không hề dữ | Từng Bước Con Đi") == "Mẹ không hề dữ | Từng Bước Con Đi"
    assert clean_title("Video hay | Kênh A") == "Video hay | Kênh A"


def test_stop_ends_running_job_and_frees_the_queue():
    gate = threading.Event()
    jobs = MediaJobs(FakeBackend(gate=gate))
    a = jobs.submit("https://a.example/v/stop", "vi")
    b = jobs.submit("https://a.example/v/next", "vi")
    time.sleep(0.1)
    assert jobs.cancel(b["id"])["status"] == "cancelled"  # a queued job stops at once
    jobs.cancel(a["id"])
    gate.set()
    assert wait_done_or(jobs, a["id"])["status"] == "cancelled"
    again = jobs.submit("https://a.example/v/stop", "vi")
    assert again["id"] != a["id"], "a stopped link starts fresh when asked again"
    assert wait_done(jobs, again["id"])["status"] == "done"


def wait_done_or(jobs, job_id):
    for _ in range(200):
        job = jobs.get(job_id)
        if job["status"] in {"done", "error", "cancelled"}:
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_cancel_api(monkeypatch):
    monkeypatch.setattr(main, "media_jobs", MediaJobs(FakeBackend(gate=threading.Event())))
    client = TestClient(app)
    job_id = client.post("/media/jobs", json={"url": "https://a.example/v/x"}).json()["id"]
    assert client.delete(f"/media/jobs/{job_id}").status_code == 200
    assert client.delete("/media/jobs/nope").status_code == 404
