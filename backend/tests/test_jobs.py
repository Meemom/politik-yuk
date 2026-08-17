import sqlite3
from dataclasses import dataclass

from app.ingestion.models import (
    IngestionFailureKind,
    IngestionResult,
    IngestionStatus,
)
from app.jobs import (
    ARTICLE_PIPELINE_STAGES,
    ArticlePipelineProcessor,
    article_pipeline_idempotency_key,
)
from app.persistence.migrations import load_migrations
from app.persistence.repositories import PersistenceRepository


@dataclass
class FakeIngestionService:
    results: list[IngestionResult]
    calls: int = 0

    def ingest_url(self, url: str) -> IngestionResult:
        self.calls += 1
        if not self.results:
            raise AssertionError("FakeIngestionService requires at least one result.")
        return self.results.pop(0)


def make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE background_jobs (
            id text PRIMARY KEY,
            idempotency_key text NOT NULL UNIQUE,
            job_type text NOT NULL,
            status text NOT NULL,
            payload text NOT NULL,
            result text,
            error text,
            failure_kind text,
            retryable integer NOT NULL,
            attempts integer NOT NULL,
            max_attempts integer NOT NULL,
            available_at text NOT NULL,
            started_at text,
            finished_at text,
            created_at text NOT NULL,
            updated_at text NOT NULL
        );
        CREATE TABLE worker_heartbeats (
            worker_id text PRIMARY KEY,
            status text NOT NULL,
            last_seen_at text NOT NULL,
            current_job_id text REFERENCES background_jobs(id)
        );
        """
    )
    return connection


def test_article_pipeline_idempotency_key_is_stable() -> None:
    assert article_pipeline_idempotency_key(
        " HTTPS://Example.com/News "
    ) == article_pipeline_idempotency_key(
        "https://example.com/news",
    )


def test_article_pipeline_moves_discovered_url_through_all_stages() -> None:
    repository = PersistenceRepository(make_connection())
    ingestion = FakeIngestionService(
        results=[
            IngestionResult(
                status=IngestionStatus.INGESTED,
                url="https://example.com/news",
                article_id=None,
                chunk_ids=[],
            )
        ]
    )
    processor = ArticlePipelineProcessor(
        repository=repository,
        ingestion_service=ingestion,
        worker_id="worker-1",
    )

    result = processor.process_url("https://example.com/news")
    job = repository.get_background_job_by_idempotency_key(
        article_pipeline_idempotency_key("https://example.com/news")
    )
    health = repository.worker_health("worker-1")

    assert result.status == "succeeded"
    assert result.stages == ARTICLE_PIPELINE_STAGES
    assert job is not None
    assert job.status == "succeeded"
    assert job.attempts == 1
    assert health is not None
    assert health.status == "idle"


def test_re_running_same_job_does_not_duplicate_completed_work() -> None:
    repository = PersistenceRepository(make_connection())
    ingestion = FakeIngestionService(
        results=[
            IngestionResult(
                status=IngestionStatus.DUPLICATE,
                url="https://example.com/news",
                duplicate_of_article_id=None,
            )
        ]
    )
    processor = ArticlePipelineProcessor(
        repository=repository,
        ingestion_service=ingestion,
        worker_id="worker-1",
    )

    first = processor.process_url("https://example.com/news", idempotency_key="same-key")
    second = processor.process_url("https://example.com/news", idempotency_key="same-key")

    assert first.status == "succeeded"
    assert second.status == "succeeded"
    assert ingestion.calls == 1


def test_retryable_partial_failures_are_visible_and_retryable() -> None:
    repository = PersistenceRepository(make_connection())
    ingestion = FakeIngestionService(
        results=[
            IngestionResult(
                status=IngestionStatus.FAILED,
                url="https://example.com/news",
                error="temporary parser outage",
                failure_kind=IngestionFailureKind.PARSE_FAILED,
                retryable=True,
            )
        ]
    )
    processor = ArticlePipelineProcessor(
        repository=repository,
        ingestion_service=ingestion,
        worker_id="worker-1",
    )

    result = processor.process_url("https://example.com/news", idempotency_key="retry-key")
    job = repository.get_background_job_by_idempotency_key("retry-key")

    assert result.status == "retryable"
    assert result.retryable is True
    assert result.error == "temporary parser outage"
    assert job is not None
    assert job.status == "retryable"
    assert job.failure_kind == "parse_failed"
    assert job.retryable is True


def test_migration_manifest_contains_background_job_tables() -> None:
    sql = "\n".join(migration.sql for migration in load_migrations())

    assert "CREATE TABLE background_jobs" in sql
    assert "CREATE TABLE worker_heartbeats" in sql
