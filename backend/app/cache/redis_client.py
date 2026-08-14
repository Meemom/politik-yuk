from dataclasses import dataclass
from importlib import import_module
from typing import Any

from app.settings import Settings


@dataclass(frozen=True)
class RedisConfig:
    url: str
    key_prefix: str


class RedisConnectionError(RuntimeError):
    pass


def redis_config_from_settings(settings: Settings) -> RedisConfig:
    return RedisConfig(url=settings.redis_url, key_prefix=settings.redis_key_prefix)


def create_redis_client(settings: Settings) -> Any:
    try:
        redis_module = import_module("redis")
    except ModuleNotFoundError as exc:
        raise RedisConnectionError(
            "redis is required for live Redis connections. Install backend dependencies first."
        ) from exc

    return redis_module.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=settings.redis_socket_timeout_seconds,
        socket_timeout=settings.redis_socket_timeout_seconds,
    )
