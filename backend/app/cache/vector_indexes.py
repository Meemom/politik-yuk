from dataclasses import dataclass


@dataclass(frozen=True)
class RedisVectorIndex:
    name: str
    prefix: str
    vector_field: str
    dimensions: int
    distance_metric: str = "COSINE"

    def create_command(self) -> list[str]:
        return [
            "FT.CREATE",
            self.name,
            "ON",
            "HASH",
            "PREFIX",
            "1",
            self.prefix,
            "SCHEMA",
            "id",
            "TAG",
            "SORTABLE",
            "text",
            "TEXT",
            "language",
            "TAG",
            self.vector_field,
            "VECTOR",
            "FLAT",
            "6",
            "TYPE",
            "FLOAT32",
            "DIM",
            str(self.dimensions),
            "DISTANCE_METRIC",
            self.distance_metric,
        ]


ARTICLE_CHUNK_INDEX = RedisVectorIndex(
    name="idx:article_chunks",
    prefix="article_chunk:",
    vector_field="embedding",
    dimensions=1_024,
)

QUERY_EMBEDDING_INDEX = RedisVectorIndex(
    name="idx:query_embeddings",
    prefix="query_embedding:",
    vector_field="embedding",
    dimensions=1_024,
)

ENTITY_EMBEDDING_INDEX = RedisVectorIndex(
    name="idx:entity_embeddings",
    prefix="entity_embedding:",
    vector_field="embedding",
    dimensions=1_024,
)

VECTOR_INDEXES = [ARTICLE_CHUNK_INDEX, QUERY_EMBEDDING_INDEX, ENTITY_EMBEDDING_INDEX]


def vector_index_commands() -> list[list[str]]:
    return [index.create_command() for index in VECTOR_INDEXES]
