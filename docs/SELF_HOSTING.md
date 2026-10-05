# Self-hosting 0liviA

0liviA is designed so every installation owns its own identity, data and provider configuration.

There is no shared 0liviA backend that public users should connect to.

## 1. Create instance secrets

Generate unique secrets for your installation:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Use separate values for:

```env
OLIVIA_GATEWAY_TOKEN=...
OLIVIA_REGISTRATION_TOKEN=...
```

Never reuse another installation's setup token, gateway token or provider credentials.

## 2. Configure your own provider

You may use local inference or **your own provider** account.

Example server-side provider registry:

```env
OLIVIA_HARD_ZERO_COST=1
OLIVIA_PROVIDERS_JSON=[{"name":"local","base_url":"http://127.0.0.1:11434/v1","model":"local-model","api_key_env":"","priority":10,"daily_limit":0,"cost_mode":"local"}]
```

For a remote provider, store its key in the server environment and reference the environment-variable name from `OLIVIA_PROVIDERS_JSON`.

Do not put provider keys in the browser UI.

## 3. First-owner registration

A new installation has no owner account.

Open the protected setup URL containing the one-time registration token, register an email/password, then stop sharing that setup URL. After the first owner is created, registration closes.

Passwords are represented by a scrypt verifier in the installation's SQLite database. Remembered devices use random server-side IDs and can be revoked from the Session panel.

## 4. Runtime data

Keep runtime state outside the Git checkout:

```env
OLIVIA_DATA_DIR=/var/lib/0livia
```

That directory contains installation-specific data such as:

- chats;
- projects;
- library items;
- memory;
- jobs/checkpoints;
- account/device state.

Back it up as private application data. Do not commit it.

## 5. Coding worker

The coding worker is optional and disabled by default.

Configure it only against a repository/token you control:

```env
OLIVIA_CODING_WORKER_ENABLED=1
OLIVIA_CODING_REPO=owner/your-repo
OLIVIA_CODING_WORKFLOW=coding-agent.yml
OLIVIA_CODING_BASE_REF=main
OLIVIA_GITHUB_TOKEN=...
```

A public clone does not inherit the maintainer's GitHub Actions secrets.

## 6. Web search

`/read` is a direct safe URL reader.

`/search` and `/research` require a separately configured search adapter. Search is disabled unless the route is explicitly marked as zero-cost verified.

Do not point a public installation at somebody else's Cloudflare AI Gateway, BYOK alias or provider account.

## 7. Cloudflare

Cloudflare is not required for the canonical Core.

The repository contains a transitional Worker implementation, but its chat/read runtime is disabled by default. A fork must provide its own Cloudflare account/bindings if it deliberately chooses to use that bridge.

## 8. Reference Linux deployment

The `deploy/` directory contains a reference Linux/Oracle A1 profile. It installs:

- Python Core;
- SQLite state;
- llama.cpp local inference;
- Caddy HTTPS;
- a protected first-run setup link.

It is a reference zero-cost profile, not a dependency on the maintainer's Oracle or Cloudflare accounts.

## Cost policy

"Zero-cost-first" means the software prefers:

- local inference; or
- a provider route with an externally verified hard-free boundary.

It does not mean every host/provider/domain is guaranteed to remain free. If `OLIVIA_HARD_ZERO_COST=1`, unverified or paid routes are blocked rather than used silently.
