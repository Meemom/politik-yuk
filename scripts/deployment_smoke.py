from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class SmokeConfig:
    frontend_url: str
    backend_url: str
    explain_query: str


def main() -> int:
    config = SmokeConfig(
        frontend_url=_required_env("FRONTEND_URL").rstrip("/") + "/",
        backend_url=_required_env("BACKEND_URL").rstrip("/") + "/",
        explain_query=os.getenv("SMOKE_EXPLAIN_QUERY", "siapa presiden indonesia sekarang?"),
    )

    checks = [
        ("frontend", lambda: _expect_text(config.frontend_url)),
        ("backend health", lambda: _expect_json(config.backend_url, "/health", expected_status="ok")),
        ("backend readiness", lambda: _expect_ready(config.backend_url)),
        ("fresh search", lambda: _expect_fresh_search(config.backend_url, config.explain_query)),
        ("explain stream", lambda: _expect_explain_stream(config.backend_url, config.explain_query)),
    ]

    failures: list[str] = []
    for name, check in checks:
        try:
            check()
            print(f"ok: {name}")
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            print(f"failed: {name}: {exc}", file=sys.stderr)

    if failures:
        print("\nDeployment smoke failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _expect_text(url: str) -> None:
    with urlopen(url, timeout=TIMEOUT_SECONDS) as response:
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}")
        body = response.read(4096).decode("utf-8", errors="ignore")
    if "Politik" not in body and "politik" not in body:
        raise RuntimeError("frontend response did not look like Politik Yuk")


def _expect_json(base_url: str, path: str, *, expected_status: str | None = None) -> dict[str, Any]:
    payload = _request_json(urljoin(base_url, path), method="GET")
    if expected_status and payload.get("status") != expected_status:
        raise RuntimeError(f"expected status={expected_status}, got {payload.get('status')}")
    return payload


def _expect_ready(base_url: str) -> None:
    payload = _expect_json(base_url, "/ready")
    if payload.get("status") != "ok":
        raise RuntimeError(json.dumps(payload, separators=(",", ":")))
    dependencies = payload.get("dependencies", [])
    required = {"model_provider", "search_provider", "postgres", "redis", "worker_queue"}
    present = {dependency.get("name") for dependency in dependencies}
    missing = required - present
    if missing:
        raise RuntimeError(f"missing readiness dependencies: {sorted(missing)}")


def _expect_fresh_search(base_url: str, query: str) -> None:
    payload = _request_json(
        urljoin(base_url, "/api/search/freshness"),
        method="POST",
        data={"query": query, "max_results": 2},
    )
    if payload.get("provider_failed"):
        raise RuntimeError(json.dumps(payload, separators=(",", ":")))
    if not payload.get("candidates"):
        raise RuntimeError("fresh search returned no candidates")


def _expect_explain_stream(base_url: str, query: str) -> None:
    request = Request(
        urljoin(base_url, "/api/explain"),
        data=json.dumps(
            {
                "input_type": "question",
                "text": query,
                "depth": "quick",
                "lenses": [],
                "locale": "id-ID",
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read().decode("utf-8", errors="ignore")
    events = _parse_sse(body)
    complete = [event for event in events if event.get("event_type") == "complete"]
    if not complete:
        raise RuntimeError("explain stream did not complete")
    explanation = complete[-1].get("payload", {}).get("explanation", {})
    if not explanation.get("sources"):
        raise RuntimeError("explain response completed without sources")


def _request_json(url: str, *, method: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    encoded = json.dumps(data).encode("utf-8") if data is not None else None
    request = Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method=method,
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(str(exc)) from exc


def _parse_sse(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for chunk in body.split("\n\n"):
        data_lines = [
            line.removeprefix("data:").strip()
            for line in chunk.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            continue
        events.append(json.loads("\n".join(data_lines)))
    return events


if __name__ == "__main__":
    raise SystemExit(main())
