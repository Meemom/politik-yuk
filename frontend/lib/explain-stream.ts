import type { ExplanationResponse, StreamEvent, UserInputRequest } from "@/types/api-contracts";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export type ExplainStreamUpdate =
  | { type: "progress"; event: StreamEvent }
  | { type: "complete"; event: StreamEvent; explanation: ExplanationResponse }
  | { type: "error"; event: StreamEvent };

export function parseServerSentEvents(buffer: string): StreamEvent[] {
  return buffer
    .split("\n\n")
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => {
      const dataLine = chunk.split("\n").find((line) => line.startsWith("data:"));
      if (!dataLine) {
        throw new Error("SSE chunk did not include a data line.");
      }
      return JSON.parse(dataLine.slice("data:".length).trim()) as StreamEvent;
    });
}

function apiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL;
}

function explanationFromEvent(event: StreamEvent): ExplanationResponse {
  const explanation = event.payload.explanation;
  if (!explanation || typeof explanation !== "object") {
    throw new Error("Complete event did not include an explanation payload.");
  }
  return explanation as ExplanationResponse;
}

export async function streamExplanation(
  request: UserInputRequest,
  onUpdate: (update: ExplainStreamUpdate) => void,
) {
  const response = await fetch(`${apiBaseUrl()}/api/explain`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Explain request failed with status ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Explain response did not include a readable stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const event of parseServerSentEvents(chunks.join("\n\n"))) {
      if (event.event_type === "complete") {
        onUpdate({ type: "complete", event, explanation: explanationFromEvent(event) });
      } else if (event.event_type === "error") {
        onUpdate({ type: "error", event });
      } else {
        onUpdate({ type: "progress", event });
      }
    }

    if (done) {
      break;
    }
  }

  for (const event of parseServerSentEvents(buffer)) {
    if (event.event_type === "complete") {
      onUpdate({ type: "complete", event, explanation: explanationFromEvent(event) });
    } else if (event.event_type === "error") {
      onUpdate({ type: "error", event });
    } else {
      onUpdate({ type: "progress", event });
    }
  }
}
