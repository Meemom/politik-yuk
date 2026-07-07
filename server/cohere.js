import {
  hasUsableExplanation,
  normalizeExplanation,
} from "./explanation-schema.js";

const COHERE_CHAT_URL = "https://api.cohere.com/v2/chat";
export const DEFAULT_COHERE_MODEL = "c4ai-aya-expanse-32b";

export const READING_LEVEL_PROMPT_GUIDANCE = {
  smp: {
    label: "SMP",
    guidance:
      "Gunakan kalimat pendek, contoh konkret, dan hindari istilah teknis kecuali langsung dijelaskan.",
  },
  sma: {
    label: "SMA",
    guidance:
      "Gunakan bahasa ringkas dengan konteks politik dasar dan hubungan sebab-akibat yang jelas.",
  },
  mahasiswa: {
    label: "Mahasiswa",
    guidance:
      "Boleh lebih analitis, tetapi tetap netral, jernih, dan tidak menambah fakta di luar artikel.",
  },
};

export class CohereConfigurationError extends Error {
  constructor(message) {
    super(message);
    this.name = "CohereConfigurationError";
  }
}

export class CohereApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "CohereApiError";
    this.status = status;
  }
}

export function buildAyaPrompt({ articleText, readingLevel }) {
  const level =
    READING_LEVEL_PROMPT_GUIDANCE[readingLevel] ??
    READING_LEVEL_PROMPT_GUIDANCE.sma;

  return `Kamu adalah asisten literasi berita politik untuk anak muda Indonesia.

Tugasmu adalah menjelaskan artikel berita politik berikut dalam Bahasa Indonesia yang jelas, netral, dan sesuai untuk tingkat pembaca: ${level.label}.

Panduan tingkat pembaca:
${level.guidance}

Aturan penting:
- Jangan menambahkan fakta baru yang tidak ada di artikel.
- Bedakan isi artikel dari interpretasi.
- Jangan berpihak pada partai, tokoh, atau kelompok politik tertentu.
- Jika ada klaim yang belum terbukti, angka, tuduhan, atau prediksi, masukkan ke needsVerification.
- Jelaskan istilah politik, hukum, ekonomi, atau pemerintahan dengan bahasa sederhana.
- Gunakan bahasa yang tidak menggurui.
- Jangan membuat kesimpulan berlebihan.
- Semua isi harus dalam Bahasa Indonesia.
- Jawab hanya dengan JSON valid. Jangan pakai markdown, pembuka, penutup, atau blok kode.

Artikel:
${articleText}

Struktur JSON wajib:
{
  "summary": "3 sampai 5 kalimat tentang apa yang terjadi",
  "simpleExplanation": "penjelasan sederhana sesuai tingkat pembaca",
  "entities": [
    { "name": "nama tokoh/lembaga", "description": "peran dalam artikel" }
  ],
  "terms": [
    { "term": "istilah sulit", "definition": "arti sederhana" }
  ],
  "whyItMatters": "kenapa isu ini penting",
  "dailyImpact": "kemungkinan dampak ke kehidupan sehari-hari tanpa berlebihan",
  "criticalQuestions": ["pertanyaan kritis 1", "pertanyaan kritis 2", "pertanyaan kritis 3"],
  "needsVerification": ["hal yang perlu dicek lagi"]
}`;
}

export function buildCohereChatPayload({ articleText, readingLevel, model }) {
  return {
    stream: false,
    model,
    messages: [
      {
        role: "user",
        content: buildAyaPrompt({ articleText, readingLevel }),
      },
    ],
    temperature: 0.3,
    max_tokens: 1200,
  };
}

export function extractCohereText(responseBody) {
  const content = responseBody?.message?.content;

  if (!Array.isArray(content)) {
    return "";
  }

  return content
    .filter((part) => part?.type === "text" && typeof part.text === "string")
    .map((part) => part.text)
    .join("\n")
    .trim();
}

export function parseExplanationJson(text) {
  const withoutFence = text
    .trim()
    .replace(/^```json\s*/i, "")
    .replace(/^```\s*/i, "")
    .replace(/```$/i, "")
    .trim();
  const start = withoutFence.indexOf("{");
  const end = withoutFence.lastIndexOf("}");

  if (start === -1 || end === -1 || end <= start) {
    throw new CohereApiError("Aya did not return a JSON explanation.", 502);
  }

  let parsed;

  try {
    parsed = JSON.parse(withoutFence.slice(start, end + 1));
  } catch {
    throw new CohereApiError("Aya returned invalid JSON.", 502);
  }

  const explanation = normalizeExplanation(parsed);

  if (!hasUsableExplanation(explanation)) {
    throw new CohereApiError("Aya returned an empty explanation.", 502);
  }

  return explanation;
}

export async function generateExplanationWithAya({
  articleText,
  readingLevel,
  apiKey = process.env.COHERE_API_KEY,
  model = process.env.COHERE_MODEL ?? DEFAULT_COHERE_MODEL,
  fetchImpl = fetch,
}) {
  if (!apiKey) {
    throw new CohereConfigurationError("COHERE_API_KEY is not configured.");
  }

  const response = await fetchImpl(COHERE_CHAT_URL, {
    method: "POST",
    headers: {
      authorization: `Bearer ${apiKey}`,
      "content-type": "application/json",
      "x-client-name": "politik-yuk-mvp",
    },
    body: JSON.stringify(
      buildCohereChatPayload({ articleText, readingLevel, model })
    ),
  });

  const responseBody = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message =
      responseBody?.message ??
      responseBody?.error?.message ??
      "Cohere request failed.";
    throw new CohereApiError(message, response.status);
  }

  const explanation = extractCohereText(responseBody);

  if (!explanation) {
    throw new CohereApiError("Cohere returned an empty explanation.", 502);
  }

  return {
    explanation: parseExplanationJson(explanation),
    rawText: explanation,
    model,
    finishReason: responseBody.finish_reason ?? null,
    usage: responseBody.usage ?? null,
  };
}
