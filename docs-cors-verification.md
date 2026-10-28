# Studio preview CORS fix — Transcript Engine 0.1.1

Reported Windows log: `OPTIONS /transcript HTTP/1.1 400 Bad Request` while Uvicorn was healthy on 127.0.0.1:8000. The prior allowlist contained production and local development origins, but not the Studio preview branch origins used by the caller.

The regression test reproduced `Disallowed CORS origin` for both preview URLs before the change. The fix adds exactly those two Studio branch origins, without a global Vercel wildcard, and keeps the existing GET/POST/OPTIONS and Content-Type policy. API request/response schema and transcript extraction remain unchanged. Health reports version 0.1.1 to identify the updated process.

Verification: `python -m pytest -q` — 21 passed; Python compileall passed. Includes real FastAPI CORS middleware preflight plus the POST contract with a fixture transcript provider, production/development origins, health CORS, and rejection of unrelated/lookalike origins. This does not claim an actual YouTube download on the user's Windows network was tested. One upstream Starlette TestClient/httpx deprecation warning remains.

Update: stop the old YouTube Transcript Engine using Ctrl+C. Rerun the existing YOUTUBE_TRANSCRIPT_ENGINE_Setup.bat, which downloads feature/transcript-service again. Keep the new engine window open, confirm /health reports 0.1.1, F5 Studio and request the transcript. No Studio extension reinstall is required.
