from dataclasses import dataclass
from uuid import UUID

from app.retrieval import EvidenceCandidate
from app.schemas import (
    AnalyticalLens,
    Citation,
    Claim,
    ClaimStatus,
    EvidencePassage,
    ExplanationDepth,
    ExplanationResponse,
    ExplanationSection,
    ExplanationSectionType,
    ParsedIntent,
    Source,
    UncertaintyLevel,
    UserInputRequest,
)

FACT_SECTION_TYPES = {
    ExplanationSectionType.TLDR,
    ExplanationSectionType.ESSENTIAL_CONTEXT,
    ExplanationSectionType.KEY_CLAIMS,
    ExplanationSectionType.EXPLANATION,
    ExplanationSectionType.DISAGREEMENT,
    ExplanationSectionType.WHY_IT_MATTERS,
}


@dataclass(frozen=True)
class CitationValidationResult:
    explanation: ExplanationResponse
    valid: bool
    warnings: list[str]


def compose_grounded_explanation(
    *,
    request_id: UUID,
    request: UserInputRequest,
    intent: ParsedIntent,
    topic: str,
    evidence_candidates: list[EvidenceCandidate],
    warnings: list[str] | None = None,
) -> ExplanationResponse:
    if not evidence_candidates:
        return _no_evidence_explanation(
            request_id=request_id,
            request=request,
            intent=intent,
            topic=topic,
            warnings=warnings or [],
        )

    sources, evidence, citations = _evidence_contracts(evidence_candidates)
    claims = _claims_from_evidence(evidence, citations)
    sections = _sections_from_evidence(
        request=request,
        topic=topic,
        evidence=evidence,
        citations=citations,
        warnings=warnings or [],
    )
    return ExplanationResponse(
        request_id=request_id,
        input=request,
        intent=intent,
        sections=sections,
        sources=sources,
        evidence=evidence,
        citations=citations,
        claims=claims,
        entities=[],
        follow_up_questions=[
            "Which cited source should be checked against another outlet?",
            "Do you want the same evidence explained from a different lens?",
            "Should unsupported claims from the original input be investigated next?",
        ][: 2 if request.depth == ExplanationDepth.QUICK else 3],
    )


def validate_explanation_citations(explanation: ExplanationResponse) -> CitationValidationResult:
    source_ids = {source.id for source in explanation.sources}
    evidence_by_id = {evidence.id: evidence for evidence in explanation.evidence}
    valid_citations = [
        citation
        for citation in explanation.citations
        if citation.source_id in source_ids and citation.evidence_passage_id in evidence_by_id
    ]
    valid_citation_ids = {citation.id for citation in valid_citations}
    valid_evidence_ids = set(evidence_by_id)
    warnings: list[str] = []
    if len(valid_citations) != len(explanation.citations):
        warnings.append("invalid_citations_removed")

    sections: list[ExplanationSection] = []
    for section in explanation.sections:
        citation_ids = [
            citation_id
            for citation_id in section.citation_ids
            if citation_id in valid_citation_ids
        ]
        uncertainty = section.uncertainty
        body = section.body
        if section.section_type in FACT_SECTION_TYPES and explanation.evidence and not citation_ids:
            uncertainty = UncertaintyLevel.HIGH
            body = f"{body} Citation support was insufficient for this section."
            warnings.append(f"section_marked_uncertain:{section.section_type}")
        sections.append(
            section.model_copy(
                update={
                    "body": body,
                    "citation_ids": citation_ids,
                    "uncertainty": uncertainty,
                }
            )
        )

    claims: list[Claim] = []
    for claim in explanation.claims:
        supporting_ids = [
            evidence_id
            for evidence_id in claim.supporting_evidence_ids
            if evidence_id in valid_evidence_ids
        ]
        contradicting_ids = [
            evidence_id
            for evidence_id in claim.contradicting_evidence_ids
            if evidence_id in valid_evidence_ids
        ]
        citation_ids = [
            citation_id for citation_id in claim.citation_ids if citation_id in valid_citation_ids
        ]
        status = claim.status
        uncertainty = claim.uncertainty
        if not supporting_ids and not contradicting_ids:
            status = ClaimStatus.UNVERIFIED
            uncertainty = UncertaintyLevel.HIGH
            citation_ids = []
            warnings.append("unsupported_claim_marked_unverified")
        claims.append(
            claim.model_copy(
                update={
                    "status": status,
                    "uncertainty": uncertainty,
                    "supporting_evidence_ids": supporting_ids,
                    "contradicting_evidence_ids": contradicting_ids,
                    "citation_ids": citation_ids,
                }
            )
        )

    validated = explanation.model_copy(
        update={
            "sections": sections,
            "citations": valid_citations,
            "claims": claims,
        }
    )
    return CitationValidationResult(
        explanation=validated,
        valid=not warnings,
        warnings=warnings,
    )


def _no_evidence_explanation(
    *,
    request_id: UUID,
    request: UserInputRequest,
    intent: ParsedIntent,
    topic: str,
    warnings: list[str],
) -> ExplanationResponse:
    warning_text = " ".join(warnings)
    body = (
        f"Belum ada bukti terambil yang cukup untuk menjawab tentang {topic}. "
        "Politik Yuk tidak akan memberi kesimpulan faktual tanpa sumber yang dapat ditelusuri."
    )
    if warning_text:
        body = f"{body} Catatan sistem: {warning_text}."
    return ExplanationResponse(
        request_id=request_id,
        input=request,
        intent=intent,
        sections=[
            ExplanationSection(
                section_type=ExplanationSectionType.TLDR,
                title="TL;DR",
                body=body,
                citation_ids=[],
                uncertainty=UncertaintyLevel.HIGH,
            ),
            ExplanationSection(
                section_type=ExplanationSectionType.ESSENTIAL_CONTEXT,
                title="Evidence status",
                body=(
                    "Tidak ada klaim politik penting yang disimpulkan karena evidence set kosong."
                ),
                citation_ids=[],
                uncertainty=UncertaintyLevel.HIGH,
            ),
        ],
        sources=[],
        evidence=[],
        citations=[],
        claims=[
            Claim(
                text="No retrieved evidence is available for this request yet.",
                normalized_text="no retrieved evidence available for this request yet",
                status=ClaimStatus.UNVERIFIED,
                uncertainty=UncertaintyLevel.HIGH,
                supporting_evidence_ids=[],
                citation_ids=[],
            )
        ],
        entities=[],
        follow_up_questions=[
            "Should Politik Yuk search for fresher sources?",
            "Do you want to paste a source URL for ingestion?",
        ],
    )


def _evidence_contracts(
    candidates: list[EvidenceCandidate],
) -> tuple[list[Source], list[EvidencePassage], list[Citation]]:
    sources: list[Source] = []
    evidence: list[EvidencePassage] = []
    citations: list[Citation] = []
    seen_sources: set[UUID] = set()
    for index, candidate in enumerate(candidates, start=1):
        if candidate.source_id not in seen_sources:
            sources.append(
                Source(
                    id=candidate.source_id,
                    url=candidate.url,
                    title=candidate.title,
                    publisher=candidate.publisher,
                    published_at=candidate.published_at,
                    retrieved_at=candidate.retrieved_at,
                    source_type=candidate.source_type,
                )
            )
            seen_sources.add(candidate.source_id)
        evidence.append(
            EvidencePassage(
                id=candidate.evidence_id,
                source_id=candidate.source_id,
                text=candidate.text,
                start_char=candidate.start_char,
                end_char=candidate.end_char,
                relevance_score=max(min(candidate.final_score or candidate.relevance_score, 1), 0),
            )
        )
        citations.append(
            Citation(
                source_id=candidate.source_id,
                evidence_passage_id=candidate.evidence_id,
                label=candidate.citation_label or str(index),
                quote=candidate.text[:1_000],
            )
        )
    return sources, evidence, citations


def _claims_from_evidence(
    evidence: list[EvidencePassage],
    citations: list[Citation],
) -> list[Claim]:
    claims: list[Claim] = []
    for passage, citation in zip(evidence, citations, strict=True):
        sentence = _first_sentence(passage.text)
        claims.append(
            Claim(
                text=sentence,
                normalized_text=_normalize_claim(sentence),
                status=ClaimStatus.SUPPORTED,
                uncertainty=UncertaintyLevel.MEDIUM,
                supporting_evidence_ids=[passage.id],
                citation_ids=[citation.id],
            )
        )
    return claims


def _sections_from_evidence(
    *,
    request: UserInputRequest,
    topic: str,
    evidence: list[EvidencePassage],
    citations: list[Citation],
    warnings: list[str],
) -> list[ExplanationSection]:
    citation_ids = [citation.id for citation in citations]
    fact_limit = 2 if request.depth == ExplanationDepth.QUICK else 4
    facts = [_first_sentence(item.text) for item in evidence[:fact_limit]]
    sections = [
        ExplanationSection(
            section_type=ExplanationSectionType.TLDR,
            title="TL;DR",
            body=_quick_summary(topic, facts),
            citation_ids=citation_ids[: max(1, min(len(citation_ids), 2))],
            uncertainty=UncertaintyLevel.MEDIUM,
        ),
        ExplanationSection(
            section_type=ExplanationSectionType.KEY_CLAIMS,
            title="Facts from retrieved evidence",
            body=" ".join(f"[{index}] {fact}" for index, fact in enumerate(facts, start=1)),
            citation_ids=citation_ids[: len(facts)],
            uncertainty=UncertaintyLevel.MEDIUM,
        ),
    ]
    if request.depth == ExplanationDepth.IN_DEPTH:
        sections.extend(
            [
                ExplanationSection(
                    section_type=ExplanationSectionType.EXPLANATION,
                    title="Interpretations",
                    body=_interpretation_text(request.lenses, evidence),
                    citation_ids=citation_ids[: max(1, min(len(citation_ids), 3))],
                    uncertainty=UncertaintyLevel.MEDIUM,
                ),
                ExplanationSection(
                    section_type=ExplanationSectionType.WHY_IT_MATTERS,
                    title="Predictions",
                    body=(
                        "Tidak ada prediksi yang dinyatakan sebagai fakta. Prediksi hanya boleh "
                        "dibuat jika evidence yang dikutip memang memuat proyeksi atau rencana."
                    ),
                    citation_ids=[],
                    uncertainty=UncertaintyLevel.HIGH,
                ),
                ExplanationSection(
                    section_type=ExplanationSectionType.DISAGREEMENT,
                    title="Disagreement and uncertainty",
                    body=_uncertainty_text(warnings),
                    citation_ids=citation_ids[:1],
                    uncertainty=UncertaintyLevel.HIGH if warnings else UncertaintyLevel.MEDIUM,
                ),
            ]
        )
    else:
        sections.append(
            ExplanationSection(
                section_type=ExplanationSectionType.DISAGREEMENT,
                title="Uncertainty",
                body=_uncertainty_text(warnings),
                citation_ids=citation_ids[:1],
                uncertainty=UncertaintyLevel.HIGH if warnings else UncertaintyLevel.MEDIUM,
            )
        )
    return sections


def _quick_summary(topic: str, facts: list[str]) -> str:
    if not facts:
        return f"Belum ada fakta terambil yang cukup untuk menjawab {topic}."
    return f"Tentang {topic}, evidence yang terambil menunjukkan: {' '.join(facts[:2])}"


def _interpretation_text(lenses: list[AnalyticalLens], evidence: list[EvidencePassage]) -> str:
    lens = lenses[0] if lenses else AnalyticalLens.DEMOCRACY
    lens_value = lens.value if isinstance(lens, AnalyticalLens) else str(lens)
    evidence_text = " ".join(_first_sentence(item.text) for item in evidence[:3])
    return (
        f"Dilihat dari lensa {lens_value}, interpretasi harus tetap terbatas pada evidence "
        f"berikut: {evidence_text}"
    )


def _uncertainty_text(warnings: list[str]) -> str:
    if not warnings:
        return (
            "Tidak ada pertentangan eksplisit yang terdeteksi di evidence set ini. "
            "Kesimpulan tetap dibatasi pada sumber yang dikutip."
        )
    return (
        "Ada keterbatasan pada evidence set ini: "
        f"{'; '.join(warnings)}. Kesimpulan faktual harus diperlakukan sementara."
    )


def _first_sentence(text: str) -> str:
    normalized = " ".join(text.split())
    for separator in [". ", "? ", "! "]:
        if separator in normalized:
            return normalized.split(separator, maxsplit=1)[0].strip() + separator.strip()
    return normalized[:500]


def _normalize_claim(text: str) -> str:
    return " ".join(text.casefold().split())[:2_000]
