import re
from urllib.parse import urlparse, parse_qs

from .errors import TranscriptServiceError
from .models import TranscriptSegment, TranscriptResult, LanguageTrack

ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(value: str) -> str:
    value = (value or "").strip()
    if ID_RE.fullmatch(value):
        return value
    parsed = urlparse(value)
    host = parsed.hostname.lower() if parsed.hostname else ""
    candidate = None
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        else:
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2 and parts[0] in {"shorts", "embed"}:
                candidate = parts[1]
    elif host in {"youtu.be", "www.youtu.be"}:
        parts = [part for part in parsed.path.split("/") if part]
        candidate = parts[0] if parts else None
    if candidate and ID_RE.fullmatch(candidate):
        return candidate
    raise ValueError("INVALID_YOUTUBE_URL")


def _clean(text: str) -> str:
    return " ".join((text or "").split())


class YouTubeTranscriptProvider:
    def _api(self):
        from youtube_transcript_api import YouTubeTranscriptApi
        return YouTubeTranscriptApi()

    def _map_error(self, exc: Exception) -> TranscriptServiceError:
        mapping = {
            "TranscriptsDisabled": ("TRANSCRIPTS_DISABLED", "Video đã tắt phụ đề.", 404),
            "VideoUnavailable": ("VIDEO_UNAVAILABLE", "Video không khả dụng.", 404),
            "InvalidVideoId": ("INVALID_YOUTUBE_URL", "ID video YouTube không hợp lệ.", 400),
            "NoTranscriptFound": ("NO_TRANSCRIPT_FOUND", "Không tìm thấy transcript phù hợp.", 404),
            "RequestBlocked": ("YOUTUBE_REQUEST_BLOCKED", "YouTube đang chặn yêu cầu từ máy chủ/mạng này.", 503),
            "IpBlocked": ("YOUTUBE_IP_BLOCKED", "YouTube đang chặn địa chỉ IP hiện tại.", 503),
        }
        code, message, status = mapping.get(
            exc.__class__.__name__, ("UPSTREAM_ERROR", f"Lỗi khi truy cập YouTube: {exc}", 502)
        )
        return TranscriptServiceError(code, message, status)

    def _id(self, value: str) -> str:
        try:
            return extract_video_id(value)
        except ValueError as exc:
            raise TranscriptServiceError("INVALID_YOUTUBE_URL", "URL hoặc ID YouTube không hợp lệ.", 400) from exc

    def fetch(self, value: str, languages: list[str] | None = None) -> TranscriptResult:
        video_id = self._id(value)
        languages = languages or ["vi", "en"]
        try:
            tracks = self._api().list(video_id)
            track = tracks.find_transcript(languages)
            fetched = track.fetch()
            segments = []
            for item in fetched:
                text = _clean(item.text)
                if text:
                    segments.append(TranscriptSegment(text=text, start=float(item.start), duration=float(item.duration)))
            return TranscriptResult(
                video_id=video_id,
                language=track.language,
                language_code=track.language_code,
                is_generated=bool(track.is_generated),
                is_translatable=bool(track.is_translatable),
                segments=segments,
                text=" ".join(segment.text for segment in segments),
            )
        except TranscriptServiceError:
            raise
        except Exception as exc:
            raise self._map_error(exc) from exc

    def list_languages(self, value: str) -> list[LanguageTrack]:
        video_id = self._id(value)
        try:
            return [
                LanguageTrack(
                    language=track.language,
                    language_code=track.language_code,
                    is_generated=bool(track.is_generated),
                    is_translatable=bool(track.is_translatable),
                )
                for track in self._api().list(video_id)
            ]
        except Exception as exc:
            raise self._map_error(exc) from exc
