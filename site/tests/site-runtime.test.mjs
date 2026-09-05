import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { fileURLToPath } from "node:url";
import net from "node:net";
import test from "node:test";
import nextEnvironment from "@next/env";
import { getSiteUrl } from "../app/site-url.ts";

const root = fileURLToPath(new URL("../", import.meta.url));
const next = fileURLToPath(new URL("../node_modules/next/dist/bin/next", import.meta.url));

process.env.NODE_ENV = "production";
nextEnvironment.loadEnvConfig(root);
const canonical = getSiteUrl();

async function unusedPort() {
  const server = net.createServer();
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  assert.notEqual(address, null);
  assert.equal(typeof address, "object");
  const port = address.port;
  server.close();
  await once(server, "close");
  return port;
}

async function waitForServer(url, output) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // The server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  assert.fail(`Next.js did not start:\n${output.join("")}`);
}

test("production routes publish the configured canonical origin", { timeout: 30_000 }, async () => {
  const port = await unusedPort();
  const environment = { ...process.env, NODE_ENV: "production" };
  const output = [];
  const child = spawn(process.execPath, [next, "start", "--hostname", "127.0.0.1", "--port", String(port)], {
    cwd: root,
    env: environment,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  child.stdout.on("data", (chunk) => output.push(chunk.toString()));
  child.stderr.on("data", (chunk) => output.push(chunk.toString()));

  try {
    const origin = `http://127.0.0.1:${port}`;
    await waitForServer(origin, output);
    async function getText(path) {
      const response = await fetch(`${origin}${path}`);
      assert.equal(response.status, 200, `${path} must respond successfully`);
      return response.text();
    }
    const [page, robots, sitemap] = await Promise.all([
      getText("/"),
      getText("/robots.txt"),
      getText("/sitemap.xml"),
    ]);

    assert.ok(page.includes(`<link rel="canonical" href="${canonical}"`), "page must use the configured canonical origin");
    assert.ok(page.includes(`<meta property="og:url" content="${canonical}"`), "Open Graph must use the configured canonical origin");
    assert.ok(robots.includes(`Sitemap: ${canonical}/sitemap.xml`), "robots.txt must use the configured canonical origin");
    assert.ok(sitemap.includes(`<loc>${canonical}</loc>`), "sitemap must use the configured canonical origin");
  } finally {
    child.kill();
    if (child.exitCode === null) await once(child, "exit");
  }
});
