import json
import time
from dataclasses import dataclass
from typing import Any, Protocol, Self

from app.cache.ttl import TtlClass, ttl_seconds


class RedisLike(Protocol):
    def get(self, key: str) -> str | None:
        ...

    def set(self, key: str, value: str, ex: int | None = None) -> bool | None:
        ...

    def delete(self, key: str) -> int:
        ...

    def incr(self, key: str) -> int:
        ...

    def expire(self, key: str, seconds: int) -> bool:
        ...

    def lpush(self, key: str, value: str) -> int:
        ...

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        ...


@dataclass
class _StoredValue:
    value: str | list[str]
    expires_at: float | None = None


class InMemoryRedis:
    def __init__(self) -> None:
        self._values: dict[str, _StoredValue] = {}

    def get(self, key: str) -> str | None:
        self._purge_if_expired(key)
        stored = self._values.get(key)
        if stored is None or not isinstance(stored.value, str):
            return None
        return stored.value

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._values[key] = _StoredValue(value=value, expires_at=self._expires_at(ex))
        return True

    def delete(self, key: str) -> int:
        existed = key in self._values
        self._values.pop(key, None)
        return int(existed)

    def incr(self, key: str) -> int:
        current = self.get(key)
        next_value = int(current or "0") + 1
        expires_at = self._values.get(key, _StoredValue("")).expires_at
        self._values[key] = _StoredValue(value=str(next_value), expires_at=expires_at)
        return next_value

    def expire(self, key: str, seconds: int) -> bool:
        self._purge_if_expired(key)
        stored = self._values.get(key)
        if stored is None:
            return False
        stored.expires_at = self._expires_at(seconds)
        return True

    def lpush(self, key: str, value: str) -> int:
        self._purge_if_expired(key)
        stored = self._values.setdefault(key, _StoredValue(value=[]))
        if isinstance(stored.value, str):
            stored.value = []
        stored.value.insert(0, value)
        return len(stored.value)

    def lrange(self, key: str, start: int, end: int) -> list[str]:
        self._purge_if_expired(key)
        stored = self._values.get(key)
        if stored is None or isinstance(stored.value, str):
            return []
        values = stored.value
        stop = None if end == -1 else end + 1
        return values[start:stop]

    def _purge_if_expired(self, key: str) -> None:
        stored = self._values.get(key)
        if (
            stored is not None
            and stored.expires_at is not None
            and stored.expires_at <= time.time()
        ):
            self._values.pop(key, None)

    @staticmethod
    def _expires_at(seconds: int | None) -> float | None:
        if seconds is None:
            return None
        return time.time() + seconds


class CacheStore:
    def __init__(self, redis: RedisLike, *, key_prefix: str = "politik-yuk") -> None:
        self._redis = redis
        self._key_prefix = key_prefix

    def key(self, namespace: str, identifier: str) -> str:
        return f"{self._key_prefix}:{namespace}:{identifier}"

    def get_json(self, namespace: str, identifier: str) -> dict[str, Any] | None:
        raw = self._redis.get(self.key(namespace, identifier))
        if raw is None:
            return None
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Cached JSON payload must be an object.")
        return parsed

    def set_json(
        self,
        namespace: str,
        identifier: str,
        payload: dict[str, Any],
        ttl_class: TtlClass,
    ) -> None:
        self._redis.set(
            self.key(namespace, identifier),
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            ex=ttl_seconds(ttl_class),
        )

    def delete(self, namespace: str, identifier: str) -> bool:
        return self._redis.delete(self.key(namespace, identifier)) > 0

    @classmethod
    def from_redis(
        cls,
        redis: RedisLike,
        *,
        key_prefix: str = "politik-yuk",
    ) -> Self:
        return cls(redis, key_prefix=key_prefix)
