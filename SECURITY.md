# Security policy

## Trust model

0liviA is self-hosted. Each installation must use its **own** infrastructure, provider accounts and credentials.

The public repository does not grant access to maintainer Cloudflare, model-provider, GitHub or personal accounts. No maintainer credential is required for normal operation.

## Secure defaults

- Canonical Core binds to loopback by default.
- Production setup uses a one-time first-owner registration token.
- Registration closes after the first owner is created.
- Browser auth uses Secure/HttpOnly/SameSite cookies.
- Remembered devices use random server-side IDs and are revocable.
- Provider secrets stay server-side and are referenced by environment-variable name.
- Secrets are redacted before durable persistence.
- `OLIVIA_HARD_ZERO_COST=1` blocks paid and unverified-cost routes.
- The transitional Cloudflare inference/read bridge is disabled by default.

## Public repository boundary

Do not commit:
- real API keys or bearer tokens;
- real cloud account IDs;
- private provider endpoints;
- personal email/password material;
- runtime SQLite databases;
- production `.env` files.

Forks and deployments must provide their own provider credentials and cloud resources.

## Vulnerability reporting

Use a **private vulnerability report** or GitHub Security Advisory for this repository when available.

Do not publish credentials, exploit tokens or private deployment data in a public issue.
