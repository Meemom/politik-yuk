from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.cache.redis_client import RedisConnectionError, create_redis_client
from app.cache.store import CacheStore, InMemoryRedis
from app.search import (
    DisabledExternalSearchProvider,
    FreshnessClass,
    FreshSearchService,
    SourceCandidate,
)
from app.settings import get_settings

router = APIRouter(prefix="/api/search", tags=["search"])


class FreshSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=512)
    max_results: int = Field(default=5, ge=1, le=10)


class SourceCandidateResponse(BaseModel):
    url: str
    title: str
    publisher: str
    snippet: str
    retrieved_at: datetime
    provider: str
    freshness: FreshnessClass
    published_at: datetime | None = None
    source_type: str
    score: float | None = None
    useful_for_ingestion: bool


class FreshSearchResponseModel(BaseModel):
    query: str
    freshness: FreshnessClass
    candidates: list[SourceCandidateResponse]
    provider: str
    from_cache: bool
    cache_stale: bool
    provider_failed: bool
    triggered_ingestion_jobs: list[str]
    warnings: list[str]


def _candidate_response(candidate: SourceCandidate) -> SourceCandidateResponse:
    return SourceCandidateResponse(
        url=candidate.url,
        title=candidate.title,
        publisher=candidate.publisher,
        snippet=candidate.snippet,
        retrieved_at=candidate.retrieved_at,
        provider=candidate.provider,
        freshness=candidate.freshness,
        published_at=candidate.published_at,
        source_type=candidate.source_type.value,
        score=candidate.score,
        useful_for_ingestion=candidate.useful_for_ingestion,
    )


@router.post("/freshness", response_model=FreshSearchResponseModel)
async def fresh_search(request: FreshSearchRequest) -> FreshSearchResponseModel:
    settings = get_settings()
    if settings.external_search_provider == "disabled":
        redis = InMemoryRedis()
    else:
        try:
            redis = create_redis_client(settings)
        except RedisConnectionError:
            redis = InMemoryRedis()
    cache = CacheStore(redis, key_prefix=settings.redis_key_prefix)
    service = FreshSearchService(
        provider=DisabledExternalSearchProvider(),
        cache=cache,
    )
    max_results = min(request.max_results, settings.external_search_max_results)
    result = service.search(request.query, max_results=max_results)
    return FreshSearchResponseModel(
        query=result.query,
        freshness=result.freshness,
        candidates=[_candidate_response(candidate) for candidate in result.candidates],
        provider=result.provider,
        from_cache=result.from_cache,
        cache_stale=result.cache_stale,
        provider_failed=result.provider_failed,
        triggered_ingestion_jobs=result.triggered_ingestion_jobs,
        warnings=result.warnings,
    )
