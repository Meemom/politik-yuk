import json

import httpx
import pytest

from app.live_model_providers import CohereModelProvider
from app.live_search_providers import BraveSearchProvider, TavilySearchProvider
from app.model_providers import (
    EmbeddingRequest,
    GenerateStructuredRequest,
    GenerateTextRequest,
    ModelErrorKind,
    ModelProviderError,
    RerankRequest,
)
from app.schemas import SourceType
from app.search import ExternalSearchError, SearchFailureKind


@pytest.mark.anyio
async def test_cohere_provider_maps_text_embed_and_rerank_responses() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v2/chat":
            return httpx.Response(
                200,
                json={
                    "message": {"content": [{"type": "text", "text": "Ringkasan singkat."}]},
                    "usage": {"tokens": {"input_tokens": 4, "output_tokens": 2}},
                },
            )
        if request.url.path == "/v2/embed":
            return httpx.Response(200, json={"embeddings": {"float": [[0.1, 0.2, 0.3]]}})
        if request.url.path == "/v2/rerank":
            return httpx.Response(
                200,
                json={"results": [{"index": 1, "relevance_score": 0.91}]},
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://fake")
    provider = CohereModelProvider(
        api_key="test-key",
        text_model="aya-text",
        structured_model="aya-structured",
        vision_model="aya-vision",
        embedding_model="embed-model",
        rerank_model="rerank-model",
        timeout_seconds=1,
        base_url="https://fake",
        client=client,
    )

    text = await provider.generate_text(GenerateTextRequest(prompt="Jelaskan pemilu"))
    embedding = await provider.embed(EmbeddingRequest(texts=["pemilu"]))
    rerank = await provider.rerank(RerankRequest(query="pemilu", documents=["ekonomi", "pemilu"]))

    assert text.text == "Ringkasan singkat."
    assert text.usage is not None
    assert text.usage.input_tokens == 4
    assert embedding.vectors == [[0.1, 0.2, 0.3]]
    assert rerank.results[0].document == "pemilu"
    assert requests[0].headers["authorization"] == "Bearer test-key"
    await client.aclose()


@pytest.mark.anyio
async def test_cohere_provider_validates_structured_json() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"content": [{"type": "text", "text": "{\"answer\":\"ya\"}"}]}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://fake")
    provider = CohereModelProvider(
        api_key="test-key",
        text_model="aya-text",
        structured_model="aya-structured",
        vision_model="aya-vision",
        embedding_model="embed-model",
        rerank_model="rerank-model",
        timeout_seconds=1,
        base_url="https://fake",
        client=client,
    )

    result = await provider.generate_structured(
        GenerateStructuredRequest(prompt="JSON", schema={"type": "object"})
    )

    assert result.data == {"answer": "ya"}
    await client.aclose()


@pytest.mark.anyio
async def test_cohere_provider_classifies_auth_errors() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "bad key"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://fake")
    provider = CohereModelProvider(
        api_key="bad-key",
        text_model="aya-text",
        structured_model="aya-structured",
        vision_model="aya-vision",
        embedding_model="embed-model",
        rerank_model="rerank-model",
        timeout_seconds=1,
        base_url="https://fake",
        client=client,
    )

    with pytest.raises(ModelProviderError) as exc_info:
        await provider.generate_text(GenerateTextRequest(prompt="Halo"))

    assert exc_info.value.kind == ModelErrorKind.AUTHENTICATION
    assert exc_info.value.retryable is False
    await client.aclose()


def test_tavily_provider_maps_news_results_and_domain_policy() -> None:
    seen_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payload.update(json.loads(request.content.decode()))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://kpu.go.id/berita/pemilu",
                        "title": "KPU jelaskan tahapan pemilu",
                        "content": "KPU menyampaikan jadwal terbaru.",
                        "published_date": "2026-08-19T08:00:00Z",
                        "score": 0.88,
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://fake")
    provider = TavilySearchProvider(
        api_key="tvly-test",
        timeout_seconds=1,
        include_domains=["kpu.go.id"],
        exclude_domains=["example.com"],
        base_url="https://fake",
        client=client,
    )

    results = provider.search("update pemilu terbaru", max_results=3)

    assert seen_payload["topic"] == "news"
    assert seen_payload["include_domains"] == ["kpu.go.id"]
    assert results[0].publisher == "kpu.go.id"
    assert results[0].source_type == SourceType.GOVERNMENT
    assert results[0].score == 0.88
    client.close()


def test_brave_provider_maps_news_and_web_results_without_duplicates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-subscription-token"] == "brave-test"
        assert request.url.params["country"] == "ID"
        return httpx.Response(
            200,
            json={
                "news": {
                    "results": [
                        {
                            "url": "https://news.example/pemilu",
                            "title": "Pemilu hari ini",
                            "description": "Ringkasan berita.",
                            "profile": {"name": "News Example"},
                        }
                    ]
                },
                "web": {
                    "results": [
                        {
                            "url": "https://news.example/pemilu",
                            "title": "Duplikat",
                            "description": "Duplikat.",
                        },
                        {
                            "url": "https://perludem.org/pemilu",
                            "title": "Analisis Perludem",
                            "description": "Analisis masyarakat sipil.",
                        },
                    ]
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://fake")
    provider = BraveSearchProvider(
        api_key="brave-test",
        timeout_seconds=1,
        base_url="https://fake",
        client=client,
    )

    results = provider.search("pemilu", max_results=5)

    assert [result.url for result in results] == [
        "https://news.example/pemilu",
        "https://perludem.org/pemilu",
    ]
    assert results[1].source_type == SourceType.CIVIL_SOCIETY
    client.close()


def test_tavily_provider_classifies_timeout_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(504, json={"error": "timeout"})

    provider = TavilySearchProvider(
        api_key="tvly-test",
        timeout_seconds=1,
        base_url="https://fake",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://fake"),
    )

    with pytest.raises(ExternalSearchError) as exc_info:
        provider.search("pemilu", max_results=1)

    assert exc_info.value.kind == SearchFailureKind.PROVIDER_TIMEOUT
