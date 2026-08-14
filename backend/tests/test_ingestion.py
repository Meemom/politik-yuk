import sqlite3
from dataclasses import dataclass

from app.ingestion.dedup import content_hash, is_near_duplicate
from app.ingestion.fetcher import ArticleFetcher
from app.ingestion.models import (
    FetchResult,
    IngestionError,
    IngestionFailureKind,
    IngestionStatus,
)
from app.ingestion.parser import parse_article
from app.ingestion.service import ArticleIngestionService
from app.ingestion.url_safety import validate_url_for_ingestion
from app.persistence.repositories import PersistenceRepository

HTML = b"""
<!doctype html>
<html lang="id">
  <head>
    <title>Rapat DPR tentang pemilu</title>
    <link rel="canonical" href="/politik/pemilu" />
    <meta name="author" content="Redaksi Politik" />
    <meta property="og:site_name" content="Example News" />
    <meta property="article:published_time" content="2026-08-13T12:00:00+07:00" />
  </head>
  <body>
    <article>
      <h1>Rapat DPR tentang pemilu</h1>
      <p>KPU menjelaskan tahapan pemilu terbaru kepada anggota DPR.</p>
      <p>Pembahasan ini menjadi penting karena berdampak pada pemilih muda Indonesia.</p>
    </article>
  </body>
</html>
"""


@dataclass
class FakeFetcher(ArticleFetcher):
    result: FetchResult | None = None
    error: IngestionError | None = None
    calls: int = 0

    def fetch(self, url: str) -> FetchResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise AssertionError("FakeFetcher requires result or error.")
        return self.result


def public_resolver(_hostname: str) -> list[str]:
    return ["93.184.216.34"]


def make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE publishers (
            id text PRIMARY KEY,
            name text NOT NULL UNIQUE,
            homepage_url text,
            source_type text NOT NULL,
            created_at text NOT NULL
        );
        CREATE TABLE articles (
            id text PRIMARY KEY,
            publisher_id text NOT NULL REFERENCES publishers(id),
            url text NOT NULL UNIQUE,
            canonical_url text UNIQUE,
            title text NOT NULL,
            author text,
            published_at text,
            retrieved_at text NOT NULL,
            language text NOT NULL,
            source_type text NOT NULL,
            content_hash text,
            body_text text NOT NULL,
            created_at text NOT NULL
        );
        CREATE TABLE article_chunks (
            id text PRIMARY KEY,
            article_id text NOT NULL REFERENCES articles(id),
            chunk_index integer NOT NULL,
            text text NOT NULL,
            start_char integer,
            end_char integer,
            created_at text NOT NULL,
            UNIQUE (article_id, chunk_index)
        );
        CREATE TABLE ingestion_attempts (
            id text PRIMARY KEY,
            url text NOT NULL,
            status text NOT NULL,
            article_id text REFERENCES articles(id),
            duplicate_of_article_id text REFERENCES articles(id),
            error text,
            failure_kind text,
            retryable integer NOT NULL,
            created_at text NOT NULL
        );
        """
    )
    return connection


def test_validate_url_blocks_private_and_local_targets() -> None:
    validate_url_for_ingestion("https://example.com/story", resolver=public_resolver)

    blocked = validate_url_for_ingestion
    for url in ["file:///etc/passwd", "http://localhost:8000", "https://internal.test/story"]:
        try:
            blocked(url, resolver=lambda _hostname: ["10.0.0.1"])
        except IngestionError as exc:
            assert exc.kind == IngestionFailureKind.INVALID_URL
        else:
            raise AssertionError(f"{url} should have been blocked.")


def test_parse_article_extracts_clean_metadata_and_body() -> None:
    parsed = parse_article(
        FetchResult(
            url="https://example.com/input",
            final_url="https://example.com/news/123",
            content_type="text/html; charset=utf-8",
            body=HTML,
        )
    )

    assert parsed.title == "Rapat DPR tentang pemilu"
    assert parsed.canonical_url == "https://example.com/politik/pemilu"
    assert parsed.publisher == "Example News"
    assert parsed.author == "Redaksi Politik"
    assert parsed.published_at is not None
    assert parsed.language == "id"
    assert "pemilih muda Indonesia" in parsed.body_text


def test_ingestion_service_persists_article_chunks_and_attempt() -> None:
    connection = make_connection()
    repository = PersistenceRepository(connection)
    service = ArticleIngestionService(
        repository=repository,
        fetcher=FakeFetcher(
            result=FetchResult(
                url="https://example.com/news/123",
                final_url="https://example.com/news/123",
                content_type="text/html",
                body=HTML,
            )
        ),
        resolver=public_resolver,
    )

    result = service.ingest_url("https://example.com/news/123")

    assert result.status == IngestionStatus.INGESTED
    assert result.article_id is not None
    assert result.content_hash == content_hash(
        "Rapat DPR tentang pemilu KPU menjelaskan tahapan pemilu terbaru kepada anggota DPR. "
        "Pembahasan ini menjadi penting karena berdampak pada pemilih muda Indonesia."
    )
    assert len(result.chunk_ids) == 1
    assert connection.execute("SELECT COUNT(*) FROM articles").fetchone() == (1,)
    assert connection.execute("SELECT COUNT(*) FROM article_chunks").fetchone() == (1,)
    assert connection.execute("SELECT status FROM ingestion_attempts").fetchone() == ("ingested",)


def test_ingestion_service_deduplicates_by_canonical_url_and_hash() -> None:
    connection = make_connection()
    repository = PersistenceRepository(connection)
    fetcher = FakeFetcher(
        result=FetchResult(
            url="https://example.com/news/123",
            final_url="https://example.com/news/123",
            content_type="text/html",
            body=HTML,
        )
    )
    service = ArticleIngestionService(
        repository=repository,
        fetcher=fetcher,
        resolver=public_resolver,
    )

    first = service.ingest_url("https://example.com/news/123")
    duplicate = service.ingest_url("https://example.com/news/123")

    assert first.status == IngestionStatus.INGESTED
    assert duplicate.status == IngestionStatus.DUPLICATE
    assert duplicate.duplicate_of_article_id == first.article_id
    assert connection.execute("SELECT COUNT(*) FROM articles").fetchone() == (1,)
    assert connection.execute("SELECT COUNT(*) FROM ingestion_attempts").fetchone() == (2,)


def test_ingestion_service_records_retryable_fetch_failures() -> None:
    connection = make_connection()
    repository = PersistenceRepository(connection)
    service = ArticleIngestionService(
        repository=repository,
        fetcher=FakeFetcher(
            error=IngestionError(
                "temporary timeout",
                kind=IngestionFailureKind.FETCH_FAILED,
                retryable=True,
            )
        ),
        resolver=public_resolver,
    )

    result = service.ingest_url("https://example.com/news/timeout")

    assert result.status == IngestionStatus.FAILED
    assert result.retryable is True
    failures = repository.recoverable_ingestion_failures()
    assert len(failures) == 1
    assert failures[0].failure_kind == "fetch_failed"
    assert failures[0].error == "temporary timeout"


def test_near_duplicate_similarity_uses_normalized_text() -> None:
    assert is_near_duplicate("KPU menjelaskan tahapan pemilu.", "kpu menjelaskan tahapan pemilu")
