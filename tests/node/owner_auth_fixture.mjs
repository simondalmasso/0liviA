// Test-only Auth0 issuer/JWKS and genuine WebCrypto RS256 JWTs.
// No passwords, API calls, provider inference or real Auth0 account.
import { webcrypto } from "node:crypto";
export const ISSUER = "https://tenant.us.auth0.com/";
export const AUDIENCE = "https://0livia.example/api";
export const OWNER_SUB = "email|owner@example.com";
export const OWNER_EMAIL = "owner@example.com";
export const SESSION_VERSION = "0123456789abcdefghijklmnopqrstuv";
const enc = new TextEncoder();
const b64 = (s) => Buffer.from(s).toString("base64url");
export const authEnvironment = Object.freeze({
  OLIVIA_AUTH0_ISSUER: ISSUER,
  OLIVIA_AUTH0_AUDIENCE: AUDIENCE,
  OLIVIA_OWNER_AUTH0_SUB: OWNER_SUB,
  OLIVIA_OWNER_EMAIL: OWNER_EMAIL,
  OLIVIA_OWNER_SESSION_VERSION: SESSION_VERSION,
  OLIVIA_OWNER_REVOKED_BEFORE: "0",
});
export async function initializeAuthTest() {
  const keys = await webcrypto.subtle.generateKey({
    name: "RSASSA-PKCS1-v1_5", modulusLength: 2048,
    publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256",
  }, true, ["sign", "verify"]);
  const jwk = await webcrypto.subtle.exportKey("jwk", keys.publicKey);
  Object.assign(jwk, { kid: "test-key-1", alg: "RS256", use: "sig" });
  const fetchOriginal = globalThis.fetch;
  globalThis.fetch = (url, options) => {
    if (url === ISSUER + ".well-known/jwks.json") {
      // Match workerd: it only supports "manual" and "follow" for redirect.
      if (options?.redirect !== "manual")
        return Promise.reject(new TypeError('Invalid redirect value; workerd accepts only manual/follow'));
      return Promise.resolve(new Response(JSON.stringify({ keys: [jwk] }),
        { headers: { "content-type": "application/json" } }));
    }
    return fetchOriginal(url, options);
  };
  async function sign(override = {}, headerOverride = {}) {
    const now = Math.floor(Date.now() / 1000);
    const h = b64(JSON.stringify({
      alg: "RS256", typ: "JWT", kid: jwk.kid, ...headerOverride,
    }));
    const p = b64(JSON.stringify({
      iss: ISSUER, aud: AUDIENCE, sub: OWNER_SUB, iat: now, nbf: now-1,
      exp: now + 600, jti: "test-jti-01234567",
      "https://0livia.app/claims/provider": "email",
      "https://0livia.app/claims/email": OWNER_EMAIL,
      "https://0livia.app/claims/email_verified": true,
      "https://0livia.app/claims/session_version": SESSION_VERSION,
      ...override,
    }));
    const sig = await webcrypto.subtle.sign(
      "RSASSA-PKCS1-v1_5", keys.privateKey, enc.encode(h + "." + p)
    );
    return h + "." + p + "." + b64(sig);
  }
  return { sign, token: await sign(), restore: () => { globalThis.fetch = fetchOriginal; } };
}
