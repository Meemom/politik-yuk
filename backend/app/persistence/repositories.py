from dataclasses import dataclass
from datetime import UTC, datetime
from sqlite3 import Connection
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
