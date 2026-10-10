const PUBLIC_SHELL_ONLY = true;
const TRANSITIONAL_BRIDGE_ENABLED = false;
const DEMO_MODEL = "@cf/zai-org/glm-4.7-flash";
const DEMO_PROVIDER = "workers-ai-demo";
const DEMO_DAILY_REQUEST_LIMIT = 25;
const DEMO_MAX_TOTAL_CHARS = 8000;
const DEMO_MAX_MESSAGES = 8;
const DEMO_MAX_OUTPUT_TOKENS = 256;

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

function demoEnabled(env) {
  return (
    env?.OLIVIA_DEMO_ZERO_COST_CONFIRMED === "1" &&
    env?.AI &&
    env?.COST_GUARD
  );
}

function health(env) {
  const demoReady = Boolean(demoEnabled(env));
  return json({
    process_alive: true,
    api_mode: "public_shell",
    public_shell: PUBLIC_SHELL_ONLY,
    bridge_enabled: TRANSITIONAL_BRIDGE_ENABLED,
    provider_ready: false,
    inference_enabled: false,
    demo_inference_enabled: demoReady,
    demo_provider_ready: demoReady,
    demo_provider: demoReady ? DEMO_PROVIDER : null,
    demo_model: demoReady ? DEMO_MODEL : null,
    demo_daily_request_limit: DEMO_DAILY_REQUEST_LIMIT,
    web_read: false,
    hard_zero_cost: !demoReady,
    demo_cost_guaranteed: false,
    cost_reason: demoReady
      ? "request_cap_is_not_a_provider_billing_cap"
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
  const messages = raw
    .filter((item) => item && (item.role === "user" || item.role === "assistant"))
    .slice(-DEMO_MAX_MESSAGES)
    .map((item) => ({
      role: item.role,
      content: redact(item.content).trim(),
    }))
    .filter((item) => item.content);

  if (!messages.length) throw new Error("at least one message is required");
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

function trustedDemoOrigin(request) {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  try {
    return new URL(origin).origin === new URL(request.url).origin;
  } catch {
    return false;
  }
}

async function readDemoBody(request) {
  const contentLength = Number(request.headers.get("content-length") || "0");
  if (!Number.isFinite(contentLength) || contentLength < 0 || contentLength > 16_384) {
    return { error: "body_too_large", status: 413 };
  }
  if (!(request.headers.get("content-type") || "").toLowerCase().startsWith("application/json")) {
    return { error: "invalid_content_type", status: 415 };
  }

  const reader = request.body?.getReader();
  if (!reader) return { error: "invalid_body", status: 400 };
  const chunks = [];
  let totalBytes = 0;
  try {
    while (true) {
      const part = await reader.read();
      if (part.done) break;
      totalBytes += part.value.byteLength;
      if (totalBytes > 16_384) {
        await reader.cancel().catch(() => {});
        return { error: "body_too_large", status: 413 };
      }
      chunks.push(part.value);
    }
    const bytes = new Uint8Array(totalBytes);
    let offset = 0;
    for (const part of chunks) {
      bytes.set(part, offset);
      offset += part.byteLength;
    }
    return { text: new TextDecoder("utf-8", { fatal: true }).decode(bytes) };
  } catch {
    return { error: "invalid_body", status: 400 };
  }
}

async function demoChat(request, env) {
  if (request.method !== "POST") {
    return json({ error: "method_not_allowed" }, { status: 405, headers: { allow: "POST" } });
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

  // Browser-safety boundary, not owner authentication: the demo remains shared and anonymous.
  if (!trustedDemoOrigin(request)) {
    return json({ error: "origin_forbidden" }, { status: 403 });
  }
  const bounded = await readDemoBody(request);
  if (bounded.error) {
    return json({ error: bounded.error }, { status: bounded.status });
  }

  let body;
  try {
    body = JSON.parse(bounded.text);
  } catch {
    return json({ error: "invalid_json" }, { status: 400 });
  }

  let messages;
  try {
    messages = normalizeDemoMessages(body?.messages);
  } catch (error) {
    return json({ error: "invalid_demo_request", message: String(error?.message || error) }, { status: 400 });
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
      "Sos 0liviA en modo de demostración pública. Respondé en español rioplatense argentino, claro y directo. No tenés identidad de propietario, memoria privada, herramientas ni acceso al Core canónico. No afirmes haber ejecutado acciones o leído datos privados.",
  };

  try {
    const result = await env.AI.run(DEMO_MODEL, {
      messages: [system, ...messages],
      max_completion_tokens: DEMO_MAX_OUTPUT_TOKENS,
      temperature: 0.4,
      stream: false,
    });
    const answer = extractAnswer(result);
    if (!answer) throw new Error("empty model response");
    return json({
      answer,
      provider: DEMO_PROVIDER,
      model: DEMO_MODEL,
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
    const storedDay = (await this.state.storage.get("day")) || "";
    let count = Number((await this.state.storage.get("count")) || 0);

    if (storedDay !== day) {
      count = 0;
      await this.state.storage.put({ day, count: 0 });
    }

    if (count >= DEMO_DAILY_REQUEST_LIMIT) {
      return json(
        {
          error: "demo_daily_limit",
          limit: DEMO_DAILY_REQUEST_LIMIT,
          message: "El cupo diario $0 del modo prueba se agotó.",
        },
        { status: 429 },
      );
    }

    count += 1;
    await this.state.storage.put({ day, count });
    return json({ ok: true, day, count, limit: DEMO_DAILY_REQUEST_LIMIT });
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/healthz") {
      return health(env);
    }

    if (url.pathname === "/api/demo-chat") {
      return demoChat(request, env);
    }

    if (
      url.pathname === "/api/chat" ||
      url.pathname === "/api/read-url" ||
      url.pathname.startsWith("/api/")
    ) {
      return disabledApi();
    }

    return env.ASSETS.fetch(request);
  },
};
