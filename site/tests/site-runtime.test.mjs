import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { fileURLToPath } from "node:url";
import net from "node:net";
import test from "node:test";

const root = fileURLToPath(new URL("../", import.meta.url));
const next = fileURLToPath(new URL("../node_modules/next/dist/bin/next", import.meta.url));
const canonical = "https://testseal-integrity.vercel.app";

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
  for (const key of ["NEXT_PUBLIC_SITE_URL", "VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_URL", "VERCEL"]) {
    delete environment[key];
  }
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
    const [page, robots, sitemap] = await Promise.all([
      fetch(origin).then((response) => response.text()),
      fetch(`${origin}/robots.txt`).then((response) => response.text()),
      fetch(`${origin}/sitemap.xml`).then((response) => response.text()),
    ]);

    assert.match(page, new RegExp(`<link rel="canonical" href="${canonical}"`));
    assert.match(page, new RegExp(`<meta property="og:url" content="${canonical}"`));
    assert.match(robots, new RegExp(`Sitemap: ${canonical}/sitemap.xml`));
    assert.match(sitemap, new RegExp(`<loc>${canonical}</loc>`));
  } finally {
    child.kill();
    if (child.exitCode === null) await once(child, "exit");
  }
});
