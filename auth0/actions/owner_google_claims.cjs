// Auth0 Post-Login Action: paste into the Auth0 action editor only after
// configuring secrets and approving activation. Do not log user or token data.
// No calls to Workers AI, external services, or payment APIs.
'use strict';

const CLAIM = 'https://0livia.app/claims/';
const API_AUDIENCE = 'https://0livia.app/api';
const VERSION_RE = /^[A-Za-z0-9_-]{16,128}$/;
const GOOGLE_ID_RE = /^[0-9]{8,32}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SPA_ID_RE = /^[A-Za-z0-9_-]{10,128}$/;

exports.onExecutePostLogin = async (event, api) => {
  // Auth0's signed API access token, never the ID token or a request header.
  if (!event || !api?.accessToken?.setCustomClaim ||
      event.resource_server?.identifier !== API_AUDIENCE ||
      event.connection?.strategy !== 'google-oauth2') return;

  // Bind issuance to the exact preconfigured SPA, not an arbitrary Auth0 client.
  const expectedSpa = event.secrets?.OLIVIA_AUTH0_SPA_CLIENT_ID;
  const sessionVersion = event.secrets?.OLIVIA_OWNER_SESSION_VERSION;
  if (typeof expectedSpa !== 'string' || !SPA_ID_RE.test(expectedSpa) ||
      event.client?.client_id !== expectedSpa ||
      typeof sessionVersion !== 'string' || !VERSION_RE.test(sessionVersion)) return;

  const user = event.user;
  const googleIdentity = Array.isArray(user?.identities)
    ? user.identities.find(i => i?.provider === 'google-oauth2' &&
      typeof i.user_id === 'string' && GOOGLE_ID_RE.test(i.user_id))
    : null;
  if (!googleIdentity || user.user_id !== `google-oauth2|${googleIdentity.user_id}` ||
      user.email_verified !== true || typeof user.email !== 'string' ||
      !EMAIL_RE.test(user.email) || user.email.length > 254) return;

  // These attest to verified Google identity, not to owner privileges. The
  // Worker verifies all claims against separately enrolled private owner IDs.
  const set = (name, value) => api.accessToken.setCustomClaim(CLAIM + name, value);
  set('provider', 'google-oauth2');
  set('google_sub', googleIdentity.user_id);
  set('email', user.email);
  set('email_verified', true);
  set('session_version', sessionVersion);
};
