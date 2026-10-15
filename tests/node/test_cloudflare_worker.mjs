import assert from "node:assert/strict";
import { test } from "node:test";
import worker, { CostGuard } from "../../cloudflare/worker.mjs";

const BASE = "https://olivia.test";
function fixture() {
  const calls = { ai: 0, assets: 0, quota: 0 };
  const env = {
    OLIVIA_RELEASE_SHA: "a".repeat(40),
    OLIVIA_AUTH0_ISSUER: "https://unused.auth0.com/",
    OLIVIA_AUTH0_AUDIENCE: "https://unused.example/api",
    OLIVIA_OWNER_AUTH0_SUB: "unused-auth0-subject",
    OLIVIA_DEMO_ZERO_COST_CONFIRMED: "1",
    OLIVIA_DEMO_QWEN_ZERO_COST_CONFIRMED: "1",
    AI: { run: async () => { calls.ai++; return { response: "MUST_NOT_RUN" }; } },
    COST_GUARD: { idFromName: () => { calls.quota++; return "unexpected"; }, get: () => ({ fetch: async () => { calls.quota++; return new Response("unexpected"); } }) },
    ASSETS: { fetch: async () => { calls.assets++; return new Response("public shell", { status: 200 }); } },
  };
  return { env, calls };
}
async function body(response) { return response.json(); }

test("health always reports static-only with no Auth0 identity or inference", async () => {
  const f = fixture();
  const response = await worker.fetch(new Request(BASE + "/healthz"), f.env);
  const h = await body(response);
  assert.equal(response.status, 200);
  assert.equal(h.api_mode, "public_shell");
  assert.equal(h.public_shell, true);
  assert.equal(h.static_only, true);
  assert.equal(h.bridge_enabled, false);
  assert.equal(h.provider_ready, false);
  assert.equal(h.inference_enabled, false);
  assert.equal(h.demo_inference_enabled, false);
  assert.equal(h.demo_provider_ready, false);
  assert.equal(h.demo_provider, null);
  assert.equal(h.demo_model, null);
  assert.equal(h.demo_qwen_ready, false);
  assert.equal(h.demo_gemma_ready, false);
  assert.equal(h.hard_zero_cost, true);
  assert.equal(h.release_sha, "a".repeat(40));
  assert.equal(f.calls.ai, 0);
  assert.equal(f.calls.quota, 0);
});

test("all API routes fail closed regardless of Auth0, Google or bearer headers", async () => {
  const f = fixture();
  const paths = ["/api/chat", "/api/read-url", "/api/demo-chat", "/api/jobs/code", "/api/unknown"];
  for (const path of paths) {
    for (const headers of [{}, { authorization: "Bearer forged" }, { "x-user": "owner", "x-role": "owner", "x-email": "owner@example.com" }]) {
      const response = await worker.fetch(new Request(BASE + path, { method: path.endsWith("demo-chat") ? "POST" : "GET", headers }), f.env);
      assert.equal(response.status, 503, path);
      assert.equal((await body(response)).error, "bridge_disabled");
    }
  }
  assert.equal(f.calls.ai, 0);
  assert.equal(f.calls.quota, 0);
  assert.equal(f.calls.assets, 0);
});

test("static assets remain public and all responses carry security headers", async () => {
  const f = fixture();
  const response = await worker.fetch(new Request(BASE + "/"), f.env);
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "public shell");
  assert.equal(f.calls.assets, 1);
  for (const r of [response, await worker.fetch(new Request(BASE + "/healthz"), f.env), await worker.fetch(new Request(BASE + "/api/chat"), f.env)]) {
    assert.equal(r.headers.get("x-content-type-options"), "nosniff");
    assert.equal(r.headers.get("x-frame-options"), "DENY");
    assert.equal(r.headers.get("referrer-policy"), "no-referrer");
    assert.equal(r.headers.get("strict-transport-security"), "max-age=31536000");
    assert.ok(r.headers.get("content-security-policy").includes("frame-ancestors 'none'"));
    assert.equal(r.headers.get("permissions-policy"), "camera=(), geolocation=(), microphone=(self)");
  }
  assert.equal(f.calls.ai, 0);
  assert.equal(f.calls.quota, 0);
});

test("invalid release SHA is never reported as a trusted release", async () => {
  const f = fixture();
  f.env.OLIVIA_RELEASE_SHA = "invalid";
  const h = await body(await worker.fetch(new Request(BASE + "/healthz"), f.env));
  assert.equal(h.release_sha, null);
});

test("retained Durable Object export has no quota or inference side effects", async () => {
  const calls = { get: 0, put: 0 };
  const guard = new CostGuard({ storage: { get: async () => { calls.get++; }, put: async () => { calls.put++; } } });
  const response = await guard.fetch(new Request("https://guard/allow", { method: "POST" }));
  assert.equal(response.status, 404);
  assert.equal(calls.get, 0);
  assert.equal(calls.put, 0);
});
