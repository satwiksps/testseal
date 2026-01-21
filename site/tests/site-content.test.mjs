import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

async function source(path) {
  return readFile(new URL(path, root), "utf8");
}

test("landing page contains the product promise and all rule IDs", async () => {
  const page = await source("app/page.tsx");

  assert.match(page, /Catch test weakening/);
  assert.match(page, /before it merges\./);
  assert.match(page, /No LLM/i);
  assert.match(page, /Example TestSeal pull request report/);
  assert.match(page, /actions\/setup-python@5fda3b95/);
  assert.match(page, /python-version: "3\.12"/);
  assert.match(page, /<figure/);
  assert.match(page, /softwareVersion: "0\.1\.0"/);
  assert.match(page, />\s*v0\.1\.0\s*</);
  assert.match(page, /satwiksps\/testseal@" \+ RELEASE_REF/);
  assert.doesNotMatch(page, /preview|Roadmap/i);
  for (let index = 1; index <= 8; index += 1) {
    assert.match(page, new RegExp(`TS${String(index).padStart(3, "0")}`));
  }
  assert.match(page, /https:\/\/github\.com\/satwiksps\/testseal/);
  for (const staleReference of [
    "your" + "-org",
    "owner" + "/testseal",
    "reviewed" + "-repository-url",
  ]) {
    assert.doesNotMatch(page, new RegExp(staleReference));
  }
});

test("site metadata and deployment target are finalized", async () => {
  const [layout, packageJson, vercel, css, siteUrl, postcss] = await Promise.all([
    source("app/layout.tsx"),
    source("package.json"),
    source("vercel.json"),
    source("app/globals.css"),
    source("app/site-url.ts"),
    source("postcss.config.mjs"),
  ]);

  assert.match(layout, /TestSeal — Catch Test Weakening Before It Merges/);
  assert.doesNotMatch(layout, /codex-preview|Starter Project/);
  assert.equal(JSON.parse(packageJson).scripts.build, "next build");
  assert.equal(JSON.parse(vercel).framework, "nextjs");
  assert.match(css, /prefers-reduced-motion: reduce/);
  assert.match(css, /:focus-visible/);
  assert.match(css, /forced-colors: active/);
  assert.match(css, /@import "tailwindcss"/);
  assert.match(postcss, /@tailwindcss\/postcss/);
  assert.match(siteUrl, /VERCEL_PROJECT_PRODUCTION_URL/);
  assert.match(siteUrl, /A public site URL is required on Vercel/);
});

test("landing page avoids the previous decorative visual language", async () => {
  const page = await source("app/page.tsx");
  const css = await source("app/globals.css");

  for (const staleClass of [
    "ambient-one",
    "floating-chip",
    "glass-panel",
    "visual-glow",
    "cta-glow",
  ]) {
    assert.doesNotMatch(page + css, new RegExp(staleClass));
  }
});
