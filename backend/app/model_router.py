import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from app.model_providers import (
    EmbeddingRequest,
    EmbeddingResult,
    FakeModelProvider,
    GenerateStructuredRequest,
    GenerateStructuredResult,
    GenerateTextRequest,
    GenerateTextResult,
    ImageAnalysisRequest,
    ImageAnalysisResult,
    ModelErrorKind,
    ModelProviderError,
    ModelRoute,
    ProviderBundle,
    RerankRequest,
    RerankResult,
    fake_provider_bundle,
)
from app.settings import Settings

TResult = TypeVar("TResult")


@dataclass(frozen=True)
class ModelRouterConfig:
    text_generation_model: str
    structured_generation_model: str
    image_analysis_model: str
    embedding_model: str
    reranking_model: str
    timeout_seconds: float = 30
    max_retries: int = 2


class ModelRouter:
    def __init__(self, providers: ProviderBundle, config: ModelRouterConfig) -> None:
        self._providers = providers
        self._config = config

    async def generate_text(self, request: GenerateTextRequest) -> GenerateTextResult:
        return await self._call_with_retries(
            ModelRoute.TEXT_GENERATION,
            request.timeout_seconds,
            lambda: self._providers.text_generation.generate_text(request),
        )

    async def generate_structured(
        self,
        request: GenerateStructuredRequest,
    ) -> GenerateStructuredResult:
        return await self._call_with_retries(
            ModelRoute.STRUCTURED_GENERATION,
            request.timeout_seconds,
            lambda: self._providers.structured_generation.generate_structured(request),
        )

    async def analyze_image(self, request: ImageAnalysisRequest) -> ImageAnalysisResult:
        return await self._call_with_retries(
            ModelRoute.IMAGE_ANALYSIS,
            request.timeout_seconds,
            lambda: self._providers.image_analysis.analyze_image(request),
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        return await self._call_with_retries(
            ModelRoute.EMBEDDING,
            request.timeout_seconds,
            lambda: self._providers.embedding.embed(request),
        )

    async def rerank(self, request: RerankRequest) -> RerankResult:
        return await self._call_with_retries(
            ModelRoute.RERANKING,
            request.timeout_seconds,
            lambda: self._providers.reranking.rerank(request),
        )

    async def _call_with_retries(
        self,
        route: ModelRoute,
        timeout_seconds: float | None,
        operation: Callable[[], Awaitable[TResult]],
    ) -> TResult:
        timeout = timeout_seconds or self._config.timeout_seconds
        attempts = self._config.max_retries + 1
        last_error: ModelProviderError | None = None

        for attempt in range(attempts):
            try:
                return await asyncio.wait_for(operation(), timeout=timeout)
            except TimeoutError as exc:
                last_error = ModelProviderError(
                    f"{route} timed out after {timeout:g}s.",
                    kind=ModelErrorKind.TIMEOUT,
                    provider="router",
                    retryable=True,
                )
                if attempt == attempts - 1:
                    raise last_error from exc
            except ModelProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt == attempts - 1:
                    raise

        if last_error is not None:
            raise last_error
        raise ModelProviderError(
            f"{route} failed before provider execution.",
            kind=ModelErrorKind.PERMANENT,
            provider="router",
        )


def model_router_config_from_settings(settings: Settings) -> ModelRouterConfig:
    return ModelRouterConfig(
        text_generation_model=settings.text_generation_model,
        structured_generation_model=settings.structured_generation_model,
        image_analysis_model=settings.image_analysis_model,
        embedding_model=settings.embedding_model,
        reranking_model=settings.reranking_model,
        timeout_seconds=settings.model_timeout_seconds,
        max_retries=settings.model_max_retries,
    )


def build_model_router(
    settings: Settings,
    providers: ProviderBundle | None = None,
) -> ModelRouter:
    if providers is not None:
        return ModelRouter(providers, model_router_config_from_settings(settings))

    if settings.model_provider_backend == "fake":
        provider = FakeModelProvider(
            text_model=settings.text_generation_model,
            structured_model=settings.structured_generation_model,
            vision_model=settings.image_analysis_model,
            embedding_model=settings.embedding_model,
            rerank_model=settings.reranking_model,
        )
        return ModelRouter(
            fake_provider_bundle(provider),
            model_router_config_from_settings(settings),
        )

    raise ModelProviderError(
        f"Model provider backend '{settings.model_provider_backend}' is not configured.",
        kind=ModelErrorKind.CONFIGURATION,
        provider=settings.model_provider_backend,
    )
