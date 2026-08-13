import { describe, expect, it } from "vitest";
import type {
  AnalyticalLens,
  ExplanationResponse,
  InputType,
  StreamEvent,
  StreamEventType,
  UserInputRequest,
} from "./api-contracts";

describe("api contracts", () => {
  it("supports typed explanation responses with claim-level citations", () => {
    const inputType: InputType = "question";
    const lens: AnalyticalLens = "democracy";
    const request: UserInputRequest = {
      input_type: inputType,
      text: "Kenapa mahasiswa protes revisi UU TNI?",
      depth: "quick",
      lenses: [lens],
      locale: "id-ID",
    };

    const response: ExplanationResponse = {
      request_id: "00000000-0000-0000-0000-000000000001",
      input: request,
      intent: {
        topic: "revisi UU TNI",
        intent: "explanation",
        depth: "quick",
        lenses: [lens],
        questions: ["why students oppose the revision"],
        tone: "clear Indonesian",
        input_language: "id",
      },
      sections: [
        {
          section_type: "tldr",
          title: "TL;DR",
          body: "Mahasiswa memprotes revisi UU TNI karena khawatir soal peran militer.",
          citation_ids: ["citation-1"],
          uncertainty: "low",
        },
      ],
      sources: [],
      evidence: [],
      citations: [
        {
          id: "citation-1",
          source_id: "source-1",
          evidence_passage_id: "evidence-1",
          label: "1",
        },
      ],
      claims: [
        {
          id: "claim-1",
          text: "Mahasiswa memprotes revisi UU TNI.",
          normalized_text: "mahasiswa memprotes revisi uu tni",
          status: "supported",
          uncertainty: "low",
          supporting_evidence_ids: ["evidence-1"],
          contradicting_evidence_ids: [],
          entity_ids: [],
          citation_ids: ["citation-1"],
        },
      ],
      entities: [],
      timeline: [],
      graph_nodes: [],
      graph_edges: [],
      follow_up_questions: [],
    };

    expect(response.claims[0]?.citation_ids).toEqual(["citation-1"]);
  });

  it("supports stream event typing", () => {
    const eventType: StreamEventType = "citations_validated";
    const event: StreamEvent = {
      request_id: "00000000-0000-0000-0000-000000000001",
      event_type: eventType,
      message: "Citations validated",
      payload: { citation_count: 1 },
    };

    expect(event.event_type).toBe("citations_validated");
  });
});
