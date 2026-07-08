import assert from "node:assert/strict";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";
import { loadLocalEnv } from "../server/env.js";

test("loads simple .env files without overwriting existing variables", async () => {
  const root = join("/tmp", `politik-yuk-env-${Date.now()}`);
  const previousValue = process.env.COHERE_API_KEY;

  await mkdir(root, { recursive: true });
  await writeFile(
    join(root, ".env"),
    'COHERE_API_KEY=from-file\nCOHERE_MODEL="c4ai-aya-expanse-32b"\n'
  );

  process.env.COHERE_API_KEY = "already-set";
  delete process.env.COHERE_MODEL;

  loadLocalEnv(root);

  assert.equal(process.env.COHERE_API_KEY, "already-set");
  assert.equal(process.env.COHERE_MODEL, "c4ai-aya-expanse-32b");

  if (previousValue === undefined) {
    delete process.env.COHERE_API_KEY;
  } else {
    process.env.COHERE_API_KEY = previousValue;
  }

  delete process.env.COHERE_MODEL;
  await rm(root, { recursive: true, force: true });
});
