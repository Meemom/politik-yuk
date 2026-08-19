from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Politik Yuk"
    environment: str = "local"
    postgres_url: str = "postgresql://aya:aya@localhost:5432/aya_context"
    redis_url: str = "redis://localhost:6379/0"
    redis_key_prefix: str = "politik-yuk"
    redis_socket_timeout_seconds: float = 2
    default_rate_limit: int = 60
    default_rate_limit_window_seconds: int = 60
    ingestion_fetch_timeout_seconds: float = 10
    ingestion_fetch_retries: int = 2
    ingestion_max_bytes: int = 2_000_000
    ingestion_chunk_target_chars: int = 1_200
    ingestion_chunk_overlap_chars: int = 120
    worker_broker_url: str = "redis://localhost:6379/1"
    worker_result_backend_url: str = "redis://localhost:6379/2"
    worker_default_max_attempts: int = 3
    worker_job_timeout_seconds: int = 120
    external_search_provider: str = "disabled"
    tavily_api_key: str | None = None
    brave_search_api_key: str | None = None
    external_search_include_domains: str = ""
    external_search_exclude_domains: str = ""
    external_search_depth: str = "basic"
    external_search_timeout_seconds: float = 5
    external_search_max_results: int = 5
    graph_checkpoint_backend: str = "memory"
    allow_inmemory_redis: bool = False
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    model_provider_backend: str = "fake"
    cohere_api_key: str | None = None
    text_generation_model: str = "c4ai-aya-expanse-32b"
    structured_generation_model: str = "c4ai-aya-expanse-32b"
    image_analysis_model: str = "c4ai-aya-vision-32b"
    embedding_model: str = "embed-v4.0"
    reranking_model: str = "rerank-v4.0-fast"
    model_timeout_seconds: float = 30
    model_max_retries: int = 2

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
