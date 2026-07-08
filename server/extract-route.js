import { extractArticleFromUrl } from "./article-extractor.js";

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

export async function handleExtractRequest(request, response) {
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

  const result = await extractArticleFromUrl(String(body.url ?? ""));

  if (!result.ok) {
    sendJson(response, 400, { error: result.error });
    return;
  }

  sendJson(response, 200, result.article);
}