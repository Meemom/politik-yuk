import json
from dataclasses import dataclass
from datetime import UTC, datetime
from sqlite3 import Connection
from typing import Any
from uuid import UUID, uuid4

from app.schemas import ClaimStatus, EntityType, SourceType, UncertaintyLevel


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return str(uuid4())


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


@dataclass(frozen=True)
class ArticleWithEvidence:
    article_id: UUID
    title: str
    url: str
    publisher: str
    claim_text: str
    evidence_text: str
    citation_label: str


@dataclass(frozen=True)
class StoredArticle:
    article_id: UUID
    url: str
    canonical_url: str | None
    content_hash: str | None
    body_text: str


@dataclass(frozen=True)
class IngestionAttemptRecord:
    attempt_id: UUID
    url: str
    status: str
    error: str | None
    failure_kind: str | None
    retryable: bool


@dataclass(frozen=True)
class BackgroundJobRecord:
    job_id: UUID
    idempotency_key: str
    job_type: str
    status: str
    payload: dict[str, object]
    attempts: int
    max_attempts: int
    error: str | None = None
    failure_kind: str | None = None
    retryable: bool = False


@dataclass(frozen=True)
class WorkerHeartbeatRecord:
    worker_id: str
    status: str
    last_seen_at: str
    current_job_id: UUID | None


class PersistenceRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def create_user(self, *, email: str | None = None, locale: str = "id-ID") -> UUID:
        user_id = _new_id()
        self._connection.execute(
            "INSERT INTO users (id, email, locale, created_at) VALUES (?, ?, ?, ?)",
            (user_id, email, locale, _utc_now()),
        )
        self._connection.execute(
            """
            INSERT INTO user_preferences (user_id, reading_level, preferred_lenses, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, "quick", "[]", _utc_now()),
        )
        self._connection.commit()
        return UUID(user_id)

    def create_publisher(
        self,
        *,
        name: str,
        source_type: SourceType = SourceType.NEWS,
        homepage_url: str | None = None,
    ) -> UUID:
        publisher_id = _new_id()
        self._connection.execute(
            """
            INSERT INTO publishers (id, name, homepage_url, source_type, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (publisher_id, name, homepage_url, source_type.value, _utc_now()),
        )
        self._connection.commit()
        return UUID(publisher_id)

    def get_or_create_publisher(
        self,
        *,
        name: str,
        source_type: SourceType = SourceType.NEWS,
        homepage_url: str | None = None,
    ) -> UUID:
        row = self._connection.execute(
            "SELECT id FROM publishers WHERE name = ?",
            (name,),
        ).fetchone()
        if row is not None:
            return UUID(str(row[0]))
        return self.create_publisher(
            name=name,
            source_type=source_type,
            homepage_url=homepage_url,
        )

    def create_article(
        self,
        *,
        publisher_id: UUID,
        url: str,
        title: str,
        body_text: str,
        canonical_url: str | None = None,
        source_type: SourceType = SourceType.NEWS,
        language: str = "id",
    ) -> UUID:
        article_id = _new_id()
        retrieved_at = _utc_now()
        self._connection.execute(
            """
            INSERT INTO articles (
                id,
                publisher_id,
                url,
                canonical_url,
                title,
                retrieved_at,
                language,
                source_type,
                body_text,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article_id,
                str(publisher_id),
                url,
                canonical_url,
                title,
                retrieved_at,
                language,
                source_type.value,
                body_text,
                retrieved_at,
            ),
        )
        self._connection.commit()
        return UUID(article_id)

    def find_article_by_url_or_hash(
        self,
        *,
        url: str,
        canonical_url: str | None,
        content_hash: str,
    ) -> StoredArticle | None:
        rows = self._connection.execute(
            """
            SELECT id, url, canonical_url, content_hash, body_text
            FROM articles
            WHERE url = ?
                OR canonical_url = ?
                OR content_hash = ?
            ORDER BY created_at
            """,
            (url, canonical_url, content_hash),
        ).fetchall()
        if not rows:
            return None
        row = rows[0]
        return StoredArticle(
            article_id=UUID(str(row[0])),
            url=str(row[1]),
            canonical_url=str(row[2]) if row[2] is not None else None,
            content_hash=str(row[3]) if row[3] is not None else None,
            body_text=str(row[4]),
        )

    def create_ingested_article(
        self,
        *,
        publisher_id: UUID,
        url: str,
        title: str,
        body_text: str,
        content_hash: str,
        canonical_url: str | None = None,
        author: str | None = None,
        published_at: str | None = None,
        retrieved_at: str | None = None,
        source_type: SourceType = SourceType.NEWS,
        language: str = "id",
    ) -> UUID:
        article_id = _new_id()
        retrieved_value = retrieved_at or _utc_now()
        self._connection.execute(
            """
            INSERT INTO articles (
                id,
                publisher_id,
                url,
                canonical_url,
                title,
                author,
                published_at,
                retrieved_at,
                language,
                source_type,
                content_hash,
                body_text,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article_id,
                str(publisher_id),
                url,
                canonical_url,
                title,
                author,
                published_at,
                retrieved_value,
                language,
                source_type.value,
                content_hash,
                body_text,
                retrieved_value,
            ),
        )
        self._connection.commit()
        return UUID(article_id)

    def create_article_chunk(
        self,
        *,
        article_id: UUID,
        chunk_index: int,
        text: str,
        start_char: int | None = None,
        end_char: int | None = None,
    ) -> UUID:
        chunk_id = _new_id()
        self._connection.execute(
            """
            INSERT INTO article_chunks (
                id,
                article_id,
                chunk_index,
                text,
                start_char,
                end_char,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (chunk_id, str(article_id), chunk_index, text, start_char, end_char, _utc_now()),
        )
        self._connection.commit()
        return UUID(chunk_id)

    def create_topic(self, *, name: str, summary: str | None = None) -> UUID:
        topic_id = _new_id()
        now = _utc_now()
        self._connection.execute(
            """
            INSERT INTO topics (id, name, normalized_name, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (topic_id, name, _normalize(name), summary, now, now),
        )
        self._connection.commit()
        return UUID(topic_id)

    def create_entity(
        self,
        *,
        name: str,
        entity_type: EntityType,
        description: str | None = None,
    ) -> UUID:
        entity_id = _new_id()
        self._connection.execute(
            """
            INSERT INTO entities (id, name, entity_type, aliases, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (entity_id, name, entity_type.value, "[]", description, _utc_now()),
        )
        self._connection.commit()
        return UUID(entity_id)

    def create_claim(
        self,
        *,
        topic_id: UUID,
        text: str,
        status: ClaimStatus = ClaimStatus.UNVERIFIED,
        uncertainty: UncertaintyLevel = UncertaintyLevel.UNKNOWN,
    ) -> UUID:
        claim_id = _new_id()
        now = _utc_now()
        self._connection.execute(
            """
            INSERT INTO claims (
                id,
                topic_id,
                text,
                normalized_text,
                status,
                uncertainty,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                claim_id,
                str(topic_id),
                text,
                _normalize(text),
                status.value,
                uncertainty.value,
                now,
                now,
            ),
        )
        self._connection.commit()
        return UUID(claim_id)

    def link_claim_entity(self, *, claim_id: UUID, entity_id: UUID) -> None:
        self._connection.execute(
            "INSERT INTO claim_entities (claim_id, entity_id) VALUES (?, ?)",
            (str(claim_id), str(entity_id)),
        )
        self._connection.commit()

    def create_evidence_passage(
        self,
        *,
        article_id: UUID,
        article_chunk_id: UUID,
        claim_id: UUID,
        text: str,
        relevance_score: float,
    ) -> UUID:
        evidence_id = _new_id()
        self._connection.execute(
            """
            INSERT INTO evidence_passages (
                id,
                article_id,
                article_chunk_id,
                claim_id,
                text,
                relevance_score,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                str(article_id),
                str(article_chunk_id),
                str(claim_id),
                text,
                relevance_score,
                _utc_now(),
            ),
        )
        self._connection.execute(
            """
            INSERT INTO claim_evidence (claim_id, evidence_passage_id, stance)
            VALUES (?, ?, ?)
            """,
            (str(claim_id), evidence_id, "supports"),
        )
        self._connection.commit()
        return UUID(evidence_id)

    def create_citation(
        self,
        *,
        article_id: UUID,
        evidence_passage_id: UUID,
        label: str,
        quote: str | None = None,
    ) -> UUID:
        citation_id = _new_id()
        self._connection.execute(
            """
            INSERT INTO citations (
                id,
                source_article_id,
                evidence_passage_id,
                label,
                quote,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (citation_id, str(article_id), str(evidence_passage_id), label, quote, _utc_now()),
        )
        self._connection.commit()
        return UUID(citation_id)

    def save_topic(self, *, user_id: UUID, topic_id: UUID) -> UUID:
        saved_topic_id = _new_id()
        self._connection.execute(
            """
            INSERT INTO saved_topics (id, user_id, topic_id, last_read_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (saved_topic_id, str(user_id), str(topic_id), _utc_now(), _utc_now()),
        )
        self._connection.commit()
        return UUID(saved_topic_id)

    def create_topic_update_snapshot(
        self,
        *,
        saved_topic_id: UUID,
        title: str,
        summary: str,
    ) -> UUID:
        snapshot_id = _new_id()
        self._connection.execute(
            """
            INSERT INTO topic_update_snapshots (
                id,
                saved_topic_id,
                title,
                summary,
                introduced_claim_ids,
                modified_claim_ids,
                resolved_uncertainty_ids,
                citation_ids,
                detected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (snapshot_id, str(saved_topic_id), title, summary, "[]", "[]", "[]", "[]", _utc_now()),
        )
        self._connection.commit()
        return UUID(snapshot_id)

    def create_quiz_result(
        self,
        *,
        user_id: UUID,
        topic_id: UUID,
        total_questions: int,
        score: int | None = None,
    ) -> UUID:
        quiz_id = _new_id()
        self._connection.execute(
            """
            INSERT INTO quiz_results (
                id,
                user_id,
                topic_id,
                score,
                total_questions,
                answers,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (quiz_id, str(user_id), str(topic_id), score, total_questions, "[]", _utc_now()),
        )
        self._connection.commit()
        return UUID(quiz_id)

    def create_feedback(
        self,
        *,
        user_id: UUID,
        article_id: UUID,
        rating: int,
        comment: str | None = None,
    ) -> UUID:
        feedback_id = _new_id()
        self._connection.execute(
            """
            INSERT INTO feedback (id, user_id, article_id, rating, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (feedback_id, str(user_id), str(article_id), rating, comment, _utc_now()),
        )
        self._connection.commit()
        return UUID(feedback_id)

    def get_article_evidence(self, article_id: UUID) -> list[ArticleWithEvidence]:
        rows = self._connection.execute(
            """
            SELECT
                articles.id,
                articles.title,
                articles.url,
                publishers.name,
                claims.text,
                evidence_passages.text,
                citations.label
            FROM articles
            JOIN publishers ON publishers.id = articles.publisher_id
            JOIN evidence_passages ON evidence_passages.article_id = articles.id
            JOIN claims ON claims.id = evidence_passages.claim_id
            JOIN citations ON citations.evidence_passage_id = evidence_passages.id
            WHERE articles.id = ?
            ORDER BY citations.label
            """,
            (str(article_id),),
        ).fetchall()
        return [
            ArticleWithEvidence(
                article_id=UUID(row[0]),
                title=str(row[1]),
                url=str(row[2]),
                publisher=str(row[3]),
                claim_text=str(row[4]),
                evidence_text=str(row[5]),
                citation_label=str(row[6]),
            )
            for row in rows
        ]

    def record_ingestion_attempt(
        self,
        *,
        url: str,
        status: str,
        article_id: UUID | None = None,
        duplicate_of_article_id: UUID | None = None,
        error: str | None = None,
        failure_kind: str | None = None,
        retryable: bool = False,
    ) -> UUID:
        attempt_id = _new_id()
        self._connection.execute(
            """
            INSERT INTO ingestion_attempts (
                id,
                url,
                status,
                article_id,
                duplicate_of_article_id,
                error,
                failure_kind,
                retryable,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                url,
                status,
                str(article_id) if article_id is not None else None,
                str(duplicate_of_article_id) if duplicate_of_article_id is not None else None,
                error,
                failure_kind,
                retryable,
                _utc_now(),
            ),
        )
        self._connection.commit()
        return UUID(attempt_id)

    def recoverable_ingestion_failures(self) -> list[IngestionAttemptRecord]:
        rows = self._connection.execute(
            """
            SELECT id, url, status, error, failure_kind, retryable
            FROM ingestion_attempts
            WHERE status = ? AND retryable = ?
            ORDER BY created_at
            """,
            ("failed", True),
        ).fetchall()
        return [
            IngestionAttemptRecord(
                attempt_id=UUID(str(row[0])),
                url=str(row[1]),
                status=str(row[2]),
                error=str(row[3]) if row[3] is not None else None,
                failure_kind=str(row[4]) if row[4] is not None else None,
                retryable=bool(row[5]),
            )
            for row in rows
        ]

    def enqueue_background_job(
        self,
        *,
        idempotency_key: str,
        job_type: str,
        payload: dict[str, object],
        max_attempts: int = 3,
    ) -> BackgroundJobRecord:
        existing = self.get_background_job_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        job_id = _new_id()
        now = _utc_now()
        self._connection.execute(
            """
            INSERT INTO background_jobs (
                id,
                idempotency_key,
                job_type,
                status,
                payload,
                retryable,
                attempts,
                max_attempts,
                available_at,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                idempotency_key,
                job_type,
                "queued",
                json.dumps(payload, sort_keys=True),
                False,
                0,
                max_attempts,
                now,
                now,
                now,
            ),
        )
        self._connection.commit()
        return self.get_background_job_by_idempotency_key(idempotency_key) or BackgroundJobRecord(
            job_id=UUID(job_id),
            idempotency_key=idempotency_key,
            job_type=job_type,
            status="queued",
            payload=payload,
            attempts=0,
            max_attempts=max_attempts,
        )

    def get_background_job_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> BackgroundJobRecord | None:
        row = self._connection.execute(
            """
            SELECT
                id,
                idempotency_key,
                job_type,
                status,
                payload,
                attempts,
                max_attempts,
                error,
                failure_kind,
                retryable
            FROM background_jobs
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
        return _background_job_from_row(row)

    def mark_background_job_running(self, job_id: UUID) -> None:
        self._connection.execute(
            """
            UPDATE background_jobs
            SET status = ?, started_at = ?, attempts = attempts + 1, updated_at = ?
            WHERE id = ?
            """,
            ("running", _utc_now(), _utc_now(), str(job_id)),
        )
        self._connection.commit()

    def mark_background_job_succeeded(self, job_id: UUID, result: dict[str, object]) -> None:
        self._connection.execute(
            """
            UPDATE background_jobs
            SET status = ?, result = ?, error = NULL, failure_kind = NULL,
                retryable = ?, finished_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                "succeeded",
                json.dumps(result, sort_keys=True),
                False,
                _utc_now(),
                _utc_now(),
                str(job_id),
            ),
        )
        self._connection.commit()

    def mark_background_job_failed(
        self,
        job_id: UUID,
        *,
        error: str,
        failure_kind: str,
        retryable: bool,
    ) -> None:
        status = "retryable" if retryable else "failed"
        self._connection.execute(
            """
            UPDATE background_jobs
            SET status = ?, error = ?, failure_kind = ?, retryable = ?,
                finished_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, error, failure_kind, retryable, _utc_now(), _utc_now(), str(job_id)),
        )
        self._connection.commit()

    def record_worker_heartbeat(
        self,
        *,
        worker_id: str,
        status: str,
        current_job_id: UUID | None = None,
    ) -> None:
        existing = self._connection.execute(
            "SELECT worker_id FROM worker_heartbeats WHERE worker_id = ?",
            (worker_id,),
        ).fetchone()
        now = _utc_now()
        if existing is None:
            self._connection.execute(
                """
                INSERT INTO worker_heartbeats (worker_id, status, last_seen_at, current_job_id)
                VALUES (?, ?, ?, ?)
                """,
                (worker_id, status, now, str(current_job_id) if current_job_id else None),
            )
        else:
            self._connection.execute(
                """
                UPDATE worker_heartbeats
                SET status = ?, last_seen_at = ?, current_job_id = ?
                WHERE worker_id = ?
                """,
                (status, now, str(current_job_id) if current_job_id else None, worker_id),
            )
        self._connection.commit()

    def worker_health(self, worker_id: str) -> WorkerHeartbeatRecord | None:
        row = self._connection.execute(
            """
            SELECT worker_id, status, last_seen_at, current_job_id
            FROM worker_heartbeats
            WHERE worker_id = ?
            """,
            (worker_id,),
        ).fetchone()
        if row is None:
            return None
        return WorkerHeartbeatRecord(
            worker_id=str(row[0]),
            status=str(row[1]),
            last_seen_at=str(row[2]),
            current_job_id=UUID(str(row[3])) if row[3] is not None else None,
        )


def _background_job_from_row(row: tuple[Any, ...] | None) -> BackgroundJobRecord | None:
    if row is None:
        return None
    payload = json.loads(str(row[4]))
    if not isinstance(payload, dict):
        raise ValueError("Background job payload must be an object.")
    return BackgroundJobRecord(
        job_id=UUID(str(row[0])),
        idempotency_key=str(row[1]),
        job_type=str(row[2]),
        status=str(row[3]),
        payload=payload,
        attempts=int(row[5]),
        max_attempts=int(row[6]),
        error=str(row[7]) if row[7] is not None else None,
        failure_kind=str(row[8]) if row[8] is not None else None,
        retryable=bool(row[9]),
    )
