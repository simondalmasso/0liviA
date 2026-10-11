"""Owner-only Cloudflare Worker auth tests with real RS256 crypto and fake AI."""
import assert from "node:assert/strict";
import { before, test } from "node:test";
import worker from "../../cloudflare/worker.mjs";
import { authEnvironment, initializeAuthTest } from "./owner_auth_fixture.mjs";

const BASE = "https://olivia.test";
let signer;

before(async () => { signer = await initializeAuthTest(); });

function backend(extra = {}) {
  const calls = { ai: 0, quota: 0, read: 0 };
  const env = {
    ...authEnvironment,
    OLIVIA_DEMO_ZERO_COST_CONFIRMED: "1",
    AI: { run: async () => { calls.ai++; return { response: "MODEL_RESPONSE" }; } },
    COST_GUARD: {
      idFromName: () => { calls.quota++; return "safe"; },
      get: () => ({ fetch: async () => {
        calls.quota++;
        return new Response(JSON.stringify({ ok: true }));
      } }),
    },
    ASSETS: { fetch: async () => { calls.read++; return new Response("static"); } },
    ...extra,
  };
  return { env, calls };
}

function prompt(token, extraHeaders = {}) {
  return new Request(BASE + "/api/demo-chat", {
    method: "POST",
    headers: { origin: BASE, "content-type": "application/json",
      ...(token === undefined ? {} : { authorization: "Bearer " + token }),
      ...extraHeaders },
    body: JSON.stringify({ messages: [{ role: "user", content: "Hola" }] }),
  });
}

test("anonymous, spoofed headers, legacy bearer, forged Origin: no quota/model calls", async () => {
  const f = backend();
  const tests = [
    prompt(undefined),
    prompt(undefined, { origin: BASE, "X-User": "owner", "X-Role": "owner", "X-Email": "owner@example.com" }),
    prompt("a-legacy-gateway-secret"),
    prompt("a.b.c", { origin: BASE, "X-Owner": "true" }),
    prompt(undefined, { origin: "https://attacker.example" }),
  ];
  for (const req of tests) {
    const response = await worker.fetch(req, f.env);
    assert.equal(response.status, 401);
  }
  assert.equal(f.calls.ai, 0);
  assert.equal(f.calls.quota, 0);
});

test("signed non-owner Google user and incorrect stable owner identity return 403", async () => {
  const f = backend();
  const ns = "https://0livia.app/claims/";
  const signedGuests = [
    { sub: "google-oauth2|999999999999999999999" },
    { [ns + "google_sub"]: "999999999999999999999" },
    { [ns + "email"]: "guest@example.com" },
    { [ns + "email_verified"]: false },
    { [ns + "provider"]: "auth0" },
    { [ns + "session_version"]: "replayed-version" },
  ];
  for (const changes of signedGuests) {
    const token = await signer.sign(changes);
    const response = await worker.fetch(prompt(token, { "X-Role": "OWNER" }), f.env);
    assert.equal(response.status, 403);
    assert.equal((await response.json()).error, "owner_only");
  }
  assert.equal(f.calls.ai, 0);
  assert.equal(f.calls.quota, 0);
});

test("invalid JWT signatures, issuer, audience and time claims return 401", async () => {
  const f = backend();
  const now = Math.floor(Date.now() / 1000);
  const badTokens = [
    await signer.sign({ iss: "https://attacker.auth0.com/" }),
    await signer.sign({ aud: "https://attacker.example/api" }),
    await signer.sign({ exp: now - 1 }),
    await signer.sign({ nbf: now + 1000 }),
    await signer.sign({ iat: now + 1000 }),
    await signer.sign({ exp: now + 10_000 }),
    await signer.sign({ jti: "" }),
    await signer.sign({}, { alg: "none" }),
    await signer.sign({}, { kid: "unexpected-key" }),
    await signer.sign({}, { jku: "https://attacker.example/jwks" }),
    (await signer.sign()).slice(0, -4) + "aaaa",
  ];
  for (const token of badTokens) {
    const response = await worker.fetch(prompt(token), f.env);
    assert.equal(response.status, 401);
  }
  assert.equal(f.calls.ai, 0);
  assert.equal(f.calls.quota, 0);
});

test("revoked issuance epoch denies previously signed JWT and makes no side effects", async () => {
  const now = Math.floor(Date.now() / 1000);
  const f = backend({ OLIVIA_OWNER_REVOKED_BEFORE: String(now + 10) });
  const response = await worker.fetch(prompt(signer.token), f.env);
  assert.equal(response.status, 403);
  assert.equal(f.calls.ai, 0);
  assert.equal(f.calls.quota, 0);
});

test("anonymous is 401, signed guest 403, owner gets 503 on private inactive APIs", async () => {
  const f = backend();
  const guest = await signer.sign({ sub: "google-oauth2|999999999999999999999" });
  for (const path of [
    "/api/chat", "/api/read-url", "/api/jobs/code",
    "/api/sessions", "/api/auth/session", "/api/unknown",
  ]) {
    for (const [token, status] of [[null, 401], [guest, 403], [signer.token, 503]]) {
      const response = await worker.fetch(new Request(BASE + path, {
        headers: token ? { authorization: "Bearer " + token } : {},
      }), f.env);
      assert.equal(response.status, status);
    }
  }
  assert.equal(f.calls.ai, 0);
  assert.equal(f.calls.quota, 0);
  assert.equal(f.calls.read, 0);
});

test("missing owner configuration prevents any inference, even with signed owner token", async () => {
  const f = backend({ OLIVIA_OWNER_GOOGLE_SUB: "" });
  const response = await worker.fetch(prompt(signer.token), f.env);
  assert.equal(response.status, 503);
  assert.equal(f.calls.ai, 0);
  assert.equal(f.calls.quota, 0);
  const health = await worker.fetch(new Request(BASE + "/healthz"), f.env);
  const obj = await health.json();
  assert.equal(obj.demo_inference_enabled, false);
  assert.equal(JSON.stringify(obj).includes("owner@example.com"), false);
});

test("50 concurrent authenticated guests cannot consume private quota", async () => {
  const f = backend();
  const guest = await signer.sign({ sub: "google-oauth2|999999999999999999999" });
  const responses = await Promise.all(Array.from({ length: 50 },
    () => worker.fetch(prompt(guest), f.env)));
  assert.ok(responses.every((response) => response.status === 403));
  assert.equal(f.calls.ai, 0);
  assert.equal(f.calls.quota, 0);
});

test("owner token alone is not a billing entitlement", async () => {
  const f = backend({ OLIVIA_DEMO_ZERO_COST_CONFIRMED: "0" });
  const response = await worker.fetch(prompt(signer.token), f.env);
  assert.equal(response.status, 503);
  assert.equal(f.calls.ai, 0);
  assert.equal(f.calls.quota, 0);
});
