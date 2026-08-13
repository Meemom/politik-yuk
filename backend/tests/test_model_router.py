import pytest

from app.model_providers import (
    EmbeddingRequest,
    FakeModelProvider,
    GenerateStructuredRequest,
    GenerateTextRequest,
    ImageAnalysisRequest,
    ModelErrorKind,
    ModelProviderError,
    ModelRoute,
    RerankRequest,
    fake_provider_bundle,
)
from app.model_router import ModelRouter, ModelRouterConfig, build_model_router
from app.settings import Settings


def test_build_model_router_uses_fake_provider_without_credentials() -> None:
    router = build_model_router(Settings())

    assert isinstance(router, ModelRouter)


@pytest.mark.anyio
async def test_build_model_router_applies_configured_fake_model_names() -> None:
    router = build_model_router(
        Settings(
            text_generation_model="text-test",
            structured_generation_model="structured-test",
            image_analysis_model="vision-test",
            embedding_model="embedding-test",
            reranking_model="rerank-test",
        )
    )

    text = await router.generate_text(GenerateTextRequest(prompt="Halo"))
    structured = await router.generate_structured(
        GenerateStructuredRequest(prompt="Halo", schema={"type": "object"})
    )
    image = await router.analyze_image(ImageAnalysisRequest(prompt="Halo", image_uri="memory://x"))
    embeddings = await router.embed(EmbeddingRequest(texts=["Halo"]))
    reranked = await router.rerank(RerankRequest(query="Halo", documents=["Halo dunia"]))

    assert text.model == "text-test"
    assert structured.model == "structured-test"
    assert image.model == "vision-test"
    assert embeddings.model == "embedding-test"
    assert reranked.model == "rerank-test"


@pytest.mark.anyio
async def test_model_router_dispatches_all_routes_to_configured_providers() -> None:
    provider = FakeModelProvider()
    router = ModelRouter(
        fake_provider_bundle(provider),
        ModelRouterConfig(
            text_generation_model="c4ai-aya-expanse-32b",
            structured_generation_model="c4ai-aya-expanse-32b",
            image_analysis_model="c4ai-aya-vision-32b",
            embedding_model="intfloat/multilingual-e5-large-instruct",
            reranking_model="cohere-rerank",
        ),
    )

    text = await router.generate_text(GenerateTextRequest(prompt="Jelaskan isu pemilu"))
    structured = await router.generate_structured(
        GenerateStructuredRequest(
            prompt="Buat ringkasan",
            schema={"type": "object", "required": ["summary"]},
        )
    )
    image = await router.analyze_image(
        ImageAnalysisRequest(prompt="Apa isi poster ini?", image_uri="memory://poster.png")
    )
    embeddings = await router.embed(EmbeddingRequest(texts=["pemilu", "partai"]))
    reranked = await router.rerank(
        RerankRequest(
            query="pemilu",
            documents=["dokumen ekonomi", "berita pemilu terbaru"],
            top_n=1,
        )
    )

    assert text.model == "c4ai-aya-expanse-32b"
    assert structured.data == {"result": "fake-structured", "schema_keys": ["required", "type"]}
    assert image.model == "c4ai-aya-vision-32b"
    assert embeddings.vectors == [[6.0, 0.0, 1.0], [6.0, 1.0, 1.0]]
    assert reranked.results[0].document == "berita pemilu terbaru"
    assert provider.calls == {
        ModelRoute.TEXT_GENERATION: 1,
        ModelRoute.STRUCTURED_GENERATION: 1,
        ModelRoute.IMAGE_ANALYSIS: 1,
        ModelRoute.EMBEDDING: 1,
        ModelRoute.RERANKING: 1,
    }


@pytest.mark.anyio
async def test_model_router_retries_retryable_provider_errors() -> None:
    provider = FakeModelProvider()
    provider.queue_failure(
        ModelRoute.TEXT_GENERATION,
        ModelProviderError(
            "rate limited",
            kind=ModelErrorKind.RATE_LIMIT,
            provider="fake",
            retryable=True,
        ),
    )
    router = ModelRouter(
        fake_provider_bundle(provider),
        ModelRouterConfig(
            text_generation_model="c4ai-aya-expanse-32b",
            structured_generation_model="c4ai-aya-expanse-32b",
            image_analysis_model="c4ai-aya-vision-32b",
            embedding_model="intfloat/multilingual-e5-large-instruct",
            reranking_model="cohere-rerank",
            max_retries=1,
        ),
    )

    result = await router.generate_text(GenerateTextRequest(prompt="Retry this"))

    assert result.text == "fake-text:Retry this"
    assert provider.calls[ModelRoute.TEXT_GENERATION] == 2


@pytest.mark.anyio
async def test_model_router_does_not_retry_non_retryable_errors() -> None:
    provider = FakeModelProvider()
    provider.queue_failure(
        ModelRoute.STRUCTURED_GENERATION,
        ModelProviderError(
            "bad key",
            kind=ModelErrorKind.AUTHENTICATION,
            provider="fake",
            retryable=False,
        ),
    )
    router = ModelRouter(
        fake_provider_bundle(provider),
        ModelRouterConfig(
            text_generation_model="c4ai-aya-expanse-32b",
            structured_generation_model="c4ai-aya-expanse-32b",
            image_analysis_model="c4ai-aya-vision-32b",
            embedding_model="intfloat/multilingual-e5-large-instruct",
            reranking_model="cohere-rerank",
            max_retries=3,
        ),
    )

    with pytest.raises(ModelProviderError) as exc_info:
        await router.generate_structured(
            GenerateStructuredRequest(prompt="Fail", schema={"type": "object"})
        )

    assert exc_info.value.kind == ModelErrorKind.AUTHENTICATION
    assert provider.calls[ModelRoute.STRUCTURED_GENERATION] == 1


@pytest.mark.anyio
async def test_model_router_classifies_timeouts_as_retryable_errors() -> None:
    provider = FakeModelProvider()
    provider.set_delay(ModelRoute.EMBEDDING, 0.05)
    router = ModelRouter(
        fake_provider_bundle(provider),
        ModelRouterConfig(
            text_generation_model="c4ai-aya-expanse-32b",
            structured_generation_model="c4ai-aya-expanse-32b",
            image_analysis_model="c4ai-aya-vision-32b",
            embedding_model="intfloat/multilingual-e5-large-instruct",
            reranking_model="cohere-rerank",
            timeout_seconds=0.001,
            max_retries=1,
        ),
    )

    with pytest.raises(ModelProviderError) as exc_info:
        await router.embed(EmbeddingRequest(texts=["lambat"]))

    assert exc_info.value.kind == ModelErrorKind.TIMEOUT
    assert exc_info.value.retryable is True
    assert provider.calls[ModelRoute.EMBEDDING] == 2


def test_unknown_provider_backend_returns_typed_configuration_error() -> None:
    with pytest.raises(ModelProviderError) as exc_info:
        build_model_router(Settings(model_provider_backend="cohere"))

    assert exc_info.value.kind == ModelErrorKind.CONFIGURATION
    assert exc_info.value.provider == "cohere"
