# Reference Linux deployment

This directory contains a reference self-hosted deployment for 0liviA.

Oracle Always Free A1 ARM64 (2 OCPU / 12 GB) is one useful zero-cost benchmark profile, not a required vendor/account. The same Core can run on another Linux host if the operator supplies the equivalent runtime prerequisites.

The scripts do **not** contain or grant access to the maintainer's Oracle, Cloudflare, GitHub or model-provider accounts.

## Runtime shape

```text
Internet
  │ HTTPS
  ▼
Caddy
  │ loopback
  ▼
0liviA Core :8080
  ├─ SQLite /var/lib/0livia
  └─ local/provider router
```

Only ports 80/443 should be public. Port 8080 stays loopback-only.

## Bootstrap

1. Provision a Linux host with a public IP.
2. Open TCP 80/443 only. Restrict SSH to the minimum administrative source needed.
3. Pick the exact green commit SHA you intend to release.
4. Run:

```bash
sudo REF=<40-hex-SHA> ./deploy/bootstrap-a1.sh
```

Mutable branches are rejected unless `ALLOW_MUTABLE_REF=1` is explicitly set for development.

5. Read `/var/lib/0livia/bootstrap-info` as root.
6. Open its one-time `SETUP_URL`.
7. Choose **Registrate**, create the first owner email/password and optionally enable **Recordarme**.
8. Registration closes after the first owner.
9. Configure only provider/accounts owned by that installation.

The setup token is placed in the URL fragment and removed from the browser address bar by the UI.

## Per-installation secrets

The bootstrap generates unique server-side values for:

- `OLIVIA_GATEWAY_TOKEN`;
- `OLIVIA_REGISTRATION_TOKEN`.

Provider keys remain in `/etc/0livia/olivia.env`, never in the normal browser UI.

The public repository contains no maintainer runtime secrets.

## Provider policy

No provider is the product identity.

`OLIVIA_PROVIDERS_JSON` references provider credentials by environment-variable name.

With `OLIVIA_HARD_ZERO_COST=1`, only:

- `cost_mode=local`; or
- `cost_mode=free_hard_cap`

are eligible.

`free_unverified` and `paid` routes are blocked before use.

If all verified-free routes are unavailable/exhausted, the expected behavior is degraded/unavailable rather than hidden spend.

## Coding worker

The coding worker is optional and disabled by default.

If enabled, configure a repository/token you control:

```env
OLIVIA_CODING_WORKER_ENABLED=1
OLIVIA_CODING_REPO=owner/your-repo
OLIVIA_CODING_WORKFLOW=coding-agent.yml
OLIVIA_CODING_BASE_REF=main
OLIVIA_GITHUB_TOKEN=...
```

Public forks do not inherit this repository's GitHub Actions secrets.

## Backups

The canonical runtime DB is:

```text
/var/lib/0livia/olivia.sqlite3
```

SQLite may also have WAL/SHM files while live.

Use SQLite's online backup API or stop the service briefly before copying. Do not copy only the main DB file while WAL has uncheckpointed data.

Git is the source of truth for code/docs, not user conversations.

## Local inference runtime

The reference bootstrap uses pinned llama.cpp binaries and SHA-256-verified GGUF files.

Profiles:

- `a1`: Qwen3 1.7B Q4_K_M, 4096-token context, up to 2 CPU threads.
- `micro`: Qwen3 0.6B Q4_K_M, 1024-token context, 1 thread plus swap.

These models are emergency/reference local baselines, not a claim of frontier-model quality.

## HTTPS hostname

The bootstrap can use an IP-derived hostname for convenience. A production operator should prefer a hostname they control.

## Rollback

Production installs accept exact commit SHAs.

Keep the previous release available until:

- compile/tests pass;
- services restart successfully;
- health/smoke checks pass;
- persistent state is readable.

`bootstrap-a1.sh` is the canonical reference installer. It does not create paid infrastructure.

## Cost claims

The reference setup is zero-cost-first, not a guarantee that every cloud/vendor will remain free.

External provider, domain, storage and network terms can change. Review the selected host/provider account before calling a deployment "$0".
