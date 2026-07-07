import assert from "node:assert/strict";
import test from "node:test";
import {
  HISTORY_STORAGE_KEY,
  MAX_HISTORY_ITEMS,
  addHistoryItem,
  clearHistory,
  createHistoryItem,
  loadHistory,
  saveHistory,
} from "../src/history.js";

function createStorage() {
  const values = new Map();

  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
}

test("loads empty history when storage is missing or invalid", () => {
  const storage = createStorage();
  storage.setItem(HISTORY_STORAGE_KEY, "{");

  assert.deepEqual(loadHistory(storage), []);
  assert.deepEqual(loadHistory(null), []);
});

test("saves only the newest maximum history items", () => {
  const storage = createStorage();
  const items = Array.from({ length: MAX_HISTORY_ITEMS + 2 }, (_, index) => ({
    id: String(index),
  }));

  saveHistory(items, storage);

  assert.equal(loadHistory(storage).length, MAX_HISTORY_ITEMS);
});

test("creates a compact history item", () => {
  const item = createHistoryItem({
    articleText: "  DPR   membahas kebijakan baru untuk publik.  ",
    readingLevel: "sma",
    explanation: { summary: "Ringkasan" },
  });

  assert.equal(item.readingLevel, "sma");
  assert.equal(item.articlePreview, "DPR membahas kebijakan baru untuk publik.");
  assert.equal(item.explanation.summary, "Ringkasan");
  assert.match(item.createdAt, /^\d{4}-\d{2}-\d{2}T/);
});

test("adds newest history items first and de-duplicates by id", () => {
  const existing = { id: "same", articlePreview: "lama" };
  const updated = { id: "same", articlePreview: "baru" };

  const items = addHistoryItem(updated, [existing, { id: "other" }]);

  assert.equal(items[0].articlePreview, "baru");
  assert.equal(items.length, 2);
});

test("clears saved history", () => {
  const storage = createStorage();
  saveHistory([{ id: "1" }], storage);
  clearHistory(storage);

  assert.deepEqual(loadHistory(storage), []);
});
