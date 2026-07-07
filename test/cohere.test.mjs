import assert from "node:assert/strict";
import test from "node:test";
import {
  DEFAULT_COHERE_MODEL,
  READING_LEVEL_PROMPT_GUIDANCE,
  buildAyaPrompt,
  buildCohereChatPayload,
  extractCohereText,
  generateExplanationWithAya,
  parseExplanationJson,
} from "../server/cohere.js";

test("builds an Indonesian Aya prompt with the article and level", () => {
  const prompt = buildAyaPrompt({
    articleText: "DPR membahas rancangan undang-undang baru.",
    readingLevel: "sma",
  });

  assert.match(prompt, /Bahasa Indonesia/);
  assert.match(prompt, /SMA/);
  assert.match(prompt, /DPR membahas/);
  assert.match(prompt, /Jangan berpihak/);
  assert.match(prompt, /Jawab hanya dengan JSON valid/);
  assert.match(prompt, /criticalQuestions/);
});

test("uses distinct reading-level guidance in prompts", () => {
  const prompts = Object.keys(READING_LEVEL_PROMPT_GUIDANCE).map((level) =>
    buildAyaPrompt({
      articleText: "a".repeat(300),
      readingLevel: level,
    })
  );

  assert.match(prompts[0], /kalimat pendek/i);
  assert.match(prompts[1], /konteks politik dasar/i);
  assert.match(prompts[2], /lebih analitis/i);
  assert.notEqual(prompts[0], prompts[2]);
});

test("keeps political safety guardrails in the prompt", () => {
  const prompt = buildAyaPrompt({
    articleText: "a".repeat(300),
    readingLevel: "sma",
  });

  assert.match(prompt, /Jangan menambahkan fakta baru/);
  assert.match(prompt, /Bedakan isi artikel dari interpretasi/);
  assert.match(prompt, /Jangan berpihak/);
  assert.match(prompt, /needsVerification/);
  assert.match(prompt, /klaim yang belum terbukti/);
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

test("parses and normalizes structured Aya explanations", () => {
  const explanation = parseExplanationJson(`\`\`\`json
  {
    "summary": "Ringkasan.",
    "simpleExplanation": "Penjelasan.",
    "entities": [{ "name": "DPR", "description": "Lembaga legislatif." }],
    "terms": [{ "term": "RUU", "definition": "Rancangan undang-undang." }],
    "whyItMatters": "Penting untuk publik.",
    "dailyImpact": "Bisa memengaruhi layanan.",
    "criticalQuestions": ["Siapa terdampak?"],
    "needsVerification": ["Angka anggaran."]
  }
  \`\`\``);

  assert.equal(explanation.summary, "Ringkasan.");
  assert.equal(explanation.entities[0].name, "DPR");
  assert.equal(explanation.terms[0].term, "RUU");
  assert.deepEqual(explanation.criticalQuestions, ["Siapa terdampak?"]);
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
            content: [
              {
                type: "text",
                text: JSON.stringify({
                  summary: "Ringkasan.",
                  simpleExplanation: "Penjelasan.",
                  entities: [],
                  terms: [],
                  whyItMatters: "Penting.",
                  dailyImpact: "Dampak.",
                  criticalQuestions: ["Apa dampaknya?"],
                  needsVerification: ["Data angka."],
                }),
              },
            ],
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
  assert.equal(result.explanation.summary, "Ringkasan.");
  assert.match(result.rawText, /Ringkasan/);
  assert.equal(result.finishReason, "COMPLETE");
});
