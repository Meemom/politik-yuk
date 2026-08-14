import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.ingestion.models import FetchResult, IngestionError, IngestionFailureKind, ParsedArticle


@dataclass
class _HtmlState:
    title_parts: list[str]
    text_parts: list[str]
    canonical_url: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    publisher: str | None = None
    language: str = "id"
    in_title: bool = False
    skip_depth: int = 0


class ArticleHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.state = _HtmlState(title_parts=[], text_parts=[])

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value or "" for name, value in attrs}
        if tag in {"script", "style", "noscript", "svg"}:
            self.state.skip_depth += 1
        if tag == "title":
            self.state.in_title = True
        if tag == "html" and attr_map.get("lang"):
            self.state.language = attr_map["lang"][:16]
        if tag == "link" and attr_map.get("rel", "").lower() == "canonical":
            self.state.canonical_url = attr_map.get("href") or None
        if tag == "meta":
            self._handle_meta(attr_map)
        if tag in {"p", "div", "section", "article", "li", "br", "h1", "h2", "h3"}:
            self.state.text_parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.state.skip_depth > 0:
            self.state.skip_depth -= 1
        if tag == "title":
            self.state.in_title = False
        if tag in {"p", "li", "h1", "h2", "h3"}:
            self.state.text_parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self.state.skip_depth > 0:
            return
        cleaned = _collapse_whitespace(data)
        if not cleaned:
            return
        if self.state.in_title:
            self.state.title_parts.append(cleaned)
            return
        self.state.text_parts.append(cleaned)

    def _handle_meta(self, attrs: dict[str, str]) -> None:
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        content = attrs.get("content", "").strip()
        if not content:
            return
        if key in {"og:title", "twitter:title"} and not self.state.title_parts:
            self.state.title_parts.append(content)
        elif key in {"author", "article:author"}:
            self.state.author = content
        elif key in {"article:published_time", "pubdate", "publishdate"}:
            self.state.published_at = _parse_datetime(content)
        elif key in {"og:site_name", "application-name"}:
            self.state.publisher = content


def parse_article(fetch_result: FetchResult) -> ParsedArticle:
    encoding = _encoding_from_content_type(fetch_result.content_type)
    parser = ArticleHtmlParser()
    try:
        parser.feed(fetch_result.body.decode(encoding, errors="replace"))
    except Exception as exc:
        raise IngestionError(
            f"Failed to parse article HTML: {exc}",
            kind=IngestionFailureKind.PARSE_FAILED,
        ) from exc

    title = _collapse_whitespace(" ".join(parser.state.title_parts))
    body_text = _collapse_whitespace(" ".join(parser.state.text_parts))
    if not title:
        title = "Untitled article"
    if len(body_text) < 40:
        raise IngestionError(
            "Article body was too short after extraction.",
            kind=IngestionFailureKind.PARSE_FAILED,
        )

    canonical_url = parser.state.canonical_url
    if canonical_url:
        canonical_url = urljoin(fetch_result.final_url, html.unescape(canonical_url))

    hostname = urlparse(fetch_result.final_url).hostname or "Unknown publisher"
    publisher = parser.state.publisher or hostname.removeprefix("www.")

    return ParsedArticle(
        url=fetch_result.final_url,
        canonical_url=canonical_url,
        title=title[:512],
        publisher=publisher[:256],
        author=parser.state.author,
        published_at=parser.state.published_at,
        retrieved_at=datetime.now(UTC),
        body_text=body_text,
        language=parser.state.language,
    )


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _encoding_from_content_type(content_type: str) -> str:
    match = re.search(r"charset=([\w-]+)", content_type, flags=re.IGNORECASE)
    return match.group(1) if match else "utf-8"


def _parse_datetime(value: str) -> datetime | None:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
