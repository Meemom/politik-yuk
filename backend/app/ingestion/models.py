from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.schemas import SourceType


class IngestionStatus(StrEnum):
    INGESTED = "ingested"
    DUPLICATE = "duplicate"
    FAILED = "failed"


class IngestionFailureKind(StrEnum):
    INVALID_URL = "invalid_url"
    FETCH_FAILED = "fetch_failed"
    PARSE_FAILED = "parse_failed"
    PERSIST_FAILED = "persist_failed"


class IngestionError(Exception):
    def __init__(
        self,
        message: str,
        *,
        kind: IngestionFailureKind,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str
    content_type: str
    body: bytes


@dataclass(frozen=True)
class ParsedArticle:
    url: str
    canonical_url: str | None
    title: str
    publisher: str
    author: str | None
    published_at: datetime | None
    retrieved_at: datetime
    body_text: str
    language: str
    source_type: SourceType = SourceType.NEWS


@dataclass(frozen=True)
class ArticleChunk:
    chunk_index: int
    text: str
    start_char: int
    end_char: int


@dataclass(frozen=True)
class IngestionResult:
    status: IngestionStatus
    url: str
    article_id: UUID | None = None
    duplicate_of_article_id: UUID | None = None
    content_hash: str | None = None
    chunk_ids: list[UUID] = field(default_factory=list)
    error: str | None = None
    failure_kind: IngestionFailureKind | None = None
    retryable: bool = False
