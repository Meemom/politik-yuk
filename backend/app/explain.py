import json
from collections.abc import AsyncIterator
from typing import cast
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.cache.checkpoints import SessionCheckpointStore
from app.cache.redis_client import RedisConnectionError, create_redis_client
from app.cache.store import CacheStore, InMemoryRedis, RedisLike
from app.graph import ExplanationGraph
from app.model_router import build_model_router
from app.retrieval import ArticleKeywordRetriever, HybridRetrievalService, InMemoryVectorRetriever
from app.schemas import StreamEvent, StreamEventType, UserInputRequest
from app.search import DisabledExternalSearchProvider, FreshSearchService
from app.settings import get_settings

router = APIRouter(prefix="/api", tags=["explain"])


def _sse(event: StreamEvent) -> str:
    payload = event.model_dump(mode="json")
    return f"event: {event.event_type}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


def _validate_request(request: UserInputRequest) -> None:
    if request.input_type == "url" and not request.url:
        raise HTTPException(status_code=422, detail="URL input requires a url value.")
    if request.input_type != "url" and not request.text:
        raise HTTPException(status_code=422, detail="Text input is required for this input type.")


def _make_error_event(request_id: UUID, error: str) -> StreamEvent:
    return StreamEvent(
        request_id=request_id,
        event_type=StreamEventType.ERROR,
        message="Explanation failed",
        payload={"error": error},
    )


def _checkpoint_redis() -> RedisLike:
    settings = get_settings()
    if settings.graph_checkpoint_backend != "redis":
        return InMemoryRedis()
    try:
        return cast(RedisLike, create_redis_client(settings))
    except RedisConnectionError:
        return InMemoryRedis()


def _make_graph() -> ExplanationGraph:
    settings = get_settings()
    redis = _checkpoint_redis()
    checkpoints = SessionCheckpointStore(redis, key_prefix=settings.redis_key_prefix)
    search_cache = CacheStore(InMemoryRedis(), key_prefix=settings.redis_key_prefix)
    freshness_service = FreshSearchService(
        provider=DisabledExternalSearchProvider(),
        cache=search_cache,
    )
    retrieval_service = HybridRetrievalService(
        keyword_retriever=ArticleKeywordRetriever([]),
        vector_retriever=InMemoryVectorRetriever([]),
        external_provider=freshness_service,
        model_router=build_model_router(settings),
    )
    return ExplanationGraph(
        checkpoints=checkpoints,
        freshness_probe=freshness_service,
        retrieval_runner=retrieval_service,
    )


async def _stream_explanation(request: UserInputRequest, request_id: UUID) -> AsyncIterator[str]:
    try:
        graph = _make_graph()
        async for event in graph.run(request, request_id):
            yield _sse(event)
    except Exception as exc:
        yield _sse(_make_error_event(request_id, str(exc)))


@router.post("/explain")
async def explain(request: UserInputRequest) -> StreamingResponse:
    _validate_request(request)
    request_id = uuid4()
    return StreamingResponse(
        _stream_explanation(request, request_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Request-ID": str(request_id),
        },
    )
