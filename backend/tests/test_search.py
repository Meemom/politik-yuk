from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.cache.store import CacheStore, InMemoryRedis
from app.main import app
from app.schemas import SourceType
from app.search import (
    ExternalSearchError,
    ExternalSearchResult,
    FreshnessClass,
    FreshSearchService,
    SearchFailureKind,
    search_cache_key,
)

NOW = datetime(2026, 8, 17, 8, 0, tzinfo=UTC)


@dataclass
class FakeSearchProvider:
    results: list[ExternalSearchResult] = field(default_factory=list)
    error: ExternalSearchError | None = None
    calls: int = 0
    provider_name: str = "fake-news-search"

    def search(self, query: str, *, max_results: int) -> list[ExternalSearchResult]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.results[:max_results]


@dataclass
class FakeIngestionDispatcher:
    enqueued: list[tuple[str, str]] = field(default_factory=list)

    def enqueue_article(self, url: str, *, idempotency_key: str) -> str:
        self.enqueued.append((url, idempotency_key))
        return idempotency_key


def make_service(
    provider: FakeSearchProvider,
    dispatcher: FakeIngestionDispatcher | None = None,
) -> FreshSearchService:
    return FreshSearchService(
        provider=provider,
        cache=CacheStore(InMemoryRedis(), key_prefix="test"),
        ingestion_dispatcher=dispatcher,
        now=NOW,
    )


def test_current_topics_produce_fresh_source_candidates_and_ingestion_jobs() -> None:
    provider = FakeSearchProvider(
        results=[
            ExternalSearchResult(
                url="https://news.example/pemilu-terbaru",
                title="KPU umumkan update tahapan pemilu terbaru",
                publisher="Example News",
                snippet="KPU menyampaikan pembaruan tahapan pemilu hari ini.",
                published_at=NOW - timedelta(hours=2),
                source_type=SourceType.NEWS,
                score=0.91,
            ),
            ExternalSearchResult(
                url="https://social.example/post",
                title="Viral post tanpa artikel",
                publisher="Social Example",
                snippet="Unggahan pengguna tentang pemilu.",
                published_at=NOW - timedelta(hours=1),
                source_type=SourceType.SOCIAL_MEDIA,
                score=0.4,
            ),
        ]
    )
    dispatcher = FakeIngestionDispatcher()
    service = make_service(provider, dispatcher)

    response = service.search("update pemilu terbaru", max_results=5)

    assert response.freshness == FreshnessClass.BREAKING_OR_CURRENT
    assert response.provider_failed is False
    assert len(response.candidates) == 2
    assert response.candidates[0].useful_for_ingestion is True
    assert response.candidates[1].useful_for_ingestion is False
    assert dispatcher.enqueued == [
        ("https://news.example/pemilu-terbaru", response.triggered_ingestion_jobs[0])
    ]


def test_fresh_search_uses_cache_before_provider_for_recent_cached_results() -> None:
    provider = FakeSearchProvider(
        results=[
            ExternalSearchResult(
                url="https://news.example/dpr",
                title="Rapat DPR terbaru",
                publisher="Example News",
                snippet="Rapat DPR berlangsung hari ini.",
                published_at=NOW - timedelta(minutes=10),
            )
        ]
    )
    cache = CacheStore(InMemoryRedis(), key_prefix="test")
    service = FreshSearchService(provider=provider, cache=cache, now=NOW)
    first = service.search("rapat DPR hari ini", max_results=5)

    cached_service = FreshSearchService(
        provider=provider,
        cache=cache,
        now=NOW + timedelta(minutes=1),
    )
    second = cached_service.search("rapat DPR hari ini", max_results=5)

    assert first.from_cache is False
    assert second.from_cache is True
    assert second.cache_stale is False
    assert provider.calls == 1


def test_stale_cache_is_not_served_blindly_when_provider_refresh_succeeds() -> None:
    provider = FakeSearchProvider(
        results=[
            ExternalSearchResult(
                url="https://news.example/refreshed",
                title="Refreshed KPU update",
                publisher="Example News",
                snippet="Fresh search result.",
                published_at=NOW - timedelta(minutes=3),
            )
        ]
    )
    cache = CacheStore(InMemoryRedis(), key_prefix="test")
    seed_service = FreshSearchService(provider=provider, cache=cache, now=NOW)
    seed_service.search("KPU update hari ini", max_results=5)

    provider.results = [
        ExternalSearchResult(
            url="https://news.example/newer",
            title="Newer KPU update",
            publisher="Example News",
            snippet="Provider was called again after cache staled.",
            published_at=NOW + timedelta(minutes=4),
        )
    ]
    stale_service = FreshSearchService(
        provider=provider,
        cache=cache,
        now=NOW + timedelta(minutes=10),
    )

    response = stale_service.search("KPU update hari ini", max_results=5)

    assert response.from_cache is False
    assert response.cache_stale is False
    assert response.candidates[0].url == "https://news.example/newer"
    assert provider.calls == 2


def test_provider_failure_returns_clear_partial_response_without_cache() -> None:
    provider = FakeSearchProvider(
        error=ExternalSearchError(
            "search timeout",
            kind=SearchFailureKind.PROVIDER_TIMEOUT,
        )
    )
    service = make_service(provider)

    response = service.search("berita politik terbaru", max_results=5)

    assert response.provider_failed is True
    assert response.from_cache is False
    assert response.candidates == []
    assert response.freshness == FreshnessClass.STALE_OR_NEEDS_REFRESH
    assert response.warnings == ["provider_timeout: search timeout"]


def test_provider_failure_can_return_stale_cached_candidates_with_warning() -> None:
    redis = InMemoryRedis()
    cache = CacheStore(redis, key_prefix="test")
    provider = FakeSearchProvider(
        results=[
            ExternalSearchResult(
                url="https://news.example/old",
                title="Old cabinet update",
                publisher="Example News",
                snippet="Cached result.",
                published_at=NOW - timedelta(days=3),
            )
        ]
    )
    service = FreshSearchService(provider=provider, cache=cache, now=NOW)
    service.search("kabinet update hari ini", max_results=5)
    provider.error = ExternalSearchError("search unavailable")

    degraded = FreshSearchService(
        provider=provider,
        cache=cache,
        now=NOW + timedelta(minutes=20),
    ).search("kabinet update hari ini", max_results=5)

    assert degraded.provider_failed is True
    assert degraded.from_cache is True
    assert degraded.cache_stale is True
    assert degraded.freshness == FreshnessClass.STALE_OR_NEEDS_REFRESH
    assert degraded.candidates[0].url == "https://news.example/old"
    assert degraded.warnings == ["provider_error: search unavailable"]


def test_search_cache_key_normalizes_whitespace() -> None:
    assert search_cache_key("  pemilu   terbaru ", max_results=5) == search_cache_key(
        "pemilu terbaru",
        max_results=5,
    )


def test_search_api_returns_degraded_response_when_provider_is_disabled() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/search/freshness",
        json={"query": "berita politik terbaru", "max_results": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "disabled"
    assert payload["provider_failed"] is True
    assert payload["freshness"] == FreshnessClass.STALE_OR_NEEDS_REFRESH
    assert payload["candidates"] == []
    assert payload["warnings"] == [
        "provider_unavailable: External search provider is not configured."
    ]
