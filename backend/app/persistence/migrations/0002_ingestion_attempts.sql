CREATE TABLE ingestion_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    url text NOT NULL,
    status text NOT NULL,
    article_id uuid REFERENCES articles(id) ON DELETE SET NULL,
    duplicate_of_article_id uuid REFERENCES articles(id) ON DELETE SET NULL,
    error text,
    failure_kind text,
    retryable boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ingestion_attempts_url_idx ON ingestion_attempts(url);
CREATE INDEX ingestion_attempts_status_idx ON ingestion_attempts(status);
