import test from "node:test";
import assert from "node:assert/strict";
import worker from "../cloudflare/worker.mjs";

const BASE = "https://olivia.test";
function makeEnv(enabled = true) {
  const calls = [];
  const env = {
    OLIVIA_DEMO_ZERO_COST_CONFIRMED: enabled ? "1" : "0",
    AI: {
      run: async (model, payload) => {
        calls.push({ model, payload });
        return { response: "Respuesta de prueba" };
      },
    },
    COST_GUARD: {
      idFromName: (name) => name,
      get: () => ({
        fetch: async () => new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      }),
    },
    ASSETS: { fetch: async () => new Response("shell") },
  };
  return { env, calls };
}
function demoRequest({ origin = BASE, body = JSON.stringify({ messages: [{ role: "user", content: "Hola" }] }), contentType = "application/json" } = {}) {
  const headers = { "content-type": contentType };
  if (origin !== null) headers.origin = origin;
  return new Request(BASE + "/api/demo-chat", { method: "POST", headers, body });
}
test("demo is disabled by default and does not consume inference", async () => {
  const { env, calls } = makeEnv(false);
  const response = await worker.fetch(demoRequest(), env);
  assert.equal(response.status, 503);
  assert.deepEqual(calls, []);
});
test("rejects absent and cross-site origins without calling inference", async () => {
  const { env, calls } = makeEnv();
  for (const origin of [null, "https://evil.test", "https://olivia.test.evil.test"]) {
    const response = await worker.fetch(demoRequest({ origin }), env);
    assert.equal(response.status, 403);
    assert.equal((await response.json()).error, "origin_forbidden");
  }
  assert.deepEqual(calls, []);
});
test("rejects invalid content type and oversized bodies without inference", async () => {
  const { env, calls } = makeEnv();
  const wrongType = await worker.fetch(demoRequest({ contentType: "text/plain" }), env);
  assert.equal(wrongType.status, 415);
  const large = await worker.fetch(demoRequest({ body: "a".repeat(16385) }), env);
  assert.equal(large.status, 413);
  assert.deepEqual(calls, []);
});
test("valid same-origin demo is bounded and reports no billing guarantee", async () => {
  const { env, calls } = makeEnv();
  const health = await (await worker.fetch(new Request(BASE + "/healthz"), env)).json();
  assert.equal(health.hard_zero_cost, false);
  assert.equal(health.demo_cost_guaranteed, false);
  assert.equal(health.provider_ready, false);
  assert.equal(health.demo_provider_ready, true);
  const response = await worker.fetch(demoRequest(), env);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.answer, "Respuesta de prueba");
  assert.equal(body.canonical, false);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].payload.max_completion_tokens, 256);
  assert.match(calls[0].payload.messages[0].content, /demostración pública/);
  assert.doesNotMatch(calls[0].payload.messages[0].content, /Simón/);
});
test("canonical chat endpoint stays disabled even with demo enabled", async () => {
  const { env, calls } = makeEnv();
  const response = await worker.fetch(new Request(BASE + "/api/chat", { method: "POST" }), env);
  assert.equal(response.status, 503);
  assert.deepEqual(calls, []);
});
