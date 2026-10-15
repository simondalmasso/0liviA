// Auth0 Post-Login Action: configure the email passwordless connection first.
// Claims are minted only for the exact verified owner email, API audience and SPA.
// Never log identity or token data; no external service calls occur here.
'use strict';

const CLAIM = 'https://0livia.app/claims/';
const AUDIENCE_RE = /^https:\/\/[A-Za-z0-9.-]+\/[A-Za-z0-9._/-]+$/;
const VERSION_RE = /^[A-Za-z0-9_-]{16,128}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SPA_ID_RE = /^[A-Za-z0-9_-]{10,128}$/;

exports.onExecutePostLogin = async (event, api) => {
  const expectedAudience = event?.secrets?.OLIVIA_AUTH0_AUDIENCE;
  if (!event || !api?.accessToken?.setCustomClaim ||
      typeof expectedAudience !== 'string' || expectedAudience.length > 512 ||
      !AUDIENCE_RE.test(expectedAudience) ||
      event.resource_server?.identifier !== expectedAudience ||
      event.connection?.strategy !== 'email') return;

  const expectedSpa = event.secrets?.OLIVIA_AUTH0_SPA_CLIENT_ID;
  const sessionVersion = event.secrets?.OLIVIA_OWNER_SESSION_VERSION;
  const ownerEmail = event.secrets?.OLIVIA_OWNER_EMAIL;
  if (typeof expectedSpa !== 'string' || !SPA_ID_RE.test(expectedSpa) ||
      event.client?.client_id !== expectedSpa ||
      typeof sessionVersion !== 'string' || !VERSION_RE.test(sessionVersion) ||
      typeof ownerEmail !== 'string' || ownerEmail.length > 254 ||
      !EMAIL_RE.test(ownerEmail)) return;

  const user = event.user;
  if (user?.email_verified !== true || typeof user.email !== 'string' ||
      !EMAIL_RE.test(user.email) || user.email.length > 254 ||
      user.email.toLowerCase() !== ownerEmail.toLowerCase()) return;

  const set = (name, value) => api.accessToken.setCustomClaim(CLAIM + name, value);
  set('provider', 'email');
  set('email', user.email);
  set('email_verified', true);
  set('session_version', sessionVersion);
};
