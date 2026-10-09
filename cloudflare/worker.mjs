const PUBLIC_SHELL_ONLY = true;
const TRANSITIONAL_BRIDGE_ENABLED = false;
const DEMO_MODEL = "@cf/zai-org/glm-4.7-flash";
const DEMO_QWEN_MODEL = "@cf/qwen/qwen3-30b-a3b-fp8";
const DEMO_PROVIDER = "workers-ai-demo";
const DEMO_DAILY_REQUEST_LIMIT = 25;
const DEMO_MAX_TOTAL_CHARS = 8000;
const DEMO_MAX_MESSAGES = 8;
const DEMO_MAX_OUTPUT_TOKENS = 1024;

function json(body, { status = 200, headers = {} } = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...headers,
    },
  });
}

// Response hardening for the thin public shell. Inline UI CSS/JS remains
// intentionally permitted until the single-file frontend is split into assets.
const PUBLIC_CSP = [
  "default-src 'self'",
  "base-uri 'none'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "media-src 'self' data: blob:",
  "font-src 'self'",
  "connect-src 'self' wss:",
  "upgrade-insecure-requests",
].join("; ");

function hardened(response) {
  // Static-assets responses can have immutable headers; clone before editing.
  const out = new Response(response.body, response);
  out.headers.set("X-Content-Type-Options", "nosniff");
  out.headers.set("X-Frame-Options", "DENY");
  out.headers.set("Referrer-Policy", "no-referrer");
  out.headers.set("Strict-Transport-Security", "max-age=31536000");
  out.headers.set("Content-Security-Policy", PUBLIC_CSP);
  out.headers.set("Cross-Origin-Resource-Policy", "same-origin");
  out.headers.set("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)");
  return out;
}

function demoEnabled(env) {
  return (
    env?.OLIVIA_DEMO_ZERO_COST_CONFIRMED === "1" &&
    env?.AI &&
    env?.COST_GUARD
  );
}

function qwenEnabled(env) {
  // Independent approval: GLM entitlement does not prove Qwen has a no-overage boundary.
  return Boolean(demoEnabled(env) && env?.OLIVIA_DEMO_QWEN_ZERO_COST_CONFIRMED === "1");
}

function health(env) {
  const demoReady = Boolean(demoEnabled(env));
  const qwenReady = qwenEnabled(env);
  return json({
    process_alive: true,
    release_sha: /^[0-9a-f]{40}$/.test(String(env?.OLIVIA_RELEASE_SHA || "")) ? env.OLIVIA_RELEASE_SHA : null,
    api_mode: "public_shell",
    public_shell: PUBLIC_SHELL_ONLY,
    bridge_enabled: TRANSITIONAL_BRIDGE_ENABLED,
    provider_ready: false,
    inference_enabled: false,
    demo_inference_enabled: demoReady,
    demo_provider_ready: demoReady,
    demo_provider: demoReady ? DEMO_PROVIDER : null,
    demo_model: demoReady ? DEMO_MODEL : null,
    demo_qwen_ready: qwenReady,
    demo_models: [
      { id: "glm", model: DEMO_MODEL, label: "GLM 4.7 Flash", available: demoReady },
      { id: "qwen", model: DEMO_QWEN_MODEL, label: "Qwen3 30B", available: qwenReady },
    ],
    demo_daily_request_limit: DEMO_DAILY_REQUEST_LIMIT,
    web_read: false,
    hard_zero_cost: true,
    cost_reason: demoReady
      ? "canonical_inference_off_demo_hard_capped"
      : "no_inference_or_search_backend",
    canonical_backend: "self_hosted_python_core",
  });
}

function disabledApi() {
  return json(
    {
      error: "bridge_disabled",
      message:
        "This public shell has no canonical shared model, search, memory or user-data backend. Self-host the canonical Python Core.",
    },
    { status: 503 },
  );
}

function redact(value) {
  let out = String(value ?? "");
  const rules = [
    [/\bbearer\s+[A-Za-z0-9._~+/\-]{8,}=*/gi, "[redacted]"],
    [/\bsk-[A-Za-z0-9._\-]{6,}/g, "[redacted]"],
    [/\b(?:gsk|AIza|hf|ghp|gho|xoxb|xoxp)[A-Za-z0-9._\-]{6,}/g, "[redacted]"],
    [/\bnvapi-[A-Za-z0-9._\-]{6,}/gi, "[redacted]"],
    [/\b[A-Za-z0-9_\-]{40,}\b/g, "[redacted]"],
    [
      /(api[_-]?key|secret|token|authorization|password)\s*[:=]\s*["']?[^"'\s,}]{4,}/gi,
      "$1=[redacted]",
    ],
  ];
  for (const [pattern, replacement] of rules) out = out.replace(pattern, replacement);
  return out;
}

function normalizeDemoMessages(raw) {
  if (!Array.isArray(raw)) throw new Error("messages must be an array");
  const rawMessages = raw
    .filter((item) => item && (item.role === "user" || item.role === "assistant"))
    .slice(-DEMO_MAX_MESSAGES);
  // Check the original text before redaction: replacing long tokens must not bypass the limit.
  const rawTotalChars = rawMessages.reduce((sum, item) => sum + String(item.content ?? "").length, 0);
  if (rawTotalChars > DEMO_MAX_TOTAL_CHARS) throw new Error("demo context too large");
  const messages = rawMessages
    .map((item) => ({
      role: item.role,
      content: redact(item.content).trim(),
    }))
    .filter((item) => item.content);

  if (!messages.length) throw new Error("at least one message is required");
  if (messages[messages.length - 1].role !== "user") throw new Error("last message must be user");
  const lastUser = [...messages].reverse().find((item) => item.role === "user");
  if (!lastUser) throw new Error("a user message is required");
  if (lastUser.content.startsWith("/")) throw new Error("commands require the canonical Core");

  const totalChars = messages.reduce((sum, item) => sum + item.content.length, 0);
  if (totalChars > DEMO_MAX_TOTAL_CHARS) throw new Error("demo context too large");
  return messages;
}

function extractAnswer(result) {
  const choice = result?.choices?.[0];
  return String(
    choice?.message?.content ??
      choice?.delta?.content ??
      result?.response ??
      "",
  ).trim();
}

async function demoChat(request, env) {
  if (request.method !== "POST") {
    return json({ error: "method_not_allowed" }, { status: 405, headers: { allow: "POST" } });
  }
  const origin = request.headers.get("origin");
  if (origin && origin !== new URL(request.url).origin) {
    return json({ error: "cross_origin_denied" }, { status: 403 });
  }
  if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
    return json({ error: "json_required" }, { status: 415 });
  }
  if (!demoEnabled(env)) {
    return json(
      {
        error: "demo_unavailable",
        message: "The zero-cost demo route is not enabled on this deployment.",
      },
      { status: 503 },
    );
  }

  const contentLength = Number(request.headers.get("content-length") || "0");
  if (contentLength > 16_384) {
    return json({ error: "body_too_large" }, { status: 413 });
  }

  let rawBody;
  try {
    rawBody = await request.text();
  } catch {
    return json({ error: "invalid_body" }, { status: 400 });
  }
  if (rawBody.length > 16_384) {
    return json({ error: "body_too_large" }, { status: 413 });
  }

  let body;
  try {
    body = JSON.parse(rawBody);
  } catch {
    return json({ error: "invalid_json" }, { status: 400 });
  }

  let messages;
  try {
    messages = normalizeDemoMessages(body?.messages);
  } catch (error) {
    return json({ error: "invalid_demo_request", message: String(error?.message || error) }, { status: 400 });
  }

  // Validate model before burning daily quota; no arbitrary model IDs reach Workers AI.
  const selected = body?.model === undefined ? "glm" : body.model;
  if (selected !== "glm" && selected !== "qwen") {
    return json({ error: "invalid_demo_model" }, { status: 400 });
  }
  if (selected === "qwen" && !qwenEnabled(env)) {
    return json({ error: "qwen_unavailable", message: "Qwen needs separately verified zero-cost admission." }, { status: 503 });
  }
  const model = selected === "qwen" ? DEMO_QWEN_MODEL : DEMO_MODEL;
  const lastQuestion = messages[messages.length - 1]?.content || "";
  // Model identity is a shell fact, not generative text. Do not spend public quota
  // on an answer that the provider might misidentify.
  if (/^\s*(?:(?:q|qu[eé])\s+)?modelo\s+(?:sos|us[aá]s|utiliz[aá]s|ten[eé]s)\s*\??\s*$/i.test(lastQuestion)) {
    return json({
      answer: `Esta es la demo pública de 0liviA. Modelo seleccionado: ${model} (Cloudflare Workers AI). El Core privado no está conectado a esta demo.`,
      provider: "local-demo",
      model,
      canonical: false,
    });
  }

  const id = env.COST_GUARD.idFromName("public-demo-global");
  const guard = env.COST_GUARD.get(id);
  const allowance = await guard.fetch("https://cost-guard/allow", { method: "POST" });
  if (!allowance.ok) {
    const payload = await allowance.json().catch(() => ({ error: "demo_daily_limit" }));
    return json(payload, { status: allowance.status });
  }

  const system = {
    role: "system",
    content:
      `Sos 0liviA en modo prueba, con el modelo ${model}. Respondé en español de Argentina con voseo natural, claridad y respeto, sin apodos ni familiaridad forzada. Si te preguntan qué modelo sos, identificá exactamente ${model} (Cloudflare Workers AI, demo), sin inventar otro. No tenés memoria privada, acceso a herramientas ni conexión al Core canónico. Nunca afirmes haber ejecutado acciones, leído archivos privados o usado el Core canónico.`,
  };

  try {
    const result = await env.AI.run(model, {
      messages: [system, ...messages],
      ...(selected === "qwen" ? { max_tokens: DEMO_MAX_OUTPUT_TOKENS } : { max_completion_tokens: DEMO_MAX_OUTPUT_TOKENS }),
      temperature: 0.4,
      stream: false,
    });
    const answer = extractAnswer(result);
    if (!answer) throw new Error("empty model response");
    return json({
      answer,
      provider: DEMO_PROVIDER,
      model,
      canonical: false,
    });
  } catch {
    return json(
      {
        error: "demo_provider_unavailable",
        message: "The zero-cost demo model is temporarily unavailable.",
      },
      { status: 503 },
    );
  }
}

export class CostGuard {
  constructor(state) {
    this.state = state;
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (request.method !== "POST" || url.pathname !== "/allow") {
      return json({ error: "not_found" }, { status: 404 });
    }

    const day = new Date().toISOString().slice(0, 10);
    // One transaction protects the global budget when requests arrive concurrently.
    const allowance = await this.state.storage.transaction(async (txn) => {
      const storedDay = (await txn.get("day")) || "";
      let count = storedDay === day ? Number((await txn.get("count")) || 0) : 0;
      if (count >= DEMO_DAILY_REQUEST_LIMIT) return { allowed: false, count };
      count += 1;
      await txn.put({ day, count });
      return { allowed: true, count };
    });

    if (!allowance.allowed) {
      return json(
        {
          error: "demo_daily_limit",
          limit: DEMO_DAILY_REQUEST_LIMIT,
          message: "El cupo diario $0 del modo prueba se agotó.",
        },
        { status: 429 },
      );
    }

    return json({ ok: true, day, count: allowance.count, limit: DEMO_DAILY_REQUEST_LIMIT });
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    let result;
    if (url.pathname === "/healthz") {
      result = health(env);
    } else if (url.pathname === "/api/demo-chat") {
      result = await demoChat(request, env);
    } else if (
      url.pathname === "/api/chat" ||
      url.pathname === "/api/read-url" ||
      url.pathname.startsWith("/api/")
    ) {
      result = disabledApi();
    } else {
      result = await env.ASSETS.fetch(request);
    }
    return hardened(result);
  },
};
