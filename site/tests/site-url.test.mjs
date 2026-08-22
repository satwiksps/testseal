import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import ts from "typescript";

const source = await readFile(new URL("../app/site-url.ts", import.meta.url), "utf8");
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { getSiteUrl } = await import(
  `data:text/javascript;base64,${Buffer.from(javascript).toString("base64")}`
);

const environmentKeys = [
  "NEXT_PUBLIC_SITE_URL",
  "VERCEL_PROJECT_PRODUCTION_URL",
  "VERCEL_URL",
  "NODE_ENV",
  "VERCEL",
];

function withEnvironment(values, operation) {
  const previous = Object.fromEntries(environmentKeys.map((key) => [key, process.env[key]]));
  for (const key of environmentKeys) delete process.env[key];
  Object.assign(process.env, values);
  try {
    return operation();
  } finally {
    for (const key of environmentKeys) {
      const value = previous[key];
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

test("normalizes valid public HTTP URLs", () => {
  assert.equal(
    withEnvironment({ NEXT_PUBLIC_SITE_URL: "example.com" }, getSiteUrl),
    "https://example.com",
  );
});

test("rejects explicit non-HTTP schemes", () => {
  assert.throws(
    () => withEnvironment({ NEXT_PUBLIC_SITE_URL: "ftp://example.com/path" }, getSiteUrl),
    /must use http or https/,
  );
});

test("reports malformed public URLs as configuration errors", () => {
  assert.throws(
    () => withEnvironment({ NEXT_PUBLIC_SITE_URL: "https://[" }, getSiteUrl),
    /public site URL must be a valid http or https URL/i,
  );
});

test("uses the documented canonical URL in non-Vercel production", () => {
  assert.equal(
    withEnvironment({ NODE_ENV: "production" }, getSiteUrl),
    "https://testseal-integrity.vercel.app",
  );
});
