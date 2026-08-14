INSERT INTO publishers (name, homepage_url, source_type)
VALUES
    ('Politik Yuk Demo Publisher', 'https://example.com', 'news')
ON CONFLICT (name) DO NOTHING;

INSERT INTO topics (name, normalized_name, summary)
VALUES
    ('Pemilu Indonesia', 'pemilu indonesia', 'Local seed topic for persistence checks.')
ON CONFLICT (normalized_name) DO NOTHING;
