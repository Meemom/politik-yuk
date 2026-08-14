from app.ingestion.models import ArticleChunk


def chunk_text(
    text: str,
    *,
    target_chars: int = 1_200,
    overlap_chars: int = 120,
) -> list[ArticleChunk]:
    if target_chars <= 0:
        raise ValueError("target_chars must be positive.")
    if overlap_chars < 0 or overlap_chars >= target_chars:
        raise ValueError("overlap_chars must be non-negative and smaller than target_chars.")

    chunks: list[ArticleChunk] = []
    start = 0
    while start < len(text):
        end = min(start + target_chars, len(text))
        if end < len(text):
            sentence_end = max(text.rfind(". ", start, end), text.rfind("? ", start, end))
            if sentence_end > start + target_chars // 2:
                end = sentence_end + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(
                ArticleChunk(
                    chunk_index=len(chunks),
                    text=chunk,
                    start_char=start,
                    end_char=end,
                )
            )
        if end == len(text):
            break
        start = max(end - overlap_chars, start + 1)

    return chunks
