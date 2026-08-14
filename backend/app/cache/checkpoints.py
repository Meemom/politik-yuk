import json
from dataclasses import dataclass
from typing import Any

from app.cache.store import RedisLike
from app.cache.ttl import TtlClass, ttl_seconds


@dataclass(frozen=True)
class SessionCheckpoint:
    session_id: str
    node_name: str
    state: dict[str, Any]


class SessionCheckpointStore:
    def __init__(self, redis: RedisLike, *, key_prefix: str = "politik-yuk") -> None:
        self._redis = redis
        self._key_prefix = key_prefix

    def save(
        self,
        checkpoint: SessionCheckpoint,
        ttl_class: TtlClass = TtlClass.CURRENT_TOPIC,
    ) -> None:
        self._redis.set(
            self._checkpoint_key(checkpoint.session_id),
            json.dumps(
                {
                    "session_id": checkpoint.session_id,
                    "node_name": checkpoint.node_name,
                    "state": checkpoint.state,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            ex=ttl_seconds(ttl_class),
        )

    def load(self, session_id: str) -> SessionCheckpoint | None:
        raw = self._redis.get(self._checkpoint_key(session_id))
        if raw is None:
            return None
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Checkpoint payload must be an object.")
        state = payload.get("state")
        if not isinstance(state, dict):
            raise ValueError("Checkpoint state must be an object.")
        return SessionCheckpoint(
            session_id=str(payload["session_id"]),
            node_name=str(payload["node_name"]),
            state=state,
        )

    def append_event(
        self,
        session_id: str,
        event: dict[str, Any],
        ttl_class: TtlClass = TtlClass.CURRENT_TOPIC,
    ) -> None:
        key = self._events_key(session_id)
        self._redis.lpush(key, json.dumps(event, sort_keys=True, separators=(",", ":")))
        self._redis.expire(key, ttl_seconds(ttl_class))

    def events(self, session_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        raw_events = self._redis.lrange(self._events_key(session_id), 0, limit - 1)
        events: list[dict[str, Any]] = []
        for raw_event in raw_events:
            parsed = json.loads(raw_event)
            if isinstance(parsed, dict):
                events.append(parsed)
        return events

    def _checkpoint_key(self, session_id: str) -> str:
        return f"{self._key_prefix}:checkpoint:{session_id}"

    def _events_key(self, session_id: str) -> str:
        return f"{self._key_prefix}:checkpoint-events:{session_id}"
