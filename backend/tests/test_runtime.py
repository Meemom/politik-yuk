import pytest

from app.cache.store import InMemoryRedis
from app.live_search_providers import BraveSearchProvider, TavilySearchProvider
from app.model_providers import ModelErrorKind, ModelProviderError
from app.model_router import build_model_router
from app.runtime import (
    RuntimeDependencyError,
    build_external_search_provider,
    readiness_status,
    runtime_redis,
)
from app.search import ExternalSearchError, SearchFailureKind
from app.settings import Settings


def test_external_search_factory_builds_tavily_provider_when_configured() -> None:
    provider = build_external_search_provider(
        Settings(external_search_provider="tavily", tavily_api_key="tvly-test")
    )

    assert isinstance(provider, TavilySearchProvider)


def test_external_search_factory_builds_brave_provider_when_configured() -> None:
    provider = build_external_search_provider(
        Settings(external_search_provider="brave", brave_search_api_key="brave-test")
    )

    assert isinstance(provider, BraveSearchProvider)


def test_missing_search_secret_degrades_through_provider_error() -> None:
    provider = build_external_search_provider(Settings(external_search_provider="tavily"))

    with pytest.raises(ExternalSearchError) as exc_info:
        provider.search("pemilu", max_results=1)

    assert exc_info.value.kind == SearchFailureKind.PROVIDER_UNAVAILABLE


def test_runtime_redis_allows_memory_only_for_test_or_explicit_local_setting() -> None:
    redis = runtime_redis(
        Settings(environment="test"),
        purpose="tests",
        require_live=False,
    )

    assert isinstance(redis, InMemoryRedis)


def test_runtime_redis_requires_live_redis_for_live_provider_paths() -> None:
    with pytest.raises(RuntimeDependencyError):
        runtime_redis(
            Settings(redis_url="redis://localhost:1/0"),
            purpose="external search cache",
            require_live=True,
        )


def test_model_router_builds_cohere_provider_when_key_is_configured() -> None:
    router = build_model_router(Settings(model_provider_backend="cohere", cohere_api_key="key"))

    assert router is not None


def test_model_router_requires_cohere_key() -> None:
    with pytest.raises(ModelProviderError) as exc_info:
        build_model_router(Settings(model_provider_backend="cohere", cohere_api_key=""))

    assert exc_info.value.kind == ModelErrorKind.CONFIGURATION
    assert exc_info.value.provider == "cohere"


def test_readiness_reports_missing_live_dependencies_without_secrets() -> None:
    statuses = readiness_status(
        Settings(
            model_provider_backend="cohere",
            external_search_provider="tavily",
            cohere_api_key="",
            tavily_api_key="",
            redis_url="redis://localhost:1/0",
        )
    )

    by_name = {status.name: status for status in statuses}

    assert by_name["model_provider"].status == "degraded"
    assert by_name["search_provider"].status == "degraded"
    assert by_name["redis"].status == "unavailable"
