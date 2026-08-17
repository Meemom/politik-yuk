import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.model_providers import EmbeddingRequest, RerankRequest
from app.model_router import ModelRouter
from app.persistence.repositories import RetrievalArticleChunk
from app.schemas import SourceType
from app.search import FreshSearchResponse, SourceCandidate


class RetrievalSource(StrEnum):
    KEYWORD = "keyword"
    VECTOR = "vector"
    EXTERNAL_SEARCH = "external_search"
    RERANK = "rerank"


@dataclass(frozen=True)
class EvidenceCandidate:
    evidence_id: UUID
    source_id: UUID
    article_id: UUID | None
    article_chunk_id: UUID | None
    url: str
    title: str
    publisher: str
    text: str
    source_type: SourceType
    retrieved_at: datetime
    published_at: datetime | None = None
    start_char: int | None = None
    end_char: int | None = None
    relevance_score: float = 0
    recency_score: float = 0
    credibility_score: float = 0
    diversity_score: float = 0
    information_gain_score: float = 0
    final_score: float = 0
    retrieval_sources: tuple[RetrievalSource, ...] = ()
    citation_label: str | None = None


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    evidence: list[EvidenceCandidate]
    warnings: list[str]


class KeywordRetriever(Protocol):
    def retrieve(self, query: str, *, limit: int) -> list[EvidenceCandidate]:
        ...


class VectorRetriever(Protocol):
    async def retrieve(
        self,
        query: str,
        *,
        query_vector: Sequence[float],
        limit: int,
    ) -> list[EvidenceCandidate]:
        ...


class ExternalCandidateProvider(Protocol):
    def search(self, query: str, *, max_results: int) -> FreshSearchResponse:
        ...


class ArticleKeywordRetriever:
    def __init__(self, chunks: Sequence[RetrievalArticleChunk]) -> None:
        self._chunks = list(chunks)

    def retrieve(self, query: str, *, limit: int) -> list[EvidenceCandidate]:
        if not self._chunks:
            return []

        tokenized_docs = [_tokenize(chunk.text) for chunk in self._chunks]
        query_terms = _tokenize(query)
        doc_count = len(tokenized_docs)
        document_frequency = Counter[str]()
        for tokens in tokenized_docs:
            document_frequency.update(set(tokens))

        average_length = sum(len(tokens) for tokens in tokenized_docs) / doc_count
        scored: list[tuple[float, RetrievalArticleChunk]] = []
        for chunk, tokens in zip(self._chunks, tokenized_docs, strict=True):
            score = _bm25_score(
                query_terms=query_terms,
                document_terms=tokens,
                document_frequency=document_frequency,
                document_count=doc_count,
                average_document_length=average_length,
            )
            if score > 0:
                scored.append((score, chunk))

        max_score = max((score for score, _chunk in scored), default=1)
        return [
            _candidate_from_chunk(
                chunk,
                relevance_score=score / max_score,
                retrieval_source=RetrievalSource.KEYWORD,
            )
            for score, chunk in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]
        ]


class InMemoryVectorRetriever:
    def __init__(self, candidates: Sequence[EvidenceCandidate]) -> None:
        self._candidates = list(candidates)

    async def retrieve(
        self,
        query: str,
        *,
        query_vector: Sequence[float],
        limit: int,
    ) -> list[EvidenceCandidate]:
        del query
        scored = [
            replace(
                candidate,
                relevance_score=max(
                    candidate.relevance_score,
                    _cosine_similarity(query_vector, _embedding_from_text(candidate.text)),
                ),
                retrieval_sources=_with_source(
                    candidate.retrieval_sources,
                    RetrievalSource.VECTOR,
                ),
            )
            for candidate in self._candidates
        ]
        return sorted(scored, key=lambda candidate: candidate.relevance_score, reverse=True)[:limit]


class RedisVectorRetriever:
    def __init__(self, redis: Any, *, index_name: str = "idx:article_chunks") -> None:
        self._redis = redis
        self._index_name = index_name

    async def retrieve(
        self,
        query: str,
        *,
        query_vector: Sequence[float],
        limit: int,
    ) -> list[EvidenceCandidate]:
        del query, query_vector, limit
        # Redis vector search is wired as an integration seam. Live hydration of hashes into
        # EvidenceCandidate records belongs with the production Redis schema introduced later.
        if not hasattr(self._redis, "execute_command"):
            return []
        return []


class HybridRetrievalService:
    def __init__(
        self,
        *,
        keyword_retriever: KeywordRetriever,
        vector_retriever: VectorRetriever,
        external_provider: ExternalCandidateProvider,
        model_router: ModelRouter,
        now: datetime | None = None,
    ) -> None:
        self._keyword_retriever = keyword_retriever
        self._vector_retriever = vector_retriever
        self._external_provider = external_provider
        self._model_router = model_router
        self._now = now

    async def retrieve(self, query: str, *, limit: int = 6) -> RetrievalResult:
        now = self._now or datetime.now(UTC)
        warnings: list[str] = []
        keyword_candidates = self._keyword_retriever.retrieve(query, limit=limit * 2)
        embedding = await self._embed_query(query)
        vector_candidates = await self._vector_retriever.retrieve(
            query,
            query_vector=embedding,
            limit=limit * 2,
        )
        external_response = self._external_provider.search(query, max_results=limit)
        warnings.extend(external_response.warnings)
        external_candidates = [
            _candidate_from_external(candidate, now=now)
            for candidate in external_response.candidates
        ]

        merged = _merge_candidates(
            [*keyword_candidates, *vector_candidates, *external_candidates],
            now=now,
        )
        reranked = await self._rerank(query, merged)
        scored = _score_candidates(reranked, query=query, now=now)
        selected = select_diverse_evidence(scored, limit=limit)
        return RetrievalResult(
            query=query,
            evidence=[
                replace(candidate, citation_label=str(index + 1))
                for index, candidate in enumerate(selected)
            ],
            warnings=warnings,
        )

    async def _embed_query(self, query: str) -> list[float]:
        result = await self._model_router.embed(
            request=EmbeddingRequest(
                texts=[query],
                input_type="search_query",
            )
        )
        if not result.vectors:
            return []
        return result.vectors[0]

    async def _rerank(
        self,
        query: str,
        candidates: list[EvidenceCandidate],
    ) -> list[EvidenceCandidate]:
        if not candidates:
            return []
        result = await self._model_router.rerank(
            RerankRequest(
                query=query,
                documents=[candidate.text for candidate in candidates],
                top_n=len(candidates),
            )
        )
        reranked: list[EvidenceCandidate] = []
        for item in result.results:
            candidate = candidates[item.index]
            reranked.append(
                replace(
                    candidate,
                    relevance_score=max(candidate.relevance_score, item.relevance_score),
                    retrieval_sources=_with_source(
                        candidate.retrieval_sources,
                        RetrievalSource.RERANK,
                    ),
                )
            )
        return reranked


def select_diverse_evidence(
    candidates: Sequence[EvidenceCandidate],
    *,
    limit: int,
    max_per_publisher: int = 2,
) -> list[EvidenceCandidate]:
    selected: list[EvidenceCandidate] = []
    publisher_counts: Counter[str] = Counter()
    seen_urls: set[str] = set()
    for candidate in sorted(candidates, key=lambda item: item.final_score, reverse=True):
        if candidate.url in seen_urls:
            continue
        if publisher_counts[candidate.publisher] >= max_per_publisher:
            continue
        selected.append(candidate)
        seen_urls.add(candidate.url)
        publisher_counts[candidate.publisher] += 1
        if len(selected) == limit:
            break
    return selected


def _candidate_from_chunk(
    chunk: RetrievalArticleChunk,
    *,
    relevance_score: float,
    retrieval_source: RetrievalSource,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        evidence_id=uuid4(),
        source_id=chunk.article_id,
        article_id=chunk.article_id,
        article_chunk_id=chunk.chunk_id,
        url=chunk.url,
        title=chunk.title,
        publisher=chunk.publisher,
        text=chunk.text,
        source_type=chunk.source_type,
        retrieved_at=chunk.retrieved_at,
        published_at=chunk.published_at,
        start_char=chunk.start_char,
        end_char=chunk.end_char,
        relevance_score=relevance_score,
        retrieval_sources=(retrieval_source,),
    )


def _candidate_from_external(candidate: SourceCandidate, *, now: datetime) -> EvidenceCandidate:
    return EvidenceCandidate(
        evidence_id=uuid4(),
        source_id=uuid4(),
        article_id=None,
        article_chunk_id=None,
        url=candidate.url,
        title=candidate.title,
        publisher=candidate.publisher,
        text=candidate.snippet,
        source_type=candidate.source_type,
        retrieved_at=now,
        published_at=candidate.published_at,
        relevance_score=candidate.score or 0.5,
        retrieval_sources=(RetrievalSource.EXTERNAL_SEARCH,),
    )


def _merge_candidates(
    candidates: Sequence[EvidenceCandidate],
    *,
    now: datetime,
) -> list[EvidenceCandidate]:
    merged: dict[str, EvidenceCandidate] = {}
    for candidate in candidates:
        key = _dedupe_key(candidate)
        existing = merged.get(key)
        if existing is None:
            merged[key] = candidate
            continue
        merged[key] = replace(
            existing,
            relevance_score=max(existing.relevance_score, candidate.relevance_score),
            recency_score=max(existing.recency_score, _recency_score(candidate, now)),
            retrieval_sources=tuple(
                dict.fromkeys([*existing.retrieval_sources, *candidate.retrieval_sources])
            ),
        )
    return list(merged.values())


def _score_candidates(
    candidates: Sequence[EvidenceCandidate],
    *,
    query: str,
    now: datetime,
) -> list[EvidenceCandidate]:
    selected_tokens: set[str] = set()
    scored: list[EvidenceCandidate] = []
    for candidate in sorted(candidates, key=lambda item: item.relevance_score, reverse=True):
        information_gain = _information_gain(query, candidate.text, selected_tokens)
        selected_tokens.update(_tokenize(candidate.text))
        recency = _recency_score(candidate, now)
        credibility = _credibility_score(candidate.source_type)
        diversity = _publisher_diversity_hint(candidate)
        final_score = (
            0.38 * candidate.relevance_score
            + 0.2 * recency
            + 0.18 * credibility
            + 0.14 * diversity
            + 0.1 * information_gain
        )
        scored.append(
            replace(
                candidate,
                recency_score=recency,
                credibility_score=credibility,
                diversity_score=diversity,
                information_gain_score=information_gain,
                final_score=final_score,
            )
        )
    return scored


def _dedupe_key(candidate: EvidenceCandidate) -> str:
    if candidate.article_chunk_id is not None:
        return str(candidate.article_chunk_id)
    return f"{candidate.url}:{_fingerprint(candidate.text)}"


def _fingerprint(text: str) -> str:
    return " ".join(_tokenize(text)[:32])


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.casefold())


def _bm25_score(
    *,
    query_terms: Sequence[str],
    document_terms: Sequence[str],
    document_frequency: Counter[str],
    document_count: int,
    average_document_length: float,
) -> float:
    if not query_terms or not document_terms:
        return 0
    term_frequency = Counter(document_terms)
    score = 0.0
    k1 = 1.5
    b = 0.75
    for term in query_terms:
        if term not in term_frequency:
            continue
        idf = math.log(
            1
            + (document_count - document_frequency[term] + 0.5)
            / (document_frequency[term] + 0.5)
        )
        denominator = term_frequency[term] + k1 * (
            1 - b + b * len(document_terms) / average_document_length
        )
        score += idf * (term_frequency[term] * (k1 + 1)) / denominator
    return score


def _embedding_from_text(text: str) -> list[float]:
    tokens = _tokenize(text)
    return [float(len(tokens)), float(sum(len(token) for token in tokens)), 1.0]


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right:
        return 0
    size = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(value * value for value in left[:size]))
    right_norm = math.sqrt(sum(value * value for value in right[:size]))
    if left_norm == 0 or right_norm == 0:
        return 0
    return max(min(dot / (left_norm * right_norm), 1), 0)


def _recency_score(candidate: EvidenceCandidate, now: datetime) -> float:
    timestamp = candidate.published_at or candidate.retrieved_at
    age_days = max((now - timestamp).total_seconds() / 86_400, 0)
    return 1 / (1 + age_days / 7)


def _credibility_score(source_type: SourceType) -> float:
    return {
        SourceType.GOVERNMENT: 0.95,
        SourceType.ACADEMIC: 0.9,
        SourceType.CIVIL_SOCIETY: 0.82,
        SourceType.NEWS: 0.74,
        SourceType.INTERNATIONAL_NEWS: 0.72,
        SourceType.OTHER: 0.5,
        SourceType.SOCIAL_MEDIA: 0.32,
    }[source_type]


def _publisher_diversity_hint(candidate: EvidenceCandidate) -> float:
    if candidate.source_type in {SourceType.GOVERNMENT, SourceType.ACADEMIC}:
        return 0.9
    return 0.75


def _information_gain(query: str, text: str, selected_tokens: set[str]) -> float:
    query_tokens = set(_tokenize(query))
    text_tokens = set(_tokenize(text))
    useful_tokens = text_tokens - query_tokens
    if not useful_tokens:
        return 0
    new_tokens = useful_tokens - selected_tokens
    return len(new_tokens) / len(useful_tokens)


def _with_source(
    sources: tuple[RetrievalSource, ...],
    source: RetrievalSource,
) -> tuple[RetrievalSource, ...]:
    if source in sources:
        return sources
    return (*sources, source)
