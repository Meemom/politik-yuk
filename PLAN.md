# PLAN.md

## Product Objective

Rebuild the current prototype into a production-minded agentic political news context engine for young Indonesians.

The product should let users submit a political topic, natural-language question, headline, pasted text, URL, or screenshot, then return a source-grounded explanation in Bahasa Indonesia that is understandable, traceable at the claim level, explicit about uncertainty, and adaptable by explanation depth or analytical lens.

The system may personalize wording, depth, examples, and emphasis. It must not personalize factual conclusions, claim status, or evidence interpretation.

## Non-Negotiable Principles

1. Evidence before generation.
2. Factual conclusions are not personalized.
3. Every important factual assertion must map to retrievable evidence.
4. Screenshots, headlines, and social posts are user inputs to investigate, not evidence by themselves.
5. Disagreement and uncertainty must be shown clearly.
6. Source diversity matters; duplicated or syndicated reporting must not count as independent confirmation.
7. Freshness is part of correctness for current political topics.
8. Simple questions should use cheaper paths; complex or current claims should use deeper retrieval and synthesis.
9. External API, retrieval, OCR, database, cache, and model failures must degrade gracefully.
10. The product optimizes for understanding, not persuasion or engagement.

## Required Checks

Before declaring implementation work complete, run the checks that exist for that milestone.

Frontend:

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

Backend:

```bash
ruff check .
mypy app
pytest
```

CI must run the same deterministic checks on pull requests. Heavier retrieval, model, and evaluation checks may run manually, nightly, or behind required environment secrets.

## Milestone 1: Repository Reset, CI, and Local Architecture

**Objective:** Replace the static Node prototype with a clean monorepo foundation that can support frontend, backend, workers, tests, and deployment from the beginning.

**Scope:**

- Create the target workspace layout:
  - `frontend/` for Next.js, React, TypeScript, Tailwind, and shadcn/ui.
  - `backend/` for FastAPI, Pydantic, LangGraph orchestration, and REST APIs.
  - `workers/` for ingestion and background processing.
  - `shared/` or `packages/` for shared API contracts if needed.
  - `infra/` for Docker Compose, service configuration, and local infrastructure.
- Add local development commands for frontend, backend, workers, and infrastructure.
- Add frontend lint, typecheck, test, and build commands.
- Add backend ruff, mypy, and pytest commands.
- Add placeholder frontend app shell.
- Add backend `/health` endpoint.
- Add Docker Compose for local Postgres and Redis.
- Add `.github/workflows/ci.yml` with separate frontend and backend jobs.
- Add deployment workflow/configuration placeholders only where they clarify the intended target.
- Preserve the old prototype only as reference, or remove it if the new skeleton fully replaces it.

**Acceptance Criteria:**

- Frontend starts locally and renders the new app shell.
- Backend starts locally and exposes `/health`.
- Docker Compose starts local Postgres and Redis.
- CI runs frontend lint, typecheck, tests, and build.
- CI runs backend ruff, mypy, and pytest.
- The repo has a documented local setup path.

**Depends On:** None.

## Milestone 2: Canonical Schemas and API Contracts

**Objective:** Define stable product contracts before implementing agent behavior.

**Scope:**

- Add Pydantic schemas for:
  - user input requests
  - parsed intent
  - retrieval plans
  - evidence passages
  - sources
  - citations
  - claims
  - entities
  - timelines
  - topic graph nodes and edges
  - explanations
  - quizzes
  - saved topic updates
- Add TypeScript types generated from, or strictly aligned with, backend schemas.
- Define response envelopes for standard JSON responses and streaming events.
- Add enums for:
  - input type
  - explanation depth
  - analytical lens
  - claim status
  - source type
  - uncertainty level
  - graph edge type
  - stream event type
- Encode claim-level citation support from day one.

**Acceptance Criteria:**

- Backend schema tests cover representative valid and invalid payloads.
- Frontend imports or consumes matching response types.
- Explanation responses can represent citations, uncertainty, disagreement, claims, entities, and follow-up suggestions.

**Depends On:** Milestone 1.

## Milestone 3: Core Frontend Workflow

**Objective:** Build the first usable Next.js interface for submitting political inputs and reading structured explanations.

**Scope:**

- Build the primary explainer workspace as the first screen.
- Add input modes:
  - topic
  - question
  - headline
  - pasted text
  - URL
  - screenshot placeholder
- Add controls for:
  - Quick Read
  - In Depth
  - analytical lenses such as democracy, jobs, taxes, education, environment, civil liberties, public services, and regional impact
- Add structured answer rendering for:
  - TL;DR
  - essential context
  - key claims
  - evidence-backed explanation
  - disagreement and uncertainty
  - why it matters
  - citations
  - related entities
  - follow-up questions
- Add empty, loading, streaming, success, and error states.
- Add mocked responses so the UI can be developed before live retrieval/model integration.

**Acceptance Criteria:**

- Users can submit text, topic, question, headline, or URL input from the UI.
- The UI renders a mocked structured explanation with citations.
- Long Indonesian text does not overflow on mobile or desktop.
- UI controls affect request payloads without bypassing evidence constraints.

**Depends On:** Milestones 1 and 2.

## Milestone 4: Backend Explanation API and Streaming

**Objective:** Implement the primary backend request path with validated input and streaming structured progress/results.

**Scope:**

- Add `POST /api/explain`.
- Validate requests with Pydantic schemas.
- Add request IDs.
- Add server-sent events or streaming JSON events.
- Add deterministic placeholder graph execution.
- Stream progress events such as:
  - input parsed
  - planning retrieval
  - retrieving evidence
  - composing answer
  - validating citations
  - complete
- Return structured final explanations compatible with the frontend.
- Add clear validation and failure responses.

**Acceptance Criteria:**

- Frontend receives streamed progress and final answer from FastAPI.
- Invalid inputs return useful errors.
- Tests cover success, validation failure, and internal failure paths.

**Depends On:** Milestones 2 and 3.

## Milestone 5: Model Router and Provider Interfaces

**Objective:** Keep graph nodes independent from model vendors and make models replaceable and benchmarkable.

**Scope:**

- Add provider interfaces for:
  - text generation
  - structured generation
  - image analysis
  - embeddings
  - reranking
- Implement a model router with conceptual routes:
  - `generate_text()` to Aya Expanse 32B
  - `generate_structured()` to Aya Expanse 32B
  - `analyze_image()` to Aya Vision 32B
  - `embed()` to `intfloat/multilingual-e5-large-instruct`
  - `rerank()` to Cohere Rerank
- Add fake/test providers for deterministic tests.
- Add timeout, retry, and error classification behavior.
- Add configuration and environment variable documentation.

**Acceptance Criteria:**

- Backend nodes call provider abstractions, not SDKs directly.
- Tests can run without live model credentials.
- Provider failures return typed errors that graph nodes can handle.

**Depends On:** Milestones 1, 2, and 4.

## Milestone 6: Postgres Persistence Foundation

**Objective:** Establish durable storage for users, sources, articles, topics, entities, claims, quizzes, feedback, and saved-topic state.

**Scope:**

- Add Postgres connection management.
- Add migrations for:
  - users
  - user preferences
  - publishers
  - articles
  - article chunks
  - evidence passages
  - entities
  - topics
  - claims
  - topic/entity/claim relationships
  - saved topics
  - topic update snapshots
  - quiz results
  - feedback
- Add repository/data-access layer.
- Add local seed data.
- Add migration commands to CI where safe.

**Acceptance Criteria:**

- Migrations run cleanly on a fresh local database.
- Tests can create and query core records.
- Article, claim, topic, and entity records support the fields required for citation and provenance.

**Depends On:** Milestones 1 and 2.

## Milestone 7: Redis Cache, State, Rate Limits, and Vector Indexes

**Objective:** Add Redis as the low-latency layer for cache, semantic cache, LangGraph checkpoints, rate limits, and vector search.

**Scope:**

- Add Redis client configuration.
- Add cache helpers with TTL policy support.
- Add rate limiting primitives.
- Add LangGraph checkpoint/session-state storage.
- Add Redis Vector Search index definitions for article chunks and optional query/entity embeddings.
- Add semantic cache interfaces without enabling unsafe answer reuse.
- Define TTL classes for breaking news, current topics, stable historical information, and immutable article content.

**Acceptance Criteria:**

- Redis starts through Docker Compose.
- Cache, rate limit, checkpoint, and vector index smoke tests pass.
- TTL policy distinguishes current political topics from stable entity or historical data.

**Depends On:** Milestones 1 and 2.

## Milestone 8: Article Ingestion, Parsing, and Deduplication

**Objective:** Turn URLs and discovered articles into clean, canonical source records.

**Scope:**

- Implement URL validation and SSRF-aware safety checks.
- Fetch article pages with timeouts and retries.
- Extract:
  - canonical URL
  - title
  - publisher
  - author
  - publication timestamp
  - retrieval timestamp
  - body text
  - language
  - source type
- Compute content hashes.
- Deduplicate by canonical URL, content hash, and normalized text similarity.
- Persist articles and article chunks.

**Acceptance Criteria:**

- Backend can ingest a URL and store a clean article record.
- Duplicate URLs/content do not create duplicate records.
- Failed fetches are recoverable and visible.

**Depends On:** Milestone 6.

## Milestone 9: Background Processing Pipeline

**Objective:** Move ingestion and enrichment into reliable asynchronous jobs.

**Scope:**

- Choose Celery or Temporal for the first production path.
- Implement jobs for:
  - discovery
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
- Add worker health checks.

**Acceptance Criteria:**

- A discovered article can move through the full pipeline.
- Re-running the same job does not duplicate durable records.
- Partial failures are visible and retryable.

**Depends On:** Milestones 5, 6, 7, and 8.

## Milestone 10: External Search and Freshness Layer

**Objective:** Retrieve fresh information for current political topics instead of relying only on stored content.

**Scope:**

- Add external search/news provider abstraction.
- Normalize search results into source candidates.
- Cache search results with freshness-aware TTLs.
- Add freshness classification:
  - stable or historical
  - recently active
  - breaking or current
  - stale or needs refresh
- Trigger ingestion for useful fresh results.
- Add graceful degradation when search providers fail.

**Acceptance Criteria:**

- Current topics can produce fresh source candidates.
- The system does not blindly serve stale cached answers for fast-changing claims.
- Provider failures produce partial but clear user-facing responses.

**Depends On:** Milestones 8 and 9.

## Milestone 11: Hybrid Retrieval and Reranking

**Objective:** Implement evidence retrieval that balances relevance, recency, credibility, diversity, and information gain.

**Scope:**

- Add keyword/BM25 retrieval.
- Add query embedding for semantic retrieval.
- Add vector retrieval from Redis.
- Add Cohere Rerank through the model router.
- Merge candidates from keyword, vector, and external search.
- Score candidates using:
  - relevance
  - recency
  - source credibility
  - source diversity
  - information gain
- Add source diversity selection to reduce duplicate reporting.

**Acceptance Criteria:**

- Retrieval returns a diverse evidence set, not just nearest vectors.
- Tests cover deduplication, source diversity, and recency weighting.
- Each evidence item includes metadata needed for citation display.

**Depends On:** Milestones 5, 7, 9, and 10.

## Milestone 12: LangGraph Orchestration MVP

**Objective:** Replace placeholder backend flow with a conditional, inspectable LangGraph workflow.

**Scope:**

- Implement typed graph state.
- Add core nodes:
  - input router
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
- Add conditional routing for cheap/simple versus deep/current requests.
- Store checkpoints in Redis.
- Emit graph events through the streaming API.

**Acceptance Criteria:**

- Simple entity questions use a short path.
- Complex or current political claims use deeper retrieval.
- Graph node outputs are structured, logged, and testable.

**Depends On:** Milestones 4, 5, 7, and 11.

## Milestone 13: Evidence-Grounded Answer Composition and Citation Validation

**Objective:** Generate final explanations that are readable, useful, and grounded at the claim level.

**Scope:**

- Compose answers only from retrieved evidence.
- Support Quick Read and In Depth modes.
- Support lens-specific emphasis for finances, taxes, jobs, education, environment, civil liberties, democracy, public services, and regional impact.
- Separate:
  - facts
  - interpretations
  - predictions
  - disagreements
  - uncertainty
- Add citation validation that rejects or rewrites unsupported factual assertions.
- Ensure citations map to actual evidence passages.

**Acceptance Criteria:**

- Important factual claims include citations.
- Unsupported factual claims are removed, rewritten, or explicitly marked uncertain.
- Depth and lens change presentation, not factual conclusions.

**Depends On:** Milestones 11 and 12.

## Milestone 13.5: Live Provider Integrations and Production Redis

**Objective:** Replace fake model/search providers and memory-backed live paths with real, configurable production services while keeping deterministic test doubles for CI.

**Provider Decision:**

- Use Cohere as the primary model provider because the product is centered on Aya, multilingual Indonesian explanations, embeddings, and reranking.
- Use Tavily as the primary external search provider because it is optimized for agentic/RAG search, returns LLM-ready snippets, supports news/currentness controls, supports domain filters, and can optionally extract clean page content.
- Add Brave Search as an optional fallback adapter, not the first implementation, because it is a strong general web/news search API but returns more search-engine-shaped results that usually need extra extraction and normalization work before evidence synthesis.
- Keep fake providers only for local deterministic tests and CI.

**Scope:**

- Implement a Cohere-backed provider bundle for:
  - text generation through Aya Expanse
  - structured generation through Aya Expanse with schema validation
  - image analysis through Aya Vision
  - embeddings through `embed-v4.0`
  - reranking through `rerank-v4.0-fast`
- Implement a Tavily-backed external search provider with:
  - `topic=news` for current political queries
  - recency/time-range controls from the freshness classifier
  - Indonesian/public-interest domain include and exclude lists
  - provider scores mapped into source-candidate scores
  - explicit handling for authentication, quota, timeout, rate-limit, and malformed-response failures
- Add an optional Brave Search adapter behind the same `ExternalSearchProvider` interface for fallback or later comparison.
- Wire provider selection through settings and environment variables:
  - `MODEL_PROVIDER_BACKEND=cohere|fake`
  - `COHERE_API_KEY`
  - `EXTERNAL_SEARCH_PROVIDER=tavily|brave|disabled`
  - `TAVILY_API_KEY`
  - `BRAVE_SEARCH_API_KEY`
  - provider timeout, retry, max-results, and domain-policy settings
- Replace fake in-memory Redis usage in live backend paths:
  - use real Redis for freshness cache, graph checkpoints, rate limits, semantic cache, and worker broker/result backend outside tests
  - allow `InMemoryRedis` only when `ENVIRONMENT=test` or an explicit local test setting is enabled
  - return a clear degraded health/status response when Redis is required but unavailable
- Add dependency injection factories so API routes and graph construction choose real providers once configured instead of hardcoding disabled/fake implementations.
- Extend `/health` or add `/ready` to report model provider, search provider, Postgres, Redis, worker, and configuration readiness without exposing secrets.
- Add provider contract tests with mocked HTTP responses and disabled-by-default smoke tests for real credentials.
- Document local `.env` setup, CI secrets, production secrets, and how to run optional live-provider smoke tests.
- Update CI/CD to preserve deterministic required checks while adding a manual or secret-gated provider smoke workflow:
  - required PR CI uses fake providers and local service containers
  - optional workflow validates Cohere, Tavily, Redis, Postgres, and deployment readiness when secrets are present
  - deployment workflow blocks production promotion if required provider readiness checks fail

**Acceptance Criteria:**

- Setting `MODEL_PROVIDER_BACKEND=cohere` sends model-router calls to Cohere and preserves typed timeout/retry/error behavior.
- Setting `EXTERNAL_SEARCH_PROVIDER=tavily` returns fresh source candidates for current political topics and triggers ingestion for useful URLs.
- `EXTERNAL_SEARCH_PROVIDER=disabled` still degrades clearly without pretending search succeeded.
- Live API and graph paths no longer silently use `InMemoryRedis` when Redis is configured for production.
- Tests still run without live API keys.
- CI includes deterministic fake-provider checks, and CI/CD includes a documented secret-gated provider smoke path.
- Health/readiness output makes missing Redis, model, search, worker, or database dependencies visible before deployment.

**Depends On:** Milestones 5, 7, 10, 11, 12, and 13.

## Milestone 14: Claim Extraction and Evidence Mapping

**Objective:** Persist and classify claims so the system can reason across sources and topics.

**Scope:**

- Add claim extraction node/job.
- Normalize semantically equivalent claims.
- Classify claims as:
  - supported
  - disputed
  - opinion or interpretation
  - prediction
  - unverified
- Link claims to supporting and contradicting evidence passages.
- Add confidence/evidence-strength scoring.
- Expose claim data to answer composition.

**Acceptance Criteria:**

- Claims from multiple articles can be grouped when they describe the same assertion.
- Disputed claims show both supporting and contradicting evidence.
- The answer composer can use claim status directly.

**Depends On:** Milestones 9, 11, and 13.

## Milestone 15: Entity Resolution and Context Cards

**Objective:** Make political entities clickable and context-aware.

**Scope:**

- Extract entities from user inputs, articles, and generated answers.
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
- Add frontend entity cards that answer:
  - what it is
  - why it is relevant here
  - what role it plays
  - related people, events, and topics
- Use cached/structured entity data before invoking models.

**Acceptance Criteria:**

- Entity explanations prioritize current-topic relevance, not generic biographies.
- Users can click an entity in an answer and see useful context.
- Entity resolution handles aliases and common Indonesian abbreviations.

**Depends On:** Milestones 6, 12, and 13.

## Milestone 16: Timeline Builder

**Objective:** Add chronological context for political topics and controversies.

**Scope:**

- Extract dated events from evidence.
- Normalize event dates.
- Link events to topics, claims, and entities.
- Add timeline sections to In Depth responses.
- Add frontend timeline component.

**Acceptance Criteria:**

- Timelines only include source-supported events.
- Ambiguous dates are marked approximate or uncertain.
- Timeline events link back to citations.

**Depends On:** Milestones 13, 14, and 15.

## Milestone 17: Topic Graph

**Objective:** Build a meaningful graph of topics, entities, claims, laws, events, and institutions.

**Scope:**

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
- Preserve provenance for edges where applicable.

**Acceptance Criteria:**

- Edges are based on extracted relationships or curated logic, not embedding similarity alone.
- Users can traverse from a topic to related institutions, claims, laws, and events.
- Graph nodes and edges preserve evidence provenance when available.

**Depends On:** Milestones 14, 15, and 16.

## Milestone 18: Screenshot and Image Claim Flow

**Objective:** Let users upload screenshots and investigate political claims visible in images.

**Scope:**

- Add image upload API and frontend flow.
- Use Aya Vision only for image analysis.
- Extract:
  - visible text
  - visible claims
  - people/entities
  - implied topic
  - apparent source or platform when visible
- Route extracted claims through normal retrieval and evidence synthesis.
- Clearly label screenshot contents as unverified user input.

**Acceptance Criteria:**

- A screenshot can produce an investigated explanation.
- The answer distinguishes what the screenshot claims from what independent evidence supports.
- OCR/vision failure produces a clear recoverable error.

**Depends On:** Milestones 12, 13, 14, and 15.

## Milestone 19: Saved Topics and Update Tracker

**Objective:** Let users follow topics and see meaningful changes since they last read them.

**Scope:**

- Add saved topic APIs and UI.
- Store previous and latest topic state.
- Detect meaningful changes such as:
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
- Add "since you last read this" summaries.

**Acceptance Criteria:**

- Updates are based on new information, not merely new articles.
- Users can save, view, and revisit topics.
- The system records when a user last read a topic.

**Depends On:** Milestones 14, 16, and 17.

## Milestone 20: Quiz Me

**Objective:** Generate evidence-backed comprehension quizzes from existing explanations and evidence.

**Scope:**

- Add quiz generation endpoint/node.
- Support multiple choice, true/false, and short conceptual questions.
- Test key facts, institutional understanding, causal relationships, and fact/opinion distinctions.
- Store quiz attempts and results.
- Explain correct answers using relevant evidence.
- Avoid new retrieval unless the existing evidence is insufficient.

**Acceptance Criteria:**

- Quiz questions avoid obscure trivia.
- Answers include explanations and citations.
- Quiz results persist for signed-in or session-based users.

**Depends On:** Milestones 13 and 14.

## Milestone 21: User Preferences Without Factual Personalization

**Objective:** Add lightweight user/session preferences while preserving evidence-based conclusions.

**Scope:**

- Store preferences for:
  - default depth
  - default language/register
  - preferred lenses
  - saved topics
- Add frontend preference controls.
- Add backend guardrails preventing preference data from altering claim status or factual conclusions.
- Add tests showing that factual conclusions remain independent from preferences.

**Acceptance Criteria:**

- Preferences change style, depth, and emphasis only.
- Claim status and factual conclusions are independent of user preference.
- Users can update preferences and see them applied in future requests.

**Depends On:** Milestones 6, 13, and 19.

## Milestone 22: Observability and Cost Tracking

**Objective:** Make the system inspectable enough to operate, debug, and improve safely.

**Scope:**

- Add OpenTelemetry tracing across frontend, backend, workers, retrieval, and LangGraph nodes.
- Add LangSmith tracing/evaluation hooks for agent and model behavior.
- Add structured logs.
- Track:
  - request latency
  - latency per graph node
  - latency per model/provider
  - cache hit rate
  - semantic cache hit rate
  - retrieval latency
  - embedding latency
  - reranking latency
  - model/token cost
  - model call counts
  - tool/provider failure rate
  - retrieval quality
  - answer groundedness
- Add optional Prometheus/Grafana dashboards if infrastructure is ready.

**Acceptance Criteria:**

- Each explanation request has a traceable request ID.
- Slow or failing graph nodes are identifiable.
- Model and retrieval cost can be inspected per request.

**Depends On:** Milestones 12 and 13.

## Milestone 23: Evaluation Dataset and Quality Gates

**Objective:** Prevent regressions in factuality, retrieval, citation quality, and explanation style.

**Scope:**

- Add an evaluation dataset for Indonesian political queries across:
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
  - reranker improvement
  - source diversity
  - citation correctness
  - claim groundedness
  - factuality
  - completeness
  - hallucination rate
  - depth adherence
  - Indonesian language/register quality
  - latency
  - cost
  - cache hit rate
- Add CI smoke evals.
- Add scheduled or manually triggered heavier eval workflow.

**Acceptance Criteria:**

- CI catches broken schemas, unsupported citations, and obvious grounding failures.
- Eval results are saved and comparable across runs.
- Heavy evals can run without blocking ordinary feature PRs.

**Depends On:** Milestones 11, 13, 14, and 22.

## Milestone 24: Security, Abuse Prevention, and Reliability Hardening

**Objective:** Harden the app for public or semi-public use.

**Scope:**

- Add input size limits and upload limits.
- Add rate limiting.
- Harden URL fetch behavior against SSRF.
- Add content safety handling for harmful or targeted political abuse.
- Add API timeout budgets.
- Add graceful fallbacks for:
  - search provider failure
  - OCR/vision failure
  - reranker failure
  - LLM failure
  - database degraded state
  - Redis degraded state
- Add privacy-conscious retention for screenshots, user history, and saved topics.

**Acceptance Criteria:**

- Known bad URL patterns are rejected.
- Oversized inputs and files fail safely.
- The product can return partial/uncertain answers instead of crashing.

**Depends On:** Milestones 4, 7, 8, 18, and 21.

## Milestone 25: Deployment and Production Readiness

**Objective:** Prepare the rebuilt system for repeatable cloud deployment and safe operation.

**Scope:**

- Add production Dockerfiles.
- Finalize environment variable documentation.
- Maintain `.github/workflows/ci.yml` as the required PR gate.
- Add deployment workflow/configuration for the selected target:
  - Vercel or equivalent for Next.js frontend.
  - GCP, AWS, Fly, Render, or equivalent for FastAPI and workers.
  - Managed Postgres.
  - Managed Redis with vector support.
- Add database migration workflow.
- Add post-deployment smoke tests.
- Add rollback/recovery notes.
- Add an operational runbook.

**Acceptance Criteria:**

- A fresh environment can be deployed from documented steps.
- Health checks cover frontend, backend, database, Redis, workers, and search/model dependencies.
- Deployment workflow runs smoke tests after deploy.
- Rollback/recovery steps are documented.

**Depends On:** Milestones 22, 23, and 24.

## First Production MVP

The first serious release should include Milestones 1 through 13.5.

That release should support:

- topic, question, headline, pasted text, and URL input
- Quick Read and In Depth modes
- analytical lens selection
- fresh external retrieval through a live search provider
- hybrid retrieval over ingested sources
- LangGraph routing
- live model routing through Cohere
- production Redis for cache, checkpoints, rate limits, workers, and vector index readiness
- evidence-grounded explanations
- claim-level citations
- explicit uncertainty and disagreement
- streaming frontend responses
- CI checks for frontend and backend, plus secret-gated provider smoke checks

It can defer:

- screenshot upload
- quizzes
- saved topics
- topic graph traversal
- full user accounts
- heavy observability dashboards

## Implementation Notes

- Use LangGraph for typed orchestration, not unconstrained autonomous behavior.
- Keep graph nodes specialized, structured, and independently testable.
- Use Aya Expanse for text reasoning and synthesis only after retrieval.
- Use Aya Vision only for screenshot/image parsing.
- Use embeddings only for semantic retrieval, semantic cache, and related similarity operations.
- Use Cohere Rerank after broad retrieval, before source diversity selection.
- Store immutable article content and evidence passages so citations remain auditable.
- Keep current-event cache TTLs short and historical/entity cache TTLs longer.
- Build citation validation before advanced product features.
- Treat CI/CD, migrations, health checks, and deployment smoke tests as architecture, not release chores.
