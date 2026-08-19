from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from app.schemas import SourceType
from app.search import ExternalSearchError, ExternalSearchResult, SearchFailureKind


class TavilySearchProvider:
    provider_name = "tavily"

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float,
        search_depth: str = "basic",
        include_domains: Sequence[str] = (),
        exclude_domains: Sequence[str] = (),
        base_url: str = "https://api.tavily.com",
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._search_depth = search_depth
        self._include_domains = list(include_domains)
        self._exclude_domains = list(exclude_domains)
        self._base_url = base_url.rstrip("/")
        self._client = client

    def search(self, query: str, *, max_results: int) -> list[ExternalSearchResult]:
        payload = {
            "query": query,
            "topic": "news",
            "search_depth": self._search_depth,
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
            "include_favicon": False,
            "include_domains": self._include_domains,
            "exclude_domains": self._exclude_domains,
            "safe_search": True,
        }
        response = self._post_json("/search", payload)
        raw_results = response.get("results")
        if not isinstance(raw_results, list):
            raise ExternalSearchError("Tavily response did not include results.", retryable=False)
        return [
            _result_from_tavily(item)
            for item in raw_results[:max_results]
            if isinstance(item, dict)
        ]

    def _post_json(self, path: str, payload: Mapping[str, object]) -> dict[str, object]:
        client = self._client or httpx.Client(timeout=self._timeout_seconds)
        owns_client = self._client is None
        try:
            response = client.post(
                f"{self._base_url}{path}",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout_seconds,
            )
            if response.status_code >= 400:
                raise _search_http_error(
                    "Tavily",
                    response.status_code,
                    provider_unavailable_statuses={401, 403, 432, 433},
                )
            parsed = response.json()
        except httpx.TimeoutException as exc:
            raise ExternalSearchError(
                "Tavily request timed out.",
                kind=SearchFailureKind.PROVIDER_TIMEOUT,
            ) from exc
        except httpx.HTTPError as exc:
            raise ExternalSearchError(f"Tavily request failed: {exc}") from exc
        finally:
            if owns_client:
                client.close()
        if not isinstance(parsed, dict):
            raise ExternalSearchError("Tavily response must be a JSON object.", retryable=False)
        return parsed


class BraveSearchProvider:
    provider_name = "brave"

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float,
        base_url: str = "https://api.search.brave.com/res/v1",
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url.rstrip("/")
        self._client = client

    def search(self, query: str, *, max_results: int) -> list[ExternalSearchResult]:
        response = self._get_json(
            "/web/search",
            {
                "q": query,
                "count": str(max_results),
                "country": "ID",
                "search_lang": "id",
                "result_filter": "news,web",
                "text_decorations": "false",
            },
        )
        return _results_from_brave(response, max_results=max_results)

    def _get_json(self, path: str, params: Mapping[str, str]) -> dict[str, object]:
        client = self._client or httpx.Client(timeout=self._timeout_seconds)
        owns_client = self._client is None
        try:
            response = client.get(
                f"{self._base_url}{path}",
                headers={"X-Subscription-Token": self._api_key, "Accept": "application/json"},
                params=params,
                timeout=self._timeout_seconds,
            )
            if response.status_code >= 400:
                raise _search_http_error(
                    "Brave Search",
                    response.status_code,
                    provider_unavailable_statuses={401, 403},
                )
            parsed = response.json()
        except httpx.TimeoutException as exc:
            raise ExternalSearchError(
                "Brave Search request timed out.",
                kind=SearchFailureKind.PROVIDER_TIMEOUT,
            ) from exc
        except httpx.HTTPError as exc:
            raise ExternalSearchError(f"Brave Search request failed: {exc}") from exc
        finally:
            if owns_client:
                client.close()
        if not isinstance(parsed, dict):
            raise ExternalSearchError(
                "Brave Search response must be a JSON object.",
                retryable=False,
            )
        return parsed


def _result_from_tavily(payload: Mapping[str, object]) -> ExternalSearchResult:
    url = str(payload.get("url", ""))
    published_at = _parse_datetime(payload.get("published_date") or payload.get("published_at"))
    return ExternalSearchResult(
        url=url,
        title=str(payload.get("title") or url),
        publisher=_publisher(payload.get("source"), url),
        snippet=str(payload.get("content") or payload.get("snippet") or ""),
        published_at=published_at,
        source_type=_source_type(url),
        score=_optional_float(payload.get("score")),
    )


def _results_from_brave(
    payload: Mapping[str, object],
    *,
    max_results: int,
) -> list[ExternalSearchResult]:
    raw_results: list[object] = []
    news = payload.get("news")
    web = payload.get("web")
    if isinstance(news, dict) and isinstance(news.get("results"), list):
        raw_results.extend(news["results"])
    if isinstance(web, dict) and isinstance(web.get("results"), list):
        raw_results.extend(web["results"])

    results: list[ExternalSearchResult] = []
    seen_urls: set[str] = set()
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", ""))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        results.append(
            ExternalSearchResult(
                url=url,
                title=str(item.get("title") or url),
                publisher=_publisher(item.get("profile"), url),
                snippet=str(item.get("description") or item.get("snippet") or ""),
                published_at=_parse_datetime(item.get("age") or item.get("published")),
                source_type=_source_type(url),
                score=None,
            )
        )
        if len(results) >= max_results:
            break
    return results


def _publisher(value: object, url: str) -> str:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str) and name:
            return name
    host = urlparse(url).netloc.removeprefix("www.")
    return host or "Unknown publisher"


def _source_type(url: str) -> SourceType:
    host = urlparse(url).netloc.casefold()
    if host.endswith(".go.id") or ".go.id" in host:
        return SourceType.GOVERNMENT
    if any(part in host for part in ("ngo", "lbh", "perludem", "kontras", "walhi")):
        return SourceType.CIVIL_SOCIETY
    return SourceType.NEWS


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _search_http_error(
    provider: str,
    status_code: int,
    *,
    provider_unavailable_statuses: set[int],
) -> ExternalSearchError:
    if status_code in provider_unavailable_statuses:
        return ExternalSearchError(
            f"{provider} returned HTTP {status_code}.",
            kind=SearchFailureKind.PROVIDER_UNAVAILABLE,
            retryable=False,
        )
    if status_code == 429:
        return ExternalSearchError(
            f"{provider} returned HTTP 429.",
            kind=SearchFailureKind.PROVIDER_ERROR,
            retryable=True,
        )
    if status_code in {408, 504}:
        return ExternalSearchError(
            f"{provider} returned HTTP {status_code}.",
            kind=SearchFailureKind.PROVIDER_TIMEOUT,
            retryable=True,
        )
    return ExternalSearchError(
        f"{provider} returned HTTP {status_code}.",
        retryable=status_code >= 500,
    )
