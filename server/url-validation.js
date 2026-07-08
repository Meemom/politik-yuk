const PRIVATE_HOSTS = new Set(["localhost", "127.0.0.1", "0.0.0.0", "::1"]);

export function validateArticleUrl(value) {
  let url;

  try {
    url = new URL(value);
  } catch {
    return { ok: false, error: "Masukkan URL artikel yang valid." };
  }

  if (!["http:", "https:"].includes(url.protocol)) {
    return { ok: false, error: "URL harus diawali http atau https." };
  }

  if (PRIVATE_HOSTS.has(url.hostname)) {
    return { ok: false, error: "URL lokal tidak didukung." };
  }

  return { ok: true, url };
}