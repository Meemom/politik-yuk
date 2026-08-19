import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.cache.checkpoints import SessionCheckpointStore
from app.cache.store import InMemoryRedis
from app.graph import ExplanationGraph, GraphNodeName, GraphRoute
from app.retrieval import EvidenceCandidate, RetrievalResult, RetrievalSource
from app.schemas import SourceType, StreamEvent, UserInputRequest
from app.search import FreshnessClass, FreshSearchResponse

NOW = datetime(2026, 8, 19, 8, 0, tzinfo=UTC)


@dataclass
class FakeFreshnessProbe:
    calls: int = 0

    def search(self, query: str, *, max_results: int) -> FreshSearchResponse:
        self.calls += 1
        return FreshSearchResponse(
            query=query,
            freshness=FreshnessClass.BREAKING_OR_CURRENT,
            candidates=[],
            provider="fake",
            from_cache=False,
            cache_stale=False,
            provider_failed=False,
            triggered_ingestion_jobs=[],
            warnings=[],
        )


@dataclass
class FakeRetrievalRunner:
    calls: int = 0
    evidence: list[EvidenceCandidate] = field(default_factory=list)

    async def retrieve(self, query: str, *, limit: int) -> RetrievalResult:
        self.calls += 1
        return RetrievalResult(query=query, evidence=self.evidence[:limit], warnings=[])


def make_candidate() -> EvidenceCandidate:
    return EvidenceCandidate(
        evidence_id=uuid4(),
        source_id=uuid4(),
        article_id=uuid4(),
        article_chunk_id=uuid4(),
        url="https://news.example/pemilu",
        title="Pemilu terbaru",
        publisher="Example News",
        text="KPU menjelaskan tahapan pemilu terbaru untuk pemilih muda.",
        source_type=SourceType.NEWS,
        retrieved_at=NOW,
        published_at=NOW,
        relevance_score=0.8,
        final_score=0.82,
        retrieval_sources=(RetrievalSource.KEYWORD, RetrievalSource.RERANK),
        citation_label="1",
    )


async def collect_events(
    graph: ExplanationGraph,
    request: UserInputRequest,
    request_id: UUID | None = None,
) -> list[StreamEvent]:
    return [event async for event in graph.run(request, request_id or uuid4())]


def test_simple_entity_question_uses_short_path_and_skips_retrieval() -> None:
    redis = InMemoryRedis()
    graph = ExplanationGraph(
        checkpoints=SessionCheckpointStore(redis, key_prefix="test"),
        freshness_probe=FakeFreshnessProbe(),
        retrieval_runner=FakeRetrievalRunner(evidence=[make_candidate()]),
    )

    events = asyncio.run(
        collect_events(
            graph,
            UserInputRequest(
                input_type="question",
                text="Siapa ketua KPU?",
                depth="quick",
                lenses=[],
            ),
        )
    )
    graph_payload = events[-1].payload["graph"]
    node_names = [node["node_name"] for node in graph_payload["node_outputs"]]

    assert graph_payload["route"] == GraphRoute.SHORT
    assert GraphNodeName.FRESHNESS_CHECKER not in node_names
    assert GraphNodeName.KEYWORD_RETRIEVER not in node_names
    assert events[-1].payload["explanation"]["citations"][0]["label"] == "1"


def test_current_topic_uses_deep_path_with_freshness_and_retrieval_nodes() -> None:
    freshness = FakeFreshnessProbe()
    retrieval = FakeRetrievalRunner(evidence=[make_candidate()])
    redis = InMemoryRedis()
    graph = ExplanationGraph(
        checkpoints=SessionCheckpointStore(redis, key_prefix="test"),
        freshness_probe=freshness,
        retrieval_runner=retrieval,
    )

    events = asyncio.run(
        collect_events(
            graph,
            UserInputRequest(
                input_type="question",
                text="Apa update pemilu terbaru hari ini?",
                depth="quick",
                lenses=[],
            ),
        )
    )
    graph_payload = events[-1].payload["graph"]
    node_names = [node["node_name"] for node in graph_payload["node_outputs"]]

    assert graph_payload["route"] == GraphRoute.DEEP
    assert GraphNodeName.FRESHNESS_CHECKER in node_names
    assert GraphNodeName.KEYWORD_RETRIEVER in node_names
    assert GraphNodeName.RERANKER in node_names
    assert freshness.calls == 1
    assert retrieval.calls == 1
    assert events[-1].payload["explanation"]["sources"][0]["publisher"] == "Example News"


def test_graph_checkpoints_and_events_are_stored() -> None:
    redis = InMemoryRedis()
    request_id = uuid4()
    checkpoints = SessionCheckpointStore(redis, key_prefix="test")
    graph = ExplanationGraph(
        checkpoints=checkpoints,
        freshness_probe=FakeFreshnessProbe(),
        retrieval_runner=FakeRetrievalRunner(),
    )

    events = asyncio.run(
        collect_events(
            graph,
            UserInputRequest(
                input_type="question",
                text="Siapa ketua KPU?",
                depth="quick",
                lenses=[],
            ),
            request_id=request_id,
        )
    )

    checkpoint = checkpoints.load(str(request_id))
    stored_events = checkpoints.events(str(request_id), limit=20)

    assert events[-1].event_type == "complete"
    assert checkpoint is not None
    assert checkpoint.node_name == GraphNodeName.CITATION_VALIDATOR
    assert checkpoint.state["route"] == GraphRoute.SHORT
    assert stored_events[0]["event_type"] == "complete"
    assert any(event["node_name"] == GraphNodeName.INPUT_ROUTER for event in stored_events)
