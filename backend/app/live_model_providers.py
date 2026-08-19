import base64
import json
from collections.abc import Mapping
from typing import Any

import httpx

from app.model_providers import (
    EmbeddingRequest,
    EmbeddingResult,
    GenerateStructuredRequest,
    GenerateStructuredResult,
    GenerateTextRequest,
    GenerateTextResult,
    ImageAnalysisRequest,
    ImageAnalysisResult,
    ModelErrorKind,
    ModelProviderError,
    ModelUsage,
    ProviderBundle,
    RerankRequest,
    RerankResult,
    RerankResultItem,
)


class CohereModelProvider:
    provider_name = "cohere"

    def __init__(
        self,
        *,
        api_key: str,
        text_model: str,
        structured_model: str,
        vision_model: str,
        embedding_model: str,
        rerank_model: str,
        timeout_seconds: float,
        base_url: str = "https://api.cohere.com",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._text_model = text_model
        self._structured_model = structured_model
        self._vision_model = vision_model
        self._embedding_model = embedding_model
        self._rerank_model = rerank_model
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url.rstrip("/")
        self._client = client

    async def generate_text(self, request: GenerateTextRequest) -> GenerateTextResult:
        payload = await self._post_json(
            "/v2/chat",
            {
                "model": self._text_model,
                "messages": _text_messages(request.prompt, request.system_prompt),
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            },
            timeout=request.timeout_seconds,
        )
        return GenerateTextResult(
            text=_chat_text(payload),
            model=self._text_model,
            provider=self.provider_name,
            usage=_usage(payload),
        )

    async def generate_structured(
        self,
        request: GenerateStructuredRequest,
    ) -> GenerateStructuredResult:
        payload = await self._post_json(
            "/v2/chat",
            {
                "model": self._structured_model,
                "messages": _text_messages(request.prompt, request.system_prompt),
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "response_format": {"type": "json_object", "schema": dict(request.schema)},
            },
            timeout=request.timeout_seconds,
        )
        text = _chat_text(payload)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ModelProviderError(
                "Cohere structured response was not valid JSON.",
                kind=ModelErrorKind.INVALID_RESPONSE,
                provider=self.provider_name,
            ) from exc
        if not isinstance(data, dict):
            raise ModelProviderError(
                "Cohere structured response must be a JSON object.",
                kind=ModelErrorKind.INVALID_RESPONSE,
                provider=self.provider_name,
            )
        return GenerateStructuredResult(
            data=data,
            model=self._structured_model,
            provider=self.provider_name,
            usage=_usage(payload),
        )

    async def analyze_image(self, request: ImageAnalysisRequest) -> ImageAnalysisResult:
        content: list[dict[str, object]] = [{"type": "text", "text": request.prompt}]
        if request.image_uri is not None:
            content.append({"type": "image_url", "image_url": {"url": request.image_uri}})
        elif request.image_bytes is not None:
            encoded = base64.b64encode(request.image_bytes).decode("ascii")
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}
            )
        else:
            raise ModelProviderError(
                "Image analysis requires image bytes or an image URI.",
                kind=ModelErrorKind.CONFIGURATION,
                provider=self.provider_name,
            )
        payload = await self._post_json(
            "/v2/chat",
            {
                "model": self._vision_model,
                "messages": [{"role": "user", "content": content}],
            },
            timeout=request.timeout_seconds,
        )
        return ImageAnalysisResult(
            text=_chat_text(payload),
            model=self._vision_model,
            provider=self.provider_name,
            usage=_usage(payload),
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        payload = await self._post_json(
            "/v2/embed",
            {
                "model": self._embedding_model,
                "texts": list(request.texts),
                "input_type": request.input_type,
                "embedding_types": ["float"],
            },
            timeout=request.timeout_seconds,
        )
        vectors = _embedding_vectors(payload)
        return EmbeddingResult(
            vectors=vectors,
            model=self._embedding_model,
            provider=self.provider_name,
        )

    async def rerank(self, request: RerankRequest) -> RerankResult:
        payload = await self._post_json(
            "/v2/rerank",
            {
                "model": self._rerank_model,
                "query": request.query,
                "documents": list(request.documents),
                "top_n": request.top_n,
            },
            timeout=request.timeout_seconds,
        )
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise ModelProviderError(
                "Cohere rerank response did not include results.",
                kind=ModelErrorKind.INVALID_RESPONSE,
                provider=self.provider_name,
            )
        return RerankResult(
            results=[
                RerankResultItem(
                    index=int(item["index"]),
                    document=request.documents[int(item["index"])],
                    relevance_score=float(item["relevance_score"]),
                )
                for item in raw_results
                if isinstance(item, dict)
            ],
            model=self._rerank_model,
            provider=self.provider_name,
        )

    async def _post_json(
        self,
        path: str,
        payload: Mapping[str, object],
        *,
        timeout: float | None,
    ) -> dict[str, Any]:
        client = self._client or httpx.AsyncClient(timeout=timeout or self._timeout_seconds)
        owns_client = self._client is None
        try:
            response = await client.post(
                f"{self._base_url}{path}",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout or self._timeout_seconds,
            )
            if response.status_code >= 400:
                raise _cohere_http_error(response)
            parsed = response.json()
        except httpx.TimeoutException as exc:
            raise ModelProviderError(
                "Cohere request timed out.",
                kind=ModelErrorKind.TIMEOUT,
                provider=self.provider_name,
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise ModelProviderError(
                f"Cohere request failed: {exc}",
                kind=ModelErrorKind.TRANSIENT,
                provider=self.provider_name,
                retryable=True,
            ) from exc
        finally:
            if owns_client:
                await client.aclose()
        if not isinstance(parsed, dict):
            raise ModelProviderError(
                "Cohere response must be a JSON object.",
                kind=ModelErrorKind.INVALID_RESPONSE,
                provider=self.provider_name,
            )
        return parsed


def cohere_provider_bundle(provider: CohereModelProvider) -> ProviderBundle:
    return ProviderBundle(
        text_generation=provider,
        structured_generation=provider,
        image_analysis=provider,
        embedding=provider,
        reranking=provider,
    )


def _text_messages(prompt: str, system_prompt: str | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages


def _chat_text(payload: Mapping[str, Any]) -> str:
    message = payload.get("message")
    if not isinstance(message, dict):
        raise ModelProviderError(
            "Cohere chat response did not include a message.",
            kind=ModelErrorKind.INVALID_RESPONSE,
            provider=CohereModelProvider.provider_name,
        )
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            str(item["text"])
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        if parts:
            return "".join(parts)
    raise ModelProviderError(
        "Cohere chat response did not include text content.",
        kind=ModelErrorKind.INVALID_RESPONSE,
        provider=CohereModelProvider.provider_name,
    )


def _embedding_vectors(payload: Mapping[str, Any]) -> list[list[float]]:
    embeddings = payload.get("embeddings")
    raw_vectors = embeddings.get("float") if isinstance(embeddings, dict) else embeddings
    if not isinstance(raw_vectors, list):
        raise ModelProviderError(
            "Cohere embed response did not include float embeddings.",
            kind=ModelErrorKind.INVALID_RESPONSE,
            provider=CohereModelProvider.provider_name,
        )
    return [
        [float(value) for value in vector]
        for vector in raw_vectors
        if isinstance(vector, list)
    ]


def _usage(payload: Mapping[str, Any]) -> ModelUsage | None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    tokens = usage.get("tokens")
    if not isinstance(tokens, dict):
        return None
    input_tokens = tokens.get("input_tokens")
    output_tokens = tokens.get("output_tokens")
    total_tokens = tokens.get("total_tokens")
    return ModelUsage(
        input_tokens=int(input_tokens) if input_tokens is not None else None,
        output_tokens=int(output_tokens) if output_tokens is not None else None,
        total_tokens=int(total_tokens) if total_tokens is not None else None,
    )


def _cohere_http_error(response: httpx.Response) -> ModelProviderError:
    kind = ModelErrorKind.PERMANENT
    retryable = False
    if response.status_code in {401, 403}:
        kind = ModelErrorKind.AUTHENTICATION
    elif response.status_code == 429:
        kind = ModelErrorKind.RATE_LIMIT
        retryable = True
    elif response.status_code in {408, 504}:
        kind = ModelErrorKind.TIMEOUT
        retryable = True
    elif response.status_code >= 500:
        kind = ModelErrorKind.TRANSIENT
        retryable = True
    return ModelProviderError(
        f"Cohere returned HTTP {response.status_code}.",
        kind=kind,
        provider=CohereModelProvider.provider_name,
        retryable=retryable,
    )
