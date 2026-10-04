# Oracle deployment

Primary target: Oracle Always Free A1 ARM64, 2 OCPU / 12 GB. The bootstrap also has a deliberately degraded `micro` profile for the existing 1 GB E2 fallback. This directory does not create paid resources.

## Runtime shape

Internet → HTTPS/Caddy → `127.0.0.1:8080` → 0liviA Core → SQLite in `/var/lib/0livia`.

Only ports 80/443 should be public. Port 8080 stays loopback-only. The owner's PC is not part of the runtime.

## Bootstrap

1. Provision the A1 VM with a public IPv4 and Ubuntu ARM64.
2. Open OCI ingress TCP 80/443 only (SSH 22 restricted to the minimum source needed for administration).
3. Run `sudo REF=arch/gpt-synthesis-v1 ./deploy/bootstrap-a1.sh`.
4. Edit `/etc/0livia/olivia.env` (0600): generate the gateway token and add at least one legitimate provider key/route.
5. Pick an HTTPS hostname. Preferred: a domain you control pointing DNS-only at the Oracle IP. For bootstrap, an IP-derived DNS hostname can be used if you deliberately accept that external DNS dependency.
6. Configure Caddy from `deploy/Caddyfile.example`; keep `OLIVIA_PUBLIC_HOST` and `ACME_EMAIL` outside Git.
7. `sudo systemctl restart caddy olivia`.
8. Run `deploy/smoke.sh https://HOST TOKEN`.

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
