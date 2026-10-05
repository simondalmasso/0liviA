# Oracle deployment

Primary target: Oracle Always Free A1 ARM64, 2 OCPU / 12 GB. The bootstrap also has a deliberately degraded `micro` profile for the existing 1 GB E2 fallback. This directory does not create paid resources.

## Runtime shape

Internet → HTTPS/Caddy → `127.0.0.1:8080` → 0liviA Core → SQLite in `/var/lib/0livia`.

Only ports 80/443 should be public. Port 8080 stays loopback-only. The owner's PC is not part of the runtime.

## Bootstrap

1. Provision the A1 VM with a public IPv4 and Ubuntu ARM64.
2. Open OCI ingress TCP 80/443 only (SSH 22 restricted to the minimum source needed for administration).
3. Pick the exact green commit SHA you intend to release and run `sudo REF=<40-hex-SHA> ./deploy/bootstrap-a1.sh`. Mutable branches are rejected unless `ALLOW_MUTABLE_REF=1` is explicitly set for development.
4. Read `/var/lib/0livia/bootstrap-info` as root and open its one-time `SETUP_URL`. The setup token lives in the URL fragment and is removed from the browser address bar immediately.
5. Choose **Registrate**, create the owner email/password, and optionally enable **Recordarme**. Registration closes after the first owner.
6. If adding external providers, edit `/etc/0livia/olivia.env` (0640 root:olivia) and configure only accounts/routes owned by that deployment.
7. Pick an HTTPS hostname you control and keep port 8080 private. Browser auth uses Secure/HttpOnly/SameSite cookies; provider credentials remain server-side.
8. Run the CLI smoke with the server-side bearer obtained directly from `/etc/0livia/olivia.env`, never through a browser URL or UI.

## Provider policy

No provider is the brain. Provider keys stay in `/etc/0livia/olivia.env`; `OLIVIA_PROVIDERS_JSON` references their environment variable names. If all free lanes are exhausted, 0liviA reports unavailable/degraded instead of silently paying.

## Backups

The durable runtime file is `/var/lib/0livia/olivia.sqlite3` plus WAL/SHM while live. Use SQLite's online backup API or stop the service briefly before copying; never copy only the main DB file while WAL has uncheckpointed data. Git remains the source of truth for code/docs, not conversations.

## Rollback

Deploys are branch/commit based. Keep the previous checkout under a versioned release path before production rollout; switch `/opt/0livia/current` only after compile/tests/smoke pass. `bootstrap-a1.sh` is the single canonical installer. Atomic release switching remains a deployment hardening gate.


## Zero-spend gate

Production keeps `OLIVIA_HARD_ZERO_COST=1`. Provider entries are accepted only with `cost_mode=local` or `cost_mode=free_hard_cap`, where the upstream account/route has a verified hard boundary that cannot create a charge.

An advertised free quota without a hard billing boundary is `free_unverified` and is blocked. When all verified-free lanes are unavailable or quota-exhausted, the expected behavior is **degraded/unavailable, USD 0 spend**.


## Local inference runtime

The bootstrap uses a pinned **llama.cpp** prebuilt instead of Ollama to keep the hot path small. The runtime binds only to loopback and exposes its OpenAI-compatible endpoint to 0liviA Core.

Profiles:
- `a1`: Qwen3 1.7B Q4_K_M, 4096-token context, up to 2 CPU threads.
- `micro`: Qwen3 0.6B Q4_K_M, 1024-token context, 1 thread plus swap. This is only a temporary text fallback; it is not considered the final super-AI quality target.

The model route is tagged `cost_mode=local`, so the hard-zero-cost router accepts it without an API key.


## Release immutability

Production installs accept an exact 40-hex Git commit SHA. `cloud-init-a1.yaml` is intentionally a template that fails closed until `REF` is supplied as an immutable SHA. Never execute a mutable branch as root in production.

The bootstrap pins the llama.cpp release plus SHA-256 per architecture and pins each GGUF to an immutable Hugging Face revision plus SHA-256. Every download is verified before execution/use.
