import assert from "node:assert/strict";
import test from "node:test";
import {
  emptyExplanation,
  hasUsableExplanation,
  normalizeExplanation,
} from "../server/explanation-schema.js";

test("creates an empty explanation with every expected key", () => {
  assert.deepEqual(Object.keys(emptyExplanation()), [
    "summary",
    "simpleExplanation",
    "entities",
    "terms",
    "whyItMatters",
    "dailyImpact",
    "criticalQuestions",
    "needsVerification",
  ]);
});

test("normalizes string fields and array items", () => {
  const explanation = normalizeExplanation({
    summary: " Ringkasan ",
    entities: [{ name: " DPR ", description: " Lembaga legislatif " }],
    terms: [{ term: " RUU ", definition: " Rancangan undang-undang " }],
    criticalQuestions: [" Apa dampaknya? ", ""],
  });

  assert.equal(explanation.summary, "Ringkasan");
  assert.deepEqual(explanation.entities, [
    { name: "DPR", description: "Lembaga legislatif" },
  ]);
  assert.deepEqual(explanation.terms, [
    { term: "RUU", definition: "Rancangan undang-undang" },
  ]);
  assert.deepEqual(explanation.criticalQuestions, ["Apa dampaknya?"]);
});

test("detects whether a normalized explanation has useful content", () => {
  assert.equal(hasUsableExplanation(emptyExplanation()), false);
  assert.equal(
    hasUsableExplanation({ ...emptyExplanation(), summary: "Ada isi." }),
    true
  );
});
