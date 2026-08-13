from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import (
    AnalyticalLens,
    Citation,
    Claim,
    ClaimStatus,
    Entity,
    EntityType,
    EvidencePassage,
    ExplanationDepth,
    ExplanationResponse,
    ExplanationSection,
    ExplanationSectionType,
    GraphEdgeType,
    InputType,
    ParsedIntent,
    Quiz,
    QuizQuestion,
    QuizQuestionType,
    RetrievalPlan,
    SavedTopicUpdate,
    Source,
    SourceType,
    StreamEvent,
    StreamEventType,
    TimelineEvent,
    TopicGraphEdge,
    TopicGraphNode,
    TopicUpdate,
    UncertaintyLevel,
    UserInputRequest,
)


def now() -> datetime:
    return datetime.now(UTC)


def test_user_input_request_normalizes_text_and_rejects_unknown_fields() -> None:
    request = UserInputRequest(
        input_type=InputType.QUESTION,
        text="  Kenapa revisi UU TNI diprotes?  ",
        depth=ExplanationDepth.QUICK,
        lenses=[AnalyticalLens.DEMOCRACY],
    )

    assert request.text == "Kenapa revisi UU TNI diprotes?"
    assert request.model_dump()["input_type"] == "question"

    with pytest.raises(ValidationError):
        UserInputRequest(
            input_type=InputType.QUESTION,
            text="   ",
        )

    with pytest.raises(ValidationError):
        UserInputRequest(
            input_type=InputType.TOPIC,
            text="KPK",
            unsupported=True,
        )


def test_retrieval_plan_requires_at_least_one_query() -> None:
    plan = RetrievalPlan(
        queries=["revisi UU TNI protes mahasiswa"],
        target_source_types=[SourceType.NEWS, SourceType.GOVERNMENT],
        freshness_window_days=30,
    )

    assert plan.needs_freshness is True
    assert plan.model_dump()["target_source_types"] == ["news", "government"]

    with pytest.raises(ValidationError):
        RetrievalPlan(queries=[])


def test_explanation_response_supports_claim_level_citations() -> None:
    source_id = uuid4()
    evidence_id = uuid4()
    citation_id = uuid4()
    claim_id = uuid4()
    entity_id = uuid4()
    node_a = uuid4()
    node_b = uuid4()

    source = Source(
        id=source_id,
        url="https://example.com/news",
        title="Mahasiswa protes revisi UU TNI",
        publisher="Example News",
        retrieved_at=now(),
        source_type=SourceType.NEWS,
    )
    evidence = EvidencePassage(
        id=evidence_id,
        source_id=source_id,
        text="Mahasiswa menilai revisi UU TNI perlu dikaji karena berdampak pada sipil.",
        relevance_score=0.92,
    )
    citation = Citation(
        id=citation_id,
        source_id=source_id,
        evidence_passage_id=evidence_id,
        label="1",
    )
    entity = Entity(
        id=entity_id,
        name="DPR",
        entity_type=EntityType.GOVERNMENT_INSTITUTION,
        aliases=["Dewan Perwakilan Rakyat"],
        source_ids=[source_id],
    )
    claim = Claim(
        id=claim_id,
        text="Mahasiswa memprotes revisi UU TNI.",
        normalized_text="mahasiswa memprotes revisi uu tni",
        status=ClaimStatus.SUPPORTED,
        uncertainty=UncertaintyLevel.LOW,
        supporting_evidence_ids=[evidence_id],
        entity_ids=[entity_id],
        citation_ids=[citation_id],
    )
    section = ExplanationSection(
        section_type=ExplanationSectionType.TLDR,
        title="TL;DR",
        body="Mahasiswa memprotes revisi UU TNI karena khawatir soal peran militer di ranah sipil.",
        citation_ids=[citation_id],
        uncertainty=UncertaintyLevel.LOW,
    )
    event = TimelineEvent(
        title="Protes mahasiswa",
        happened_at=now(),
        summary="Mahasiswa menggelar protes terkait revisi UU TNI.",
        citation_ids=[citation_id],
    )
    graph_node_a = TopicGraphNode(
        id=node_a,
        label="Revisi UU TNI",
        node_type="topic",
    )
    graph_node_b = TopicGraphNode(
        id=node_b,
        label="DPR",
        node_type="entity",
        entity_id=entity_id,
    )
    graph_edge = TopicGraphEdge(
        source_node_id=node_a,
        target_node_id=node_b,
        edge_type=GraphEdgeType.RELATED_TO,
        citation_ids=[citation_id],
        confidence=0.75,
    )

    response = ExplanationResponse(
        input=UserInputRequest(input_type=InputType.QUESTION, text="Kenapa mahasiswa protes?"),
        intent=ParsedIntent(
            topic="revisi UU TNI",
            intent="explanation",
            depth=ExplanationDepth.QUICK,
            lenses=[AnalyticalLens.DEMOCRACY],
            questions=["why students oppose the revision"],
        ),
        sections=[section],
        sources=[source],
        evidence=[evidence],
        citations=[citation],
        claims=[claim],
        entities=[entity],
        timeline=[event],
        graph_nodes=[graph_node_a, graph_node_b],
        graph_edges=[graph_edge],
        follow_up_questions=["Apa pasal yang paling diperdebatkan?"],
    )

    dumped = response.model_dump()

    assert dumped["claims"][0]["citation_ids"] == [citation_id]
    assert dumped["sections"][0]["citation_ids"] == [citation_id]
    assert dumped["graph_edges"][0]["edge_type"] == "related_to"


def test_quiz_saved_topic_update_and_stream_event_contracts() -> None:
    request_id = uuid4()
    citation_id = uuid4()

    quiz = Quiz(
        explanation_request_id=request_id,
        questions=[
            QuizQuestion(
                question_type=QuizQuestionType.TRUE_FALSE,
                prompt="Benar atau salah: screenshot otomatis menjadi bukti.",
                correct_answer="Salah",
                explanation=(
                    "Screenshot adalah input yang perlu diverifikasi dengan sumber independen."
                ),
                citation_ids=[citation_id],
            )
        ],
    )
    topic_update = SavedTopicUpdate(
        saved_topic_id=uuid4(),
        topic="revisi UU TNI",
        last_read_at=now(),
        latest_checked_at=now(),
        updates=[
            TopicUpdate(
                title="Pernyataan resmi baru",
                summary="Ada pernyataan resmi baru yang mengubah konteks pembahasan.",
                citation_ids=[citation_id],
                detected_at=now(),
            )
        ],
    )
    event = StreamEvent(
        request_id=request_id,
        event_type=StreamEventType.CITATIONS_VALIDATED,
        message="Citations validated",
        payload={"citation_count": 1},
    )

    assert quiz.questions[0].question_type == "true_false"
    assert topic_update.updates[0].citation_ids == [citation_id]
    assert event.model_dump()["event_type"] == "citations_validated"


def test_invalid_enum_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        UserInputRequest(input_type="rumor", text="Apa ini benar?")

    with pytest.raises(ValidationError):
        Claim(
            text="Sebuah klaim",
            normalized_text="sebuah klaim",
            status="definitely_true",
        )
