import sqlite3

from app.persistence.migrations import load_migrations, load_seed_sql, split_sql_statements
from app.persistence.repositories import PersistenceRepository
from app.schemas import ClaimStatus, EntityType, SourceType, UncertaintyLevel


def make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE users (
            id text PRIMARY KEY,
            email text UNIQUE,
            locale text NOT NULL,
            created_at text NOT NULL
        );
        CREATE TABLE user_preferences (
            user_id text PRIMARY KEY REFERENCES users(id),
            reading_level text NOT NULL,
            preferred_lenses text NOT NULL,
            updated_at text NOT NULL
        );
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
            canonical_url text,
            title text NOT NULL,
            retrieved_at text NOT NULL,
            language text NOT NULL,
            source_type text NOT NULL,
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
            created_at text NOT NULL
        );
        CREATE TABLE topics (
            id text PRIMARY KEY,
            name text NOT NULL UNIQUE,
            normalized_name text NOT NULL UNIQUE,
            summary text,
            created_at text NOT NULL,
            updated_at text NOT NULL
        );
        CREATE TABLE entities (
            id text PRIMARY KEY,
            name text NOT NULL,
            entity_type text NOT NULL,
            aliases text NOT NULL,
            description text,
            created_at text NOT NULL
        );
        CREATE TABLE claims (
            id text PRIMARY KEY,
            topic_id text REFERENCES topics(id),
            text text NOT NULL,
            normalized_text text NOT NULL UNIQUE,
            status text NOT NULL,
            uncertainty text NOT NULL,
            created_at text NOT NULL,
            updated_at text NOT NULL
        );
        CREATE TABLE evidence_passages (
            id text PRIMARY KEY,
            article_id text NOT NULL REFERENCES articles(id),
            article_chunk_id text REFERENCES article_chunks(id),
            claim_id text REFERENCES claims(id),
            text text NOT NULL,
            relevance_score real,
            created_at text NOT NULL
        );
        CREATE TABLE citations (
            id text PRIMARY KEY,
            source_article_id text NOT NULL REFERENCES articles(id),
            evidence_passage_id text NOT NULL REFERENCES evidence_passages(id),
            label text NOT NULL,
            quote text,
            created_at text NOT NULL
        );
        CREATE TABLE claim_entities (
            claim_id text NOT NULL REFERENCES claims(id),
            entity_id text NOT NULL REFERENCES entities(id),
            PRIMARY KEY (claim_id, entity_id)
        );
        CREATE TABLE claim_evidence (
            claim_id text NOT NULL REFERENCES claims(id),
            evidence_passage_id text NOT NULL REFERENCES evidence_passages(id),
            stance text NOT NULL,
            PRIMARY KEY (claim_id, evidence_passage_id, stance)
        );
        CREATE TABLE saved_topics (
            id text PRIMARY KEY,
            user_id text NOT NULL REFERENCES users(id),
            topic_id text NOT NULL REFERENCES topics(id),
            last_read_at text,
            created_at text NOT NULL
        );
        CREATE TABLE topic_update_snapshots (
            id text PRIMARY KEY,
            saved_topic_id text NOT NULL REFERENCES saved_topics(id),
            title text NOT NULL,
            summary text NOT NULL,
            introduced_claim_ids text NOT NULL,
            modified_claim_ids text NOT NULL,
            resolved_uncertainty_ids text NOT NULL,
            citation_ids text NOT NULL,
            detected_at text NOT NULL
        );
        CREATE TABLE quiz_results (
            id text PRIMARY KEY,
            user_id text REFERENCES users(id),
            topic_id text REFERENCES topics(id),
            score integer,
            total_questions integer NOT NULL,
            answers text NOT NULL,
            created_at text NOT NULL
        );
        CREATE TABLE feedback (
            id text PRIMARY KEY,
            user_id text REFERENCES users(id),
            article_id text REFERENCES articles(id),
            rating integer,
            comment text,
            created_at text NOT NULL
        );
        """
    )
    return connection


def test_migration_manifest_contains_core_postgres_tables() -> None:
    migrations = load_migrations()
    migration_ids = [migration.migration_id for migration in migrations]
    sql = "\n".join(migration.sql for migration in migrations)

    assert migration_ids == sorted(migration_ids)
    assert "CREATE TABLE users" in sql
    assert "CREATE TABLE articles" in sql
    assert "CREATE TABLE claims" in sql
    assert "CREATE TABLE saved_topics" in sql
    assert "CREATE TABLE feedback" in sql
    assert all(";" not in statement for statement in split_sql_statements(sql))


def test_seed_sql_is_present_and_idempotent() -> None:
    seed_sql = load_seed_sql()

    assert "ON CONFLICT" in seed_sql
    assert "Politik Yuk Demo Publisher" in seed_sql


def test_repository_creates_and_queries_core_records() -> None:
    connection = make_connection()
    repository = PersistenceRepository(connection)

    user_id = repository.create_user(email="reader@example.com")
    publisher_id = repository.create_publisher(
        name="Example News",
        source_type=SourceType.NEWS,
        homepage_url="https://example.com",
    )
    article_id = repository.create_article(
        publisher_id=publisher_id,
        url="https://example.com/pemilu",
        canonical_url="https://example.com/pemilu",
        title="Berita pemilu",
        body_text="KPU menjelaskan tahapan pemilu terbaru.",
    )
    chunk_id = repository.create_article_chunk(
        article_id=article_id,
        chunk_index=0,
        text="KPU menjelaskan tahapan pemilu terbaru.",
        start_char=0,
        end_char=38,
    )
    topic_id = repository.create_topic(name="Pemilu Indonesia")
    entity_id = repository.create_entity(
        name="KPU",
        entity_type=EntityType.GOVERNMENT_INSTITUTION,
        description="Komisi Pemilihan Umum",
    )
    claim_id = repository.create_claim(
        topic_id=topic_id,
        text="KPU menjelaskan tahapan pemilu terbaru.",
        status=ClaimStatus.SUPPORTED,
        uncertainty=UncertaintyLevel.LOW,
    )
    repository.link_claim_entity(claim_id=claim_id, entity_id=entity_id)
    evidence_id = repository.create_evidence_passage(
        article_id=article_id,
        article_chunk_id=chunk_id,
        claim_id=claim_id,
        text="KPU menjelaskan tahapan pemilu terbaru.",
        relevance_score=0.95,
    )
    repository.create_citation(
        article_id=article_id,
        evidence_passage_id=evidence_id,
        label="1",
        quote="KPU menjelaskan tahapan pemilu terbaru.",
    )
    saved_topic_id = repository.save_topic(user_id=user_id, topic_id=topic_id)
    repository.create_topic_update_snapshot(
        saved_topic_id=saved_topic_id,
        title="Tahapan baru",
        summary="Ada pembaruan tahapan pemilu.",
    )
    repository.create_quiz_result(user_id=user_id, topic_id=topic_id, total_questions=3, score=2)
    repository.create_feedback(
        user_id=user_id,
        article_id=article_id,
        rating=5,
        comment="Mudah dipahami.",
    )

    evidence = repository.get_article_evidence(article_id)

    assert len(evidence) == 1
    assert evidence[0].title == "Berita pemilu"
    assert evidence[0].publisher == "Example News"
    assert evidence[0].claim_text == "KPU menjelaskan tahapan pemilu terbaru."
    assert evidence[0].evidence_text == "KPU menjelaskan tahapan pemilu terbaru."
    assert evidence[0].citation_label == "1"
