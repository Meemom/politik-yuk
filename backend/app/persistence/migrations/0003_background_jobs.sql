CREATE TABLE background_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key text NOT NULL UNIQUE,
    job_type text NOT NULL,
    status text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    result jsonb,
    error text,
    failure_kind text,
    retryable boolean NOT NULL DEFAULT false,
    attempts integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL DEFAULT 3,
    available_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE worker_heartbeats (
    worker_id text PRIMARY KEY,
    status text NOT NULL,
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    current_job_id uuid REFERENCES background_jobs(id) ON DELETE SET NULL
);

CREATE INDEX background_jobs_status_available_idx
    ON background_jobs(status, available_at);

CREATE INDEX background_jobs_type_idx ON background_jobs(job_type);
