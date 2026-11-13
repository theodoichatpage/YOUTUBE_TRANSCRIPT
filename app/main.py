from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .errors import TranscriptServiceError
from .media import MediaJobs
from .models import LanguageTrack, MediaJobRequest, TranscriptRequest, TranscriptResult
from .youtube import YouTubeTranscriptProvider

SERVICE_VERSION = "0.2.0"

app = FastAPI(title="YOUTUBE_TRANSCRIPT", version=SERVICE_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://video-image-studio.vercel.app",
        "https://video-image-studio-git-phase3-manager-presence-image-studio1.vercel.app",
        "https://video-image-studio-git-phase3-identity-monitor-preview-image-studio1.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
provider = YouTubeTranscriptProvider()
media_jobs = MediaJobs()


@app.exception_handler(TranscriptServiceError)
def transcript_error(_: Request, exc: TranscriptServiceError):
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


@app.get("/health")
def health():
    return {"status": "ok", "service": "YOUTUBE_TRANSCRIPT", "version": SERVICE_VERSION, "features": ["youtube_captions", "media_link"]}


@app.post("/transcript", response_model=TranscriptResult)
def transcript(body: TranscriptRequest):
    return provider.fetch(body.url or body.video_id or "", body.languages)


@app.get("/transcript/{video_id}/languages", response_model=list[LanguageTrack])
def languages(video_id: str):
    return provider.list_languages(video_id)



@app.post("/media/jobs", status_code=202)
def start_media_job(body: MediaJobRequest):
    """Any video link: download the audio and turn speech into text in the background."""
    return media_jobs.submit(body.url, body.language)


@app.get("/media/jobs/{job_id}")
def media_job(job_id: str):
    return media_jobs.get(job_id)
