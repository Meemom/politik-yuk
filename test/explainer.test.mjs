import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import {
  DEFAULT_READING_LEVEL,
  READING_LEVELS,
  buildPlaceholderExplanation,
  getReadingLevel,
  validateArticleText,
} from "../src/explainer.js";

test("defines the expected reading levels", () => {
  assert.deepEqual(
    READING_LEVELS.map((level) => level.id),
    ["smp", "sma", "mahasiswa"]
  );
  assert.equal(DEFAULT_READING_LEVEL, "sma");
});

test("falls back to the default reading level", () => {
  assert.equal(getReadingLevel("unknown").id, DEFAULT_READING_LEVEL);
});

test("builds placeholder sections for the complete MVP output", () => {
  const sections = buildPlaceholderExplanation("smp");

  assert.equal(sections.length, 8);
  assert.deepEqual(
    sections.map((section) => section.title),
    [
      "Ringkasan Singkat",
      "Penjelasan Sederhana",
      "Tokoh dan Lembaga Penting",
      "Istilah Sulit",
      "Kenapa Ini Penting",
      "Dampak ke Kehidupan Sehari-hari",
      "Pertanyaan Kritis",
      "Hal yang Perlu Dicek Lagi",
    ]
  );
});

test("validates article length before submission", () => {
  assert.equal(validateArticleText(""), "Tempel artikel terlebih dahulu.");
  assert.match(validateArticleText("terlalu pendek"), /terlalu pendek/i);
  assert.equal(validateArticleText("a".repeat(300)), "");
  assert.match(validateArticleText("a".repeat(20001)), /terlalu panjang/i);
});

test("index page contains the first milestone controls", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");

  assert.match(html, /Paham Politik/);
  assert.match(html, /id="article-text"/);
  assert.match(html, /id="reading-levels"/);
  assert.match(html, /id="result-content"/);
});
