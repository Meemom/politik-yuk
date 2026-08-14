import hashlib
import re
from difflib import SequenceMatcher


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    normalized = re.sub(r"\W+", " ", text.lower())
    return " ".join(normalized.split())


def text_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_text(left), normalize_text(right)).ratio()


def is_near_duplicate(left: str, right: str, *, threshold: float = 0.92) -> bool:
    return text_similarity(left, right) >= threshold
