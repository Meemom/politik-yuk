from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.cache.checkpoints import SessionCheckpoint, SessionCheckpointStore
from app.cache.ttl import TtlClass
from app.composition import compose_grounded_explanation, validate_explanation_citations
from app.retrieval import RetrievalResult
from app.schemas import (
    AnalyticalLens,
    ExplanationResponse,
    ParsedIntent,
    RetrievalPlan,
    SourceType,
    StreamEvent,
    StreamEventType,
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
    RETRIEVAL_ESCALATOR = "retrieval_escalator"
    ANSWER_COMPOSER = "answer_composer"
    CITATION_VALIDATOR = "citation_validator"


@dataclass(frozen=True)
class RetrievalRouteDecision:
    route: GraphRoute
    needs_freshness: bool
    needs_retrieval: bool
    needs_external_search: bool
    can_escalate: bool
    reason: str


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
    original_route: GraphRoute | None = None
    route_decision: RetrievalRouteDecision | None = None
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

        if self._should_escalate_to_deep(state):
            async for event in self._run_node(state, self._retrieval_escalator):
                yield event
            for node in self._deep_retrieval_nodes():
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
        return self._deep_retrieval_nodes()

    def _deep_retrieval_nodes(self) -> list[NodeHandler]:
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
        decision = _decide_retrieval_route(state.input, topic)
        state.topic = topic
        state.route_decision = decision
        state.route = decision.route
        state.original_route = decision.route
        return GraphNodeOutput(
            node_name=GraphNodeName.INPUT_ROUTER,
            event_type=StreamEventType.REQUEST_RECEIVED,
            message="Request received",
            payload={
                "input_type": state.input.input_type,
                "route": state.route.value,
                "route_reason": decision.reason,
                "needs_retrieval": decision.needs_retrieval,
                "needs_external_search": decision.needs_external_search,
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
        decision = state.route_decision or _decide_retrieval_route(state.input, state.topic)
        state.retrieval_plan = RetrievalPlan(
            queries=[state.topic],
            needs_freshness=decision.needs_freshness,
            needs_vector_search=decision.needs_retrieval,
            needs_keyword_search=decision.needs_retrieval,
            target_source_types=[SourceType.NEWS, SourceType.GOVERNMENT],
            freshness_window_days=14 if decision.needs_freshness else None,
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
                "route_reason": decision.reason,
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

    async def _retrieval_escalator(self, state: ExplanationGraphState) -> GraphNodeOutput:
        previous_route = state.route
        state.route = GraphRoute.DEEP
        state.route_decision = RetrievalRouteDecision(
            route=GraphRoute.DEEP,
            needs_freshness=True,
            needs_retrieval=True,
            needs_external_search=True,
            can_escalate=False,
            reason="short_path_had_no_evidence",
        )
        state.retrieval_plan = RetrievalPlan(
            queries=[state.topic],
            needs_freshness=True,
            needs_vector_search=True,
            needs_keyword_search=True,
            target_source_types=[SourceType.NEWS, SourceType.GOVERNMENT],
            freshness_window_days=14,
        )
        return GraphNodeOutput(
            node_name=GraphNodeName.RETRIEVAL_ESCALATOR,
            event_type=StreamEventType.RETRIEVAL_PLANNED,
            message="Escalating to deep retrieval",
            payload={
                "from_route": previous_route.value if previous_route is not None else None,
                "route": state.route.value,
                "reason": state.route_decision.reason,
                "needs_freshness": True,
                "needs_retrieval": True,
                "needs_external_search": True,
            },
        )

    async def _answer_composer(self, state: ExplanationGraphState) -> GraphNodeOutput:
        state.explanation = compose_grounded_explanation(
            request_id=state.request_id,
            request=state.input,
            intent=state.intent or _fallback_intent(state),
            topic=state.topic,
            evidence_candidates=state.retrieval_result.evidence
            if state.retrieval_result is not None
            else [],
            warnings=state.warnings,
        )
        return GraphNodeOutput(
            node_name=GraphNodeName.ANSWER_COMPOSER,
            event_type=StreamEventType.ANSWER_COMPOSING,
            message="Composing structured answer",
            payload={
                "section_count": len(state.explanation.sections),
                "source_count": len(state.explanation.sources),
            },
        )

    def _should_escalate_to_deep(self, state: ExplanationGraphState) -> bool:
        decision = state.route_decision
        if decision is None or state.route != GraphRoute.SHORT or not decision.can_escalate:
            return False
        return state.retrieval_result is None or not state.retrieval_result.evidence

    async def _citation_validator(self, state: ExplanationGraphState) -> GraphNodeOutput:
        if state.explanation is not None:
            validation = validate_explanation_citations(state.explanation)
            state.explanation = validation.explanation
            state.warnings.extend(validation.warnings)
        citation_count = len(state.explanation.citations) if state.explanation is not None else 0
        return GraphNodeOutput(
            node_name=GraphNodeName.CITATION_VALIDATOR,
            event_type=StreamEventType.CITATIONS_VALIDATED,
            message="Validated citations",
            payload={
                "citation_count": citation_count,
                "valid": state.explanation is not None
                and not validate_explanation_citations(state.explanation).warnings,
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


def _decide_retrieval_route(request: UserInputRequest, topic: str) -> RetrievalRouteDecision:
    deep_input_types = {"headline", "url", "text", "screenshot"}
    if request.depth == "in_depth" or request.input_type in deep_input_types:
        return _deep_route_decision("depth_or_input_requires_evidence")
    if request.input_type == "question" and _looks_like_narrow_lookup(topic):
        return RetrievalRouteDecision(
            route=GraphRoute.SHORT,
            needs_freshness=False,
            needs_retrieval=False,
            needs_external_search=False,
            can_escalate=False,
            reason="narrow_lookup_question",
        )
    if request.input_type == "topic" and len(topic.split()) <= 3:
        return RetrievalRouteDecision(
            route=GraphRoute.SHORT,
            needs_freshness=False,
            needs_retrieval=False,
            needs_external_search=False,
            can_escalate=True,
            reason="compact_topic_try_short_first",
        )
    return _deep_route_decision("default_political_context_requires_evidence")


def _deep_route_decision(reason: str) -> RetrievalRouteDecision:
    return RetrievalRouteDecision(
        route=GraphRoute.DEEP,
        needs_freshness=True,
        needs_retrieval=True,
        needs_external_search=True,
        can_escalate=False,
        reason=reason,
    )


def _looks_like_narrow_lookup(topic: str) -> bool:
    normalized = " ".join(topic.casefold().split())
    lookup_prefixes = ("siapa ", "apa itu ", "profil ")
    return len(normalized.split()) <= 6 and normalized.startswith(lookup_prefixes)


def _topic_from_request(request: UserInputRequest) -> str:
    if request.input_type == "url":
        return request.url or "submitted URL"
    if request.input_type == "screenshot":
        return request.text or "uploaded screenshot"
    return request.text or "political topic"


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
        "original_route": state.original_route.value if state.original_route is not None else None,
        "route_decision": _route_decision_payload(state.route_decision),
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
        "original_route": state.original_route.value if state.original_route is not None else None,
        "route_decision": _route_decision_payload(state.route_decision),
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


def _route_decision_payload(decision: RetrievalRouteDecision | None) -> dict[str, object] | None:
    if decision is None:
        return None
    return {
        "route": decision.route.value,
        "needs_freshness": decision.needs_freshness,
        "needs_retrieval": decision.needs_retrieval,
        "needs_external_search": decision.needs_external_search,
        "can_escalate": decision.can_escalate,
        "reason": decision.reason,
    }
