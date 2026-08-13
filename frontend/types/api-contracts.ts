export type InputType = "topic" | "question" | "headline" | "text" | "url" | "screenshot";

export type ExplanationDepth = "quick" | "in_depth";

export type AnalyticalLens =
  | "personal_finances"
  | "taxes"
  | "jobs"
  | "education"
  | "environment"
  | "civil_liberties"
  | "democracy"
  | "public_services"
  | "regional_impact";

export type ClaimStatus = "supported" | "disputed" | "opinion" | "prediction" | "unverified";

export type SourceType =
  | "government"
  | "news"
  | "international_news"
  | "academic"
  | "civil_society"
  | "social_media"
  | "other";

export type UncertaintyLevel = "low" | "medium" | "high" | "unknown";

export type GraphEdgeType =
  | "proposed_by"
  | "opposed_by"
  | "governs"
  | "amended_by"
  | "member_of"
  | "caused"
  | "responded_to"
  | "related_to";

export type StreamEventType =
  | "request_received"
  | "intent_extracted"
  | "retrieval_planned"
  | "evidence_retrieved"
  | "answer_composing"
  | "citations_validated"
  | "complete"
  | "error";

export type EntityType =
  | "politician"
  | "political_party"
  | "government_institution"
  | "legislation"
  | "program"
  | "historical_event"
  | "organization"
  | "location"
  | "other";

export type ExplanationSectionType =
  | "tldr"
  | "essential_context"
  | "key_claims"
  | "explanation"
  | "disagreement"
  | "why_it_matters"
  | "timeline"
  | "follow_ups";

export type QuizQuestionType = "multiple_choice" | "true_false" | "short_answer";

export interface UserInputRequest {
  input_type: InputType;
  text?: string | null;
  url?: string | null;
  image_id?: string | null;
  depth: ExplanationDepth;
  lenses: AnalyticalLens[];
  locale: string;
}

export interface ParsedIntent {
  topic: string;
  intent: string;
  depth: ExplanationDepth;
  lenses: AnalyticalLens[];
  questions: string[];
  tone: string;
  input_language: string;
}

export interface RetrievalPlan {
  queries: string[];
  needs_freshness: boolean;
  needs_vector_search: boolean;
  needs_keyword_search: boolean;
  target_source_types: SourceType[];
  freshness_window_days?: number | null;
}

export interface Source {
  id: string;
  url: string;
  canonical_url?: string | null;
  title: string;
  publisher: string;
  author?: string | null;
  published_at?: string | null;
  retrieved_at: string;
  source_type: SourceType;
  language: string;
}

export interface EvidencePassage {
  id: string;
  source_id: string;
  text: string;
  start_char?: number | null;
  end_char?: number | null;
  relevance_score?: number | null;
}

export interface Citation {
  id: string;
  source_id: string;
  evidence_passage_id: string;
  label: string;
  quote?: string | null;
}

export interface Entity {
  id: string;
  name: string;
  entity_type: EntityType;
  aliases: string[];
  description?: string | null;
  source_ids: string[];
}

export interface Claim {
  id: string;
  text: string;
  normalized_text: string;
  status: ClaimStatus;
  uncertainty: UncertaintyLevel;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  entity_ids: string[];
  citation_ids: string[];
}

export interface TimelineEvent {
  id: string;
  title: string;
  happened_at?: string | null;
  date_label?: string | null;
  summary: string;
  citation_ids: string[];
  uncertainty: UncertaintyLevel;
}

export interface TopicGraphNode {
  id: string;
  label: string;
  node_type: string;
  entity_id?: string | null;
  claim_id?: string | null;
  topic_id?: string | null;
}

export interface TopicGraphEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: GraphEdgeType;
  citation_ids: string[];
  confidence?: number | null;
}

export interface ExplanationSection {
  section_type: ExplanationSectionType;
  title: string;
  body: string;
  citation_ids: string[];
  uncertainty: UncertaintyLevel;
}

export interface ExplanationResponse {
  request_id: string;
  input: UserInputRequest;
  intent: ParsedIntent;
  sections: ExplanationSection[];
  sources: Source[];
  evidence: EvidencePassage[];
  citations: Citation[];
  claims: Claim[];
  entities: Entity[];
  timeline: TimelineEvent[];
  graph_nodes: TopicGraphNode[];
  graph_edges: TopicGraphEdge[];
  follow_up_questions: string[];
}

export interface QuizQuestion {
  id: string;
  question_type: QuizQuestionType;
  prompt: string;
  options: string[];
  correct_answer: string;
  explanation: string;
  citation_ids: string[];
}

export interface Quiz {
  id: string;
  explanation_request_id: string;
  questions: QuizQuestion[];
}

export interface TopicUpdate {
  id: string;
  title: string;
  summary: string;
  introduced_claim_ids: string[];
  modified_claim_ids: string[];
  resolved_uncertainty_ids: string[];
  citation_ids: string[];
  detected_at: string;
}

export interface SavedTopicUpdate {
  saved_topic_id: string;
  topic: string;
  last_read_at: string;
  latest_checked_at: string;
  updates: TopicUpdate[];
}

export interface StreamEvent {
  request_id: string;
  event_type: StreamEventType;
  message: string;
  payload: Record<string, unknown>;
}

export interface ResponseEnvelope<TData = Record<string, unknown>> {
  request_id: string;
  data?: TData | null;
  error?: string | null;
}
