import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.model_providers import EmbeddingResult, RerankResult, RerankResultItem
from app.persistence.repositories import RetrievalArticleChunk
from app.retrieval import (
    ArticleKeywordRetriever,
    EvidenceCandidate,
    HybridRetrievalService,
    RetrievalSource,
    select_diverse_evidence,
)
from app.schemas import SourceType
from app.search import FreshnessClass, FreshSearchResponse, SourceCandidate

NOW = datetime(2026, 8, 17, 8, 0, tzinfo=UTC)


class FakeModelRouter:
    async def embed(self, request: object) -> EmbeddingResult:
        return EmbeddingResult(vectors=[[4.0, 18.0, 1.0]], model="fake-embed", provider="fake")

    async def rerank(self, request: object) -> RerankResult:
        documents = list(request.documents)
        return RerankResult(
            results=[
                RerankResultItem(index=index, document=document, relevance_score=0)
                for index, document in enumerate(documents)
            ],
            model="fake-rerank",
            provider="fake",
        )


@dataclass
class StaticVectorRetriever:
    candidates: list[EvidenceCandidate]

    async def retrieve(
        self,
        query: str,
        *,
        query_vector: list[float],
        limit: int,
    ) -> list[EvidenceCandidate]:
        del query, query_vector
        return self.candidates[:limit]


@dataclass
class StaticExternalProvider:
    candidates: list[SourceCandidate]
    warnings: list[str] | None = None

    def search(self, query: str, *, max_results: int) -> FreshSearchResponse:
        return FreshSearchResponse(
            query=query,
            freshness=FreshnessClass.RECENTLY_ACTIVE,
            candidates=self.candidates[:max_results],
            provider="fake-search",
            from_cache=False,
            cache_stale=False,
            provider_failed=False,
            triggered_ingestion_jobs=[],
            warnings=self.warnings or [],
        )


def chunk(
    *,
    text: str,
    publisher: str = "Example News",
    published_at: datetime | None = None,
    source_type: SourceType = SourceType.NEWS,
) -> RetrievalArticleChunk:
    return RetrievalArticleChunk(
        chunk_id=uuid4(),
        article_id=uuid4(),
        url=f"https://{publisher.casefold().replace(' ', '-')}.example/{uuid4()}",
        title="Political source",
        publisher=publisher,
        text=text,
        source_type=source_type,
        retrieved_at=NOW,
        published_at=published_at or NOW,
        start_char=0,
        end_char=len(text),
    )


def candidate(
    *,
    url: str,
    publisher: str,
    text: str,
    relevance_score: float,
    published_at: datetime,
    source_type: SourceType = SourceType.NEWS,
    chunk_id: UUID | None = None,
    sources: tuple[RetrievalSource, ...] = (RetrievalSource.VECTOR,),
) -> EvidenceCandidate:
    return EvidenceCandidate(
        evidence_id=uuid4(),
        source_id=uuid4(),
        article_id=uuid4(),
        article_chunk_id=chunk_id,
        url=url,
        title="Evidence title",
        publisher=publisher,
        text=text,
        source_type=source_type,
        retrieved_at=NOW,
        published_at=published_at,
        relevance_score=relevance_score,
        retrieval_sources=sources,
    )


def test_keyword_retriever_ranks_bm25_matches_and_preserves_citation_metadata() -> None:
    recent_chunk = chunk(
        text="KPU menjelaskan tahapan pemilu dan jadwal pemilih muda.",
        publisher="KPU",
        source_type=SourceType.GOVERNMENT,
    )
    unrelated_chunk = chunk(text="Harga cabai naik di beberapa pasar.")
    retriever = ArticleKeywordRetriever([unrelated_chunk, recent_chunk])

    results = retriever.retrieve("tahapan pemilu KPU", limit=3)

    assert len(results) == 1
    assert results[0].article_chunk_id == recent_chunk.chunk_id
    assert results[0].article_id == recent_chunk.article_id
    assert results[0].url == recent_chunk.url
    assert results[0].publisher == "KPU"
    assert results[0].start_char == 0
    assert results[0].end_char == len(recent_chunk.text)
    assert results[0].retrieval_sources == (RetrievalSource.KEYWORD,)


def test_hybrid_retrieval_deduplicates_keyword_and_vector_candidates() -> None:
    shared_chunk = chunk(text="Mahkamah Konstitusi memutus sengketa pemilu terbaru.")
    keyword = ArticleKeywordRetriever([shared_chunk])
    duplicate_vector = candidate(
        url=shared_chunk.url,
        publisher=shared_chunk.publisher,
        text=shared_chunk.text,
        relevance_score=0.99,
        published_at=NOW,
        chunk_id=shared_chunk.chunk_id,
    )
    service = HybridRetrievalService(
        keyword_retriever=keyword,
        vector_retriever=StaticVectorRetriever([duplicate_vector]),
        external_provider=StaticExternalProvider([]),
        model_router=FakeModelRouter(),
        now=NOW,
    )

    result = asyncio.run(service.retrieve("sengketa pemilu terbaru", limit=3))

    assert len(result.evidence) == 1
    assert set(result.evidence[0].retrieval_sources) == {
        RetrievalSource.KEYWORD,
        RetrievalSource.VECTOR,
        RetrievalSource.RERANK,
    }
    assert result.evidence[0].citation_label == "1"


def test_hybrid_retrieval_balances_recency_over_stale_high_relevance() -> None:
    old = candidate(
        url="https://old.example/pemilu",
        publisher="Old News",
        text="KPU membahas pemilu dan jadwal lama.",
        relevance_score=0.75,
        published_at=NOW - timedelta(days=180),
    )
    fresh = candidate(
        url="https://fresh.example/pemilu",
        publisher="Fresh News",
        text="KPU membahas pemilu dan jadwal terbaru hari ini.",
        relevance_score=0.7,
        published_at=NOW - timedelta(hours=2),
    )
    service = HybridRetrievalService(
        keyword_retriever=ArticleKeywordRetriever([]),
        vector_retriever=StaticVectorRetriever([old, fresh]),
        external_provider=StaticExternalProvider([]),
        model_router=FakeModelRouter(),
        now=NOW,
    )

    result = asyncio.run(service.retrieve("KPU pemilu jadwal terbaru", limit=2))

    assert result.evidence[0].url == "https://fresh.example/pemilu"
    assert result.evidence[0].recency_score > result.evidence[1].recency_score


def test_source_diversity_selection_limits_duplicate_reporting() -> None:
    candidates = [
        candidate(
            url=f"https://same.example/{index}",
            publisher="Same News",
            text=f"Same outlet report {index}",
            relevance_score=0.99 - index * 0.01,
            published_at=NOW,
        )
        for index in range(4)
    ]
    candidates.append(
        candidate(
            url="https://different.example/story",
            publisher="Different News",
            text="Independent reporting with added context.",
            relevance_score=0.65,
            published_at=NOW,
        )
    )
    scored = [
        EvidenceCandidate(**{**item.__dict__, "final_score": item.relevance_score})
        for item in candidates
    ]

    selected = select_diverse_evidence(scored, limit=3, max_per_publisher=2)

    assert [item.publisher for item in selected] == ["Same News", "Same News", "Different News"]


def test_external_search_candidates_merge_with_retrieved_evidence() -> None:
    external_candidate = SourceCandidate(
        query="pemilu muda",
        url="https://external.example/pemilih-muda",
        title="Pemilih muda menjadi perhatian",
        publisher="External News",
        snippet="Pemilih muda dibahas dalam aturan pemilu terbaru.",
        retrieved_at=NOW,
        provider="fake-search",
        freshness=FreshnessClass.BREAKING_OR_CURRENT,
        published_at=NOW - timedelta(minutes=30),
        source_type=SourceType.NEWS,
        score=0.8,
    )
    service = HybridRetrievalService(
        keyword_retriever=ArticleKeywordRetriever([]),
        vector_retriever=StaticVectorRetriever([]),
        external_provider=StaticExternalProvider([external_candidate], warnings=["partial search"]),
        model_router=FakeModelRouter(),
        now=NOW,
    )

    result = asyncio.run(service.retrieve("pemilu muda", limit=2))

    assert result.warnings == ["partial search"]
    assert result.evidence[0].url == "https://external.example/pemilih-muda"
    assert result.evidence[0].retrieval_sources == (
        RetrievalSource.EXTERNAL_SEARCH,
        RetrievalSource.RERANK,
    )
    assert result.evidence[0].citation_label == "1"
