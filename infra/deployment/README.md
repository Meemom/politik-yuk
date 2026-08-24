# Deployment Runbook

Politik Yuk deploys as a split system:

- Vercel runs the Next.js frontend.
- Render runs the FastAPI API and Celery worker from the shared `backend/Dockerfile`.
- Render Postgres stores durable application data.
- Redis Cloud provides Redis/Redis Stack for cache, graph checkpoints, worker queues, and future vector indexes.

## Required Production Services

1. Create a Redis Cloud database with Redis Stack/vector support.
2. Create a Render Blueprint from `render.yaml`.
3. Create a Vercel project from the repository root so `vercel.json` can run the workspace build.

Render provisions `politik-yuk-postgres` from the blueprint. Redis is intentionally external because Milestone 25 requires vector-capable Redis, which should not be replaced by in-memory Redis or a queue-only cache in production.

## Backend And Worker Environment

Set these values on both Render services:

```text
ENVIRONMENT=production
POSTGRES_URL=<from Render database connectionString>
MIGRATION_DATABASE_CONNECT_ATTEMPTS=6
MIGRATION_DATABASE_CONNECT_DELAY_SECONDS=5
REDIS_URL=<Redis Cloud URL>
WORKER_BROKER_URL=<Redis Cloud URL, usually a dedicated database/index>
WORKER_RESULT_BACKEND_URL=<Redis Cloud URL, usually a dedicated database/index>
GRAPH_CHECKPOINT_BACKEND=redis
ALLOW_INMEMORY_REDIS=false
MODEL_PROVIDER_BACKEND=cohere
COHERE_API_KEY=<secret>
EXTERNAL_SEARCH_PROVIDER=tavily
TAVILY_API_KEY=<secret>
BRAVE_SEARCH_API_KEY=<optional secret>
CORS_ORIGINS=["https://<vercel-production-domain>","https://<vercel-preview-domain>"]
```

Use separate Redis logical databases or separate Redis Cloud databases for `REDIS_URL`, `WORKER_BROKER_URL`, and `WORKER_RESULT_BACKEND_URL` when the plan supports it.

## Frontend Environment

Set this on Vercel:

```text
NEXT_PUBLIC_API_BASE_URL=https://<render-api-domain>
```

Do not store Cohere, Tavily, Brave, Postgres, or Redis secrets in Vercel frontend variables.

## CI/CD Flow

1. Pull requests run `.github/workflows/ci.yml`.
2. Render services use `autoDeployTrigger: checksPass`, so the backend and worker deploy only after GitHub checks pass.
3. The Render API service runs `python -m app.persistence.cli migrate` as its pre-deploy command.
4. Vercel deploys the frontend from the repository root using `vercel.json`.
5. After both targets finish, run `.github/workflows/deploy-smoke.yml` with the frontend and backend URLs.

The optional `.github/workflows/provider-smoke.yml` validates Cohere, Tavily, Redis, and Postgres against disposable CI services when the provider secrets are available.

## Health Checks

Render uses `/health` as the container liveness check. Promotion should use `/ready`, which verifies:

- model provider configuration
- external search provider configuration
- Postgres connectivity
- Redis connectivity
- worker queue broker connectivity

`/ready` must return `status: "ok"` before production is considered healthy.

## Manual Smoke Test

Run the same smoke checks locally with:

```bash
FRONTEND_URL=https://<frontend-domain> \
BACKEND_URL=https://<backend-domain> \
python scripts/deployment_smoke.py
```

The smoke test loads the frontend, checks `/health` and `/ready`, calls `/api/search/freshness`, and verifies that `/api/explain` streams a completed evidence-grounded answer with sources.

## Rollback

- Frontend: use Vercel's deployment rollback or promote the last known-good deployment.
- Backend and worker: roll back the Render deploy to the previous successful commit.
- Database: prefer forward-only corrective migrations. Restore from a Render Postgres backup only for data-loss incidents.
- Redis: clear only namespaced keys under `REDIS_KEY_PREFIX` if cache or checkpoint data causes production failures.

## Recovery Notes

- If `/ready` reports `postgres` unavailable, check the Render database status and `POSTGRES_URL`.
- If `/ready` reports `redis` or `worker_queue` unavailable, check Redis Cloud networking, TLS requirements, and URL credentials.
- If provider smoke fails, verify the relevant API key has not been rotated or rate limited.
- If frontend requests fail with CORS, update backend `CORS_ORIGINS` to include the exact Vercel production or preview origin.
