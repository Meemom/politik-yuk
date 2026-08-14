import json
from dataclasses import dataclass

from app.cache.store import RedisLike
from app.cache.ttl import TtlClass, ttl_seconds


@dataclass(frozen=True)
class SemanticCandidate:
    query_hash: str
    explanation_request_id: str
    article_chunk_ids: list[str]
    embedding: list[float]


class SemanticCache:
    def __init__(self, redis: RedisLike, *, key_prefix: str = "politik-yuk") -> None:
        self._redis = redis
        self._key_prefix = key_prefix

    def store_candidate(
        self,
        candidate: SemanticCandidate,
        ttl_class: TtlClass = TtlClass.SEMANTIC_CANDIDATE,
    ) -> None:
        payload = {
            "query_hash": candidate.query_hash,
            "explanation_request_id": candidate.explanation_request_id,
            "article_chunk_ids": candidate.article_chunk_ids,
            "embedding": candidate.embedding,
            "answer_reuse_allowed": False,
        }
        self._redis.set(
            self._candidate_key(candidate.query_hash),
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            ex=ttl_seconds(ttl_class),
        )

    def get_candidate(self, query_hash: str) -> SemanticCandidate | None:
        raw = self._redis.get(self._candidate_key(query_hash))
        if raw is None:
            return None
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Semantic cache payload must be an object.")
        if payload.get("answer_reuse_allowed") is not False:
            raise ValueError("Semantic cache cannot enable final answer reuse.")
        return SemanticCandidate(
            query_hash=str(payload["query_hash"]),
            explanation_request_id=str(payload["explanation_request_id"]),
            article_chunk_ids=[str(item) for item in payload["article_chunk_ids"]],
            embedding=[float(item) for item in payload["embedding"]],
        )

    def _candidate_key(self, query_hash: str) -> str:
        return f"{self._key_prefix}:semantic-candidate:{query_hash}"
