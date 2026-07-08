import { Readability } from "@mozilla/readability";
import { JSDOM } from "jsdom";
import { validateArticleUrl } from "./url-validation.js";

export async function extractArticleFromUrl(articleUrl, fetchImpl = fetch) {
  const validation = validateArticleUrl(articleUrl);

  if (!validation.ok) {
    return { ok: false, error: validation.error };
  }

  const response = await fetchImpl(validation.url, {
    headers: {
      "user-agent": "PolitikYukBot/0.1",
      accept: "text/html",
    },
  });

  const contentType = response.headers.get("content-type") ?? "";

  if (!contentType.includes("text/html")) {
    return { ok: false, error: "URL tidak mengarah ke halaman HTML." };
  }

  const html = await response.text();
  const dom = new JSDOM(html, {
    url: validation.url.href,
  });

  const article = new Readability(dom.window.document).parse();

  if (!article?.textContent || article.textContent.trim().length < 300) {
    return { ok: false, error: "Teks artikel tidak berhasil diekstrak." };
  }

  return {
    ok: true,
    article: {
      title: article.title ?? "",
      byline: article.byline ?? "",
      siteName: article.siteName ?? validation.url.hostname,
      textContent: article.textContent.trim(),
    },
  };
}