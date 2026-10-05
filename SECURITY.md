# Security policy

0liviA is designed as a self-hosted, single-owner-per-installation AI workspace. Security boundaries are part of the product contract, not optional setup advice.

## Supported security model

A production installation should have:

- a unique `OLIVIA_GATEWAY_TOKEN`;
- a unique `OLIVIA_REGISTRATION_TOKEN` for first-owner setup;
- HTTPS in front of the Python Core;
- port 8080 bound to loopback/private networking only;
- provider/API credentials stored server-side, never in the browser UI;
- runtime SQLite state outside the Git checkout;
- `OLIVIA_HARD_ZERO_COST=1` unless the operator explicitly accepts paid routes;
- the transitional Cloudflare inference bridge disabled unless separately audited.

Each deployment is isolated. The public repository does not provide access to the maintainer's Cloudflare account, GitHub credentials, provider accounts or runtime data.

## Reporting a vulnerability

Do **not** publish live secrets, private URLs, exploit payloads against a private deployment, or personal data in a public issue.

Use GitHub private vulnerability reporting when it is available for this repository. If private vulnerability reporting is not available, open a minimal public issue that contains no sensitive exploit details and asks for a private contact channel.

A useful private vulnerability report includes:

- affected commit/version;
- affected file/endpoint;
- impact;
- minimal reproduction;
- whether authentication is required;
- whether data exfiltration, SSRF, code execution or billing risk is involved;
- suggested remediation if known.

## Secrets

Never commit:

- provider API keys;
- Cloudflare account/API tokens;
- GitHub tokens;
- registration/setup tokens;
- gateway signing tokens;
- runtime SQLite databases;
- cookies/session values;
- private user content.

The codebase applies secret redaction at API/agent boundaries and again at the durable SQLite boundary. That is defense in depth, not permission to store secrets in prompts or memory.

## Public-fork safety

Public forks do not inherit GitHub Actions secrets from this repository.

The coding worker is disabled by default and must be configured with the operator's own repository and token. The Cloudflare bridge is disabled by default for inference/read operations.

## Scope

This policy covers the 0liviA source code and reference deployment material. It does not certify the security, privacy, pricing or availability of third-party model providers, DNS services, cloud hosts or browser APIs.
