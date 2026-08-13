CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text UNIQUE,
    locale text NOT NULL DEFAULT 'id-ID',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE user_preferences (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    reading_level text NOT NULL DEFAULT 'quick',
    preferred_lenses text[] NOT NULL DEFAULT '{}',
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE publishers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    homepage_url text,
    source_type text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE articles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    publisher_id uuid NOT NULL REFERENCES publishers(id),
    url text NOT NULL,
    canonical_url text,
    title text NOT NULL,
    author text,
    published_at timestamptz,
    retrieved_at timestamptz NOT NULL DEFAULT now(),
    language text NOT NULL DEFAULT 'id',
    source_type text NOT NULL,
    content_hash text,
    body_text text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (url),
    UNIQUE (canonical_url)
);

CREATE TABLE article_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id uuid NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    text text NOT NULL,
    start_char integer,
    end_char integer,
    embedding double precision[],
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (article_id, chunk_index)
);

CREATE TABLE topics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    normalized_name text NOT NULL UNIQUE,
    summary text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE entities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    entity_type text NOT NULL,
    aliases text[] NOT NULL DEFAULT '{}',
    description text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, entity_type)
);

CREATE TABLE claims (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id uuid REFERENCES topics(id) ON DELETE SET NULL,
    text text NOT NULL,
    normalized_text text NOT NULL,
    status text NOT NULL,
    uncertainty text NOT NULL DEFAULT 'unknown',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (normalized_text)
);

CREATE TABLE evidence_passages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id uuid NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    article_chunk_id uuid REFERENCES article_chunks(id) ON DELETE SET NULL,
    claim_id uuid REFERENCES claims(id) ON DELETE SET NULL,
    text text NOT NULL,
    start_char integer,
    end_char integer,
    relevance_score double precision,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE citations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_article_id uuid NOT NULL REFERENCES articles(id),
    evidence_passage_id uuid NOT NULL REFERENCES evidence_passages(id),
    label text NOT NULL,
    quote text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE topic_entities (
    topic_id uuid NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    entity_id uuid NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relationship_type text NOT NULL DEFAULT 'related_to',
    PRIMARY KEY (topic_id, entity_id, relationship_type)
);

CREATE TABLE claim_entities (
    claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    entity_id uuid NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    PRIMARY KEY (claim_id, entity_id)
);

CREATE TABLE claim_evidence (
    claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    evidence_passage_id uuid NOT NULL REFERENCES evidence_passages(id) ON DELETE CASCADE,
    stance text NOT NULL DEFAULT 'supports',
    PRIMARY KEY (claim_id, evidence_passage_id, stance)
);

CREATE TABLE saved_topics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic_id uuid NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    last_read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, topic_id)
);

CREATE TABLE topic_update_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    saved_topic_id uuid NOT NULL REFERENCES saved_topics(id) ON DELETE CASCADE,
    title text NOT NULL,
    summary text NOT NULL,
    introduced_claim_ids uuid[] NOT NULL DEFAULT '{}',
    modified_claim_ids uuid[] NOT NULL DEFAULT '{}',
    resolved_uncertainty_ids uuid[] NOT NULL DEFAULT '{}',
    citation_ids uuid[] NOT NULL DEFAULT '{}',
    detected_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE quiz_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    topic_id uuid REFERENCES topics(id) ON DELETE SET NULL,
    explanation_request_id uuid,
    score integer,
    total_questions integer NOT NULL,
    answers jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE feedback (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    article_id uuid REFERENCES articles(id) ON DELETE SET NULL,
    claim_id uuid REFERENCES claims(id) ON DELETE SET NULL,
    rating integer,
    comment text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX articles_publisher_id_idx ON articles(publisher_id);
CREATE INDEX article_chunks_article_id_idx ON article_chunks(article_id);
CREATE INDEX evidence_claim_id_idx ON evidence_passages(claim_id);
CREATE INDEX claims_topic_id_idx ON claims(topic_id);
CREATE INDEX citations_evidence_passage_id_idx ON citations(evidence_passage_id);
CREATE INDEX saved_topics_user_id_idx ON saved_topics(user_id);
CREATE INDEX topic_update_snapshots_saved_topic_id_idx
    ON topic_update_snapshots(saved_topic_id);
