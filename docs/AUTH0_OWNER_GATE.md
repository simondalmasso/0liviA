# Owner-only Auth0 Google authentication gate — P0 (unreleased)

Status: **security code and synthetic tests only**. This does **not** create
an Auth0 account, Google connection, owner enrollment, Auth0 tenant app,
production Core deployment, or permission to enable Workers AI. It is
**impossible to declare a live owner chat** before separate login, provider
entitlement, no-overage and direct HTTP negative tests in the deployed account.

## Security contract

The Worker verifies **only** Auth0 RS256-signed **API access tokens**. It
downloads JWKS from an exact, pinned HTTPS `*.auth0.com` issuer; it rejects
unsigned tokens, ID tokens (wrong audience), bearer tokens from the old
gateway, origin/header assertions, expired tokens, unknown signing keys and
invalid signatures. The same signed token must have exact configured API
audience, Google provider, verified email, enrolled Google subject, enrolled
Auth0 subject, unrevoked issuance epoch, and session generation. Only that
combination passes `requireOwnerInference`. Claims are cryptographically
signed **by Auth0** and must be minted by a privileged, reviewed Auth0 Action
from the Google identity provider. Never accept frontend-supplied claims.

Every `/api/*` Worker endpoint now enforces that identity on the server.
On `/api/demo-chat` this check occurs before `COST_GUARD` and `AI.run`.
The backend remains **static-only** in Cloudflare deployments. Other
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
OLIVIA_OWNER_GOOGLE_SUB=<enrolled-stable-numeric-Google-user-id>
OLIVIA_OWNER_GOOGLE_EMAIL=<owner's verified Google email>
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
3. Enable Google social identity. Under a reviewed **Post Login Action**,
   after verifying `event.connection.strategy === 'google-oauth2'` and
   `event.user.email_verified === true`, read the *active* Google identity
   and add the following custom **access token claims** from the Auth0 event
   and Action private secret. Do **not** derive them from `event.request`,
   client metadata, query parameters, URL fragments or frontend headers.

```js
exports.onExecutePostLogin = async (event, api) => {
  if (event.connection?.strategy !== "google-oauth2" ||
      event.user?.email_verified !== true) return;
  const identity = (event.user.identities || []).find(
    (i) => i.provider === "google-oauth2"
  );
  const googleId = String(identity?.user_id || "");
  if (!/^\d{8,32}$/.test(googleId) ||
      !event.secrets?.OLIVIA_OWNER_SESSION_VERSION) return;

  const ns = "https://0livia.app/claims/";
  api.accessToken.setCustomClaim(ns + "provider", "google-oauth2");
  api.accessToken.setCustomClaim(ns + "google_sub", googleId);
  api.accessToken.setCustomClaim(ns + "email", String(event.user.email || ""));
  api.accessToken.setCustomClaim(ns + "email_verified", true);
  api.accessToken.setCustomClaim(
    ns + "session_version", event.secrets.OLIVIA_OWNER_SESSION_VERSION
  );
};
```

4. Enroll Auth0 `sub` and the real Google identity `sub` **privately**
   after authenticating the owner through the configured connection; never
   automatically promote a new `sub`, newly linked account or changed email.
   Test a separate real Google guest account: successful login **must** give
   403 on private APIs.
5. Preserve static/no-inference deployment until direct HTTP tests pass with
   a legitimate owner and a non-owner, tampered/revoked JWTs, websocket/SSE,
   direct Core routes, and hard-zero-cost model entitlement. Rotating only
   this Worker gate does **not** protect Python Core if Core is exposed by
   a different hostname; `requireOwnerCore` must be shipped independently.

## Remaining blockers

- The frontend currently has a legacy owner password form. Real Auth0 login,
  mobile PKCE flow, guest-only local profile, personalized greeting,
  token-lifecycle handling and user experience are **not implemented** here.
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
