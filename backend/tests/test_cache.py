import pytest

from app.cache.checkpoints import SessionCheckpoint, SessionCheckpointStore
from app.cache.rate_limits import FixedWindowRateLimiter
from app.cache.semantic_cache import SemanticCache, SemanticCandidate
from app.cache.store import CacheStore, InMemoryRedis
from app.cache.ttl import TtlClass, ttl_seconds
from app.cache.vector_indexes import (
    ARTICLE_CHUNK_INDEX,
    ENTITY_EMBEDDING_INDEX,
    QUERY_EMBEDDING_INDEX,
    vector_index_commands,
)


def test_ttl_policy_distinguishes_freshness_classes() -> None:
    assert ttl_seconds(TtlClass.BREAKING_NEWS) < ttl_seconds(TtlClass.CURRENT_TOPIC)
    assert ttl_seconds(TtlClass.CURRENT_TOPIC) < ttl_seconds(TtlClass.STABLE_HISTORICAL)
    assert ttl_seconds(TtlClass.STABLE_HISTORICAL) < ttl_seconds(TtlClass.IMMUTABLE_ARTICLE)
    assert ttl_seconds(TtlClass.SEMANTIC_CANDIDATE) == 600


def test_cache_store_round_trips_json_with_namespaced_keys() -> None:
    redis = InMemoryRedis()
    cache = CacheStore(redis, key_prefix="test")

    cache.set_json("article", "abc", {"title": "Pemilu", "fresh": True}, TtlClass.CURRENT_TOPIC)

    assert cache.get_json("article", "abc") == {"title": "Pemilu", "fresh": True}
    assert cache.delete("article", "abc") is True
    assert cache.get_json("article", "abc") is None


def test_rate_limiter_blocks_after_window_limit() -> None:
    redis = InMemoryRedis()
    limiter = FixedWindowRateLimiter(redis, key_prefix="test")

    first = limiter.check("reader-1", limit=2, window_seconds=60)
    second = limiter.check("reader-1", limit=2, window_seconds=60)
    third = limiter.check("reader-1", limit=2, window_seconds=60)

    assert first.allowed is True
    assert second.remaining == 0
    assert third.allowed is False
    assert third.remaining == 0


def test_checkpoint_store_saves_state_and_stream_events() -> None:
    redis = InMemoryRedis()
    checkpoints = SessionCheckpointStore(redis, key_prefix="test")

    checkpoints.save(
        SessionCheckpoint(
            session_id="session-1",
            node_name="retrieve_evidence",
            state={"topic": "pemilu", "step": 2},
        )
    )
    checkpoints.append_event("session-1", {"event_type": "request_received"})
    checkpoints.append_event("session-1", {"event_type": "evidence_retrieved"})

    loaded = checkpoints.load("session-1")

    assert loaded == SessionCheckpoint(
        session_id="session-1",
        node_name="retrieve_evidence",
        state={"topic": "pemilu", "step": 2},
    )
    assert checkpoints.events("session-1") == [
        {"event_type": "evidence_retrieved"},
        {"event_type": "request_received"},
    ]


def test_semantic_cache_stores_candidates_without_answer_reuse() -> None:
    redis = InMemoryRedis()
    semantic_cache = SemanticCache(redis, key_prefix="test")

    semantic_cache.store_candidate(
        SemanticCandidate(
            query_hash="hash-1",
            explanation_request_id="request-1",
            article_chunk_ids=["chunk-1", "chunk-2"],
            embedding=[0.1, 0.2],
        )
    )

    candidate = semantic_cache.get_candidate("hash-1")

    assert candidate == SemanticCandidate(
        query_hash="hash-1",
        explanation_request_id="request-1",
        article_chunk_ids=["chunk-1", "chunk-2"],
        embedding=[0.1, 0.2],
    )
    raw = redis.get("test:semantic-candidate:hash-1")
    assert raw is not None
    assert '"answer_reuse_allowed":false' in raw
    assert "final_answer" not in raw


def test_semantic_cache_rejects_answer_reuse_payloads() -> None:
    redis = InMemoryRedis()
    redis.set(
        "test:semantic-candidate:unsafe",
        (
            '{"query_hash":"unsafe","explanation_request_id":"request-1",'
            '"article_chunk_ids":[],"embedding":[],"answer_reuse_allowed":true}'
        ),
    )
    semantic_cache = SemanticCache(redis, key_prefix="test")

    with pytest.raises(ValueError, match="final answer reuse"):
        semantic_cache.get_candidate("unsafe")


def test_vector_index_commands_cover_article_query_and_entity_embeddings() -> None:
    commands = vector_index_commands()
    names = {command[1] for command in commands}

    assert names == {
        ARTICLE_CHUNK_INDEX.name,
        QUERY_EMBEDDING_INDEX.name,
        ENTITY_EMBEDDING_INDEX.name,
    }
    assert all("VECTOR" in command for command in commands)
    assert all("FLOAT32" in command for command in commands)
    assert all("1024" in command for command in commands)
