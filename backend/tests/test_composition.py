from datetime import UTC, datetime
from uuid import uuid4

from app.composition import compose_grounded_explanation, validate_explanation_citations
from app.retrieval import EvidenceCandidate, RetrievalSource
from app.schemas import (
    AnalyticalLens,
    Claim,
    ClaimStatus,
    ExplanationDepth,
    ParsedIntent,
    SourceType,
    UncertaintyLevel,
    UserInputRequest,
)

NOW = datetime(2026, 8, 19, 8, 0, tzinfo=UTC)


def request(depth: ExplanationDepth = ExplanationDepth.QUICK) -> UserInputRequest:
    return UserInputRequest(
        input_type="question",
        text="Apa dampak aturan pemilu terbaru untuk pemilih muda?",
        depth=depth,
        lenses=[AnalyticalLens.DEMOCRACY],
    )


def intent(depth: ExplanationDepth = ExplanationDepth.QUICK) -> ParsedIntent:
    return ParsedIntent(
        topic="aturan pemilu terbaru",
        intent="political_explanation",
        depth=depth,
        lenses=[AnalyticalLens.DEMOCRACY],
        questions=["Apa dampak aturan pemilu terbaru untuk pemilih muda?"],
    )


def candidate(text: str) -> EvidenceCandidate:
    return EvidenceCandidate(
        evidence_id=uuid4(),
        source_id=uuid4(),
        article_id=uuid4(),
        article_chunk_id=uuid4(),
        url="https://news.example/pemilu",
        title="Aturan pemilu terbaru",
        publisher="Example News",
        text=text,
        source_type=SourceType.NEWS,
        retrieved_at=NOW,
        published_at=NOW,
        relevance_score=0.88,
        final_score=0.9,
        retrieval_sources=(RetrievalSource.KEYWORD, RetrievalSource.RERANK),
        citation_label="1",
    )


def test_grounded_composer_uses_only_retrieved_evidence_with_citations() -> None:
    explanation = compose_grounded_explanation(
        request_id=uuid4(),
        request=request(),
        intent=intent(),
        topic="aturan pemilu terbaru",
        evidence_candidates=[
            candidate("KPU menjelaskan aturan pemilu terbaru untuk pemilih muda.")
        ],
    )

    assert explanation.sources[0].publisher == "Example News"
    assert explanation.evidence[0].text == (
        "KPU menjelaskan aturan pemilu terbaru untuk pemilih muda."
    )
    assert explanation.claims[0].status == ClaimStatus.SUPPORTED
    assert explanation.claims[0].supporting_evidence_ids == [explanation.evidence[0].id]
    assert explanation.claims[0].citation_ids == [explanation.citations[0].id]
    assert explanation.sections[0].citation_ids == [explanation.citations[0].id]
    assert "KPU menjelaskan" in explanation.sections[0].body


def test_in_depth_mode_adds_interpretation_prediction_and_uncertainty_sections() -> None:
    explanation = compose_grounded_explanation(
        request_id=uuid4(),
        request=request(ExplanationDepth.IN_DEPTH),
        intent=intent(ExplanationDepth.IN_DEPTH),
        topic="aturan pemilu terbaru",
        evidence_candidates=[
            candidate("KPU menjelaskan aturan pemilu terbaru untuk pemilih muda.")
        ],
    )

    titles = [section.title for section in explanation.sections]

    assert "Interpretations" in titles
    assert "Predictions" in titles
    assert "Disagreement and uncertainty" in titles
    prediction = next(section for section in explanation.sections if section.title == "Predictions")
    assert prediction.citation_ids == []
    assert prediction.uncertainty == UncertaintyLevel.HIGH


def test_no_evidence_response_refuses_factual_conclusions() -> None:
    explanation = compose_grounded_explanation(
        request_id=uuid4(),
        request=request(),
        intent=intent(),
        topic="aturan pemilu terbaru",
        evidence_candidates=[],
    )

    assert explanation.sources == []
    assert explanation.citations == []
    assert explanation.claims[0].status == ClaimStatus.UNVERIFIED
    assert "tidak akan memberi kesimpulan faktual" in explanation.sections[0].body


def test_citation_validator_marks_unsupported_claims_uncertain() -> None:
    explanation = compose_grounded_explanation(
        request_id=uuid4(),
        request=request(),
        intent=intent(),
        topic="aturan pemilu terbaru",
        evidence_candidates=[
            candidate("KPU menjelaskan aturan pemilu terbaru untuk pemilih muda.")
        ],
    )
    unsupported = Claim(
        text="Partai tertentu pasti menang.",
        normalized_text="partai tertentu pasti menang",
        status=ClaimStatus.SUPPORTED,
        uncertainty=UncertaintyLevel.LOW,
        supporting_evidence_ids=[],
        citation_ids=[],
    )
    broken = explanation.model_copy(update={"claims": [*explanation.claims, unsupported]})

    result = validate_explanation_citations(broken)

    rewritten = result.explanation.claims[-1]
    assert rewritten.status == ClaimStatus.UNVERIFIED
    assert rewritten.uncertainty == UncertaintyLevel.HIGH
    assert rewritten.citation_ids == []
    assert "unsupported_claim_marked_unverified" in result.warnings


def test_citation_validator_removes_invalid_citation_references() -> None:
    explanation = compose_grounded_explanation(
        request_id=uuid4(),
        request=request(),
        intent=intent(),
        topic="aturan pemilu terbaru",
        evidence_candidates=[
            candidate("KPU menjelaskan aturan pemilu terbaru untuk pemilih muda.")
        ],
    )
    invalid_citation = explanation.citations[0].model_copy(
        update={"evidence_passage_id": uuid4()}
    )
    broken = explanation.model_copy(update={"citations": [invalid_citation]})

    result = validate_explanation_citations(broken)

    assert result.explanation.citations == []
    assert result.explanation.sections[0].citation_ids == []
    assert result.explanation.sections[0].uncertainty == UncertaintyLevel.HIGH
    assert "invalid_citations_removed" in result.warnings
