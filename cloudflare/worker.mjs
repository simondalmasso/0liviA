const PUBLIC_SHELL_ONLY = true;
const TRANSITIONAL_BRIDGE_ENABLED = false;

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

function health() {
  return json({
    process_alive: true,
    api_mode: "public_shell",
    public_shell: PUBLIC_SHELL_ONLY,
    bridge_enabled: TRANSITIONAL_BRIDGE_ENABLED,
    provider_ready: false,
    inference_enabled: false,
    web_read: false,
    hard_zero_cost: true,
    cost_reason: "no_inference_or_search_backend",
    canonical_backend: "self_hosted_python_core",
  });
}

function disabledApi() {
  return json(
    {
      error: "bridge_disabled",
      message:
        "This public shell has no shared model, search, memory or user-data backend. Self-host the canonical Python Core.",
    },
    { status: 503 },
  );
}

// Historical reconciliation only.
//
// A previous production bridge provisioned this Durable Object class. Wrangler
// requires the named export to remain present while that namespace exists.
// The public-shell deployment intentionally has NO binding to this class, so
// request handling cannot invoke it and it cannot consume per-request storage.
export class CostGuard {
  async fetch() {
    return json(
      {
        error: "historical_namespace_inert",
        message: "The historical CostGuard namespace is not part of the public shell.",
      },
      { status: 410 },
    );
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/healthz") {
      return health();
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
