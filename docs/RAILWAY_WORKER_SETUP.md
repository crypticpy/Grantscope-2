# Railway Worker Setup (Recommended)

Long-running jobs (deep research, discovery runs, executive briefs, nightly scans) must run in a dedicated worker process so they survive web restarts / scale-to-zero behavior.

This repo supports running both roles from the same Docker image via `FORESIGHT_PROCESS_TYPE`.

## 1) API service (web)

- **Env**:
  - `FORESIGHT_PROCESS_TYPE=web` (or leave unset)
  - `FORESIGHT_ENABLE_SCHEDULER=false`
  - Set all required app env vars (Supabase, Azure OpenAI, Tavily, etc.)
- **Expected behavior**:
  - API endpoints enqueue rows into `research_tasks`, `executive_briefs`, and `discovery_runs`
  - No long-running work happens inside the web process

## 2) Worker service

Create a second Railway service from the same repo (a “duplicate” of the API service) and set:

- **Env**:
  - `FORESIGHT_PROCESS_TYPE=worker`
  - `FORESIGHT_ENABLE_SCHEDULER=true` (optional, enables nightly scan + weekly discovery)
  - Copy the same required app env vars as the API service
- **Notes**:
  - The worker starts a tiny health server at `/api/v1/health` when `PORT` is set (Railway), so health checks pass.
  - To prevent the worker from sleeping, configure the worker service to stay running / min replicas > 0 (Railway setting varies by plan).

## 3) Verify

- API:
  - `GET /api/v1/health` returns ok
  - Creating a research task returns `status=queued`
- Worker:
  - Logs contain `Worker starting` and then `Processing research task` / `Processing executive brief` / `Processing discovery run`

