from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .errors import TranscriptServiceError
from .models import LanguageTrack, TranscriptRequest, TranscriptResult
from .youtube import YouTubeTranscriptProvider

app = FastAPI(title="YOUTUBE_TRANSCRIPT", version="0.1.0")
provider = YouTubeTranscriptProvider()


@app.exception_handler(TranscriptServiceError)
def transcript_error(_: Request, exc: TranscriptServiceError):
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


@app.get("/health")
def health():
    return {"status": "ok", "service": "YOUTUBE_TRANSCRIPT", "version": "0.1.0"}


@app.post("/transcript", response_model=TranscriptResult)
def transcript(body: TranscriptRequest):
    return provider.fetch(body.url or body.video_id or "", body.languages)


@app.get("/transcript/{video_id}/languages", response_model=list[LanguageTrack])
def languages(video_id: str):
    return provider.list_languages(video_id)
