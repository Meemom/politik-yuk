import { createReadStream, existsSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize } from "node:path";
import { loadLocalEnv } from "../server/env.js";
import { handleExplainRequest } from "../server/explain-route.js";
import { handleExtractRequest } from "../server/extract-route.js";

const port = Number.parseInt(process.env.PORT ?? "4173", 10);
const host = process.env.HOST ?? "127.0.0.1";
const root = process.cwd();

loadLocalEnv(root);

const contentTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
]);

function resolvePath(url) {
  const pathname = new URL(url, `http://localhost:${port}`).pathname;
  const requestedPath = pathname === "/" ? "/index.html" : pathname;
  const safePath = normalize(requestedPath).replace(/^(\.\.[/\\])+/, "");
  return join(root, safePath);
}

const server = createServer((request, response) => {
  if (request.url === "/api/explain") {
    handleExplainRequest(request, response);
    return;
  }

  if (request.url === "/api/extract") {
  handleExtractRequest(request, response);
  return;
}

  const filePath = resolvePath(request.url ?? "/");

  if (!existsSync(filePath)) {
    response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    response.end("Not found");
    return;
  }

  response.writeHead(200, {
    "content-type":
      contentTypes.get(extname(filePath)) ?? "application/octet-stream",
  });
  createReadStream(filePath).pipe(response);
});

server.listen(port, host, () => {
  console.log(`Paham Politik static server running at http://${host}:${port}`);
});
