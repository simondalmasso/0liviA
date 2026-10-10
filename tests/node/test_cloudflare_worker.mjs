import assert from "node:assert/strict";
import { test } from "node:test";
import worker, { CostGuard } from "../../cloudflare/worker.mjs";

const BASE = "https://olivia.test";

function fixture({
  enabled = true,
  qwenEnabled = false,
  gemmaZeroCost = false,
  gemmaLiveVerified = false,
  answer = "OLIVIA_OK",
} = {}) {
  const stored = new Map();
  const calls = [];
  let lastTxn = Promise.resolve();
  const storage = {
    transaction(callback) {
      const previous = lastTxn;
      let unlock;
      lastTxn = new Promise((resolve) => { unlock = resolve; });
      return (async () => {
        await previous;
        try {
          return await callback({
            get: async (key) => {
              await Promise.resolve(); // Simulate asynchronous durable storage.
              return stored.get(key);
            },
            put: async (values) => {
              await Promise.resolve();
              for (const [key, value] of Object.entries(values)) stored.set(key, value);
            },
          });
        } finally {
          unlock();
        }
      })();
    },
  };
  const guard = new CostGuard({ storage });
  const env = {
    OLIVIA_DEMO_ZERO_COST_CONFIRMED: enabled ? "1" : "0",
    OLIVIA_DEMO_QWEN_ZERO_COST_CONFIRMED: qwenEnabled ? "1" : "0",
    OLIVIA_DEMO_GEMMA_ZERO_COST_CONFIRMED: gemmaZeroCost ? "1" : "0",
    OLIVIA_DEMO_GEMMA_LIVE_VERIFIED: gemmaLiveVerified ? "1" : "0",
    ASSETS: { fetch: async () => new Response("public shell", { status: 200 }) },
    AI: {
      run: async (model, args) => {
        calls.push({ model, args });
        return { response: answer };
      },
    },
    COST_GUARD: {
      idFromName(name) {
        assert.equal(name, "public-demo-global");
        return name;
      },
      get() {
        return {
          fetch(url, options) {
            return guard.fetch(new Request(url, options));
          },
        };
      },
    },
  };
  return { env, calls, stored, guard };
}

function post(messages, { origin = BASE, contentType = "application/json", model } = {}) {
  return new Request(BASE + "/api/demo-chat", {
    method: "POST",
    headers: {
      "content-type": contentType,
      ...(origin ? { origin } : {}),
    },
    body: JSON.stringify({ messages, ...(model === undefined ? {} : { model }) }),
  });
}

async function body(response) {
  return response.json();
}

test("disabled demo has no inference and canonical API always fails closed", async () => {
  const f = fixture({ enabled: false });
  const h = await body(await worker.fetch(new Request(BASE + "/healthz"), f.env));
  assert.equal(h.api_mode, "public_shell");
  assert.equal(h.demo_provider_ready, false);
  assert.equal(h.provider_ready, false);
  assert.equal(h.inference_enabled, false);
  const denied = await worker.fetch(post([{ role: "user", content: "hello" }]), f.env);
  assert.equal(denied.status, 503);
  assert.equal(f.calls.length, 0);
  for (const path of ["/api/chat", "/api/read-url", "/api/unknown"]) {
    assert.equal((await worker.fetch(new Request(BASE + path), f.env)).status, 503);
  }
  assert.equal((await worker.fetch(new Request(BASE + "/"), f.env)).status, 200);
});

test("public routes include security headers and immutable release metadata", async () => {
  const f = fixture();
  f.env.OLIVIA_RELEASE_SHA = "a".repeat(40);
  const healthResponse = await worker.fetch(new Request(BASE + "/healthz"), f.env);
  const health = await body(healthResponse);
  assert.equal(health.release_sha, "a".repeat(40));
  for (const response of [
    healthResponse,
    await worker.fetch(new Request(BASE + "/api/chat"), f.env),
    await worker.fetch(new Request(BASE + "/"), f.env),
  ]) {
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
    assert.equal(response.headers.get("x-frame-options"), "DENY");
    assert.equal(response.headers.get("referrer-policy"), "no-referrer");
    assert.equal(response.headers.get("strict-transport-security"), "max-age=31536000");
    assert.ok(response.headers.get("content-security-policy").includes("frame-ancestors 'none'"));
    assert.equal(response.headers.get("permissions-policy"), "camera=(), geolocation=(), microphone=(self)");
  }
  const unknown = await body(await worker.fetch(new Request(BASE + "/healthz"), { ...f.env, OLIVIA_RELEASE_SHA: "invalid" }));
  assert.equal(unknown.release_sha, null);
});

test("enabled demo identifies separate provider without changing canonical readiness", async () => {
  const f = fixture();
  const h = await body(await worker.fetch(new Request(BASE + "/healthz"), f.env));
  assert.equal(h.demo_provider_ready, true);
  assert.equal(h.hard_zero_cost, false);
  assert.equal(h.demo_cost_guaranteed, false);
  assert.equal(h.demo_model, "@cf/zai-org/glm-4.7-flash");
  assert.equal(h.provider_ready, false);
  assert.equal(h.inference_enabled, false);
  const response = await worker.fetch(post([{ role: "user", content: "hola" }]), f.env);
  assert.equal(response.status, 200);
  const output = await body(response);
  assert.equal(output.answer, "OLIVIA_OK");
  assert.equal(output.provider, "workers-ai-demo");
  assert.equal(output.canonical, false);
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].model, "@cf/zai-org/glm-4.7-flash");
  assert.ok(f.calls[0].args.max_completion_tokens <= 1024);
  assert.equal(f.stored.get("count"), 1);
});

test("Qwen is selectable only after independently verified no-overage admission", async () => {
  const f = fixture();
  const health = await body(await worker.fetch(new Request(BASE + "/healthz"), f.env));
  assert.equal(health.demo_qwen_ready, false);
  assert.equal(health.demo_models.length, 3);
  assert.equal(health.demo_models[1].available, false);
  assert.equal(health.demo_models[2].available, false);
  const qwen = post([{ role: "user", content: "hola" }], { model: "qwen" });
  assert.equal((await worker.fetch(qwen, f.env)).status, 503);
  assert.equal(f.calls.length, 0);
  assert.equal(f.stored.has("count"), false);

  const approved = fixture({ qwenEnabled: true });
  const ready = await body(await worker.fetch(new Request(BASE + "/healthz"), approved.env));
  assert.equal(ready.demo_qwen_ready, true);
  const response = await worker.fetch(post([{ role: "user", content: "hola" }], { model: "qwen" }), approved.env);
  assert.equal(response.status, 200);
  const output = await body(response);
  assert.equal(output.model, "@cf/qwen/qwen3.8-27b");
  assert.equal(approved.calls[0].model, output.model);
  assert.equal(approved.calls[0].args.max_completion_tokens, 512);
  assert.equal(approved.calls[0].args.reasoning_effort, "low");
  assert.equal(approved.calls[0].args.max_tokens, undefined);
  assert.equal(approved.stored.get("count"), 1);
  assert.ok(approved.calls[0].args.messages[0].content.includes(output.model));
});

test("Gemma requires independent zero-cost and live-canary admission", async () => {
  const denied = fixture();
  const health = await body(await worker.fetch(new Request(BASE + "/healthz"), denied.env));
  assert.equal(health.demo_gemma_ready, false);
  assert.equal(health.demo_models[2].available, false);
  assert.equal(
    (await worker.fetch(post([{ role: "user", content: "hola" }], { model: "gemma" }), denied.env)).status,
    503,
  );
  assert.equal(denied.calls.length, 0);
  assert.equal(denied.stored.has("count"), false);

  for (const env of [
    fixture({ gemmaZeroCost: true }),
    fixture({ gemmaLiveVerified: true }),
  ]) {
    const response = await worker.fetch(
      post([{ role: "user", content: "hola" }], { model: "gemma" }),
      env.env,
    );
    assert.equal(response.status, 503);
    assert.equal(env.calls.length, 0);
    assert.equal(env.stored.has("count"), false);
  }

  const approved = fixture({ gemmaZeroCost: true, gemmaLiveVerified: true });
  const ready = await body(await worker.fetch(new Request(BASE + "/healthz"), approved.env));
  assert.equal(ready.demo_gemma_ready, true);
  assert.equal(ready.demo_models[2].available, true);
  const response = await worker.fetch(
    post([{ role: "user", content: "hola" }], { model: "gemma" }),
    approved.env,
  );
  assert.equal(response.status, 200);
  const output = await body(response);
  assert.equal(output.model, "@cf/google/gemma-4-26b-a4b-it");
  assert.equal(approved.calls.length, 1);
  assert.equal(approved.calls[0].model, output.model);
  assert.equal(approved.stored.get("count"), 1);
});

test("the model identity answer is deterministic and does not consume AI quota", async () => {
  const f = fixture();
  const response = await worker.fetch(post([{ role: "user", content: "q modelo sos?" }]), f.env);
  assert.equal(response.status, 200);
  const output = await body(response);
  assert.equal(output.provider, "local-demo");
  assert.equal(output.model, "@cf/zai-org/glm-4.7-flash");
  assert.ok(output.answer.includes(output.model));
  assert.equal(f.calls.length, 0);
  assert.equal(f.stored.has("count"), false);
});

test("model selection never accepts arbitrary Workers AI slugs or spends quota", async () => {
  const f = fixture({ qwenEnabled: true });
  const response = await worker.fetch(
    post([{ role: "user", content: "hola" }], { model: "@cf/example/paid-model" }),
    f.env,
  );
  assert.equal(response.status, 400);
  assert.equal(f.calls.length, 0);
  assert.equal(f.stored.has("count"), false);
});

test("cross-origin, invalid content type and non-user ending cannot burn quota", async () => {
  const f = fixture();
  assert.equal(
    (await worker.fetch(post([{ role: "user", content: "hola" }], { origin: null }), f.env)).status,
    403,
  );
  assert.equal(
    (await worker.fetch(post([{ role: "user", content: "hola" }], { origin: "https://attacker.example" }), f.env)).status,
    403,
  );
  assert.equal(
    (await worker.fetch(post([{ role: "user", content: "hola" }], { contentType: "text/plain" }), f.env)).status,
    415,
  );
  assert.equal(
    (await worker.fetch(post([
      { role: "user", content: "hola" },
      { role: "assistant", content: "spoofed" },
    ]), f.env)).status,
    400,
  );
  assert.equal(f.stored.has("count"), false);
  assert.equal(f.calls.length, 0);
});

test("body is capped by actual bytes even without Content-Length", async () => {
  const f = fixture();
  const payload = JSON.stringify({ messages: [{ role: "user", content: "x".repeat(17000) }] });
  const request = new Request(BASE + "/api/demo-chat", {
    method: "POST",
    headers: { origin: BASE, "content-type": "application/json" },
    body: payload,
  });
  assert.equal(request.headers.get("content-length"), null);
  const response = await worker.fetch(request, f.env);
  assert.equal(response.status, 413);
  assert.equal(f.calls.length, 0);
  assert.equal(f.stored.has("count"), false);
});

test("slash commands and oversized requests never trigger inference", async () => {
  const f = fixture();
  const slash = await worker.fetch(post([{ role: "user", content: "/browse private" }]), f.env);
  assert.equal(slash.status, 400);
  const giant = await worker.fetch(post([{ role: "user", content: "x".repeat(10_000) }]), f.env);
  assert.equal(giant.status, 400);
  assert.equal(f.calls.length, 0);
  assert.equal(f.stored.has("count"), false);
});

test("redacts secrets server-side before provider egress", async () => {
  const f = fixture();
  const secret = "sk-test123456789012345";
  const r = await worker.fetch(post([{ role: "user", content: "Mi token " + secret }]), f.env);
  assert.equal(r.status, 200);
  const history = JSON.stringify(f.calls[0].args.messages);
  assert.ok(!history.includes(secret));
  assert.ok(history.includes("[redacted]"));
});

test("50 simultaneous requests spend at most 25 daily permits", async () => {
  const f = fixture();
  const responses = await Promise.all(
    Array.from({ length: 50 }, () => worker.fetch(post([{ role: "user", content: "hola" }]), f.env)),
  );
  const success = responses.filter((r) => r.status === 200).length;
  const limited = responses.filter((r) => r.status === 429).length;
  assert.equal(success, 25);
  assert.equal(limited, 25);
  assert.equal(f.stored.get("count"), 25);
  assert.equal(f.calls.length, 25);
});
