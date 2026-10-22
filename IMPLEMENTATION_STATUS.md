# Implementation status

Branch: `feature/transcript-service`

Implemented:
- strict YouTube URL/video ID parsing
- `youtube-transcript-api` provider boundary
- manual/generated caption metadata
- transcript segment normalization with timestamps
- stable YouTube/IP blocking error codes
- FastAPI `/health`, `/transcript`, and language-list endpoints
- Docker/local setup documentation
- automated tests

Verification during implementation: `pytest -q` → 13 passed.

Pending target-machine verification: install dependencies and smoke-test `yTwvX2RJ80Q` from the Windows/local network that will run the service. This is deliberately separate because YouTube can block cloud/datacenter IPs.
