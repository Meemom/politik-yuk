export const HISTORY_STORAGE_KEY = "politik-yuk-history";
export const MAX_HISTORY_ITEMS = 5;

export function loadHistory(storage = globalThis.localStorage) {
  if (!storage) {
    return [];
  }

  try {
    const parsed = JSON.parse(storage.getItem(HISTORY_STORAGE_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveHistory(items, storage = globalThis.localStorage) {
  if (!storage) {
    return;
  }

  storage.setItem(
    HISTORY_STORAGE_KEY,
    JSON.stringify(items.slice(0, MAX_HISTORY_ITEMS))
  );
}

export function clearHistory(storage = globalThis.localStorage) {
  if (!storage) {
    return;
  }

  storage.removeItem(HISTORY_STORAGE_KEY);
}

export function createHistoryItem({ articleText, readingLevel, explanation }) {
  return {
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
    readingLevel,
    articlePreview: articleText.trim().replace(/\s+/g, " ").slice(0, 120),
    explanation,
  };
}

export function addHistoryItem(item, items) {
  return [item, ...items.filter((existingItem) => existingItem.id !== item.id)].slice(
    0,
    MAX_HISTORY_ITEMS
  );
}
