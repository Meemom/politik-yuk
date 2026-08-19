import os

import pytest

from app.live_search_providers import TavilySearchProvider
from app.model_providers import EmbeddingRequest
from app.model_router import build_model_router
from app.settings import Settings

pytestmark = pytest.mark.live_provider_smoke


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is required for live provider smoke tests.")
    return value


@pytest.mark.anyio
async def test_live_cohere_embedding_smoke() -> None:
    router = build_model_router(
        Settings(
            model_provider_backend="cohere",
            cohere_api_key=_require_env("COHERE_API_KEY"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "embed-v4.0"),
            model_timeout_seconds=10,
            model_max_retries=0,
        )
    )

    result = await router.embed(
        EmbeddingRequest(texts=["Pemilu Indonesia terbaru"], input_type="search_query")
    )

    assert len(result.vectors) == 1
    assert result.vectors[0]
    assert result.provider == "cohere"


def test_live_tavily_search_smoke() -> None:
    provider = TavilySearchProvider(
        api_key=_require_env("TAVILY_API_KEY"),
        timeout_seconds=10,
    )

    results = provider.search("berita politik Indonesia terbaru", max_results=3)

    assert results
    assert all(result.url.startswith(("http://", "https://")) for result in results)
