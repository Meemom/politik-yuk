from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class InputType(StrEnum):
    TOPIC = "topic"
    QUESTION = "question"
    HEADLINE = "headline"
    TEXT = "text"
    URL = "url"
    SCREENSHOT = "screenshot"


class ExplanationDepth(StrEnum):
    QUICK = "quick"
    IN_DEPTH = "in_depth"


class AnalyticalLens(StrEnum):
    PERSONAL_FINANCES = "personal_finances"
    TAXES = "taxes"
    JOBS = "jobs"
    EDUCATION = "education"
    ENVIRONMENT = "environment"
    CIVIL_LIBERTIES = "civil_liberties"
    DEMOCRACY = "democracy"
    PUBLIC_SERVICES = "public_services"
    REGIONAL_IMPACT = "regional_impact"


class ClaimStatus(StrEnum):
    SUPPORTED = "supported"
    DISPUTED = "disputed"
    OPINION = "opinion"
    PREDICTION = "prediction"
    UNVERIFIED = "unverified"


class SourceType(StrEnum):
    GOVERNMENT = "government"
    NEWS = "news"
    INTERNATIONAL_NEWS = "international_news"
    ACADEMIC = "academic"
    CIVIL_SOCIETY = "civil_society"
    SOCIAL_MEDIA = "social_media"
    OTHER = "other"


class UncertaintyLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class GraphEdgeType(StrEnum):
    PROPOSED_BY = "proposed_by"
    OPPOSED_BY = "opposed_by"
    GOVERNS = "governs"
    AMENDED_BY = "amended_by"
    MEMBER_OF = "member_of"
    CAUSED = "caused"
    RESPONDED_TO = "responded_to"
    RELATED_TO = "related_to"


class StreamEventType(StrEnum):
    REQUEST_RECEIVED = "request_received"
    INTENT_EXTRACTED = "intent_extracted"
    RETRIEVAL_PLANNED = "retrieval_planned"
    EVIDENCE_RETRIEVED = "evidence_retrieved"
    ANSWER_COMPOSING = "answer_composing"
    CITATIONS_VALIDATED = "citations_validated"
    COMPLETE = "complete"
    ERROR = "error"


class EntityType(StrEnum):
    POLITICIAN = "politician"
    POLITICAL_PARTY = "political_party"
    GOVERNMENT_INSTITUTION = "government_institution"
    LEGISLATION = "legislation"
    PROGRAM = "program"
    HISTORICAL_EVENT = "historical_event"
    ORGANIZATION = "organization"
    LOCATION = "location"
    OTHER = "other"


class ExplanationSectionType(StrEnum):
    TLDR = "tldr"
    ESSENTIAL_CONTEXT = "essential_context"
    KEY_CLAIMS = "key_claims"
    EXPLANATION = "explanation"
    DISAGREEMENT = "disagreement"
    WHY_IT_MATTERS = "why_it_matters"
    TIMELINE = "timeline"
    FOLLOW_UPS = "follow_ups"


class QuizQuestionType(StrEnum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class ResponseEnvelope(ContractModel):
    request_id: UUID = Field(default_factory=uuid4)
    data: dict[str, Any] | None = None
    error: str | None = None


class UserInputRequest(ContractModel):
    input_type: InputType
    text: str | None = Field(default=None, min_length=1, max_length=20_000)
    url: str | None = Field(default=None, min_length=1, max_length=2_048)
    image_id: str | None = Field(default=None, min_length=1, max_length=256)
    depth: ExplanationDepth = ExplanationDepth.QUICK
    lenses: list[AnalyticalLens] = Field(default_factory=list, max_length=5)
    locale: str = Field(default="id-ID", min_length=2, max_length=16)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            msg = "text cannot be blank"
            raise ValueError(msg)
        return stripped


class ParsedIntent(ContractModel):
    topic: str = Field(min_length=1, max_length=512)
    intent: str = Field(min_length=1, max_length=128)
    depth: ExplanationDepth
    lenses: list[AnalyticalLens] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    tone: str = Field(default="clear Indonesian", max_length=128)
    input_language: str = Field(default="id", max_length=16)


class RetrievalPlan(ContractModel):
    queries: list[str] = Field(min_length=1, max_length=8)
    needs_freshness: bool = True
    needs_vector_search: bool = True
    needs_keyword_search: bool = True
    target_source_types: list[SourceType] = Field(default_factory=list)
    freshness_window_days: int | None = Field(default=None, ge=1, le=3650)


class Source(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    url: str = Field(min_length=1, max_length=2_048)
    canonical_url: str | None = Field(default=None, max_length=2_048)
    title: str = Field(min_length=1, max_length=512)
    publisher: str = Field(min_length=1, max_length=256)
    author: str | None = Field(default=None, max_length=256)
    published_at: datetime | None = None
    retrieved_at: datetime
    source_type: SourceType
    language: str = Field(default="id", max_length=16)


class EvidencePassage(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    text: str = Field(min_length=1, max_length=8_000)
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)
    relevance_score: float | None = Field(default=None, ge=0, le=1)


class Citation(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    evidence_passage_id: UUID
    label: str = Field(min_length=1, max_length=32)
    quote: str | None = Field(default=None, max_length=1_000)


class Entity(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=256)
    entity_type: EntityType
    aliases: list[str] = Field(default_factory=list)
    description: str | None = Field(default=None, max_length=2_000)
    source_ids: list[UUID] = Field(default_factory=list)


class Claim(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    text: str = Field(min_length=1, max_length=2_000)
    normalized_text: str = Field(min_length=1, max_length=2_000)
    status: ClaimStatus
    uncertainty: UncertaintyLevel = UncertaintyLevel.UNKNOWN
    supporting_evidence_ids: list[UUID] = Field(default_factory=list)
    contradicting_evidence_ids: list[UUID] = Field(default_factory=list)
    entity_ids: list[UUID] = Field(default_factory=list)
    citation_ids: list[UUID] = Field(default_factory=list)


class TimelineEvent(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=256)
    happened_at: datetime | None = None
    date_label: str | None = Field(default=None, max_length=128)
    summary: str = Field(min_length=1, max_length=1_000)
    citation_ids: list[UUID] = Field(default_factory=list)
    uncertainty: UncertaintyLevel = UncertaintyLevel.UNKNOWN


class TopicGraphNode(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    label: str = Field(min_length=1, max_length=256)
    node_type: str = Field(min_length=1, max_length=64)
    entity_id: UUID | None = None
    claim_id: UUID | None = None
    topic_id: UUID | None = None


class TopicGraphEdge(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    source_node_id: UUID
    target_node_id: UUID
    edge_type: GraphEdgeType
    citation_ids: list[UUID] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


class ExplanationSection(ContractModel):
    section_type: ExplanationSectionType
    title: str = Field(min_length=1, max_length=128)
    body: str = Field(min_length=1, max_length=6_000)
    citation_ids: list[UUID] = Field(default_factory=list)
    uncertainty: UncertaintyLevel = UncertaintyLevel.UNKNOWN


class ExplanationResponse(ContractModel):
    request_id: UUID = Field(default_factory=uuid4)
    input: UserInputRequest
    intent: ParsedIntent
    sections: list[ExplanationSection] = Field(min_length=1)
    sources: list[Source] = Field(default_factory=list)
    evidence: list[EvidencePassage] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    graph_nodes: list[TopicGraphNode] = Field(default_factory=list)
    graph_edges: list[TopicGraphEdge] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


class QuizQuestion(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    question_type: QuizQuestionType
    prompt: str = Field(min_length=1, max_length=1_000)
    options: list[str] = Field(default_factory=list)
    correct_answer: str = Field(min_length=1, max_length=1_000)
    explanation: str = Field(min_length=1, max_length=2_000)
    citation_ids: list[UUID] = Field(default_factory=list)


class Quiz(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    explanation_request_id: UUID
    questions: list[QuizQuestion] = Field(min_length=1, max_length=10)


class TopicUpdate(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=256)
    summary: str = Field(min_length=1, max_length=2_000)
    introduced_claim_ids: list[UUID] = Field(default_factory=list)
    modified_claim_ids: list[UUID] = Field(default_factory=list)
    resolved_uncertainty_ids: list[UUID] = Field(default_factory=list)
    citation_ids: list[UUID] = Field(default_factory=list)
    detected_at: datetime


class SavedTopicUpdate(ContractModel):
    saved_topic_id: UUID
    topic: str = Field(min_length=1, max_length=512)
    last_read_at: datetime
    latest_checked_at: datetime
    updates: list[TopicUpdate] = Field(default_factory=list)


class StreamEvent(ContractModel):
    request_id: UUID
    event_type: StreamEventType
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
