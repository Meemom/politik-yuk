from enum import StrEnum


class TtlClass(StrEnum):
    BREAKING_NEWS = "breaking_news"
    CURRENT_TOPIC = "current_topic"
    STABLE_HISTORICAL = "stable_historical"
    IMMUTABLE_ARTICLE = "immutable_article"
    SEMANTIC_CANDIDATE = "semantic_candidate"


TTL_SECONDS: dict[TtlClass, int] = {
    TtlClass.BREAKING_NEWS: 5 * 60,
    TtlClass.CURRENT_TOPIC: 30 * 60,
    TtlClass.STABLE_HISTORICAL: 24 * 60 * 60,
    TtlClass.IMMUTABLE_ARTICLE: 30 * 24 * 60 * 60,
    TtlClass.SEMANTIC_CANDIDATE: 10 * 60,
}


def ttl_seconds(ttl_class: TtlClass) -> int:
    return TTL_SECONDS[ttl_class]
