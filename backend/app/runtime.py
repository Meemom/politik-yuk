from dataclasses import dataclass
from typing import cast

from app.cache.redis_client import create_redis_client
from app.cache.store import CacheStore, InMemoryRedis, RedisLike
from app.live_search_providers import BraveSearchProvider, TavilySearchProvider
from app.model_router import ModelRouter, build_model_router
from app.search import (
    DisabledExternalSearchProvider,
    ExternalSearchError,
    ExternalSearchProvider,
    ExternalSearchResult,
    FreshSearchService,
    SearchFailureKind,
)
from app.settings import Settings


class RuntimeDependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeStatus:
    name: str
    status: str
    detail: str | None = None


def build_runtime_model_router(settings: Settings) -> ModelRouter:
    return build_model_router(settings)


def build_external_search_provider(settings: Settings) -> ExternalSearchProvider:
    provider = settings.external_search_provider.casefold()
    include_domains = _split_csv(settings.external_search_include_domains)
    exclude_domains = _split_csv(settings.external_search_exclude_domains)
    if provider == "disabled":
        return DisabledExternalSearchProvider()
    if provider == "tavily":
        if not settings.tavily_api_key:
            return MisconfiguredExternalSearchProvider(
                provider_name="tavily",
                message="TAVILY_API_KEY is required when EXTERNAL_SEARCH_PROVIDER=tavily.",
            )
        return TavilySearchProvider(
            api_key=settings.tavily_api_key,
            timeout_seconds=settings.external_search_timeout_seconds,
            search_depth=settings.external_search_depth,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
        )
    if provider == "brave":
        if not settings.brave_search_api_key:
            return MisconfiguredExternalSearchProvider(
                provider_name="brave",
                message="BRAVE_SEARCH_API_KEY is required when EXTERNAL_SEARCH_PROVIDER=brave.",
            )
        return BraveSearchProvider(
            api_key=settings.brave_search_api_key,
            timeout_seconds=settings.external_search_timeout_seconds,
        )
    return MisconfiguredExternalSearchProvider(
        provider_name=provider,
        message=f"External search provider '{settings.external_search_provider}' is not supported.",
    )


def build_fresh_search_service(settings: Settings) -> FreshSearchService:
    provider = build_external_search_provider(settings)
    cache = CacheStore(
        runtime_redis(
            settings,
            purpose="external search cache",
            require_live=provider.provider_name != "disabled" and not is_test_runtime(settings),
        ),
        key_prefix=settings.redis_key_prefix,
    )
    return FreshSearchService(provider=provider, cache=cache)


def runtime_redis(settings: Settings, *, purpose: str, require_live: bool) -> RedisLike:
    if not require_live:
        return InMemoryRedis()
    try:
        redis = create_redis_client(settings)
        redis.ping()
        return cast(RedisLike, redis)
    except Exception as exc:
        if _allow_inmemory_redis(settings):
            return InMemoryRedis()
        if require_live:
            raise RuntimeDependencyError(f"Redis is required for {purpose}: {exc}") from exc
        return InMemoryRedis()


def readiness_status(settings: Settings) -> list[RuntimeStatus]:
    statuses = [
        _model_status(settings),
        _search_status(settings),
        _postgres_status(settings),
        _redis_status(settings),
        _worker_queue_status(settings),
    ]
    return statuses


class MisconfiguredExternalSearchProvider:
    def __init__(self, *, provider_name: str, message: str) -> None:
        self.provider_name = provider_name
        self._message = message

    def search(self, query: str, *, max_results: int) -> list[ExternalSearchResult]:
        raise ExternalSearchError(
            self._message,
            kind=SearchFailureKind.PROVIDER_UNAVAILABLE,
            retryable=False,
        )


def _model_status(settings: Settings) -> RuntimeStatus:
    backend = settings.model_provider_backend.casefold()
    if backend == "fake":
        return RuntimeStatus("model_provider", "degraded", "fake provider configured")
    if backend == "cohere" and settings.cohere_api_key:
        return RuntimeStatus("model_provider", "ok", "cohere configured")
    if backend == "cohere":
        return RuntimeStatus("model_provider", "degraded", "missing COHERE_API_KEY")
    return RuntimeStatus("model_provider", "degraded", f"unsupported provider: {backend}")


def _search_status(settings: Settings) -> RuntimeStatus:
    provider = settings.external_search_provider.casefold()
    if provider == "disabled":
        return RuntimeStatus("search_provider", "degraded", "external search disabled")
    if provider == "tavily" and settings.tavily_api_key:
        return RuntimeStatus("search_provider", "ok", "tavily configured")
    if provider == "brave" and settings.brave_search_api_key:
        return RuntimeStatus("search_provider", "ok", "brave configured")
    if provider == "tavily":
        return RuntimeStatus("search_provider", "degraded", "missing TAVILY_API_KEY")
    if provider == "brave":
        return RuntimeStatus("search_provider", "degraded", "missing BRAVE_SEARCH_API_KEY")
    return RuntimeStatus("search_provider", "degraded", f"unsupported provider: {provider}")


def _redis_status(settings: Settings) -> RuntimeStatus:
    if _allow_inmemory_redis(settings):
        return RuntimeStatus("redis", "degraded", "in-memory Redis allowed for this environment")
    try:
        redis = create_redis_client(settings)
        redis.ping()
    except Exception as exc:
        return RuntimeStatus("redis", "unavailable", str(exc))
    return RuntimeStatus("redis", "ok", "connected")


def _postgres_status(settings: Settings) -> RuntimeStatus:
    if is_test_runtime(settings):
        return RuntimeStatus("postgres", "degraded", "not checked in test runtime")
    try:
        from app.persistence.connection import postgres_connection

        with postgres_connection(settings) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return RuntimeStatus("postgres", "unavailable", str(exc))
    return RuntimeStatus("postgres", "ok", "connected")


def _worker_queue_status(settings: Settings) -> RuntimeStatus:
    if _allow_inmemory_redis(settings):
        return RuntimeStatus("worker_queue", "degraded", "not checked with in-memory Redis")
    try:
        from redis import Redis

        broker = Redis.from_url(
            settings.worker_broker_url,
            socket_timeout=settings.redis_socket_timeout_seconds,
            socket_connect_timeout=settings.redis_socket_timeout_seconds,
        )
        broker.ping()
    except Exception as exc:
        return RuntimeStatus("worker_queue", "unavailable", str(exc))
    return RuntimeStatus("worker_queue", "ok", "broker connected")


def _allow_inmemory_redis(settings: Settings) -> bool:
    return is_test_runtime(settings) or settings.allow_inmemory_redis


def is_test_runtime(settings: Settings) -> bool:
    return settings.environment.casefold() == "test"


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]
