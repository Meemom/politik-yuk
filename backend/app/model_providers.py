import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ModelRoute(StrEnum):
    TEXT_GENERATION = "text_generation"
    STRUCTURED_GENERATION = "structured_generation"
    IMAGE_ANALYSIS = "image_analysis"
    EMBEDDING = "embedding"
    RERANKING = "reranking"


class ModelErrorKind(StrEnum):
    AUTHENTICATION = "authentication"
    CONFIGURATION = "configuration"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    TRANSIENT = "transient"
    INVALID_RESPONSE = "invalid_response"
    PERMANENT = "permanent"


class ModelProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        kind: ModelErrorKind,
        provider: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.provider = provider
        self.retryable = retryable


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class GenerateTextRequest:
    prompt: str
    system_prompt: str | None = None
    temperature: float = 0.2
    max_tokens: int = 1_024
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class GenerateTextResult:
    text: str
    model: str
    provider: str
    usage: ModelUsage | None = None


@dataclass(frozen=True)
class GenerateStructuredRequest:
    prompt: str
    schema: Mapping[str, object]
    system_prompt: str | None = None
    temperature: float = 0.1
    max_tokens: int = 1_024
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class GenerateStructuredResult:
    data: Mapping[str, object]
    model: str
    provider: str
    usage: ModelUsage | None = None


@dataclass(frozen=True)
class ImageAnalysisRequest:
    prompt: str
    image_bytes: bytes | None = None
    image_uri: str | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class ImageAnalysisResult:
    text: str
    model: str
    provider: str
    usage: ModelUsage | None = None


@dataclass(frozen=True)
class EmbeddingRequest:
    texts: Sequence[str]
    input_type: str = "search_document"
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    provider: str


@dataclass(frozen=True)
class RerankRequest:
    query: str
    documents: Sequence[str]
    top_n: int | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class RerankResultItem:
    index: int
    document: str
    relevance_score: float


@dataclass(frozen=True)
class RerankResult:
    results: list[RerankResultItem]
    model: str
    provider: str


class TextGenerationProvider(Protocol):
    async def generate_text(self, request: GenerateTextRequest) -> GenerateTextResult:
        ...


class StructuredGenerationProvider(Protocol):
    async def generate_structured(
        self,
        request: GenerateStructuredRequest,
    ) -> GenerateStructuredResult:
        ...


class ImageAnalysisProvider(Protocol):
    async def analyze_image(self, request: ImageAnalysisRequest) -> ImageAnalysisResult:
        ...


class EmbeddingProvider(Protocol):
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        ...


class RerankingProvider(Protocol):
    async def rerank(self, request: RerankRequest) -> RerankResult:
        ...


@dataclass(frozen=True)
class ProviderBundle:
    text_generation: TextGenerationProvider
    structured_generation: StructuredGenerationProvider
    image_analysis: ImageAnalysisProvider
    embedding: EmbeddingProvider
    reranking: RerankingProvider


@dataclass
class FakeModelProvider:
    provider_name: str = "fake"
    text_model: str = "c4ai-aya-expanse-32b"
    structured_model: str = "c4ai-aya-expanse-32b"
    vision_model: str = "c4ai-aya-vision-32b"
    embedding_model: str = "intfloat/multilingual-e5-large-instruct"
    rerank_model: str = "cohere-rerank"
    fail_next: dict[ModelRoute, list[ModelProviderError]] = field(default_factory=dict)
    delays: dict[ModelRoute, float] = field(default_factory=dict)
    calls: dict[ModelRoute, int] = field(default_factory=dict)

    def queue_failure(self, route: ModelRoute, error: ModelProviderError) -> None:
        self.fail_next.setdefault(route, []).append(error)

    def set_delay(self, route: ModelRoute, delay_seconds: float) -> None:
        self.delays[route] = delay_seconds

    async def _before_call(self, route: ModelRoute) -> None:
        self.calls[route] = self.calls.get(route, 0) + 1
        delay = self.delays.get(route, 0)
        if delay > 0:
            await asyncio.sleep(delay)
        failures = self.fail_next.get(route, [])
        if failures:
            raise failures.pop(0)

    async def generate_text(self, request: GenerateTextRequest) -> GenerateTextResult:
        await self._before_call(ModelRoute.TEXT_GENERATION)
        return GenerateTextResult(
            text=f"fake-text:{request.prompt[:64]}",
            model=self.text_model,
            provider=self.provider_name,
            usage=ModelUsage(input_tokens=len(request.prompt.split()), output_tokens=2),
        )

    async def generate_structured(
        self,
        request: GenerateStructuredRequest,
    ) -> GenerateStructuredResult:
        await self._before_call(ModelRoute.STRUCTURED_GENERATION)
        return GenerateStructuredResult(
            data={"result": "fake-structured", "schema_keys": sorted(request.schema.keys())},
            model=self.structured_model,
            provider=self.provider_name,
            usage=ModelUsage(input_tokens=len(request.prompt.split()), output_tokens=4),
        )

    async def analyze_image(self, request: ImageAnalysisRequest) -> ImageAnalysisResult:
        await self._before_call(ModelRoute.IMAGE_ANALYSIS)
        image_reference = request.image_uri or f"{len(request.image_bytes or b'')} bytes"
        return ImageAnalysisResult(
            text=f"fake-image-analysis:{image_reference}",
            model=self.vision_model,
            provider=self.provider_name,
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        await self._before_call(ModelRoute.EMBEDDING)
        vectors = [
            [float(len(text)), float(index), 1.0]
            for index, text in enumerate(request.texts)
        ]
        return EmbeddingResult(
            vectors=vectors,
            model=self.embedding_model,
            provider=self.provider_name,
        )

    async def rerank(self, request: RerankRequest) -> RerankResult:
        await self._before_call(ModelRoute.RERANKING)
        ranked = sorted(
            enumerate(request.documents),
            key=lambda item: (request.query.lower() in item[1].lower(), len(item[1])),
            reverse=True,
        )
        if request.top_n is not None:
            ranked = ranked[: request.top_n]
        return RerankResult(
            results=[
                RerankResultItem(index=index, document=document, relevance_score=1 / (rank + 1))
                for rank, (index, document) in enumerate(ranked)
            ],
            model=self.rerank_model,
            provider=self.provider_name,
        )


def fake_provider_bundle(provider: FakeModelProvider | None = None) -> ProviderBundle:
    fake_provider = provider or FakeModelProvider()
    return ProviderBundle(
        text_generation=fake_provider,
        structured_generation=fake_provider,
        image_analysis=fake_provider,
        embedding=fake_provider,
        reranking=fake_provider,
    )
