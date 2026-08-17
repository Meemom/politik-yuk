# Workers

Milestone 9 uses Celery with Redis as the broker/result backend for background ingestion and enrichment jobs. The production task wrapper lives in `workers/tasks.py`; the core processor lives in `backend/app/jobs.py` so it can be tested without a live broker.

Run a local worker after Postgres and Redis are up:

```bash
PYTHONPATH=backend celery -A workers.celery_app.celery_app worker --loglevel=info
```

The article pipeline records durable job status, attempts, retryable failures, and worker heartbeats while moving a discovered URL through discovery, fetch, parse, deduplicate, classify, chunk, embed, extract, persist, and index stages.
