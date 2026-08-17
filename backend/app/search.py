import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from app.cache.store import CacheStore
from app.cache.ttl import TtlClass
from app.jobs import article_pipeline_idempotency_key
from app.schemas import SourceType


class FreshnessClass(StrEnum):
    STABLE_OR_HISTORICAL = "stable_or_historical"
    RECENTLY_ACTIVE = "recently_active"
    BREAKING_OR_CURRENT = "breaking_or_current"
    STALE_OR_NEEDS_REFRESH = "stale_or_needs_refresh"


class SearchFailureKind(StrEnum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_ERROR = "provider_error"


class ExternalSearchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        kind: SearchFailureKind = SearchFailureKind.PROVIDER_ERROR,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable


@dataclass(frozen=True)
class ExternalSearchResult:
    url: str
    title: str
    publisher: str
    snippet: str
    published_at: datetime | None = None
    source_type: SourceType = SourceType.NEWS
    score: float | None = None


@dataclass(frozen=True)
class SourceCandidate:
    query: str
    url: str
    title: str
    publisher: str
    snippet: str
    retrieved_at: datetime
    provider: str
    freshness: FreshnessClass
    published_at: datetime | None = None
    source_type: SourceType = SourceType.NEWS
    score: float | None = None
    useful_for_ingestion: bool = True


@dataclass(frozen=True)
class FreshSearchResponse:
    query: str
    freshness: FreshnessClass
    candidates: list[SourceCandidate]
    provider: str
    from_cache: bool
    cache_stale: bool
    provider_failed: bool
    triggered_ingestion_jobs: list[str]
    warnings: list[str]


class ExternalSearchProvider(Protocol):
    provider_name: str

    def search(self, query: str, *, max_results: int) -> list[ExternalSearchResult]:
        ...


class IngestionDispatcher(Protocol):
    def enqueue_article(self, url: str, *, idempotency_key: str) -> str:
        ...


class NoopIngestionDispatcher:
    def enqueue_article(self, url: str, *, idempotency_key: str) -> str:
        return idempotency_key


class DisabledExternalSearchProvider:
    provider_name = "disabled"

    def search(self, query: str, *, max_results: int) -> list[ExternalSearchResult]:
        raise ExternalSearchError(
            "External search provider is not configured.",
            kind=SearchFailureKind.PROVIDER_UNAVAILABLE,
        )


class FreshnessClassifier:
    _breaking_terms = {
        "baru",
        "barusan",
        "breaking",
        "hari ini",
        "terbaru",
        "update",
        "putusan",
        "rapat",
    }
    _historical_terms = {"sejarah", "historis", "latar belakang", "asal usul"}

    def classify(
        self,
        *,
        query: str,
        now: datetime,
        newest_published_at: datetime | None = None,
        cached_at: datetime | None = None,
    ) -> FreshnessClass:
        if cached_at is not None and self.is_cache_stale(
            query=query,
            freshness=self.classify(query=query, now=now, newest_published_at=newest_published_at),
            cached_at=cached_at,
            now=now,
        ):
            return FreshnessClass.STALE_OR_NEEDS_REFRESH

        normalized_query = query.casefold()
        if any(term in normalized_query for term in self._breaking_terms):
            return FreshnessClass.BREAKING_OR_CURRENT
        if newest_published_at is not None:
            age_seconds = max((now - newest_published_at).total_seconds(), 0)
            if age_seconds <= 2 * 24 * 60 * 60:
                return FreshnessClass.BREAKING_OR_CURRENT
            if age_seconds <= 14 * 24 * 60 * 60:
                return FreshnessClass.RECENTLY_ACTIVE
        if any(term in normalized_query for term in self._historical_terms):
            return FreshnessClass.STABLE_OR_HISTORICAL
        return FreshnessClass.RECENTLY_ACTIVE

    def is_cache_stale(
        self,
        *,
        query: str,
        freshness: FreshnessClass,
        cached_at: datetime,
        now: datetime,
    ) -> bool:
        max_age_seconds = _freshness_ttl_seconds(query=query, freshness=freshness)
        return (now - cached_at).total_seconds() > max_age_seconds


class FreshSearchService:
    def __init__(
        self,
        *,
        provider: ExternalSearchProvider,
        cache: CacheStore,
        ingestion_dispatcher: IngestionDispatcher | None = None,
        classifier: FreshnessClassifier | None = None,
        now: datetime | None = None,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._ingestion_dispatcher = ingestion_dispatcher or NoopIngestionDispatcher()
        self._classifier = classifier or FreshnessClassifier()
        self._now = now

    def search(self, query: str, *, max_results: int = 5) -> FreshSearchResponse:
        normalized_query = _normalize_query(query)
        now = self._current_time()
        cache_key = search_cache_key(normalized_query, max_results=max_results)
        cached = self._cached_response(normalized_query, cache_key, now)
        if cached is not None and not cached.cache_stale:
            return cached

        try:
            raw_results = self._provider.search(normalized_query, max_results=max_results)
        except ExternalSearchError as exc:
            return self._degraded_response(
                query=normalized_query,
                cached=cached,
                provider_failed=True,
                warning=f"{exc.kind.value}: {exc}",
            )

        candidates = self._normalize_results(
            query=normalized_query,
            results=raw_results[:max_results],
            now=now,
        )
        freshness = _response_freshness(normalized_query, candidates, now, self._classifier)
        triggered_jobs = self._trigger_ingestion(candidates)
        response = FreshSearchResponse(
            query=normalized_query,
            freshness=freshness,
            candidates=candidates,
            provider=self._provider.provider_name,
            from_cache=False,
            cache_stale=False,
            provider_failed=False,
            triggered_ingestion_jobs=triggered_jobs,
            warnings=[],
        )
        self._cache_response(cache_key, response)
        return response

    def _cached_response(
        self,
        query: str,
        cache_key: str,
        now: datetime,
    ) -> FreshSearchResponse | None:
        payload = self._cache.get_json("external-search", cache_key)
        if payload is None:
            return None
        response = _response_from_payload(payload)
        cached_at = response.candidates[0].retrieved_at if response.candidates else now
        cache_stale = self._classifier.is_cache_stale(
            query=query,
            freshness=response.freshness,
            cached_at=cached_at,
            now=now,
        )
        if not cache_stale:
            return FreshSearchResponse(
                query=response.query,
                freshness=response.freshness,
                candidates=response.candidates,
                provider=response.provider,
                from_cache=True,
                cache_stale=False,
                provider_failed=False,
                triggered_ingestion_jobs=[],
                warnings=[],
            )
        return FreshSearchResponse(
            query=response.query,
            freshness=FreshnessClass.STALE_OR_NEEDS_REFRESH,
            candidates=response.candidates,
            provider=response.provider,
            from_cache=True,
            cache_stale=True,
            provider_failed=False,
            triggered_ingestion_jobs=[],
            warnings=[],
        )

    def _degraded_response(
        self,
        *,
        query: str,
        cached: FreshSearchResponse | None,
        provider_failed: bool,
        warning: str,
    ) -> FreshSearchResponse:
        if cached is not None:
            return FreshSearchResponse(
                query=query,
                freshness=FreshnessClass.STALE_OR_NEEDS_REFRESH
                if cached.cache_stale
                else cached.freshness,
                candidates=cached.candidates,
                provider=cached.provider,
                from_cache=True,
                cache_stale=cached.cache_stale,
                provider_failed=provider_failed,
                triggered_ingestion_jobs=[],
                warnings=[warning],
            )
        return FreshSearchResponse(
            query=query,
            freshness=FreshnessClass.STALE_OR_NEEDS_REFRESH,
            candidates=[],
            provider=self._provider.provider_name,
            from_cache=False,
            cache_stale=False,
            provider_failed=provider_failed,
            triggered_ingestion_jobs=[],
            warnings=[warning],
        )

    def _normalize_results(
        self,
        *,
        query: str,
        results: list[ExternalSearchResult],
        now: datetime,
    ) -> list[SourceCandidate]:
        newest = max(
            (result.published_at for result in results if result.published_at is not None),
            default=None,
        )
        freshness = self._classifier.classify(
            query=query,
            now=now,
            newest_published_at=newest,
        )
        return [
            SourceCandidate(
                query=query,
                url=result.url,
                title=result.title,
                publisher=result.publisher,
                snippet=result.snippet,
                retrieved_at=now,
                provider=self._provider.provider_name,
                freshness=freshness,
                published_at=result.published_at,
                source_type=result.source_type,
                score=result.score,
                useful_for_ingestion=_is_useful_for_ingestion(result),
            )
            for result in results
        ]

    def _trigger_ingestion(self, candidates: list[SourceCandidate]) -> list[str]:
        job_ids: list[str] = []
        seen_urls: set[str] = set()
        for candidate in candidates:
            if not candidate.useful_for_ingestion or candidate.url in seen_urls:
                continue
            seen_urls.add(candidate.url)
            job_ids.append(
                self._ingestion_dispatcher.enqueue_article(
                    candidate.url,
                    idempotency_key=article_pipeline_idempotency_key(candidate.url),
                )
            )
        return job_ids

    def _cache_response(self, cache_key: str, response: FreshSearchResponse) -> None:
        self._cache.set_json(
            "external-search",
            cache_key,
            _response_to_payload(response),
            _ttl_class_for_freshness(response.freshness),
        )

    def _current_time(self) -> datetime:
        return self._now or datetime.now(UTC)


def search_cache_key(query: str, *, max_results: int) -> str:
    digest = hashlib.sha256(f"{_normalize_query(query)}:{max_results}".encode()).hexdigest()
    return digest


def _normalize_query(query: str) -> str:
    return " ".join(query.strip().split())


def _response_freshness(
    query: str,
    candidates: list[SourceCandidate],
    now: datetime,
    classifier: FreshnessClassifier,
) -> FreshnessClass:
    newest = max(
        (candidate.published_at for candidate in candidates if candidate.published_at is not None),
        default=None,
    )
    return classifier.classify(query=query, now=now, newest_published_at=newest)


def _is_useful_for_ingestion(result: ExternalSearchResult) -> bool:
    return result.url.startswith(("https://", "http://")) and result.source_type in {
        SourceType.GOVERNMENT,
        SourceType.NEWS,
        SourceType.INTERNATIONAL_NEWS,
        SourceType.CIVIL_SOCIETY,
    }


def _ttl_class_for_freshness(freshness: FreshnessClass) -> TtlClass:
    if freshness == FreshnessClass.BREAKING_OR_CURRENT:
        return TtlClass.BREAKING_NEWS
    if freshness == FreshnessClass.STABLE_OR_HISTORICAL:
        return TtlClass.STABLE_HISTORICAL
    return TtlClass.CURRENT_TOPIC


def _freshness_ttl_seconds(*, query: str, freshness: FreshnessClass) -> int:
    if freshness == FreshnessClass.BREAKING_OR_CURRENT:
        return 5 * 60
    if freshness == FreshnessClass.STABLE_OR_HISTORICAL:
        return 24 * 60 * 60
    if any(term in query.casefold() for term in FreshnessClassifier._breaking_terms):
        return 5 * 60
    return 30 * 60


def _response_to_payload(response: FreshSearchResponse) -> dict[str, object]:
    return {
        "query": response.query,
        "freshness": response.freshness.value,
        "provider": response.provider,
        "candidates": [
            {
                "query": candidate.query,
                "url": candidate.url,
                "title": candidate.title,
                "publisher": candidate.publisher,
                "snippet": candidate.snippet,
                "retrieved_at": candidate.retrieved_at.isoformat(),
                "provider": candidate.provider,
                "freshness": candidate.freshness.value,
                "published_at": candidate.published_at.isoformat()
                if candidate.published_at is not None
                else None,
                "source_type": candidate.source_type.value,
                "score": candidate.score,
                "useful_for_ingestion": candidate.useful_for_ingestion,
            }
            for candidate in response.candidates
        ],
    }


def _response_from_payload(payload: dict[str, object]) -> FreshSearchResponse:
    raw_candidates = payload.get("candidates", [])
    if not isinstance(raw_candidates, list):
        raise ValueError("Cached search candidates must be a list.")
    candidates = [_candidate_from_payload(candidate) for candidate in raw_candidates]
    return FreshSearchResponse(
        query=str(payload["query"]),
        freshness=FreshnessClass(str(payload["freshness"])),
        candidates=candidates,
        provider=str(payload["provider"]),
        from_cache=True,
        cache_stale=False,
        provider_failed=False,
        triggered_ingestion_jobs=[],
        warnings=[],
    )


def _candidate_from_payload(payload: object) -> SourceCandidate:
    if not isinstance(payload, dict):
        raise ValueError("Cached search candidate must be an object.")
    published_at = payload.get("published_at")
    score = payload.get("score")
    parsed_published_at = (
        datetime.fromisoformat(str(published_at)) if published_at is not None else None
    )
    return SourceCandidate(
        query=str(payload["query"]),
        url=str(payload["url"]),
        title=str(payload["title"]),
        publisher=str(payload["publisher"]),
        snippet=str(payload["snippet"]),
        retrieved_at=datetime.fromisoformat(str(payload["retrieved_at"])),
        provider=str(payload["provider"]),
        freshness=FreshnessClass(str(payload["freshness"])),
        published_at=parsed_published_at,
        source_type=SourceType(str(payload["source_type"])),
        score=float(score) if score is not None else None,
        useful_for_ingestion=bool(payload["useful_for_ingestion"]),
    )
