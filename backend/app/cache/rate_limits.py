import time
from dataclasses import dataclass

from app.cache.store import RedisLike


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    key: str
    limit: int
    remaining: int
    reset_at: int


class FixedWindowRateLimiter:
    def __init__(self, redis: RedisLike, *, key_prefix: str = "politik-yuk") -> None:
        self._redis = redis
        self._key_prefix = key_prefix

    def check(self, identifier: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        now = int(time.time())
        window = now // window_seconds
        key = f"{self._key_prefix}:rate:{identifier}:{window}"
        count = self._redis.incr(key)
        if count == 1:
            self._redis.expire(key, window_seconds)

        remaining = max(limit - count, 0)
        return RateLimitDecision(
            allowed=count <= limit,
            key=key,
            limit=limit,
            remaining=remaining,
            reset_at=(window + 1) * window_seconds,
        )
