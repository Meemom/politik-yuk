# Shared Contracts

Canonical contracts are currently defined in two aligned places:

- Backend Pydantic schemas: `backend/app/schemas.py`
- Frontend TypeScript types: `frontend/types/api-contracts.ts`

The contracts cover request inputs, parsed intent, retrieval plans, sources, evidence passages, claim-level citations, claims, entities, timelines, topic graph nodes and edges, explanations, quizzes, saved topic updates, and streaming events.

Later milestones may replace the manual TypeScript alignment with generated types from the backend schema or OpenAPI output.
