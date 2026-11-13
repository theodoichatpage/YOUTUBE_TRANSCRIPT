"""Transcript from any video link (Facebook, TikTok, YouTube without captions...).

The audio is downloaded with yt-dlp and turned into text with faster-whisper on
this machine. Speech-to-text takes minutes on a CPU, so each link is a job that
runs in the background; the caller polls it for progress and the result.
"""

import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from urllib.parse import urlparse

from .errors import TranscriptServiceError

MODEL_NAME = os.environ.get("TRANSCRIPT_WHISPER_MODEL", "large-v3-turbo")
MAX_SECONDS = float(os.environ.get("TRANSCRIPT_MAX_SECONDS", str(3 * 3600)))
KEEP_JOBS = 30
# Facebook titles start with "7.2K views · 63 reactions | "
STATS_PREFIX = re.compile(r"^\s*[\d.,]+\s*[KMB]?\s+views?\b[^|]*\|\s*", re.IGNORECASE)

STAGE_TEXT = {
    "queued": "Đang chờ lượt",
    "downloading": "Đang tải âm thanh từ link",
    "loading_model": "Đang nạp model nhận giọng nói (lần đầu tải ~1,6 GB)",
    "transcribing": "Đang nhận giọng nói",
    "done": "Xong",
    "error": "Lỗi",
}


def check_url(value: str) -> str:
    value = (value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise TranscriptServiceError("INVALID_MEDIA_URL", "Link không hợp lệ (cần http:// hoặc https://).", 400)
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"} or host.endswith(".local"):
        raise TranscriptServiceError("INVALID_MEDIA_URL", "Link phải là trang video trên mạng.", 400)
    return value


def _download_error(exc: Exception) -> TranscriptServiceError:
    text = str(exc)
    low = text.lower()
    if "login" in low or "private" in low or "cookies" in low or "registered users" in low:
        return TranscriptServiceError(
            "MEDIA_LOGIN_REQUIRED",
            "Video này cần đăng nhập hoặc không công khai, Engine không tải được. Hãy dùng link video công khai.",
            403,
        )
    if "unsupported url" in low:
        return TranscriptServiceError("MEDIA_UNSUPPORTED", "Trang này không có video mà Engine nhận ra.", 400)
    return TranscriptServiceError("MEDIA_DOWNLOAD_FAILED", f"Không tải được video: {text[-300:]}", 502)


def clean_title(title: str) -> str:
    return STATS_PREFIX.sub("", title).strip()


class YtDlpWhisper:
    """Real downloader and speech-to-text. Tests swap this for a fake."""

    def __init__(self):
        self._model = None
        self._model_lock = threading.Lock()

    def download(self, url: str, folder: str, progress) -> dict:
        import yt_dlp

        def hook(state):
            if state.get("status") == "downloading":
                total = state.get("total_bytes") or state.get("total_bytes_estimate") or 0
                if total:
                    progress(min(1.0, state.get("downloaded_bytes", 0) / total))

        options = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(folder, "media.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [hook],
            "match_filter": yt_dlp.utils.match_filter_func(f"duration <=? {int(MAX_SECONDS)}"),
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as exc:
            raise _download_error(exc) from exc
        if info.get("_type") == "playlist":
            entries = [entry for entry in info.get("entries") or [] if entry]
            if not entries:
                raise TranscriptServiceError("MEDIA_UNSUPPORTED", "Link không chứa video.", 400)
            info = entries[0]
        files = [name for name in os.listdir(folder) if name.startswith("media.")]
        if not files:
            duration = info.get("duration")
            if duration and duration > MAX_SECONDS:
                raise TranscriptServiceError(
                    "MEDIA_TOO_LONG", f"Video dài {int(duration // 60)} phút, vượt giới hạn {int(MAX_SECONDS // 60)} phút.", 400
                )
            raise TranscriptServiceError("MEDIA_DOWNLOAD_FAILED", "Không tải được âm thanh của video.", 502)
        return {
            "path": os.path.join(folder, files[0]),
            "id": f"{info.get('extractor_key') or 'media'}:{info.get('id') or ''}".lower(),
            "title": clean_title(info.get("title") or ""),
            "thumbnail": info.get("thumbnail") or "",
            "duration": float(info.get("duration") or 0),
            "uploader": info.get("uploader") or "",
        }

    def _load(self, loading):
        with self._model_lock:
            if self._model is None:
                loading()
                from faster_whisper import WhisperModel

                self._model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
            return self._model

    def transcribe(self, path: str, language: str | None, loading, progress):
        model = self._load(loading)
        progress(0.0)
        segments, info = model.transcribe(path, language=language or None, vad_filter=True, beam_size=5)
        total = float(info.duration or 0)
        out = []
        for segment in segments:
            text = " ".join((segment.text or "").split())
            if text:
                out.append({"text": text, "start": round(float(segment.start), 2), "duration": round(float(segment.end - segment.start), 2)})
            if total:
                progress(min(1.0, float(segment.end) / total))
        return out, info.language or (language or ""), total


class MediaJobs:
    """One job at a time (the CPU is the limit); the same link is not done twice."""

    def __init__(self, backend=None):
        self.backend = backend or YtDlpWhisper()
        self.jobs: dict[str, dict] = {}
        self.order: list[str] = []
        self.lock = threading.Lock()
        self.wake = threading.Condition(self.lock)
        self.worker = None

    def _public(self, job: dict) -> dict:
        data = {key: job[key] for key in ("id", "url", "language", "status", "progress", "message", "created_at", "updated_at")}
        data["result"] = job.get("result")
        data["error"] = job.get("error")
        return data

    def submit(self, url: str, language: str | None) -> dict:
        url = check_url(url)
        language = (language or "").strip() or None
        with self.lock:
            for job_id in reversed(self.order):
                job = self.jobs[job_id]
                if job["url"] == url and job["language"] == language and job["status"] != "error":
                    return self._public(job)
            now = time.time()
            job = {
                "id": uuid.uuid4().hex[:12], "url": url, "language": language, "status": "queued", "progress": 0.0,
                "message": STAGE_TEXT["queued"], "created_at": now, "updated_at": now,
            }
            self.jobs[job["id"]] = job
            self.order.append(job["id"])
            while len(self.order) > KEEP_JOBS:
                old = self.order[0]
                if self.jobs[old]["status"] in {"queued", "downloading", "loading_model", "transcribing"}:
                    break
                self.order.pop(0)
                self.jobs.pop(old, None)
            if self.worker is None or not self.worker.is_alive():
                self.worker = threading.Thread(target=self._run, name="media-transcript", daemon=True)
                self.worker.start()
            self.wake.notify_all()
            return self._public(job)

    def get(self, job_id: str) -> dict:
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                raise TranscriptServiceError("JOB_NOT_FOUND", "Không tìm thấy việc lấy transcript này (Engine có thể vừa khởi động lại).", 404)
            return self._public(job)

    def _set(self, job: dict, status: str | None = None, progress: float | None = None, **extra):
        with self.lock:
            if status:
                job["status"] = status
                job["message"] = STAGE_TEXT[status]
            if progress is not None:
                job["progress"] = round(max(job["progress"], progress), 3)
            job.update(extra)
            job["updated_at"] = time.time()

    def _next(self):
        with self.lock:
            while True:
                for job_id in self.order:
                    if self.jobs[job_id]["status"] == "queued":
                        return self.jobs[job_id]
                if not self.wake.wait(timeout=300):
                    self.worker = None
                    return None

    def _run(self):
        while True:
            job = self._next()
            if job is None:
                return
            self._work(job)

    def _work(self, job: dict):
        folder = tempfile.mkdtemp(prefix="vis_media_")
        try:
            self._set(job, "downloading", 0.0)
            media = self.backend.download(job["url"], folder, lambda f: self._set(job, progress=0.15 * f))
            self._set(job, progress=0.15, title=media["title"])
            segments, language, total = self.backend.transcribe(
                media["path"], job["language"],
                lambda: self._set(job, "loading_model"),
                lambda f: self._set(job, "transcribing", 0.15 + 0.85 * f),
            )
            if not segments:
                raise TranscriptServiceError("NO_SPEECH", "Không nghe thấy lời nói nào trong video.", 404)
            result = {
                "video_id": media["id"], "title": media["title"], "thumbnail": media["thumbnail"],
                "duration": media["duration"] or total, "language": language, "language_code": language,
                "is_generated": True, "is_translatable": False, "source": "speech",
                "segments": segments, "text": " ".join(item["text"] for item in segments),
            }
            self._set(job, "done", 1.0, result=result)
        except TranscriptServiceError as exc:
            self._set(job, "error", error={"code": exc.code, "message": exc.message})
        except Exception as exc:  # keep the worker alive whatever happens
            self._set(job, "error", error={"code": "MEDIA_FAILED", "message": f"Lỗi khi nhận giọng nói: {exc}"})
        finally:
            shutil.rmtree(folder, ignore_errors=True)
