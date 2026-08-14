from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID

from app.ingestion.chunker import chunk_text
from app.ingestion.dedup import content_hash, is_near_duplicate
from app.ingestion.fetcher import ArticleFetcher, UrlLibArticleFetcher
from app.ingestion.models import (
    IngestionError,
    IngestionFailureKind,
    IngestionResult,
    IngestionStatus,
    ParsedArticle,
)
from app.ingestion.parser import parse_article
from app.ingestion.url_safety import Resolver, validate_url_for_ingestion
from app.persistence.repositories import PersistenceRepository, StoredArticle


@dataclass(frozen=True)
class ArticleIngestionService:
    repository: PersistenceRepository
    fetcher: ArticleFetcher = UrlLibArticleFetcher()
    resolver: Resolver | None = None
    duplicate_similarity_threshold: float = 0.92

    def ingest_url(self, url: str) -> IngestionResult:
        try:
            safe_url = validate_url_for_ingestion(
                url,
                resolver=self.resolver if self.resolver is not None else _public_resolver,
            )
            fetch_result = self.fetcher.fetch(safe_url)
            article = parse_article(fetch_result)
            article_hash = content_hash(article.body_text)
            duplicate = self.repository.find_article_by_url_or_hash(
                url=article.url,
                canonical_url=article.canonical_url,
                content_hash=article_hash,
            )
            if duplicate is not None and self._is_duplicate(duplicate, article):
                result = IngestionResult(
                    status=IngestionStatus.DUPLICATE,
                    url=article.url,
                    duplicate_of_article_id=duplicate.article_id,
                    content_hash=article_hash,
                )
                self._record_result(result)
                return result
            article_id = self._persist_article(article, article_hash)
            chunk_ids = [
                self.repository.create_article_chunk(
                    article_id=article_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                )
                for chunk in chunk_text(article.body_text)
            ]
            result = IngestionResult(
                status=IngestionStatus.INGESTED,
                url=article.url,
                article_id=article_id,
                content_hash=article_hash,
                chunk_ids=chunk_ids,
            )
            self._record_result(result)
            return result
        except IngestionError as exc:
            result = IngestionResult(
                status=IngestionStatus.FAILED,
                url=url,
                error=str(exc),
                failure_kind=exc.kind,
                retryable=exc.retryable,
            )
            self._record_result(result)
            return result
        except Exception as exc:
            result = IngestionResult(
                status=IngestionStatus.FAILED,
                url=url,
                error=str(exc),
                failure_kind=IngestionFailureKind.PERSIST_FAILED,
                retryable=True,
            )
            self._record_result(result)
            return result

    def _persist_article(self, article: ParsedArticle, article_hash: str) -> UUID:
        publisher_id = self.repository.get_or_create_publisher(
            name=article.publisher,
            source_type=article.source_type,
            homepage_url=_homepage_from_url(article.url),
        )
        return self.repository.create_ingested_article(
            publisher_id=publisher_id,
            url=article.url,
            canonical_url=article.canonical_url,
            title=article.title,
            author=article.author,
            published_at=article.published_at.isoformat() if article.published_at else None,
            retrieved_at=article.retrieved_at.isoformat(),
            language=article.language,
            source_type=article.source_type,
            content_hash=article_hash,
            body_text=article.body_text,
        )

    def _record_result(self, result: IngestionResult) -> None:
        self.repository.record_ingestion_attempt(
            url=result.url,
            status=result.status.value,
            article_id=result.article_id,
            duplicate_of_article_id=result.duplicate_of_article_id,
            error=result.error,
            failure_kind=result.failure_kind.value if result.failure_kind is not None else None,
            retryable=result.retryable,
        )

    def _is_duplicate(self, stored: StoredArticle, article: ParsedArticle) -> bool:
        return (
            stored.url == article.url
            or stored.canonical_url == article.canonical_url
            or stored.content_hash == content_hash(article.body_text)
            or is_near_duplicate(
                stored.body_text,
                article.body_text,
                threshold=self.duplicate_similarity_threshold,
            )
        )


def _homepage_from_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _public_resolver(hostname: str) -> list[str]:
    from app.ingestion.url_safety import default_resolver

    return default_resolver(hostname)
