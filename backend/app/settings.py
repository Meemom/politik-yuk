from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Politik Yuk"
    environment: str = "local"
    postgres_url: str = "postgresql://aya:aya@localhost:5432/aya_context"
    redis_url: str = "redis://localhost:6379/0"
    model_provider_backend: str = "fake"
    text_generation_model: str = "c4ai-aya-expanse-32b"
    structured_generation_model: str = "c4ai-aya-expanse-32b"
    image_analysis_model: str = "c4ai-aya-vision-32b"
    embedding_model: str = "intfloat/multilingual-e5-large-instruct"
    reranking_model: str = "cohere-rerank"
    model_timeout_seconds: float = 30
    model_max_retries: int = 2

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
