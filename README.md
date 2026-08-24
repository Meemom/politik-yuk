# politik-yuk: Political Context Engine

Reuters Institute's 2025 Indonesia report found social media had overtaken TV, print, and conventional online sources as the dominant route to news, while overall interest and trust were declining. An analysis of the same survey found that half of Indonesian 18–24-year-olds primarily encountered news through social media, with TikTok's use for news rising substantially. 

After discovering this, I wanted to build Politik Yuk to help young readers easily access political news in Indonesia from trusted sources in one centralized platform. 

I also just wanted to test **Cohere's Aya** for fun! specifically to see if it can handle various colloquialisms in the Indonesian language. 

## Local Setup

Install frontend dependencies:

```bash
npm install
```

Create and install backend dependencies:

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Start local infrastructure:

```bash
docker compose -f infra/docker-compose.yml up -d
```

Apply the local Postgres schema and seed data:

```bash
cd backend
.venv/bin/python -m app.persistence.cli migrate
.venv/bin/python -m app.persistence.cli seed
```

Run the frontend:

```bash
npm run dev
```

Run the backend:

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## AI Model Routing

Politik Yuk keeps model usage behind provider interfaces so graph nodes and product logic are not tied to one SDK. Local development and required CI default `MODEL_PROVIDER_BACKEND` to `fake`; set `MODEL_PROVIDER_BACKEND=cohere` and `COHERE_API_KEY` to route Aya text and vision calls, `embed-v4.0` embeddings, and `rerank-v4.0-fast` reranking through Cohere.

## Redis Cache And State

Redis supports TTL-aware cache entries, fixed-window rate limits, graph/session checkpoints, streamed event history, semantic retrieval candidates, and Redis Search vector index definitions. Live provider paths require real Redis outside tests unless `ALLOW_INMEMORY_REDIS=true` is explicitly set for local development.

## Article Ingestion

The backend can ingest URLs through SSRF-aware validation, timed and retried fetching, HTML metadata and body extraction, content hashing, canonical URL and content deduplication, chunking, and recorded ingestion attempts for retryable failures.

## Background Workers

Celery with Redis powers background article processing. Jobs are durable and idempotent, record attempts, status, and failures in Postgres, and share the same ingestion processor used in deterministic backend tests.

## External Search Freshness

The freshness layer retrieves and normalizes external search results into source candidates, caches them with freshness-aware TTLs, classifies stale/current/historical topics, and enqueues useful article URLs into the background ingestion pipeline. Set `EXTERNAL_SEARCH_PROVIDER=tavily` with `TAVILY_API_KEY` for the primary live search path, or `EXTERNAL_SEARCH_PROVIDER=brave` with `BRAVE_SEARCH_API_KEY` for the optional fallback adapter. If no live provider is configured, `POST /api/search/freshness` returns a clear degraded response instead of silently serving uncertain stale data.

## Hybrid Retrieval

Hybrid retrieval merges BM25 keyword matches, vector candidates, and external search candidates, then reranks and scores evidence by relevance, recency, source credibility, diversity, and information gain. Returned evidence candidates include article and source metadata needed for citation display.

## Graph Orchestration

The explanation API runs through a typed graph runner. It records node outputs and checkpoints, routes simple requests through a short path, sends current or complex topics through freshness and retrieval nodes, and streams graph metadata through the existing SSE API. Set `GRAPH_CHECKPOINT_BACKEND=redis` to persist checkpoints in Redis outside local deterministic tests.

## Evidence-Grounded Composition

Answer sections are composed only from retrieved evidence candidates, and every citation is validated against real evidence and source IDs. Unsupported factual claims are rewritten as unverified with high uncertainty, while depth and lens controls change presentation without changing factual conclusions.

## Required Checks

Frontend:

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

Backend:

```bash
cd backend
ruff check .
mypy app
pytest
```

## Deployment

The production path uses Vercel for the Next.js frontend, Render for the FastAPI API and Celery worker, Render Postgres for durable data, and Redis Cloud for Redis Stack/vector-capable cache and queue state. See [infra/deployment/README.md](./infra/deployment/README.md) for provisioning, environment variables, migrations, smoke tests, rollback, and recovery steps.

## Planning

See [PLAN.md](./PLAN.md) for the rebuild milestones and pull request sequence.
