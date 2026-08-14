import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from app.ingestion.models import FetchResult, IngestionError, IngestionFailureKind


class ArticleFetcher(Protocol):
    def fetch(self, url: str) -> FetchResult:
        ...


@dataclass(frozen=True)
class UrlLibArticleFetcher:
    timeout_seconds: float = 10
    max_bytes: int = 2_000_000
    retries: int = 2
    user_agent: str = "PolitikYukBot/0.1 (+https://example.com/politik-yuk)"

    def fetch(self, url: str) -> FetchResult:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    content_type = response.headers.get("Content-Type", "")
                    if not _is_supported_content_type(content_type):
                        raise IngestionError(
                            f"Unsupported content type: {content_type or 'unknown'}.",
                            kind=IngestionFailureKind.FETCH_FAILED,
                        )
                    body = response.read(self.max_bytes + 1)
                    if len(body) > self.max_bytes:
                        raise IngestionError(
                            "Fetched article exceeded the maximum allowed size.",
                            kind=IngestionFailureKind.FETCH_FAILED,
                        )
                    return FetchResult(
                        url=url,
                        final_url=response.geturl(),
                        content_type=content_type,
                        body=body,
                    )
            except IngestionError:
                raise
            except (TimeoutError, urllib.error.URLError, OSError) as exc:
                last_error = exc
                if attempt == self.retries:
                    raise IngestionError(
                        f"Failed to fetch article: {exc}",
                        kind=IngestionFailureKind.FETCH_FAILED,
                        retryable=True,
                    ) from exc

        raise IngestionError(
            f"Failed to fetch article: {last_error}",
            kind=IngestionFailureKind.FETCH_FAILED,
            retryable=True,
        )


def _is_supported_content_type(content_type: str) -> bool:
    normalized = content_type.lower()
    return normalized == "" or "text/html" in normalized or "application/xhtml+xml" in normalized
