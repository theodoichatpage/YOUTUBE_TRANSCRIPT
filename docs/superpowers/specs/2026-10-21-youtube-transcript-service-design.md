# YOUTUBE_TRANSCRIPT Service — Design Specification

Date: 2026-10-21
Status: Proposed for user review

## Goal

Create a standalone transcript service for VIDEO IMAGE STUDIO using `jdepoix/youtube-transcript-api` as the transcript extraction core. The service must accept a YouTube URL or video ID, retrieve available manual or automatically generated captions, normalize them, and return structured JSON that VIDEO IMAGE STUDIO can consume.

## Constraints

- Repository: `theodoichatpage/YOUTUBE_TRANSCRIPT`
- Python service using FastAPI.
- Core dependency: `youtube-transcript-api`.
- No paid transcript API dependency.
- Must support Vietnamese and other available YouTube caption languages.
- Must preserve timestamps (`start`, `duration`) and provide joined plain text.
- Must clearly distinguish manual vs automatically generated captions.
- Must not pretend a video has no transcript when the real failure is YouTube/IP blocking.
- Architecture must leave a clean extension point for proxy support or local speech-to-text later.

## Architecture

### API layer

FastAPI application exposing:

- `GET /health`
  - Returns service status and version.

- `POST /transcript`
  - Input:
    - `url` or `video_id`
    - optional `languages`, ordered by preference, e.g. `["vi", "en"]`
  - Output:
    - `video_id`
    - `language`
    - `language_code`
    - `is_generated`
    - `is_translatable`
    - `segments[]` containing `text`, `start`, `duration`
    - `text` containing the normalized full transcript

- `GET /transcript/{video_id}/languages`
  - Lists available caption tracks and their metadata so the frontend can offer a language selector.

### Transcript provider

A provider module wraps `youtube-transcript-api` rather than spreading library calls through route handlers.

Responsibilities:

1. Parse and validate YouTube video IDs from common URL formats.
2. Query available transcript tracks.
3. Prefer requested languages in user-defined order.
4. Within the same requested language, prefer manually created captions over generated captions, following the upstream library's default behavior.
5. Fetch caption snippets.
6. Normalize whitespace without destroying transcript order or timestamps.
7. Convert upstream exceptions into stable application error codes.

This provider boundary allows the extraction implementation to be replaced later without changing VIDEO IMAGE STUDIO's API contract.

## Error handling

The service returns explicit error categories instead of one generic “no transcript” response:

- `INVALID_YOUTUBE_URL`
- `VIDEO_UNAVAILABLE`
- `TRANSCRIPTS_DISABLED`
- `NO_TRANSCRIPT_FOUND`
- `YOUTUBE_REQUEST_BLOCKED`
- `YOUTUBE_IP_BLOCKED`
- `RATE_LIMITED`
- `UPSTREAM_ERROR`

HTTP responses include a human-readable Vietnamese message plus a machine-readable code.

IP blocking is intentionally separate from missing captions. If the machine running this service is blocked by YouTube, VIDEO IMAGE STUDIO must show that infrastructure error rather than claiming the video has no subtitles.

## Deployment model

Primary intended use is as a local/self-hosted service reachable by VIDEO IMAGE STUDIO. This avoids relying on Vercel's cloud IP for YouTube caption extraction.

Initial implementation does not require a proxy. A future provider configuration can add rotating residential proxy credentials if the host IP itself becomes blocked.

Docker support will be included for portable deployment, but Docker is not required to run the service locally.

## VIDEO IMAGE STUDIO integration contract

VIDEO IMAGE STUDIO will later call this service first for transcript retrieval. The current Vercel transcript endpoint can remain temporarily as a fallback until the new service is verified.

The service itself will not contain Mindmap or script-rewriting logic. Those remain responsibilities of VIDEO IMAGE STUDIO. This repository has one job: reliably obtain and normalize YouTube transcripts.

## Project structure

```text
YOUTUBE_TRANSCRIPT/
  app/
    __init__.py
    main.py
    models.py
    errors.py
    youtube.py
  tests/
    test_video_id.py
    test_provider.py
    test_api.py
  requirements.txt
  Dockerfile
  .gitignore
  README.md
```

## Testing

Tests will cover:

- YouTube URL/video ID parsing (`watch`, `youtu.be`, `shorts`, `embed`).
- Language preference and manual/generated selection.
- Transcript normalization.
- Stable mapping of upstream exceptions to API errors.
- `/health` and `/transcript` response contracts.

Provider/network behavior will be mocked in unit/API tests so tests do not depend on YouTube availability. A manual smoke-test command will be documented for testing a real video such as `yTwvX2RJ80Q` on the actual host machine.

## Success criteria

The implementation is considered functionally successful when:

1. The service starts locally with documented commands.
2. `/health` responds successfully.
3. A public YouTube video with available captions can return transcript segments and full text when run from an unblocked network.
4. Vietnamese captions can be selected when available.
5. Cloud/IP blocking is reported distinctly from “no transcript”.
6. Automated tests validate the API contract and provider behavior.
