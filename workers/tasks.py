from app.ingestion.fetcher import UrlLibArticleFetcher
from app.ingestion.service import ArticleIngestionService
from app.jobs import ArticlePipelineProcessor
from app.persistence.connection import postgres_connection
from app.persistence.repositories import PersistenceRepository
from app.settings import get_settings

from workers.celery_app import celery_app


@celery_app.task(name="article_pipeline.process_url", bind=True)
def process_article_url(
    self: object,
    url: str,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    with postgres_connection(settings) as connection:
        repository = PersistenceRepository(connection)
        ingestion_service = ArticleIngestionService(
            repository=repository,
            fetcher=UrlLibArticleFetcher(
                timeout_seconds=settings.ingestion_fetch_timeout_seconds,
                max_bytes=settings.ingestion_max_bytes,
                retries=settings.ingestion_fetch_retries,
            ),
        )
        processor = ArticlePipelineProcessor(
            repository=repository,
            ingestion_service=ingestion_service,
            worker_id=getattr(getattr(self, "request", None), "hostname", "celery-worker"),
        )
        result = processor.process_url(url, idempotency_key=idempotency_key)
        return {
            "job_id": str(result.job.job_id),
            "status": result.status,
            "stages": [stage.value for stage in result.stages],
            "article_id": result.article_id,
            "duplicate_of_article_id": result.duplicate_of_article_id,
            "error": result.error,
            "retryable": result.retryable,
        }
