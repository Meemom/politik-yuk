import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import (
    AnalyticalLens,
    Citation,
    Claim,
    ClaimStatus,
    Entity,
    EntityType,
    EvidencePassage,
    ExplanationResponse,
    ExplanationSection,
    ExplanationSectionType,
    ParsedIntent,
    Source,
    SourceType,
    StreamEvent,
    StreamEventType,
    UncertaintyLevel,
    UserInputRequest,
)

router = APIRouter(prefix="/api", tags=["explain"])


def _sse(event: StreamEvent) -> str:
    payload = event.model_dump(mode="json")
    return f"event: {event.event_type}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


def _topic_from_request(request: UserInputRequest) -> str:
    if request.input_type == "url":
        return request.url or "submitted URL"
    if request.input_type == "screenshot":
        return request.text or "uploaded screenshot"
    return request.text or "political topic"


def _validate_request(request: UserInputRequest) -> None:
    if request.input_type == "url" and not request.url:
        raise HTTPException(status_code=422, detail="URL input requires a url value.")
    if request.input_type != "url" and not request.text:
        raise HTTPException(status_code=422, detail="Text input is required for this input type.")


def _make_event(
    request_id: UUID,
    event_type: StreamEventType,
    message: str,
    payload: dict[str, object] | None = None,
) -> StreamEvent:
    return StreamEvent(
        request_id=request_id,
        event_type=event_type,
        message=message,
        payload=payload or {},
    )


def _placeholder_explanation(request: UserInputRequest, request_id: UUID) -> ExplanationResponse:
    topic = _topic_from_request(request)
    retrieved_at = datetime.now(UTC)
    source_id = uuid4()
    evidence_id = uuid4()
    citation_id = uuid4()
    entity_id = uuid4()

    source = Source(
        id=source_id,
        url="https://example.com/placeholder-source",
        title="Placeholder source for streaming integration",
        publisher="Politik Yuk System",
        retrieved_at=retrieved_at,
        source_type=SourceType.OTHER,
    )
    evidence = EvidencePassage(
        id=evidence_id,
        source_id=source_id,
        text=(
            "This deterministic placeholder evidence proves the streaming contract only. "
            "Live retrieval and model synthesis are implemented in later milestones."
        ),
        relevance_score=1,
    )
    citation = Citation(
        id=citation_id,
        source_id=source_id,
        evidence_passage_id=evidence_id,
        label="1",
        quote="Placeholder evidence for contract validation.",
    )
    entity = Entity(
        id=entity_id,
        name="Politik Yuk",
        entity_type=EntityType.ORGANIZATION,
        description="The product surface receiving and structuring this explanation request.",
        source_ids=[source_id],
    )
    claim = Claim(
        text="This response is a deterministic placeholder, not a factual political conclusion.",
        normalized_text="deterministic placeholder not factual political conclusion",
        status=ClaimStatus.UNVERIFIED,
        uncertainty=UncertaintyLevel.HIGH,
        supporting_evidence_ids=[evidence_id],
        entity_ids=[entity_id],
        citation_ids=[citation_id],
    )

    lenses = request.lenses or [AnalyticalLens.DEMOCRACY]

    return ExplanationResponse(
        request_id=request_id,
        input=request,
        intent=ParsedIntent(
            topic=topic[:512],
            intent="explanation",
            depth=request.depth,
            lenses=lenses,
            questions=[topic],
            tone="clear Indonesian",
        ),
        sections=[
            ExplanationSection(
                section_type=ExplanationSectionType.TLDR,
                title="TL;DR",
                body=(
                    "Politik Yuk has received the request and returned a structured placeholder "
                    "answer while live retrieval and synthesis are still pending."
                ),
                citation_ids=[citation_id],
                uncertainty=UncertaintyLevel.HIGH,
            ),
            ExplanationSection(
                section_type=ExplanationSectionType.ESSENTIAL_CONTEXT,
                title="Essential context",
                body=(
                    "Milestone 4 validates request handling, streaming events, request IDs, "
                    "and the final explanation contract. It does not claim to verify politics yet."
                ),
                citation_ids=[citation_id],
                uncertainty=UncertaintyLevel.HIGH,
            ),
            ExplanationSection(
                section_type=ExplanationSectionType.KEY_CLAIMS,
                title="Key claims",
                body=(
                    "Claims shown here are contract placeholders. Later milestones will map "
                    "real claims to retrieved evidence before generation."
                ),
                citation_ids=[citation_id],
                uncertainty=UncertaintyLevel.HIGH,
            ),
            ExplanationSection(
                section_type=ExplanationSectionType.WHY_IT_MATTERS,
                title="Why it matters",
                body=(
                    "The API now supports the response shape needed for citations, uncertainty, "
                    "related entities, and follow-up prompts in the frontend."
                ),
                citation_ids=[],
                uncertainty=UncertaintyLevel.UNKNOWN,
            ),
        ],
        sources=[source],
        evidence=[evidence],
        citations=[citation],
        claims=[claim],
        entities=[entity],
        follow_up_questions=[
            "Which sources should Politik Yuk retrieve first?",
            "Should this be a Quick Read or In Depth explanation?",
            "Which lens matters most for this topic?",
        ],
    )


async def _run_placeholder_graph(
    request: UserInputRequest,
    request_id: UUID,
) -> AsyncIterator[StreamEvent]:
    if request.text == "__force_error__":
        raise RuntimeError("Forced placeholder graph failure.")

    steps: list[tuple[StreamEventType, str, dict[str, object]]] = [
        (StreamEventType.REQUEST_RECEIVED, "Request received", {"input_type": request.input_type}),
        (StreamEventType.INTENT_EXTRACTED, "Input parsed", {"topic": _topic_from_request(request)}),
        (
            StreamEventType.RETRIEVAL_PLANNED,
            "Planning retrieval",
            {"depth": request.depth, "lenses": request.lenses},
        ),
        (
            StreamEventType.EVIDENCE_RETRIEVED,
            "Prepared placeholder evidence",
            {"candidate_count": 1},
        ),
        (StreamEventType.ANSWER_COMPOSING, "Composing structured answer", {}),
        (
            StreamEventType.CITATIONS_VALIDATED,
            "Validated placeholder citations",
            {"citation_count": 1},
        ),
    ]

    for event_type, message, payload in steps:
        yield _make_event(request_id, event_type, message, payload)
        await asyncio.sleep(0)

    explanation = _placeholder_explanation(request, request_id)
    yield _make_event(
        request_id,
        StreamEventType.COMPLETE,
        "Explanation complete",
        {"explanation": explanation.model_dump(mode="json")},
    )


async def _stream_explanation(request: UserInputRequest, request_id: UUID) -> AsyncIterator[str]:
    try:
        async for event in _run_placeholder_graph(request, request_id):
            yield _sse(event)
    except Exception as exc:
        yield _sse(
            _make_event(
                request_id,
                StreamEventType.ERROR,
                "Explanation failed",
                {"error": str(exc)},
            )
        )


@router.post("/explain")
async def explain(request: UserInputRequest) -> StreamingResponse:
    _validate_request(request)
    request_id = uuid4()
    return StreamingResponse(
        _stream_explanation(request, request_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Request-ID": str(request_id),
        },
    )
