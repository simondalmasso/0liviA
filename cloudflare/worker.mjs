// Public Cloudflare surface is deliberately static-only. Authentication and
// all private state live in the canonical Python Core; this Worker never accepts
// an Auth0/Google identity and never invokes a model provider.
const PUBLIC_SHELL_ONLY = true;
const DEMO_MODEL = "@cf/zai-org/glm-4.7-flash";
const DEMO_QWEN_MODEL = "@cf/qwen/qwen3.8-27b";
const DEMO_GEMMA_MODEL = "@cf/google/gemma-4-26b-a4b-it";

function json(body, { status = 200, headers = {} } = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...headers },
  });
}

const PUBLIC_CSP = [
  "default-src 'self'", "base-uri 'none'", "object-src 'none'", "frame-ancestors 'none'",
  "form-action 'self'", "script-src 'self' 'unsafe-inline'", "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:", "media-src 'self' data: blob:", "font-src 'self'",
  "connect-src 'self' wss:", "upgrade-insecure-requests",
].join("; ");

function hardened(response) {
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

function health(env) {
  return json({
    process_alive: true,
    release_sha: /^[0-9a-f]{40}$/.test(String(env?.OLIVIA_RELEASE_SHA || "")) ? env.OLIVIA_RELEASE_SHA : null,
    api_mode: "public_shell",
    public_shell: PUBLIC_SHELL_ONLY,
    static_only: true,
    bridge_enabled: false,
    provider_ready: false,
    inference_enabled: false,
    demo_inference_enabled: false,
    demo_provider_ready: false,
    demo_provider: null,
    demo_model: null,
    demo_qwen_ready: false,
    demo_gemma_ready: false,
    demo_models: [
      { id: "glm", model: DEMO_MODEL, label: "GLM 4.7 Flash", available: false },
      { id: "qwen", model: DEMO_QWEN_MODEL, label: "Qwen3.8 27B", available: false },
      { id: "gemma", model: DEMO_GEMMA_MODEL, label: "Gemma 4 26B A4B", available: false },
    ],
    demo_daily_request_limit: 0,
    web_read: false,
    hard_zero_cost: true,
    demo_cost_guaranteed: false,
    cost_reason: "static_only_no_inference_backend",
    canonical_backend: "self_hosted_python_core",
  });
}

function disabledApi() {
  return json({
    error: "bridge_disabled",
    message: "The public shell is static-only. Use the separately deployed canonical Python Core for authenticated chat and private data.",
  }, { status: 503 });
}

// Keep the already-provisioned export shape for deployment compatibility. No
// binding points at this class in the static-only release and it has no stateful
// quota/inference side effects.
export class CostGuard {
  constructor(state) { this.state = state; }
  async fetch() { return json({ error: "not_found" }, { status: 404 }); }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    let result;
    if (url.pathname === "/healthz") {
      result = health(env);
    } else if (url.pathname.startsWith("/api/")) {
      result = disabledApi();
    } else {
      result = await env.ASSETS.fetch(request);
    }
    return hardened(result);
  },
};
