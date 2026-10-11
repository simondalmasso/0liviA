// Auth0-issued, RS256-signed API access tokens only. Never accept ID tokens,
// client-supplied roles, Origin, email headers, or legacy gateway bearer secrets.
// Zero provider/cost-guard calls occur until the complete owner predicate holds.
const CLAIM = "https://0livia.app/claims/";
const JWKS_CACHE_MS = 120_000;
const MAX_TOKEN_AGE_S = 900;
const keyCache = new Map();
const enc = new TextEncoder();
const dec = new TextDecoder("utf-8", { fatal: true });

function base64urlBytes(s) {
  if (typeof s !== "string" || !/^[A-Za-z0-9_-]+$/.test(s) || s.length > 16_384) {
    throw new Error("bad_base64url");
  }
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64 + "=".repeat((4 - b64.length % 4) % 4));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

function decodePart(text) {
  const decoded = dec.decode(base64urlBytes(text));
  return JSON.parse(decoded);
}

function issuerOf(env) {
  const raw = env?.OLIVIA_AUTH0_ISSUER;
  if (typeof raw !== "string" || raw.length > 160) return null;
  let u;
  try { u = new URL(raw); } catch { return null; }
  // Default Auth0-hosted tenant only. No custom-domain, localhost, ports,
  // userinfo, redirect, arbitrary URL, query or origin override.
  if (u.protocol !== "https:" || !u.hostname.endsWith(".auth0.com") ||
      !u.hostname.includes(".") || u.username || u.password || u.port ||
      u.pathname !== "/" || u.search || u.hash || raw !== u.origin + "/") return null;
  return u.origin + "/";
}

export function ownerAuthConfigured(env) {
  return Boolean(issuerOf(env) &&
    typeof env?.OLIVIA_AUTH0_AUDIENCE === "string" &&
    /^https:\/\/[A-Za-z0-9.-]+\/[A-Za-z0-9._/-]+$/.test(env.OLIVIA_AUTH0_AUDIENCE) &&
    typeof env?.OLIVIA_OWNER_AUTH0_SUB === "string" && env.OLIVIA_OWNER_AUTH0_SUB.length > 5 &&
    typeof env?.OLIVIA_OWNER_GOOGLE_SUB === "string" && /^[0-9]{8,32}$/.test(env.OLIVIA_OWNER_GOOGLE_SUB) &&
    typeof env?.OLIVIA_OWNER_GOOGLE_EMAIL === "string" &&
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(env.OLIVIA_OWNER_GOOGLE_EMAIL) &&
    typeof env?.OLIVIA_OWNER_SESSION_VERSION === "string" &&
    /^[A-Za-z0-9_-]{16,128}$/.test(env.OLIVIA_OWNER_SESSION_VERSION) &&
    typeof env?.OLIVIA_OWNER_REVOKED_BEFORE === "string" &&
    /^(0|[1-9][0-9]{0,11})$/.test(env.OLIVIA_OWNER_REVOKED_BEFORE));
}

async function trustedKeys(issuer, force = false) {
  const url = issuer + ".well-known/jwks.json";
  const now = Date.now();
  if (!force && keyCache.has(url) && keyCache.get(url).expires > now) {
    return keyCache.get(url).value;
  }
  // One shared cache entry for concurrent requests. Failed fetches are never
  // cached as trust, and an unknown kid triggers one fresh JWKS request.
  const pending = (async () => {
    const response = await fetch(url, { method: "GET", redirect: "error",
      signal: AbortSignal.timeout(5000), headers: { accept: "application/json" } });
    if (!response.ok) throw new Error("jwks_unavailable");
    const text = await response.text();
    if (text.length > 32_768) throw new Error("jwks_oversize");
    const result = JSON.parse(text);
    if (!Array.isArray(result?.keys) || result.keys.length > 16) throw new Error("bad_jwks");
    return result.keys.filter((key) =>
      key?.kty === "RSA" && key?.use === "sig" &&
      key?.alg === "RS256" && /^[A-Za-z0-9_-]{1,128}$/.test(key?.kid || "") &&
      key?.e === "AQAB" && typeof key?.n === "string" && key.n.length > 200);
  })();
  keyCache.set(url, { expires: now + JWKS_CACHE_MS, value: pending });
  try { return await pending; } catch (e) { keyCache.delete(url); throw e; }
}

async function claimsFromRequest(request, env) {
  const match = /^Bearer ([A-Za-z0-9._-]{1,8192})$/.exec(request.headers.get("Authorization") || "");
  if (!match) return null;
  const raw = match[1], pieces = raw.split(".");
  if (pieces.length !== 3 || pieces.some((p) => !p)) return null;
  let header, claims;
  try {
    header = decodePart(pieces[0]);
    claims = decodePart(pieces[1]);
  } catch { return null; }
  if (!header || typeof header !== "object" || Array.isArray(header) ||
      header.alg !== "RS256" || header.typ !== "JWT" ||
      typeof header.kid !== "string" || !/^[A-Za-z0-9_-]{1,128}$/.test(header.kid) ||
      header.jku !== undefined || header.jwk !== undefined ||
      header.x5u !== undefined || header.crit !== undefined) return null;
  const issuer = issuerOf(env);
  if (!issuer || !claims || typeof claims !== "object" || Array.isArray(claims)) return null;
  const now = Math.floor(Date.now() / 1000);
  if (claims.iss !== issuer || claims.aud !== env.OLIVIA_AUTH0_AUDIENCE ||
      typeof claims.sub !== "string" || claims.sub.length > 256 ||
      !Number.isSafeInteger(claims.exp) || !Number.isSafeInteger(claims.iat) ||
      !Number.isSafeInteger(claims.nbf) ||
      claims.iat > now + 30 || claims.nbf > now ||
      claims.exp <= now || claims.exp <= claims.iat ||
      claims.exp - claims.iat > MAX_TOKEN_AGE_S ||
      typeof claims.jti !== "string" || claims.jti.length < 8 || claims.jti.length > 256 ||
      !/^[A-Za-z0-9_-]+$/.test(claims.jti)) return null;
  const payload = enc.encode(pieces[0] + "." + pieces[1]);
  try {
    const sig = base64urlBytes(pieces[2]);
    let keys = await trustedKeys(issuer);
    let jwk = keys.find((key) => key.kid === header.kid);
    if (!jwk) {
      keys = await trustedKeys(issuer, true);
      jwk = keys.find((key) => key.kid === header.kid);
    }
    if (!jwk) return null;
    const key = await crypto.subtle.importKey("jwk", jwk,
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    const valid = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, sig, payload);
    return valid ? claims : null;
  } catch { return null; }
}

export async function requireOwnerInference(request, env) {
  if (!/^Bearer [A-Za-z0-9._-]{1,8192}$/.test(request.headers.get("Authorization") || "")) {
    return { ok: false, status: 401, error: "invalid_access_token" };
  }
  if (!ownerAuthConfigured(env)) {
    // Never fall back to a legacy token or guessed user identity.
    return { ok: false, status: 503, error: "owner_identity_unconfigured" };
  }
  const claims = await claimsFromRequest(request, env);
  if (!claims) return { ok: false, status: 401, error: "invalid_access_token" };
  const owner = (
    claims.sub === env.OLIVIA_OWNER_AUTH0_SUB &&
    claims[CLAIM + "provider"] === "google-oauth2" &&
    claims[CLAIM + "google_sub"] === env.OLIVIA_OWNER_GOOGLE_SUB &&
    claims[CLAIM + "email_verified"] === true &&
    typeof claims[CLAIM + "email"] === "string" &&
    claims[CLAIM + "email"].toLowerCase() === env.OLIVIA_OWNER_GOOGLE_EMAIL.toLowerCase() &&
    claims[CLAIM + "session_version"] === env.OLIVIA_OWNER_SESSION_VERSION &&
    claims.iat > Number(env.OLIVIA_OWNER_REVOKED_BEFORE)
  );
  return owner ? { ok: true } : { ok: false, status: 403, error: "owner_only" };
}
