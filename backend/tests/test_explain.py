import json

from fastapi.testclient import TestClient

from app.main import app


def _sse_events(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for chunk in body.strip().split("\n\n"):
        data_line = next(line for line in chunk.splitlines() if line.startswith("data: "))
        events.append(json.loads(data_line.removeprefix("data: ")))
    return events


def test_explain_streams_progress_and_final_answer() -> None:
    client = TestClient(app)

    with client.stream(
        "POST",
        "/api/explain",
        json={
            "input_type": "question",
            "text": "Kenapa mahasiswa protes revisi UU TNI?",
            "depth": "quick",
            "lenses": ["democracy"],
            "locale": "id-ID",
        },
    ) as response:
        body = response.read().decode()

    events = _sse_events(body)
    event_types = [event["event_type"] for event in events]
    final_payload = events[-1]["payload"]

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-request-id"]
    assert event_types == [
        "request_received",
        "intent_extracted",
        "retrieval_planned",
        "evidence_retrieved",
        "answer_composing",
        "citations_validated",
        "complete",
    ]
    assert isinstance(final_payload, dict)
    assert final_payload["explanation"]["sections"][0]["title"] == "TL;DR"
    assert final_payload["explanation"]["citations"][0]["label"] == "1"


def test_explain_rejects_missing_url_for_url_input() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/explain",
        json={
            "input_type": "url",
            "depth": "quick",
            "lenses": [],
            "locale": "id-ID",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "URL input requires a url value."


def test_explain_streams_controlled_error_event() -> None:
    client = TestClient(app)

    with client.stream(
        "POST",
        "/api/explain",
        json={
            "input_type": "question",
            "text": "__force_error__",
            "depth": "quick",
            "lenses": [],
            "locale": "id-ID",
        },
    ) as response:
        body = response.read().decode()

    events = _sse_events(body)

    assert response.status_code == 200
    assert events[-1]["event_type"] == "error"
    assert events[-1]["payload"] == {"error": "Forced placeholder graph failure."}
