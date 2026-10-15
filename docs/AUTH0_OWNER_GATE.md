# Owner-only Auth0 authentication gate — provider-neutral (unreleased)

Status: **security code and synthetic tests only**. This does not create an Auth0
tenant/application, configure a login connection, enroll the owner, deploy the
Python Core, or authorize Workers AI. Production owner access and provider
entitlement remain separate release gates.

## Security contract

The Worker verifies only Auth0 RS256-signed **API access tokens** from a pinned
HTTPS `*.auth0.com` issuer. It rejects unsigned/tampered tokens, ID tokens with
the wrong audience, legacy gateway bearer secrets, origin/header assertions,
expired tokens, unknown signing keys and invalid signatures.

The owner predicate is provider-neutral: exact enrolled Auth0 subject, verified
email matching the privately configured owner email, matching session version,
and issuance newer than the revocation floor. The token must be minted by Auth0
after the tenant's configured login connection verifies the account. The Worker
does not require Google-specific claims or a Google identity. Never accept
frontend-supplied owner claims or automatically enroll a new subject.

Every `/api/*` Worker endpoint enforces this identity on the server. On
`/api/demo-chat`, authentication occurs before quota accounting and model
inference. The Cloudflare backend remains static-only; other private API routes
remain unavailable even to the owner (503). `/healthz` is public and omits
owner identity/email fields.

| Input | Worker response | Model/quota calls |
| --- | --- | --- |
| Missing or forged bearer | 401 | 0 |
| Valid signed non-owner | 403 | 0 |
| Owner configuration missing or inference disabled | 503 | 0 |
| Owner plus verified release/cost entitlements | Candidate route; not production-certified | Only after release gates |

Static assets are public and are not private Core data.

## Private Worker configuration

```text
OLIVIA_AUTH0_ISSUER=https://<your-tenant>.<region>.auth0.com/
OLIVIA_AUTH0_AUDIENCE=https://<private-api-audience>
OLIVIA_OWNER_AUTH0_SUB=<privately enrolled stable Auth0 subject>
OLIVIA_OWNER_EMAIL=<owner's verified email>
OLIVIA_OWNER_SESSION_VERSION=<random >=128-bit token generation>
OLIVIA_OWNER_REVOKED_BEFORE=0
```

Keep these values out of Git and frontend JavaScript. Rotate
`OLIVIA_OWNER_SESSION_VERSION` and set `OLIVIA_OWNER_REVOKED_BEFORE` to the
current Unix timestamp to revoke previously minted owner API tokens, then
reissue the owner session. Access tokens must have a lifetime of at most 900
seconds. Frontend logout alone is not immediate cryptographic revocation.

## Login connection

Configure the authorized Auth0 tenant with the owner's intended connection,
such as Auth0's database/email-password connection. Google social login is
optional and is not a requirement of the Worker authorization code. Use
Authorization Code + PKCE, exact HTTPS callback/logout/origin allowlists, and
request an API access token for the configured audience. Do not treat an ID
token, profile object, browser-provided email, or `/userinfo` response as an
API credential.

Enroll the exact Auth0 subject and verified email privately after the owner
authenticates through the approved connection. Never promote a new subject,
linked account or changed email automatically. Test a different account and
confirm it receives 403 with zero model/quota side effects.

## Remaining blockers

- The current frontend uses a legacy email/password form against the Python
  Core; it does not implement an Auth0 browser PKCE flow or pass Auth0 access
  tokens to this Worker. Removing the Google-only claim requirement does not
  itself wire up the frontend login.
- The Python Core's own session/cookie authorization is separate. Do not remove
  that gate or expose private routes without an independently verified owner
  authorization path.
- `COST_GUARD` measures request count, not the Cloudflare account invoice.
  No real Worker inference until account-level no-overage and cost limits are
  independently verified.
- Privileged OCI access, backup/restore, provider canary, exact-SHA deployment
  and production smoke remain pending.

Official references:
- https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce
- https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens
- https://auth0.com/docs/customize/actions/flows-and-triggers/login-flow
