import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
import { test } from 'node:test';

const require = createRequire(import.meta.url);
const { onExecutePostLogin } = require('../../auth0/actions/owner_google_claims.cjs');
const CLAIM = 'https://0livia.app/claims/';
const SPA_ID = 'PublicSpaClient01234567890';
const SECRET_VERSION = 'PrivateRandomVersion_123456';
const CONFIGURED_AUDIENCE = 'https://api.example.test/olivia';
const OWNER_EMAIL = 'verified@example.test';

function example(overrides = {}) {
  const profile = {
    user_id: 'email|verified@example.test',
    email: OWNER_EMAIL,
    email_verified: true,
    identities: [{ provider: 'email', user_id: 'verified@example.test', isSocial: false }],
  };
  return {
    resource_server: { identifier: CONFIGURED_AUDIENCE },
    connection: { strategy: 'email' },
    client: { client_id: SPA_ID },
    secrets: { OLIVIA_AUTH0_AUDIENCE: CONFIGURED_AUDIENCE, OLIVIA_AUTH0_SPA_CLIENT_ID: SPA_ID, OLIVIA_OWNER_SESSION_VERSION: SECRET_VERSION, OLIVIA_OWNER_EMAIL: OWNER_EMAIL },
    user: profile,
    ...overrides,
  };
}
async function claims(event) {
  const list = [];
  await onExecutePostLogin(event, {
    accessToken: { setCustomClaim: (key, value) => list.push([key, value]) },
    idToken: { setCustomClaim: () => { throw Error('ID token must not receive claims'); } },
  });
  return list;
}
test('verified owner email connection, configured audience and exact SPA: only four namespaced access claims', async () => {
  const got = await claims(example());
  assert.deepEqual(got, [
    [CLAIM + 'provider', 'email'],
    [CLAIM + 'email', OWNER_EMAIL],
    [CLAIM + 'email_verified', true],
    [CLAIM + 'session_version', SECRET_VERSION],
  ]);
});
test('Action accepts a custom audience only when its secret and Auth0 API match exactly', async () => {
  const customAudience = 'https://api.custom.example.test/v3';
  const baseSecrets = example().secrets;
  const matching = example({
    resource_server: { identifier: customAudience },
    secrets: { ...baseSecrets, OLIVIA_AUTH0_AUDIENCE: customAudience },
  });
  assert.equal((await claims(matching)).length, 4);
  assert.deepEqual(await claims(example({
    resource_server: { identifier: customAudience },
  })), []);
  assert.deepEqual(await claims(example({
    secrets: { ...baseSecrets, OLIVIA_AUTH0_AUDIENCE: customAudience },
  })), []);
});
test('wrong, missing or malformed audience configuration never receives claims', async () => {
  assert.deepEqual(await claims(example({
    resource_server: { identifier: 'https://other.example/api' },
  })), []);
  assert.deepEqual(await claims(example({ resource_server: null })), []);
  const missing = { ...example().secrets };
  delete missing.OLIVIA_AUTH0_AUDIENCE;
  assert.deepEqual(await claims(example({ secrets: missing })), []);
  for (const audience of [
    '',
    ' https://api.example.test/olivia',
    'https://api.example.test/olivia ',
    'https://api.example.test/olivia?x=1',
    'x'.repeat(513),
  ]) {
    assert.deepEqual(await claims(example({
      secrets: { ...example().secrets, OLIVIA_AUTH0_AUDIENCE: audience },
    })), []);
  }
});
test('wrong application never receives claims', async () => {
  assert.deepEqual(await claims(example({client:{client_id:'AttackerApp01234567890'}})), []);
  assert.deepEqual(await claims(example({secrets:{OLIVIA_AUTH0_AUDIENCE:CONFIGURED_AUDIENCE,OLIVIA_AUTH0_SPA_CLIENT_ID:'OtherApp01234567890',OLIVIA_OWNER_SESSION_VERSION:SECRET_VERSION,OLIVIA_OWNER_EMAIL:OWNER_EMAIL}})), []);
});
test('session version, SPA secret, or owner email secret missing: refuse all claims', async () => {
  assert.deepEqual(await claims(example({secrets:{OLIVIA_AUTH0_AUDIENCE:CONFIGURED_AUDIENCE,OLIVIA_AUTH0_SPA_CLIENT_ID:SPA_ID,OLIVIA_OWNER_EMAIL:OWNER_EMAIL}})), []);
  assert.deepEqual(await claims(example({secrets:{OLIVIA_AUTH0_AUDIENCE:CONFIGURED_AUDIENCE,OLIVIA_OWNER_SESSION_VERSION:SECRET_VERSION,OLIVIA_OWNER_EMAIL:OWNER_EMAIL}})), []);
  assert.deepEqual(await claims(example({secrets:{OLIVIA_AUTH0_AUDIENCE:CONFIGURED_AUDIENCE,OLIVIA_AUTH0_SPA_CLIENT_ID:SPA_ID,OLIVIA_OWNER_SESSION_VERSION:'short',OLIVIA_OWNER_EMAIL:OWNER_EMAIL}})), []);
  assert.deepEqual(await claims(example({secrets:{OLIVIA_AUTH0_AUDIENCE:CONFIGURED_AUDIENCE,OLIVIA_AUTH0_SPA_CLIENT_ID:SPA_ID,OLIVIA_OWNER_SESSION_VERSION:SECRET_VERSION}})), []);
});
test('Google, database-password and every non-email connection are refused', async () => {
  for (const strategy of ['google-oauth2', 'auth0', 'sms', 'github']) {
    assert.deepEqual(await claims(example({connection:{strategy}})), []);
  }
});
test('unverified, mismatched or malformed email never receives claims', async () => {
  for (const user of [
    {...example().user,email_verified:false},
    {...example().user,email:'other@example.test'},
    {...example().user,email:'not-an-email'},
    {...example().user,email:null},
  ]) assert.deepEqual(await claims(example({user})), []);
});
test('no event, no mutation', async () => {
  assert.deepEqual(await claims(null), []);
});
