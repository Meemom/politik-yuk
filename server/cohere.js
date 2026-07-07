const COHERE_CHAT_URL = "https://api.cohere.com/v2/chat";
export const DEFAULT_COHERE_MODEL = "c4ai-aya-expanse-32b";

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
  return `Kamu adalah asisten literasi berita politik untuk anak muda Indonesia.

Jelaskan artikel berita politik berikut dalam Bahasa Indonesia yang jelas, netral, dan sesuai untuk tingkat pembaca: ${readingLevel}.

Aturan:
- Jangan menambahkan fakta baru yang tidak ada di artikel.
- Jangan berpihak pada partai, tokoh, atau kelompok politik tertentu.
- Tandai klaim, angka, tuduhan, atau prediksi yang perlu dicek lagi.
- Gunakan bahasa yang tidak menggurui.

Artikel:
${articleText}

Berikan penjelasan ringkas dengan bagian:
1. Ringkasan Singkat
2. Penjelasan Sederhana
3. Hal yang Perlu Dicek Lagi`;
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
    explanation,
    model,
    finishReason: responseBody.finish_reason ?? null,
    usage: responseBody.usage ?? null,
  };
}
