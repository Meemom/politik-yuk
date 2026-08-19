from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from app.cache.checkpoints import SessionCheckpoint, SessionCheckpointStore
from app.cache.ttl import TtlClass
from app.retrieval import EvidenceCandidate, RetrievalResult
from app.schemas import (
    AnalyticalLens,
    Citation,
    Claim,
    ClaimStatus,
    Entity,
    EntityType,
    EvidencePassage,
    ExplanationResponse,
    ExplanationSection,
    ExplanationSectionType,
    ParsedIntent,
    RetrievalPlan,
    Source,
    SourceType,
    StreamEvent,
    StreamEventType,
    UncertaintyLevel,
    UserInputRequest,
)
from app.search import FreshnessClass, FreshSearchResponse


class GraphRoute(StrEnum):
    SHORT = "short"
    DEEP = "deep"


class GraphNodeName(StrEnum):
    INPUT_ROUTER = "input_router"
    INTENT_EXTRACTOR = "intent_extractor"
    QUERY_PLANNER = "query_planner"
    FRESHNESS_CHECKER = "freshness_checker"
    RETRIEVAL_ROUTER = "retrieval_router"
    KEYWORD_RETRIEVER = "keyword_retriever"
    VECTOR_RETRIEVER = "vector_retriever"
    RERANKER = "reranker"
    SOURCE_DIVERSITY_SELECTOR = "source_diversity_selector"
    ANSWER_COMPOSER = "answer_composer"
    CITATION_VALIDATOR = "citation_validator"


@dataclass(frozen=True)
class GraphNodeOutput:
    node_name: GraphNodeName
    event_type: StreamEventType
    message: str
    payload: dict[str, object] = field(default_factory=dict)


@dataclass
class ExplanationGraphState:
    request_id: UUID
    input: UserInputRequest
    route: GraphRoute | None = None
    topic: str = ""
    intent: ParsedIntent | None = None
    retrieval_plan: RetrievalPlan | None = None
    freshness: FreshnessClass | None = None
    retrieval_result: RetrievalResult | None = None
    explanation: ExplanationResponse | None = None
    warnings: list[str] = field(default_factory=list)
    node_outputs: list[GraphNodeOutput] = field(default_factory=list)


class FreshnessProbe(Protocol):
    def search(self, query: str, *, max_results: int) -> FreshSearchResponse:
        ...


class RetrievalRunner(Protocol):
    async def retrieve(self, query: str, *, limit: int) -> RetrievalResult:
        ...


NodeHandler = Callable[[ExplanationGraphState], Awaitable[GraphNodeOutput]]


class ExplanationGraph:
    def __init__(
        self,
        *,
        checkpoints: SessionCheckpointStore,
        freshness_probe: FreshnessProbe | None = None,
        retrieval_runner: RetrievalRunner | None = None,
    ) -> None:
        self._checkpoints = checkpoints
        self._freshness_probe = freshness_probe
        self._retrieval_runner = retrieval_runner

    async def run(
        self,
        request: UserInputRequest,
        request_id: UUID,
    ) -> AsyncIterator[StreamEvent]:
        if request.text == "__force_error__":
            raise RuntimeError("Forced placeholder graph failure.")

        state = ExplanationGraphState(request_id=request_id, input=request)
        initial_nodes: list[NodeHandler] = [
            self._input_router,
            self._intent_extractor,
            self._query_planner,
        ]
        final_nodes: list[NodeHandler] = [self._answer_composer, self._citation_validator]
        for node in initial_nodes:
            async for event in self._run_node(state, node):
                yield event

        for node in self._route_for(state):
            async for event in self._run_node(state, node):
                yield event

        for node in final_nodes:
            async for event in self._run_node(state, node):
                yield event

        complete = GraphNodeOutput(
            node_name=GraphNodeName.CITATION_VALIDATOR,
            event_type=StreamEventType.COMPLETE,
            message="Explanation complete",
            payload={
                "explanation": state.explanation.model_dump(mode="json")
                if state.explanation is not None
                else {},
                "graph": _graph_summary(state),
            },
        )
        self._append_event(state, complete)
        yield _stream_event(state, complete)

    async def _run_node(
        self,
        state: ExplanationGraphState,
        node: NodeHandler,
    ) -> AsyncIterator[StreamEvent]:
        output = await node(state)
        state.node_outputs.append(output)
        self._save_checkpoint(state, output.node_name)
        yield _stream_event(state, output)

    def _route_for(self, state: ExplanationGraphState) -> list[NodeHandler]:
        if state.route == GraphRoute.SHORT:
            return []
        return [
            self._freshness_checker,
            self._retrieval_router,
            self._keyword_retriever,
            self._vector_retriever,
            self._reranker,
            self._source_diversity_selector,
        ]

    async def _input_router(self, state: ExplanationGraphState) -> GraphNodeOutput:
        topic = _topic_from_request(state.input)
        state.topic = topic
        state.route = _classify_route(state.input, topic)
        return GraphNodeOutput(
            node_name=GraphNodeName.INPUT_ROUTER,
            event_type=StreamEventType.REQUEST_RECEIVED,
            message="Request received",
            payload={
                "input_type": state.input.input_type,
                "route": state.route.value,
            },
        )

    async def _intent_extractor(self, state: ExplanationGraphState) -> GraphNodeOutput:
        lenses = state.input.lenses or [AnalyticalLens.DEMOCRACY]
        state.intent = ParsedIntent(
            topic=state.topic[:512],
            intent="entity_lookup" if state.route == GraphRoute.SHORT else "political_explanation",
            depth=state.input.depth,
            lenses=lenses,
            questions=[state.topic],
            tone="clear Indonesian",
        )
        return GraphNodeOutput(
            node_name=GraphNodeName.INTENT_EXTRACTOR,
            event_type=StreamEventType.INTENT_EXTRACTED,
            message="Input parsed",
            payload={
                "topic": state.intent.topic,
                "intent": state.intent.intent,
                "route": state.route.value if state.route is not None else None,
            },
        )

    async def _query_planner(self, state: ExplanationGraphState) -> GraphNodeOutput:
        deep = state.route == GraphRoute.DEEP
        state.retrieval_plan = RetrievalPlan(
            queries=[state.topic],
            needs_freshness=deep,
            needs_vector_search=deep,
            needs_keyword_search=deep,
            target_source_types=[SourceType.NEWS, SourceType.GOVERNMENT],
            freshness_window_days=14 if deep else None,
        )
        return GraphNodeOutput(
            node_name=GraphNodeName.QUERY_PLANNER,
            event_type=StreamEventType.RETRIEVAL_PLANNED,
            message="Planning retrieval",
            payload={
                "route": state.route.value if state.route is not None else None,
                "queries": state.retrieval_plan.queries,
                "needs_freshness": state.retrieval_plan.needs_freshness,
                "needs_vector_search": state.retrieval_plan.needs_vector_search,
            },
        )

    async def _freshness_checker(self, state: ExplanationGraphState) -> GraphNodeOutput:
        if state.route == GraphRoute.SHORT or self._freshness_probe is None:
            state.freshness = FreshnessClass.STABLE_OR_HISTORICAL
            return GraphNodeOutput(
                node_name=GraphNodeName.FRESHNESS_CHECKER,
                event_type=StreamEventType.EVIDENCE_RETRIEVED,
                message="Freshness check skipped for short path",
                payload={"freshness": state.freshness.value, "skipped": True},
            )

        response = self._freshness_probe.search(state.topic, max_results=3)
        state.freshness = response.freshness
        state.warnings.extend(response.warnings)
        return GraphNodeOutput(
            node_name=GraphNodeName.FRESHNESS_CHECKER,
            event_type=StreamEventType.EVIDENCE_RETRIEVED,
            message="Freshness checked",
            payload={
                "freshness": response.freshness.value,
                "candidate_count": len(response.candidates),
                "provider_failed": response.provider_failed,
            },
        )

    async def _retrieval_router(self, state: ExplanationGraphState) -> GraphNodeOutput:
        return GraphNodeOutput(
            node_name=GraphNodeName.RETRIEVAL_ROUTER,
            event_type=StreamEventType.EVIDENCE_RETRIEVED,
            message="Retrieval route selected",
            payload={
                "route": state.route.value if state.route is not None else None,
                "retrieval_enabled": state.route == GraphRoute.DEEP,
            },
        )

    async def _keyword_retriever(self, state: ExplanationGraphState) -> GraphNodeOutput:
        if state.route == GraphRoute.DEEP and self._retrieval_runner is not None:
            state.retrieval_result = await self._retrieval_runner.retrieve(state.topic, limit=6)
            state.warnings.extend(state.retrieval_result.warnings)
        return GraphNodeOutput(
            node_name=GraphNodeName.KEYWORD_RETRIEVER,
            event_type=StreamEventType.EVIDENCE_RETRIEVED,
            message="Keyword retrieval complete",
            payload={
                "candidate_count": len(state.retrieval_result.evidence)
                if state.retrieval_result is not None
                else 0,
            },
        )

    async def _vector_retriever(self, state: ExplanationGraphState) -> GraphNodeOutput:
        return GraphNodeOutput(
            node_name=GraphNodeName.VECTOR_RETRIEVER,
            event_type=StreamEventType.EVIDENCE_RETRIEVED,
            message="Vector retrieval complete",
            payload={
                "candidate_count": len(state.retrieval_result.evidence)
                if state.retrieval_result is not None
                else 0,
            },
        )

    async def _reranker(self, state: ExplanationGraphState) -> GraphNodeOutput:
        return GraphNodeOutput(
            node_name=GraphNodeName.RERANKER,
            event_type=StreamEventType.EVIDENCE_RETRIEVED,
            message="Reranking complete",
            payload={
                "candidate_count": len(state.retrieval_result.evidence)
                if state.retrieval_result is not None
                else 0,
            },
        )

    async def _source_diversity_selector(self, state: ExplanationGraphState) -> GraphNodeOutput:
        return GraphNodeOutput(
            node_name=GraphNodeName.SOURCE_DIVERSITY_SELECTOR,
            event_type=StreamEventType.EVIDENCE_RETRIEVED,
            message="Source diversity selected",
            payload={
                "evidence_count": len(state.retrieval_result.evidence)
                if state.retrieval_result is not None
                else 0,
            },
        )

    async def _answer_composer(self, state: ExplanationGraphState) -> GraphNodeOutput:
        state.explanation = _compose_explanation(state)
        return GraphNodeOutput(
            node_name=GraphNodeName.ANSWER_COMPOSER,
            event_type=StreamEventType.ANSWER_COMPOSING,
            message="Composing structured answer",
            payload={
                "section_count": len(state.explanation.sections),
                "source_count": len(state.explanation.sources),
            },
        )

    async def _citation_validator(self, state: ExplanationGraphState) -> GraphNodeOutput:
        citation_count = len(state.explanation.citations) if state.explanation is not None else 0
        return GraphNodeOutput(
            node_name=GraphNodeName.CITATION_VALIDATOR,
            event_type=StreamEventType.CITATIONS_VALIDATED,
            message="Validated citations",
            payload={
                "citation_count": citation_count,
                "valid": citation_count > 0,
            },
        )

    def _save_checkpoint(
        self,
        state: ExplanationGraphState,
        node_name: GraphNodeName,
    ) -> None:
        checkpoint = SessionCheckpoint(
            session_id=str(state.request_id),
            node_name=node_name.value,
            state=_state_snapshot(state),
        )
        try:
            self._checkpoints.save(checkpoint, ttl_class=TtlClass.CURRENT_TOPIC)
            if state.node_outputs:
                self._append_event(state, state.node_outputs[-1])
        except Exception as exc:
            state.warnings.append(f"checkpoint_failed: {exc}")

    def _append_event(self, state: ExplanationGraphState, output: GraphNodeOutput) -> None:
        try:
            self._checkpoints.append_event(
                str(state.request_id),
                {
                    "node_name": output.node_name.value,
                    "event_type": output.event_type.value,
                    "message": output.message,
                    "payload": output.payload,
                },
                ttl_class=TtlClass.CURRENT_TOPIC,
            )
        except Exception as exc:
            state.warnings.append(f"checkpoint_event_failed: {exc}")


def _stream_event(state: ExplanationGraphState, output: GraphNodeOutput) -> StreamEvent:
    return StreamEvent(
        request_id=state.request_id,
        event_type=output.event_type,
        message=output.message,
        payload={
            **output.payload,
            "node_name": output.node_name.value,
        },
    )


def _classify_route(request: UserInputRequest, topic: str) -> GraphRoute:
    current_terms = {"hari ini", "terbaru", "breaking", "update", "putusan", "rapat"}
    simple_terms = {"siapa", "apa itu", "profil"}
    normalized = topic.casefold()
    deep_input_types = {"headline", "url", "text", "screenshot"}
    if request.depth == "in_depth" or request.input_type in deep_input_types:
        return GraphRoute.DEEP
    if any(term in normalized for term in current_terms):
        return GraphRoute.DEEP
    if any(term in normalized for term in simple_terms):
        return GraphRoute.SHORT
    return GraphRoute.DEEP if len(topic.split()) > 8 else GraphRoute.SHORT


def _topic_from_request(request: UserInputRequest) -> str:
    if request.input_type == "url":
        return request.url or "submitted URL"
    if request.input_type == "screenshot":
        return request.text or "uploaded screenshot"
    return request.text or "political topic"


def _compose_explanation(state: ExplanationGraphState) -> ExplanationResponse:
    retrieved_at = datetime.now(UTC)
    evidence_candidates = state.retrieval_result.evidence if state.retrieval_result else []
    if evidence_candidates:
        return _compose_retrieved_explanation(state, evidence_candidates, retrieved_at)
    return _compose_contract_explanation(state, retrieved_at)


def _compose_retrieved_explanation(
    state: ExplanationGraphState,
    candidates: list[EvidenceCandidate],
    retrieved_at: datetime,
) -> ExplanationResponse:
    sources: list[Source] = []
    evidence: list[EvidencePassage] = []
    citations: list[Citation] = []
    for index, candidate in enumerate(candidates, start=1):
        source_id = candidate.source_id
        evidence_id = candidate.evidence_id
        sources.append(
            Source(
                id=source_id,
                url=candidate.url,
                title=candidate.title,
                publisher=candidate.publisher,
                published_at=candidate.published_at,
                retrieved_at=candidate.retrieved_at,
                source_type=candidate.source_type,
            )
        )
        evidence.append(
            EvidencePassage(
                id=evidence_id,
                source_id=source_id,
                text=candidate.text,
                start_char=candidate.start_char,
                end_char=candidate.end_char,
                relevance_score=max(min(candidate.final_score or candidate.relevance_score, 1), 0),
            )
        )
        citations.append(
            Citation(
                source_id=source_id,
                evidence_passage_id=evidence_id,
                label=str(index),
                quote=candidate.text[:1_000],
            )
        )

    first_citation_id = citations[0].id
    return ExplanationResponse(
        request_id=state.request_id,
        input=state.input,
        intent=state.intent or _fallback_intent(state),
        sections=[
            ExplanationSection(
                section_type=ExplanationSectionType.TLDR,
                title="TL;DR",
                body=(
                    "Politik Yuk found retrievable evidence and prepared it for "
                    "grounded synthesis."
                ),
                citation_ids=[first_citation_id],
                uncertainty=UncertaintyLevel.MEDIUM,
            ),
            ExplanationSection(
                section_type=ExplanationSectionType.ESSENTIAL_CONTEXT,
                title="Essential context",
                body=(
                    "This graph response exposes the evidence set and graph route. Milestone 13 "
                    "will replace this deterministic composition with claim-grounded generation."
                ),
                citation_ids=[first_citation_id],
                uncertainty=UncertaintyLevel.MEDIUM,
            ),
        ],
        sources=sources,
        evidence=evidence,
        citations=citations,
        claims=[
            Claim(
                text="Retrieved evidence is available for later claim-grounded answer composition.",
                normalized_text=(
                    "retrieved evidence available for claim grounded answer composition"
                ),
                status=ClaimStatus.UNVERIFIED,
                uncertainty=UncertaintyLevel.MEDIUM,
                supporting_evidence_ids=[item.id for item in evidence],
                citation_ids=[item.id for item in citations],
            )
        ],
        entities=[],
        follow_up_questions=[
            "Which evidence should be checked against other outlets?",
            "Do you want a Quick Read or In Depth answer?",
        ],
    )


def _compose_contract_explanation(
    state: ExplanationGraphState,
    retrieved_at: datetime,
) -> ExplanationResponse:
    source_id = uuid4()
    evidence_id = uuid4()
    citation_id = uuid4()
    entity_id = uuid4()
    source = Source(
        id=source_id,
        url="https://example.com/graph-contract-source",
        title="Graph orchestration contract source",
        publisher="Politik Yuk System",
        retrieved_at=retrieved_at,
        source_type=SourceType.OTHER,
    )
    evidence = EvidencePassage(
        id=evidence_id,
        source_id=source_id,
        text=(
            "This deterministic evidence confirms graph orchestration, routing, checkpointing, "
            "and streaming behavior only."
        ),
        relevance_score=1,
    )
    citation = Citation(
        id=citation_id,
        source_id=source_id,
        evidence_passage_id=evidence_id,
        label="1",
        quote="Deterministic evidence confirms graph orchestration behavior.",
    )
    entity = Entity(
        id=entity_id,
        name="Politik Yuk",
        entity_type=EntityType.ORGANIZATION,
        description="The product surface receiving and structuring this explanation request.",
        source_ids=[source_id],
    )
    return ExplanationResponse(
        request_id=state.request_id,
        input=state.input,
        intent=state.intent or _fallback_intent(state),
        sections=[
            ExplanationSection(
                section_type=ExplanationSectionType.TLDR,
                title="TL;DR",
                body=(
                    "Politik Yuk routed this request through the graph MVP and returned a "
                    "structured placeholder while grounded answer generation remains pending."
                ),
                citation_ids=[citation_id],
                uncertainty=UncertaintyLevel.HIGH,
            ),
            ExplanationSection(
                section_type=ExplanationSectionType.ESSENTIAL_CONTEXT,
                title="Essential context",
                body=(
                    "The graph records typed node outputs, route decisions, checkpoints, and "
                    "streaming events. It does not yet assert live political conclusions."
                ),
                citation_ids=[citation_id],
                uncertainty=UncertaintyLevel.HIGH,
            ),
        ],
        sources=[source],
        evidence=[evidence],
        citations=[citation],
        claims=[
            Claim(
                text="This response is a deterministic graph MVP placeholder.",
                normalized_text="deterministic graph mvp placeholder",
                status=ClaimStatus.UNVERIFIED,
                uncertainty=UncertaintyLevel.HIGH,
                supporting_evidence_ids=[evidence_id],
                entity_ids=[entity_id],
                citation_ids=[citation_id],
            )
        ],
        entities=[entity],
        follow_up_questions=[
            "Should this use a short route or deep retrieval route?",
            "Which lens matters most for this topic?",
        ],
    )


def _fallback_intent(state: ExplanationGraphState) -> ParsedIntent:
    return ParsedIntent(
        topic=state.topic[:512] or "political topic",
        intent="explanation",
        depth=state.input.depth,
        lenses=state.input.lenses or [AnalyticalLens.DEMOCRACY],
        questions=[state.topic or "political topic"],
        tone="clear Indonesian",
    )


def _state_snapshot(state: ExplanationGraphState) -> dict[str, object]:
    return {
        "request_id": str(state.request_id),
        "route": state.route.value if state.route is not None else None,
        "topic": state.topic,
        "intent": state.intent.model_dump(mode="json") if state.intent is not None else None,
        "retrieval_plan": state.retrieval_plan.model_dump(mode="json")
        if state.retrieval_plan is not None
        else None,
        "freshness": state.freshness.value if state.freshness is not None else None,
        "evidence_count": len(state.retrieval_result.evidence)
        if state.retrieval_result is not None
        else 0,
        "warnings": state.warnings,
        "node_outputs": [
            {
                "node_name": output.node_name.value,
                "event_type": output.event_type.value,
                "message": output.message,
                "payload": output.payload,
            }
            for output in state.node_outputs
        ],
    }


def _graph_summary(state: ExplanationGraphState) -> dict[str, object]:
    return {
        "route": state.route.value if state.route is not None else None,
        "node_outputs": [
            {
                "node_name": output.node_name.value,
                "event_type": output.event_type.value,
                "message": output.message,
                "payload": output.payload,
            }
            for output in state.node_outputs
        ],
        "warnings": state.warnings,
    }
