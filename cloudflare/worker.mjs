import { DurableObject } from "cloudflare:workers";

const MODEL = "@cf/qwen/qwen3-30b-a3b-fp8";
const MAX_CALLS_PER_UTC_DAY = 80;
const MAX_CONTEXT_BYTES = 7000;
const MAX_OUTPUT_TOKENS = 384;

const SYSTEM = [
  "Tu identidad de producto es 0liviA.",
  "Esta ruta usa como modelo base Qwen3-30B-A3B-FP8 en Cloudflare Workers AI.",
  "Si te preguntan qué modelo sos o qué modelo usás, decí ese nombre exacto; nunca digas que no tenés un modelo específico.",
  "Respondé siempre en español rioplatense argentino natural, claro y directo.",
  "Evitá fórmulas torpes como 'Soy Sos 0liviA'. Si te preguntan quién sos, respondé simplemente que sos 0liviA, la IA personal de Simón.",
  "Nunca cambies espontáneamente a alemán, inglés u otro idioma salvo que el usuario lo pida.",
  "No inventes acciones, archivos, accesos ni resultados.",
  "No hagas relleno. Priorizá utilidad, continuidad y precisión."
].join(" ");

function json(data, status = 200, extra = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...extra,
    },
  });
}

function sameOrigin(request) {
  const origin = request.headers.get("origin");
  if (!origin) return true;
  return origin === new URL(request.url).origin;
}

function cleanMessages(raw) {
  if (!Array.isArray(raw)) return null;
  const out = [];
  for (const item of raw.slice(-12)) {
    if (!item || (item.role !== "user" && item.role !== "assistant")) continue;
    const content = typeof item.content === "string" ? item.content.trim() : "";
    if (!content) continue;
    out.push({ role: item.role, content: content.slice(0, 6000) });
  }
  if (!out.length || out[out.length - 1].role !== "user") return null;
  return out;
}

function byteCount(messages) {
  const enc = new TextEncoder();
  let total = enc.encode(SYSTEM).byteLength;
  for (const message of messages) total += enc.encode(message.content).byteLength;
  return total;
}

function normalizedQuestion(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9ñ ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function fixedSelfAnswer(messages) {
  const latest = normalizedQuestion(messages[messages.length - 1]?.content);
  if (!latest) return null;

  if (
    /(^| )(que|q) modelo (sos|usas|utilizas|tenes|corres)( |$)/.test(latest) ||
    /(^| )modelo estas usando( |$)/.test(latest) ||
    /(^| )cual es tu modelo( |$)/.test(latest)
  ) {
    return "Qwen3-30B-A3B-FP8, corriendo en Cloudflare Workers AI. 0liviA es la identidad y la capa de producto que lo envuelve.";
  }

  if (
    /(^| )(quien sos|quien eres|que sos)( |$)/.test(latest)
  ) {
    return "Soy 0liviA, tu IA personal. Esta ruta usa Qwen3-30B-A3B-FP8 en Cloudflare Workers AI.";
  }

  return null;
}

function fixedSse(text) {
  const payload = JSON.stringify({ response: text });
  return new Response(`data: ${payload}\n\ndata: [DONE]\n\n`, {
    status: 200,
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-store",
      "x-accel-buffering": "no",
    },
  });
}

export class CostGuard extends DurableObject {
  async fetch(request) {
    if (request.method !== "POST") return json({ error: "method" }, 405);
    const day = new Date().toISOString().slice(0, 10);
    const storedDay = (await this.ctx.storage.get("day")) || "";
    let count = Number((await this.ctx.storage.get("count")) || 0);
    if (storedDay !== day) {
      count = 0;
      await this.ctx.storage.put({ day, count: 0 });
    }
    if (count >= MAX_CALLS_PER_UTC_DAY) {
      return json({
        ok: false,
        reason: "zero_cost_daily_cap",
        used: count,
        limit: MAX_CALLS_PER_UTC_DAY,
      }, 429);
    }
    count += 1;
    await this.ctx.storage.put({ day, count });
    return json({ ok: true, used: count, limit: MAX_CALLS_PER_UTC_DAY });
  }
}

async function takeZeroCostSlot(env) {
  const id = env.COST_GUARD.idFromName("global");
  const stub = env.COST_GUARD.get(id);
  return stub.fetch("https://cost-guard.internal/consume", { method: "POST" });
}

async function chat(request, env) {
  if (!sameOrigin(request)) return json({ error: "origin" }, 403);

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "json" }, 400);
  }

  const messages = cleanMessages(body?.messages);
  if (!messages) return json({ error: "messages" }, 400);

  const fixed = fixedSelfAnswer(messages);
  if (fixed) return fixedSse(fixed);

  const bytes = byteCount(messages);
  if (bytes > MAX_CONTEXT_BYTES) {
    return json({
      error: "context_too_large",
      max_bytes: MAX_CONTEXT_BYTES,
    }, 413);
  }

  const guard = await takeZeroCostSlot(env);
  if (!guard.ok) {
    return json({
      error: "zero_cost_daily_cap",
      message: "Límite diario $0 alcanzado.",
    }, 429);
  }

  try {
    const stream = await env.AI.run(MODEL, {
      messages: [{ role: "system", content: SYSTEM }, ...messages],
      stream: true,
      max_tokens: MAX_OUTPUT_TOKENS,
      temperature: 0.35,
      top_p: 0.9,
      repetition_penalty: 1.06,
      chat_template_kwargs: { enable_thinking: false },
    });

    return new Response(stream, {
      status: 200,
      headers: {
        "content-type": "text/event-stream; charset=utf-8",
        "cache-control": "no-cache, no-store",
        "x-accel-buffering": "no",
      },
    });
  } catch (error) {
    const message = String(error?.message || error || "AI unavailable");
    const limited = /3036|allocation|limit|quota|429/i.test(message);
    return json({
      error: limited ? "workers_ai_free_limit" : "ai_unavailable",
      message: limited
        ? "Workers AI agotó su cupo gratuito."
        : "El modelo no está disponible ahora.",
    }, limited ? 429 : 503);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/healthz") {
      return json({
        process_alive: true,
        provider_ready: true,
        hard_zero_cost: true,
        model: MODEL,
        max_calls_per_utc_day: MAX_CALLS_PER_UTC_DAY,
        max_context_bytes: MAX_CONTEXT_BYTES,
        max_output_tokens: MAX_OUTPUT_TOKENS,
      });
    }

    if (url.pathname === "/api/chat" && request.method === "POST") {
      return chat(request, env);
    }

    if (url.pathname.startsWith("/api/")) {
      return json({ error: "not_found" }, 404);
    }

    return env.ASSETS.fetch(request);
  },
};
