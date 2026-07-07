import assert from "node:assert/strict";
import test from "node:test";
import {
  DEFAULT_COHERE_MODEL,
  buildAyaPrompt,
  buildCohereChatPayload,
  extractCohereText,
  generateExplanationWithAya,
} from "../server/cohere.js";

test("builds an Indonesian Aya prompt with the article and level", () => {
  const prompt = buildAyaPrompt({
    articleText: "DPR membahas rancangan undang-undang baru.",
    readingLevel: "sma",
  });

  assert.match(prompt, /Bahasa Indonesia/);
  assert.match(prompt, /sma/);
  assert.match(prompt, /DPR membahas/);
  assert.match(prompt, /Jangan berpihak/);
});

test("builds a Cohere v2 chat payload for Aya Expanse", () => {
  const payload = buildCohereChatPayload({
    articleText: "a".repeat(300),
    readingLevel: "smp",
    model: DEFAULT_COHERE_MODEL,
  });

  assert.equal(payload.stream, false);
  assert.equal(payload.model, "c4ai-aya-expanse-32b");
  assert.equal(payload.messages[0].role, "user");
  assert.equal(payload.temperature, 0.3);
});

test("extracts text from Cohere chat responses", () => {
  const text = extractCohereText({
    message: {
      content: [
        { type: "text", text: "Ringkasan" },
        { type: "text", text: "Penjelasan" },
      ],
    },
  });

  assert.equal(text, "Ringkasan\nPenjelasan");
});

test("calls Cohere with authorization and returns explanation metadata", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      status: 200,
      async json() {
        return {
          finish_reason: "COMPLETE",
          message: {
            content: [{ type: "text", text: "Penjelasan selesai." }],
          },
          usage: { billed_units: { input_tokens: 10, output_tokens: 20 } },
        };
      },
    };
  };

  const result = await generateExplanationWithAya({
    articleText: "a".repeat(300),
    readingLevel: "sma",
    apiKey: "test-key",
    fetchImpl,
  });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "https://api.cohere.com/v2/chat");
  assert.equal(calls[0].options.headers.authorization, "Bearer test-key");
  assert.equal(result.explanation, "Penjelasan selesai.");
  assert.equal(result.finishReason, "COMPLETE");
});
