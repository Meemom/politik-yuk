export const EXPLANATION_SECTION_LABELS = {
  summary: "Ringkasan Singkat",
  simpleExplanation: "Penjelasan Sederhana",
  entities: "Tokoh dan Lembaga Penting",
  terms: "Istilah Sulit",
  whyItMatters: "Kenapa Ini Penting",
  dailyImpact: "Dampak ke Kehidupan Sehari-hari",
  criticalQuestions: "Pertanyaan Kritis",
  needsVerification: "Hal yang Perlu Dicek Lagi",
};

export function emptyExplanation() {
  return {
    summary: "",
    simpleExplanation: "",
    entities: [],
    terms: [],
    whyItMatters: "",
    dailyImpact: "",
    criticalQuestions: [],
    needsVerification: [],
  };
}

function normalizeString(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeStringList(value) {
  return Array.isArray(value)
    ? value.map(normalizeString).filter(Boolean)
    : [];
}

function normalizeNamedItems(value, nameKey, descriptionKey) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => ({
      [nameKey]: normalizeString(item?.[nameKey]),
      [descriptionKey]: normalizeString(item?.[descriptionKey]),
    }))
    .filter((item) => item[nameKey] || item[descriptionKey]);
}

export function normalizeExplanation(value) {
  return {
    summary: normalizeString(value?.summary),
    simpleExplanation: normalizeString(value?.simpleExplanation),
    entities: normalizeNamedItems(value?.entities, "name", "description"),
    terms: normalizeNamedItems(value?.terms, "term", "definition"),
    whyItMatters: normalizeString(value?.whyItMatters),
    dailyImpact: normalizeString(value?.dailyImpact),
    criticalQuestions: normalizeStringList(value?.criticalQuestions),
    needsVerification: normalizeStringList(value?.needsVerification),
  };
}

export function hasUsableExplanation(value) {
  return Boolean(
    value.summary ||
      value.simpleExplanation ||
      value.whyItMatters ||
      value.dailyImpact ||
      value.entities.length ||
      value.terms.length ||
      value.criticalQuestions.length ||
      value.needsVerification.length
  );
}
