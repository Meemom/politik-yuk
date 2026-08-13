# Cohere Aya Context Engine

Production-minded rebuild of the original Indonesian political explainer prototype into an agentic political news context engine.

The first milestone establishes the application skeleton:

- `frontend/` - Next.js, React, TypeScript, Tailwind-ready UI shell.
- `backend/` - FastAPI app with typed settings and health endpoint.
- `workers/` - background processing package placeholder.
- `infra/` - local Postgres and Redis configuration.
- `.github/workflows/ci.yml` - pull request checks for frontend and backend.

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

Run the frontend:

```bash
npm run dev
```

Run the backend:

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

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
