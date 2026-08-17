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

## Model Provider Configuration

Milestone 5 defaults `MODEL_PROVIDER_BACKEND` to `fake` so local development and CI never require live model credentials. The router still exposes explicit routes for Aya Expanse text/structured generation, Aya Vision image analysis, multilingual E5 embeddings, and Cohere reranking through the variables documented in `.env.example`.

## Redis Cache And State

Milestone 7 uses Redis for TTL-aware cache entries, fixed-window rate limits, graph/session checkpoints, streamed event history, semantic retrieval candidates, and Redis Search vector index definitions. TTL classes intentionally separate breaking news, current topics, stable historical context, immutable article content, and semantic candidates so current political facts expire faster than stable provenance.

## Article Ingestion

Milestone 8 adds a backend ingestion pipeline for URLs: SSRF-aware validation, timed/retried fetching, HTML metadata and body extraction, content hashing, canonical URL/content deduplication, chunking, and recorded ingestion attempts for retryable failures.

## Background Workers

Milestone 9 uses Celery with Redis for background article processing. Jobs are durable and idempotent, record attempts/status/failures in Postgres, and share the same ingestion processor used in deterministic backend tests.

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

## Planning

See [PLAN.md](./PLAN.md) for the rebuild milestones and pull request sequence.
