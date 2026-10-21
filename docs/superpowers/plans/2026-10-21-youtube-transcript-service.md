# YOUTUBE_TRANSCRIPT Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone FastAPI service that retrieves and normalizes YouTube captions using `youtube-transcript-api` for VIDEO IMAGE STUDIO.

**Architecture:** A thin FastAPI API delegates all YouTube behavior to a focused provider module. The provider parses video IDs, selects transcript tracks by language preference, normalizes snippets, and maps upstream failures to stable service error codes. The service is designed for local/self-hosted execution so transcript requests do not originate from Vercel cloud IPs.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, youtube-transcript-api 1.2.x, Pydantic, pytest, FastAPI TestClient, Docker.

**Spec:** `docs/superpowers/specs/2026-10-21-youtube-transcript-service-design.md`

## Global Constraints

- Repository: `theodoichatpage/YOUTUBE_TRANSCRIPT`.
- No paid transcript API dependency.
- Support manual and automatically generated YouTube captions.
- Preserve `text`, `start`, and `duration` for every transcript segment.
- Return joined normalized plain text in addition to segments.
- Keep YouTube/IP blocking distinct from missing captions.
- Keep a provider boundary so proxy or local speech-to-text can be added later without changing the public API contract.

## Review Focus

- Invalid/non-YouTube URLs must return `INVALID_YOUTUBE_URL`, not an upstream error.
- `youtu.be`, `watch`, `shorts`, `embed`, and raw 11-character IDs must resolve consistently.
- Requested Vietnamese should be preferred over English when both exist, while manual captions should win over generated captions for the same language.
- `RequestBlocked`/`IpBlocked` must become infrastructure errors, never `NO_TRANSCRIPT_FOUND`.
- Empty/whitespace caption snippets must not corrupt ordering or timestamp values.

---

### Task 1: Provider foundation and video ID parsing

**Files:**
- Create: `app/__init__.py`
- Create: `app/youtube.py`
- Create: `tests/test_video_id.py`
- Create: `requirements.txt`
- Create: `.gitignore`

**Interfaces:**
- Produces: `extract_video_id(value: str) -> str` in `app.youtube`.
- Produces: dependency baseline used by later tasks.

- [ ] Write failing tests covering raw ID, `watch?v=`, `youtu.be`, `/shorts/`, `/embed/`, and invalid URL.
- [ ] Run `pytest tests/test_video_id.py -v` and verify failure before implementation.
- [ ] Implement `extract_video_id(value: str) -> str` with strict 11-character YouTube ID validation.
- [ ] Run `pytest tests/test_video_id.py -v` and verify PASS.
- [ ] Commit provider foundation.

### Task 2: Transcript models, provider selection, normalization, and errors

**Files:**
- Create: `app/models.py`
- Create: `app/errors.py`
- Modify: `app/youtube.py`
- Create: `tests/test_provider.py`

**Interfaces:**
- Consumes: `extract_video_id(value: str) -> str`.
- Produces: `TranscriptSegment`, `TranscriptResult`, `LanguageTrack` models.
- Produces: `YouTubeTranscriptProvider.fetch(value: str, languages: list[str]) -> TranscriptResult`.
- Produces: `YouTubeTranscriptProvider.list_languages(value: str) -> list[LanguageTrack]`.
- Produces: stable `TranscriptServiceError(code, message, status_code)`.

- [ ] Write failing mocked-provider tests for language priority, manual/generated selection, segment normalization, joined text, and empty snippets.
- [ ] Write failing exception-mapping tests for disabled transcripts, unavailable video, no matching transcript, request/IP blocking, and generic upstream errors.
- [ ] Run `pytest tests/test_provider.py -v` and verify failure.
- [ ] Implement models and error classes.
- [ ] Implement a fresh `YouTubeTranscriptApi()` instance per provider operation and use upstream `list(video_id)` / transcript `fetch()` APIs.
- [ ] Normalize whitespace while preserving order, start, and duration.
- [ ] Map upstream exceptions to the stable service codes defined by the spec.
- [ ] Run `pytest tests/test_provider.py -v` and verify PASS.
- [ ] Commit transcript provider.

### Task 3: FastAPI contract

**Files:**
- Create: `app/main.py`
- Create: `tests/test_api.py`

**Interfaces:**
- Consumes: `YouTubeTranscriptProvider` and response models from Task 2.
- Produces: `GET /health`.
- Produces: `POST /transcript` accepting `{ "url"?: str, "video_id"?: str, "languages"?: [str] }`.
- Produces: `GET /transcript/{video_id}/languages`.

- [ ] Write failing TestClient tests for `/health`, valid transcript response, URL/video-ID validation, language listing, and structured service errors.
- [ ] Run `pytest tests/test_api.py -v` and verify failure.
- [ ] Implement FastAPI routes and exception handling without embedding YouTube extraction logic in route handlers.
- [ ] Run `pytest tests/test_api.py -v` and verify PASS.
- [ ] Run `pytest -v` and verify the full suite passes.
- [ ] Commit API contract.

### Task 4: Local deployment and operator documentation

**Files:**
- Create: `Dockerfile`
- Create: `README.md`

**Interfaces:**
- Consumes: FastAPI app `app.main:app`.
- Produces: documented local startup on port `8000`, Docker startup, curl examples, and real-video smoke test instructions.

- [ ] Add Docker image based on a slim supported Python runtime, install `requirements.txt`, expose `8000`, and start `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- [ ] Document Windows/local setup, `/health`, `/transcript`, language listing, and smoke test with video `yTwvX2RJ80Q`.
- [ ] Document that cloud IP blocking can still occur and that `YOUTUBE_IP_BLOCKED`/`YOUTUBE_REQUEST_BLOCKED` mean infrastructure blocking rather than missing captions.
- [ ] Run `pytest -v` as final regression verification.
- [ ] Commit deployment/docs.

### Task 5: Integration readiness verification

**Files:**
- Modify only if verification exposes a defect: files owned by Tasks 1-4.

**Interfaces:**
- Produces: stable service contract ready for VIDEO IMAGE STUDIO integration.

- [ ] Verify repository contains no secrets or proxy credentials.
- [ ] Verify OpenAPI exposes all three endpoints and request/response schemas.
- [ ] Run the documented local smoke test from an unblocked machine; confirm `segments` and `text` are returned for a captioned video.
- [ ] Confirm blocked-IP errors remain distinguishable from unavailable/no-caption errors.
- [ ] Commit only if verification requires fixes.
