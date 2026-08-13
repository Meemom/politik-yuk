# Deployment Configuration

The production target has not been selected yet.

Milestone 1 keeps deployment as an architectural concern by reserving this boundary and adding CI. Milestone 25 will finalize:

- frontend deployment target, likely Vercel or equivalent
- FastAPI and worker runtime target
- managed Postgres
- managed Redis with vector support
- migration workflow
- post-deployment smoke tests
- rollback and recovery runbook
