# Rebuild Milestones: Agentic Political News Context Engine

## Objective

Rebuild the current prototype into a production-minded agentic political news context engine for young Indonesians.

The finished product should let users submit a political topic, question, headline, pasted text, URL, or screenshot, then receive a source-grounded explanation in Bahasa Indonesia that is easy to understand, traceable at the claim level, explicit about uncertainty, and adaptable by depth or analytical lens without personalizing factual conclusions.

## Non-Negotiable Product Principles

1. Evidence before generation.
2. Facts are not personalized; only wording, depth, examples, and emphasis are personalized.
3. Every important factual assertion must be traceable to retrieved evidence.
4. Screenshots, headlines, and social posts are claims to investigate, not evidence by themselves.
5. Disagreement and uncertainty must be shown instead of flattened into false certainty.
6. Source diversity matters; duplicated or syndicated reporting must not count as independent confirmation.
7. Freshness is part of correctness for current political topics.
8. Simple questions should use a cheap path; complex claims should use deeper retrieval and synthesis.
9. External API, retrieval, OCR, and LLM failures must degrade gracefully.
10. The product optimizes for understanding, not persuasion or engagement bait.

## Recommended PR Sequence

### PR 1: Repository Reset and Application Skeleton

**Objective:** Replace the small static Node prototype with a clean monorepo foundation for the rebuild.

**Deliverables:**

- Create a workspace layout:
  - `frontend/` for Next.js, React, TypeScript, Tailwind, and shadcn/ui.
  - `backend/` for FastAPI, Pydantic schemas, and REST endpoints.
  - `workers/` for ingestion/background processing.
  - `packages/` or `shared/` for shared API contracts if needed.
  - `infra/` for Docker Compose and local service configuration.
- Add basic local development commands.
- Add linting, formatting, type checking, and test commands for frontend and backend.
- Add placeholder health endpoints and a minimal frontend shell.
- Preserve the old prototype only if needed as reference; otherwise remove it in this PR.

**Acceptance Criteria:**

- `frontend` starts locally and renders the new app shell.
- `backend` starts locally and exposes `/health`.
- CI runs frontend checks and backend checks.
- Docker Compose can start required local services, even if most are initially unused.

**Depends On:** None.

---

### PR 2: Canonical API Contracts and Domain Schemas

**Objective:** Define the stable data contracts before implementing agent behavior.

**Deliverables:**

- Add Pydantic schemas for:
  - user input requests
  - parsed intent
  - retrieval plans
  - sources/evidence passages
  - citations
  - claims
  - entities
  - timelines
  - topic graph nodes/edges
  - explanations
  - quizzes
  - saved topic updates
- Add TypeScript types generated from, or manually aligned with, backend schemas.
- Define response envelopes for streaming and non-streaming responses.
- Add explicit enums for:
  - input type
  - depth
  - analytical lens
  - claim status
  - source type
  - uncertainty level
  - graph edge type

**Acceptance Criteria:**

- Backend schema tests validate representative valid and invalid payloads.
- Frontend can import/use matching response types.
- The explanation response supports claim-level citations from day one.

**Depends On:** PR 1.

---

### PR 3: Core Frontend Experience

**Objective:** Build the first usable Next.js interface for submitting political inputs and reading structured explanations.

**Deliverables:**

- Create the main workspace UI with:
  - input mode selector: topic/question/headline/text/URL/screenshot
  - text input area
  - URL field
  - screenshot upload field
  - depth selector: Quick Read and In Depth
  - lens selector: finance, taxes, jobs, education, environment, civil liberties, democracy, public services, regional impact
  - streaming answer panel
  - citations panel
  - uncertainty/disagreement indicators
- Add empty, loading, partial, success, and error states.
- Add responsive behavior for mobile and desktop.
- Keep the interface focused on the actual explainer workflow, not a marketing landing page.

**Acceptance Criteria:**

- Users can submit a text/question/headline request from the UI.
- The UI can render a mocked structured explanation with citations.
- Long text, Indonesian language content, and mobile layouts do not overflow or overlap.

**Depends On:** PR 1 and PR 2.

---

### PR 4: Backend Explanation Endpoint With Streaming

**Objective:** Implement the primary backend request path and stream structured progress/results to the frontend.

**Deliverables:**

- Add `POST /api/explain`.
- Add request validation and clear error responses.
- Add server-sent events or streaming JSON chunks.
- Add placeholder graph execution using deterministic/mock nodes.
- Return structured sections:
  - TL;DR
  - essential context
  - key claims
  - source-backed explanation
  - disagreement/uncertainty
  - why it matters
  - related entities
  - follow-up suggestions
- Add request IDs for tracing.

**Acceptance Criteria:**

- Frontend receives streamed status and final answer from FastAPI.
- Invalid inputs return useful validation errors.
- Tests cover successful, invalid, and failed requests.

**Depends On:** PR 2 and PR 3.

---

### PR 5: Postgres Persistence Foundation

**Objective:** Establish durable storage for users, sources, articles, topics, entities, claims, and feedback.

**Deliverables:**

- Add Postgres connection management.
- Add migrations for:
  - users
  - user preferences
  - publishers
  - articles
  - article chunks
  - sources/evidence passages
  - entities
  - topics
  - claims
  - topic/entity/claim relationships
  - saved topics
  - topic update snapshots
  - quiz results
  - feedback
- Add repository/data-access layer.
- Add seed data for local development.

**Acceptance Criteria:**

- Migrations run cleanly on a fresh database.
- Tests can create and query core records.
- Article, claim, topic, and entity records support the fields required by the product brief.

**Depends On:** PR 1 and PR 2.

---

### PR 6: Redis Foundation for Cache, State, and Vector Indexes

**Objective:** Add Redis as the shared low-latency layer for caching, session state, rate limits, and vector search.

**Deliverables:**

- Add Redis client configuration.
- Add cache helpers with TTL policies.
- Add rate limiting primitives.
- Add LangGraph checkpoint/session-state storage.
- Add Redis Vector Search index definitions for article chunks and optional query/entity embeddings.
- Add semantic cache interfaces without enabling unsafe answer reuse yet.

**Acceptance Criteria:**

- Redis starts via local Docker Compose.
- Cache set/get, rate limit, checkpoint, and vector index smoke tests pass.
- TTL configuration distinguishes current political topics from stable historical/entity data.

**Depends On:** PR 1 and PR 2.

---

### PR 7: Article Fetching, Parsing, and Deduplication

**Objective:** Build the ingestion path for turning URLs and discovered articles into clean, canonical source records.

**Deliverables:**

- Implement URL validation and safety checks.
- Fetch article pages with timeouts and retries.
- Extract:
  - canonical URL
  - title
  - publisher
  - author
  - publication timestamp
  - body text
  - language
  - source type
- Compute content hashes.
- Detect duplicates using canonical URLs, hashes, and normalized text similarity.
- Persist articles and article chunks.

**Acceptance Criteria:**

- Backend can ingest a URL and store a clean article record.
- Duplicate URLs/content do not create duplicate source records.
- Failed fetches return recoverable errors and do not poison state.

**Depends On:** PR 5.

---

### PR 8: Background Processing Pipeline

**Objective:** Move ingestion and enrichment into reliable asynchronous jobs.

**Deliverables:**

- Choose Celery or Temporal for the first production path.
- Implement jobs for:
  - discover article
  - fetch
  - parse
  - deduplicate
  - classify
  - chunk
  - embed
  - extract claims
  - extract entities
  - persist
  - index
- Add retries, timeouts, idempotency keys, and partial failure recovery.
- Add job status tracking.

**Acceptance Criteria:**

- A discovered article can move through the full pipeline.
- Re-running the same job does not duplicate durable records.
- Partial failures are visible and retryable.

**Depends On:** PR 5, PR 6, and PR 7.

---

### PR 9: External Search and Freshness Layer

**Objective:** Retrieve fresh information for current political topics instead of relying only on stored content.

**Deliverables:**

- Add external search/news provider abstraction.
- Normalize search results into source candidates.
- Cache search results with freshness-aware TTLs.
- Add freshness classification:
  - stable/historical
  - recently active
  - breaking/current
  - stale/needs refresh
- Trigger ingestion for useful fresh results.

**Acceptance Criteria:**

- A current topic can produce fresh candidate sources.
- The system avoids blindly serving stale cached results for fast-changing topics.
- Provider failures degrade gracefully.

**Depends On:** PR 7 and PR 8.

---

### PR 10: Hybrid Retrieval and Reranking

**Objective:** Implement evidence retrieval that balances relevance, recency, credibility, diversity, and information gain.

**Deliverables:**

- Add keyword/BM25 retrieval.
- Add vector retrieval from Redis.
- Add query embedding only for semantic search/cache, not for intent understanding.
- Add reranker integration or local reranking abstraction.
- Add scoring that considers:
  - relevance
  - recency
  - source credibility
  - source diversity
  - information gain
- Add source diversity selection to reduce duplicate reporting.

**Acceptance Criteria:**

- Retrieval returns a diverse evidence set, not simply nearest vectors.
- Tests cover deduplication, source diversity, and recency weighting.
- Each returned evidence item includes enough metadata for citation display.

**Depends On:** PR 6, PR 8, and PR 9.

---

### PR 11: LangGraph Orchestration MVP

**Objective:** Replace the placeholder backend flow with a conditional LangGraph workflow.

**Deliverables:**

- Implement graph state.
- Add core nodes:
  - input parser
  - intent extractor
  - query planner
  - freshness checker
  - retrieval router
  - keyword retriever
  - vector retriever
  - reranker
  - source diversity selector
  - answer composer
  - citation validator
- Add conditional routing for cheap/simple vs deep/current queries.
- Add graph checkpointing in Redis.

**Acceptance Criteria:**

- "What is DPR?" uses a short entity/context path.
- "Is this claim true and why are people protesting?" uses a deeper retrieval path.
- Graph node outputs are structured and testable.

**Depends On:** PR 4, PR 6, and PR 10.

---

### PR 12: Evidence-Grounded Answer Composition

**Objective:** Generate final explanations that are useful, readable, and grounded at the claim level.

**Deliverables:**

- Compose answers using retrieved evidence only.
- Support Quick Read and In Depth outputs.
- Support lens-specific emphasis:
  - personal finances
  - taxes
  - jobs
  - education
  - environment
  - civil liberties
  - democracy
  - public services
  - regional impact
- Separate:
  - facts
  - interpretations
  - predictions
  - disagreements
  - uncertainty
- Add citation validation that rejects unsupported factual assertions.
- Ensure citations map to actual evidence passages.

**Acceptance Criteria:**

- Important factual claims include citations.
- Unsupported generated factual claims are removed or rewritten as uncertain.
- Depth and lens change presentation, not factual conclusions.

**Depends On:** PR 10 and PR 11.

---

### PR 13: Claim Extraction and Evidence Mapping

**Objective:** Persist and classify claims so the system can reason across sources and topics.

**Deliverables:**

- Add claim extraction node/job.
- Normalize semantically equivalent claims.
- Classify claims as:
  - supported
  - disputed
  - opinion/interpretation
  - prediction
  - unverified
- Link claims to supporting and contradicting articles/evidence passages.
- Add confidence/evidence-strength scoring.

**Acceptance Criteria:**

- Claims from multiple articles can be grouped when they describe the same assertion.
- Disputed claims show both supporting and contradicting evidence.
- The answer composer can use claim status directly.

**Depends On:** PR 8, PR 10, and PR 12.

---

### PR 14: Entity Extraction, Resolution, and Context Cards

**Objective:** Make political entities clickable and context-aware.

**Deliverables:**

- Extract entities from inputs, articles, and generated answers.
- Resolve entities to canonical records.
- Support entity types:
  - politicians
  - political parties
  - government institutions
  - legislation
  - programs
  - historical events
  - organizations
  - locations
- Add frontend entity cards with:
  - what it is
  - why it matters here
  - role in the current topic
  - related people/events/topics

**Acceptance Criteria:**

- Entity explanations prioritize relevance to the current topic, not generic biographies.
- Users can click an entity in an answer and see useful context.
- Entity resolution handles aliases and common Indonesian abbreviations.

**Depends On:** PR 5, PR 11, and PR 12.

---

### PR 15: Timeline Builder

**Objective:** Add chronological context for political topics and controversies.

**Deliverables:**

- Extract dated events from evidence.
- Normalize event dates.
- Link events to topics, claims, and entities.
- Add timeline section to In Depth responses.
- Add frontend timeline component.

**Acceptance Criteria:**

- Timelines only include events supported by sources.
- Ambiguous dates are marked as approximate or uncertain.
- Timeline events link back to citations.

**Depends On:** PR 12, PR 13, and PR 14.

---

### PR 16: Topic Graph

**Objective:** Build a meaningful graph of topics, entities, claims, laws, events, and institutions.

**Deliverables:**

- Add graph-building node/job.
- Support meaningful edge types:
  - proposed_by
  - opposed_by
  - governs
  - amended_by
  - member_of
  - caused
  - responded_to
  - related_to
- Add graph persistence/query APIs.
- Add frontend topic graph view.
- Allow users to request explanations for connected nodes.

**Acceptance Criteria:**

- Edges are based on extracted relationships or curated logic, not embedding similarity alone.
- Users can traverse from a topic to related institutions, claims, laws, and events.
- Graph nodes preserve evidence provenance where applicable.

**Depends On:** PR 13, PR 14, and PR 15.

---

### PR 17: Screenshot and Image Claim Flow

**Objective:** Let users upload screenshots and investigate political claims visible in images.

**Deliverables:**

- Add image upload API and frontend flow.
- Add OCR/vision extraction.
- Extract:
  - visible text
  - visible claim
  - people/entities
  - implied topic
  - identifiable source, if present
- Route extracted claims through retrieval and evidence synthesis.
- Clearly label screenshot text as unverified input.

**Acceptance Criteria:**

- A screenshot can produce an investigated explanation.
- The answer distinguishes "what the screenshot claims" from "what evidence supports."
- OCR/vision failure produces a clear recoverable error.

**Depends On:** PR 11, PR 12, PR 13, and PR 14.

---

### PR 18: Saved Topics and Update Tracker

**Objective:** Allow users to follow topics and see meaningful changes since they last read them.

**Deliverables:**

- Add saved topic APIs and UI.
- Store previous and latest topic state.
- Detect meaningful changes:
  - policy passed
  - court ruling
  - official statement
  - revised budget
  - protest
  - investigation
  - implementation change
  - newly introduced claim
  - modified claim
  - resolved uncertainty
- Add "Since you last read this" summaries.

**Acceptance Criteria:**

- Updates are based on new information, not merely new articles.
- Users can save, view, and revisit topics.
- The system records when a user last read a topic.

**Depends On:** PR 13, PR 15, and PR 16.

---

### PR 19: Quiz Me

**Objective:** Generate evidence-backed comprehension quizzes from explanations.

**Deliverables:**

- Add quiz generation endpoint/node.
- Support:
  - multiple choice
  - true/false
  - short conceptual questions
- Test:
  - key facts
  - institutional understanding
  - causal relationships
  - fact vs opinion distinctions
- Store quiz attempts and results.
- Explain correct answers using relevant evidence.

**Acceptance Criteria:**

- Quiz questions avoid obscure trivia.
- Answers include explanations and citations.
- Quiz results persist for signed-in or session-based users.

**Depends On:** PR 12 and PR 13.

---

### PR 20: User Preferences Without Factual Personalization

**Objective:** Add lightweight user/session preferences while preserving evidence-based conclusions.

**Deliverables:**

- Add preference storage for:
  - default depth
  - default language/register
  - preferred lenses
  - saved topics
- Add frontend preference controls.
- Add backend guardrails preventing preference data from altering claim status or factual conclusions.

**Acceptance Criteria:**

- Preferences change explanation style/emphasis only.
- Tests verify claim status is independent of user preference.
- Users can update preferences and see them applied in future requests.

**Depends On:** PR 5, PR 12, and PR 18.

---

### PR 21: Observability and Cost Tracking

**Objective:** Make the system inspectable enough to operate and improve safely.

**Deliverables:**

- Add OpenTelemetry tracing across frontend, backend, workers, retrieval, and LangGraph nodes.
- Add LangSmith tracing/evaluation hooks for agent and LLM behavior.
- Track:
  - request latency
  - latency per graph node
  - cache hit rate
  - retrieval latency
  - LLM/token cost
  - tool failure rate
  - retrieval quality
  - answer groundedness
- Add structured logs.
- Add optional Prometheus/Grafana dashboards if infrastructure is ready.

**Acceptance Criteria:**

- Each explanation request has a traceable request ID.
- Slow/failing graph nodes are identifiable.
- LLM and retrieval cost can be inspected per request.

**Depends On:** PR 11 and PR 12.

---

### PR 22: Evaluation Dataset and CI Quality Gates

**Objective:** Prevent regressions in factuality, retrieval, citation quality, and explanation style.

**Deliverables:**

- Add evaluation dataset for Indonesian political queries across:
  - basic factual questions
  - complex controversies
  - historical context
  - financial impact
  - environmental impact
  - ambiguous queries
  - misinformation claims
  - screenshots/headlines
  - multi-turn conversations
  - breaking-news queries
- Add automated evaluators for:
  - retrieval relevance
  - retrieval recall
  - source diversity
  - citation correctness
  - claim groundedness
  - factuality
  - completeness
  - hallucination rate
  - depth adherence
  - language/register adherence
  - latency
  - cost
  - cache hit rate
- Add CI gates for deterministic tests and lightweight eval smoke tests.

**Acceptance Criteria:**

- CI catches broken schemas, unsupported citations, and obvious grounding failures.
- Eval results are saved and comparable across runs.
- Heavy evals can run manually or on scheduled workflows.

**Depends On:** PR 10, PR 12, PR 13, and PR 21.

---

### PR 23: Security, Abuse Prevention, and Reliability Hardening

**Objective:** Harden the app for public or semi-public use.

**Deliverables:**

- Add input size limits and file upload limits.
- Add rate limiting.
- Add URL fetch allow/deny behavior to reduce SSRF risk.
- Add content safety handling for harmful or targeted political abuse.
- Add API timeout budgets.
- Add graceful fallbacks for:
  - search provider failure
  - OCR failure
  - reranker failure
  - LLM failure
  - database/Redis degraded state
- Add privacy-conscious handling of uploaded screenshots and user history.

**Acceptance Criteria:**

- Known bad URL patterns are rejected.
- Oversized inputs and files fail safely.
- The product can return partial/uncertain answers instead of crashing.

**Depends On:** PR 4, PR 6, PR 7, PR 17, and PR 20.

---

### PR 24: Deployment and Production Readiness

**Objective:** Prepare the rebuilt system for cloud deployment.

**Deliverables:**

- Add production Dockerfiles.
- Add environment variable documentation.
- Add GitHub Actions workflows.
- Add deployment targets:
  - Vercel or equivalent for Next.js frontend.
  - GCP/AWS/Fly/Render or equivalent for FastAPI and workers.
  - Managed Postgres.
  - Managed Redis with vector support.
- Add database migration workflow.
- Add smoke tests after deployment.
- Add operational runbook.

**Acceptance Criteria:**

- A fresh environment can be deployed from documented steps.
- Health checks cover frontend, backend, database, Redis, worker, and search dependencies.
- Rollback/recovery steps are documented.

**Depends On:** PR 21, PR 22, and PR 23.

## Efficient Delivery Path

The most efficient path is to treat PRs 1 through 12 as the first production MVP. That gives the product its essential identity:

- modern frontend
- FastAPI backend
- durable schemas
- streaming responses
- fresh retrieval
- hybrid search
- LangGraph routing
- source-grounded explanation
- citation validation

PRs 13 through 20 expand the product into a richer civic learning engine:

- claims
- entities
- timelines
- topic graph
- screenshots
- saved topic updates
- quizzes
- preferences

PRs 21 through 24 make it reliable enough to run continuously:

- observability
- evaluations
- security
- deployment

## First Release Target

The first serious release should include PRs 1 through 12.

It should support:

- topic/question/headline/text/URL input
- Quick Read and In Depth modes
- lens selection
- fresh external retrieval
- hybrid retrieval over ingested sources
- evidence-grounded explanations
- claim-level citations
- explicit uncertainty and disagreement
- streaming frontend responses

It can defer:

- screenshots
- quizzes
- saved topics
- topic graph traversal
- full user accounts
- heavy dashboards

This release is small enough to build coherently but complete enough to prove the core product promise.

## Implementation Notes

- Use LangGraph for orchestration, not for unconstrained autonomous behavior.
- Keep graph nodes specialized, typed, and independently testable.
- Prefer structured model outputs for intent, claims, entities, and answer plans.
- Use embeddings for retrieval and semantic caching, not for primary intent understanding.
- Store immutable article content and evidence passages so citations remain auditable.
- Keep current-event cache TTLs short and historical/entity cache TTLs longer.
- Build citation validation before adding advanced product features.
- Do not let UI controls bypass evidence constraints.
- Avoid adding a topic graph until claim/entity/timeline extraction is useful enough to support meaningful edges.
