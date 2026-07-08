import { validateArticleText } from "../src/explainer.js";
import {
  CohereApiError,
  CohereConfigurationError,
  generateExplanationWithAya,
} from "./cohere.js";

const VALID_READING_LEVELS = new Set(["smp", "sma", "mahasiswa"]);

async function readJson(request) {
  const chunks = [];

  for await (const chunk of request) {
    chunks.push(chunk);
  }

  if (chunks.length === 0) {
    return {};
  }

  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, {
    "content-type": "application/json; charset=utf-8",
  });
  response.end(JSON.stringify(payload));
}

export async function handleExplainRequest(request, response) {
  if (request.method !== "POST") {
    sendJson(response, 405, { error: "Method not allowed." });
    return;
  }

  let body;

  try {
    body = await readJson(request);
  } catch {
    sendJson(response, 400, { error: "Request body must be valid JSON." });
    return;
  }

  const articleText = String(body.articleText ?? "");
  const readingLevel = String(body.readingLevel ?? "sma");
  const validationMessage = validateArticleText(articleText);

  if (validationMessage) {
    sendJson(response, 400, { error: validationMessage });
    return;
  }

  if (!VALID_READING_LEVELS.has(readingLevel)) {
    sendJson(response, 400, { error: "Tingkat penjelasan tidak valid." });
    return;
  }

  try {
    const result = await generateExplanationWithAya({
      articleText: articleText.trim(),
      readingLevel,
    });
    sendJson(response, 200, result);
  } catch (error) {
    if (error instanceof CohereConfigurationError) {
      sendJson(response, 503, {
        error: "COHERE_API_KEY belum dikonfigurasi di server.",
      });
      return;
    }

    if (error instanceof CohereApiError) {
      sendJson(response, error.status >= 400 ? error.status : 502, {
        error: error.message,
      });
      return;
    }

    sendJson(response, 500, {
      error: "Terjadi kesalahan saat membuat penjelasan.",
    });
  }
}
