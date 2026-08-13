import { describe, expect, it } from "vitest";
import { parseServerSentEvents } from "./explain-stream";

describe("parseServerSentEvents", () => {
  it("parses one or more streamed events", () => {
    const events = parseServerSentEvents(
      [
        'event: request_received\ndata: {"request_id":"one","event_type":"request_received","message":"Request received","payload":{}}',
        'event: complete\ndata: {"request_id":"one","event_type":"complete","message":"Done","payload":{"ok":true}}',
      ].join("\n\n"),
    );

    expect(events).toHaveLength(2);
    expect(events[0]?.event_type).toBe("request_received");
    expect(events[1]?.payload).toEqual({ ok: true });
  });
});
