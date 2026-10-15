# Owner-only Auth0 passwordless email authentication gate — P0 (unreleased)

Status: **passwordless email flow is implemented in source, but Auth0 tenant configuration, owner enrollment, deployment and production chat are NOT RELEASED**. This document does **not** enroll an owner,
activate the reviewed Action, publish the Worker/Core or authorize Workers AI. It is
**impossible to declare a live owner chat** before separate login, provider
entitlement, no-overage and direct HTTP negative tests in the deployed account.

## Security contract

The Worker verifies **only** Auth0 RS256-signed **API access tokens**. It
downloads JWKS from an exact, pinned HTTPS `*.auth0.com` issuer; it rejects
unsigned tokens, ID tokens (wrong audience), bearer tokens from the old
gateway, origin/header assertions, expired tokens, unknown signing keys and
invalid signatures. The same signed token must have exact configured API
audience, email passwordless provider, verified owner email, enrolled
Auth0 subject, unrevoked issuance epoch, and session generation. Only that
combination passes `requireOwnerInference`. Claims are cryptographically
signed **by Auth0** and must be minted by a privileged, reviewed Auth0 Action
from the passwordless email connection. Never accept frontend-supplied claims.

Every `/api/*` Worker endpoint now enforces that identity on the server.
On `/api/demo-chat` this check occurs before `COST_GUARD` and `AI.run`.
The currently published Worker remains **static-only**; the unreleased PR contains a separate manually gated dynamic path. Other
`/api/*` routes remain unavailable even to the owner: 503.
`/healthz` remains public without identity/email fields.

| Input | Worker response | Workers AI/quota calls |
| --- | --- | --- |
| Missing/forged bearer | 401 | 0 |
| Valid signed non-owner | 403 | 0 |
| Owner with unset Auth0 entitlement or demo disabled | 503 | 0 |
| Owner plus verified entitlements / limits | Candidate route; not yet production-certified | Only after release gates |

Static assets **are public** and use Cloudflare Worker requests, even though
they cannot access Core or Workers AI.

## Privately configured Cloudflare Worker values

```text
OLIVIA_AUTH0_ISSUER=https://<your-tenant>.<region>.auth0.com/
OLIVIA_AUTH0_AUDIENCE=https://<private-api-audience>
OLIVIA_OWNER_AUTH0_SUB=<enrolled-stable-Auth0-sub>
OLIVIA_OWNER_EMAIL=<owner's verified email>
OLIVIA_OWNER_SESSION_VERSION=<random >=128-bit token generation>
OLIVIA_OWNER_REVOKED_BEFORE=0
```

Treat the owner identifiers as *private configuration*, not files in GitHub
or JavaScript. Rotate SESSION_VERSION and set REVOKED_BEFORE to the current
Unix timestamp to revoke previously minted owner API tokens, and reissue
a new owner session. JWTs must have at most **900 seconds** of lifetime
(Auth0 API access-token settings). A normal frontend logout **alone** is not
instant cryptographic revocation of an already issued bearer token; a private
revocation control needs to rotate the trusted generation and/or issue-time
floor. This policy is a release blocker for real login/logout acceptance.

## Auth0 configuration steps requiring the authorized tenant administrator

1. Use **Auth0 Free** only after verifying the actual tenant entitlement.
   Create a **Single Page Application**, register exact HTTPS callback,
   logout and allowed origins, use Authorization Code + PKCE S256 and
   `state`, `nonce` and `openid profile email` scopes. Use hosted Auth0
   tenant domain; do not buy a custom domain.
2. Create an **API audience** with RS256 access tokens of lifetime <=900s.
   The SPA must explicitly request that audience; an Auth0 ID token, profile
   object, or `/userinfo` email is NOT an API credential.
3. Enable passwordless email identity. Under a reviewed **Post Login Action**,
   after verifying `event.connection.strategy === 'email'` and
   `event.user.email_verified === true`, read the *active* email identity
   and add the following custom **access token claims** from the Auth0 event
   and Action private secret. Do **not** derive them from `event.request`,
   client metadata, query parameters, URL fragments or frontend headers.

### Exact API audience: Action secret and Worker configuration must match

Configure an Auth0 Post-Login Action secret named `OLIVIA_AUTH0_AUDIENCE`.
The Worker reads `env.OLIVIA_AUTH0_AUDIENCE` in `cloudflare/owner_auth.mjs`;
the Action reads `event.secrets.OLIVIA_AUTH0_AUDIENCE`. Set both independently
to the same byte-for-byte value, and make that value equal the identifier of
the Auth0 API resource server. The Action fails closed if its secret is missing,
malformed, or different from `event.resource_server.identifier`; the Worker
independently validates access-token `aud` against its own configured value.
There is no hard-coded audience or fallback. Do not put private owner identifiers
or configuration values into source control.

**Single source of truth:** `auth0/actions/owner_google_claims.cjs` in PR #114; its login strategy is passwordless email, not Google.
Copy **that entire reviewed file**, not older snippets or examples, into the Auth0
Post-Login Action editor. The canonical Action additionally requires the
configured `OLIVIA_AUTH0_AUDIENCE` secret, which must exactly match the
Worker configuration and Auth0 API identifier, the configured SPA Client ID,
the exact verified owner email, and a private session
generation. Its tests are `tests/node/test_auth0_action.mjs`, executed in
`.github/workflows/ci.yml`. The Action must not be deployed or added to
the Post Login flow before its private secrets are correctly provisioned
and the owner-only release gates are satisfied. Offline tests are **not**
evidence that an Auth0 Action is installed, deployed or connected to a flow.

4. Enroll Auth0 `sub` and the real email identity `sub` **privately**
   after authenticating the owner through the configured connection; never
   automatically promote a new `sub`, newly linked account or changed email.
   Test a separate different verified email account: successful login **must** give
   403 on private APIs.
5. Preserve static/no-inference deployment until direct HTTP tests pass with
   a legitimate owner and a non-owner, tampered/revoked JWTs, websocket/SSE,
   direct Core routes, and hard-zero-cost model entitlement. Rotating only
   this Worker gate does **not** protect Python Core if Core is exposed by
   a different hostname; `requireOwnerCore` must be shipped independently.

## Remaining blockers

- This branch contains the browser PKCE bridge and owner-only passwordless email controls,
  tested offline with mocks. This does **not** validate production SPA login,
  mobile behavior, token lifecycle or real owner access until deployment and
  end-to-end authenticated testing.
- Canonical Python Core still uses a legacy bearer/cookie; its private routes,
  jobs, streaming and websocket upgrade need a separately proven
  `requireOwnerCore` bridge. Keep OCI Core isolated and not publicly routed
  until that gate exists.
- `COST_GUARD` measures request count, **not** Cloudflare account neurons.
  Its existence never proves a hard invoice cap. No real Worker AI inference
  until the account-specific Free/no-overage guarantee and conservative
  shared-neuron budget are independently proven.
- Core OCI privileged access, encrypted backup/restore, provider live canary
  and published-SHA smoke remain pending.

Official references:
- https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce
- https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens
- https://auth0.com/docs/authenticate/identity-providers/social-identity-providers/google
- https://auth0.com/docs/customize/actions/flows-and-triggers/login-flow
