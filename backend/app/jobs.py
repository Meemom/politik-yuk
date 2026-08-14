import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.ingestion.models import IngestionResult, IngestionStatus
from app.persistence.repositories import BackgroundJobRecord, PersistenceRepository


class PipelineStage(StrEnum):
    DISCOVERY = "discovery"
    FETCH = "fetch"
    PARSE = "parse"
    DEDUPLICATE = "deduplicate"
    CLASSIFY = "classify"
    CHUNK = "chunk"
    EMBED = "embed"
    EXTRACT_CLAIMS = "extract_claims"
    EXTRACT_ENTITIES = "extract_entities"
    PERSIST = "persist"
    INDEX = "index"


ARTICLE_PIPELINE_STAGES = [
    PipelineStage.DISCOVERY,
    PipelineStage.FETCH,
    PipelineStage.PARSE,
    PipelineStage.DEDUPLICATE,
    PipelineStage.CLASSIFY,
    PipelineStage.CHUNK,
    PipelineStage.EMBED,
    PipelineStage.EXTRACT_CLAIMS,
    PipelineStage.EXTRACT_ENTITIES,
    PipelineStage.PERSIST,
    PipelineStage.INDEX,
]


@dataclass(frozen=True)
class PipelineRunResult:
    job: BackgroundJobRecord
    status: str
    stages: list[PipelineStage]
    article_id: str | None = None
    duplicate_of_article_id: str | None = None
    error: str | None = None
    retryable: bool = False


class IngestionRunner(Protocol):
    def ingest_url(self, url: str) -> IngestionResult:
        ...


class ArticlePipelineProcessor:
    def __init__(
        self,
        *,
        repository: PersistenceRepository,
        ingestion_service: IngestionRunner,
        worker_id: str,
    ) -> None:
        self._repository = repository
        self._ingestion_service = ingestion_service
        self._worker_id = worker_id

    def process_url(self, url: str, *, idempotency_key: str | None = None) -> PipelineRunResult:
        key = idempotency_key or article_pipeline_idempotency_key(url)
        job = self._repository.enqueue_background_job(
            idempotency_key=key,
            job_type="article_pipeline",
            payload={"url": url},
        )
        if job.status == "succeeded":
            return PipelineRunResult(job=job, status="succeeded", stages=ARTICLE_PIPELINE_STAGES)

        self._repository.record_worker_heartbeat(
            worker_id=self._worker_id,
            status="running",
            current_job_id=job.job_id,
        )
        self._repository.mark_background_job_running(job.job_id)
        ingestion_result = self._ingestion_service.ingest_url(url)

        if ingestion_result.status in {IngestionStatus.INGESTED, IngestionStatus.DUPLICATE}:
            result_payload: dict[str, object] = {
                "ingestion_status": ingestion_result.status.value,
                "stages": [stage.value for stage in ARTICLE_PIPELINE_STAGES],
                "chunk_ids": [str(chunk_id) for chunk_id in ingestion_result.chunk_ids],
            }
            if ingestion_result.article_id is not None:
                result_payload["article_id"] = str(ingestion_result.article_id)
            if ingestion_result.duplicate_of_article_id is not None:
                result_payload["duplicate_of_article_id"] = str(
                    ingestion_result.duplicate_of_article_id
                )
            self._repository.mark_background_job_succeeded(job.job_id, result_payload)
            self._repository.record_worker_heartbeat(worker_id=self._worker_id, status="idle")
            refreshed = self._repository.get_background_job_by_idempotency_key(key) or job
            return PipelineRunResult(
                job=refreshed,
                status="succeeded",
                stages=ARTICLE_PIPELINE_STAGES,
                article_id=str(ingestion_result.article_id)
                if ingestion_result.article_id is not None
                else None,
                duplicate_of_article_id=str(ingestion_result.duplicate_of_article_id)
                if ingestion_result.duplicate_of_article_id is not None
                else None,
            )

        self._repository.mark_background_job_failed(
            job.job_id,
            error=ingestion_result.error or "Article ingestion failed.",
            failure_kind=(
                ingestion_result.failure_kind.value
                if ingestion_result.failure_kind is not None
                else "unknown"
            ),
            retryable=ingestion_result.retryable,
        )
        self._repository.record_worker_heartbeat(worker_id=self._worker_id, status="idle")
        refreshed = self._repository.get_background_job_by_idempotency_key(key) or job
        return PipelineRunResult(
            job=refreshed,
            status=refreshed.status,
            stages=ARTICLE_PIPELINE_STAGES,
            error=ingestion_result.error,
            retryable=ingestion_result.retryable,
        )


def article_pipeline_idempotency_key(url: str) -> str:
    digest = hashlib.sha256(url.strip().lower().encode("utf-8")).hexdigest()
    return f"article_pipeline:{digest}"
