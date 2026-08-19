# Deployment Configuration

The production target has not been selected yet.

Deployment is treated as architecture, so production promotion should require the same dependency shape the app uses at runtime:

- frontend deployment target, likely Vercel or equivalent
- FastAPI and worker runtime target
- managed Postgres
- managed Redis with vector support
- Cohere credentials for model routing
- Tavily credentials for primary external search
- optional Brave Search credentials for fallback/comparison
- migration workflow
- `/ready` dependency checks before promotion
- post-deployment smoke tests, including the manual `Provider Smoke` workflow when secrets are present
- rollback and recovery runbook
