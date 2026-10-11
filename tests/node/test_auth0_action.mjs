import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
import { test } from 'node:test';

const require = createRequire(import.meta.url);
const { onExecutePostLogin } = require('../../auth0/actions/owner_google_claims.cjs');
const CLAIM = 'https://0livia.app/claims/';
const SPA_ID = 'PublicSpaClient01234567890';
const SECRET_VERSION = 'PrivateRandomVersion_123456';

function example(overrides = {}) {
  const profile = {
    user_id: 'google-oauth2|12345678901234567890',
    email: 'verified@example.test',
    email_verified: true,
    identities: [{ provider: 'google-oauth2', user_id: '12345678901234567890' }],
  };
  return {
    resource_server: { identifier: 'https://0livia.app/api' },
    connection: { strategy: 'google-oauth2' },
    client: { client_id: SPA_ID },
    secrets: { OLIVIA_AUTH0_SPA_CLIENT_ID: SPA_ID, OLIVIA_OWNER_SESSION_VERSION: SECRET_VERSION },
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
test('verified Google, exact SPA and API: only five namespaced access claims', async () => {
  const got = await claims(example());
  assert.deepEqual(got, [
    [CLAIM + 'provider', 'google-oauth2'],
    [CLAIM + 'google_sub', '12345678901234567890'],
    [CLAIM + 'email', 'verified@example.test'],
    [CLAIM + 'email_verified', true],
    [CLAIM + 'session_version', SECRET_VERSION],
  ]);
});
test('wrong audience never receives claims', async () => {
  assert.deepEqual(await claims(example({resource_server:{identifier:'https://other.example/api'}})), []);
  assert.deepEqual(await claims(example({resource_server:null})), []);
});
test('wrong application never receives claims', async () => {
  assert.deepEqual(await claims(example({client:{client_id:'AttackerApp01234567890'}})), []);
  assert.deepEqual(await claims(example({secrets:{OLIVIA_AUTH0_SPA_CLIENT_ID:'OtherApp01234567890',OLIVIA_OWNER_SESSION_VERSION:SECRET_VERSION}})), []);
});
test('session version or SPA secret missing: refuse all claims', async () => {
  assert.deepEqual(await claims(example({secrets:{OLIVIA_AUTH0_SPA_CLIENT_ID:SPA_ID}})), []);
  assert.deepEqual(await claims(example({secrets:{OLIVIA_OWNER_SESSION_VERSION:SECRET_VERSION}})), []);
  assert.deepEqual(await claims(example({secrets:{OLIVIA_AUTH0_SPA_CLIENT_ID:SPA_ID,OLIVIA_OWNER_SESSION_VERSION:'short'}})), []);
});
test('non-Google connections never receive claims', async () => {
  assert.deepEqual(await claims(example({connection:{strategy:'auth0'}})), []);
});
test('unverified or malformed email never receives claims', async () => {
  for(const u of [{email_verified:false}, {email:'not-an-email'}, {email:null}])
    assert.deepEqual(await claims(example({user:{...example().user,...u}})), []);
});
test('linked-account or forged Google IDs do not mint identity claims', async () => {
  for (const user of [
    {...example().user,user_id:'auth0|primary'},
    {...example().user,identities:[{provider:'google-oauth2',user_id:'bad_user'}]},
    {...example().user,identities:[{provider:'facebook',user_id:'12345678901234567890'}]},
    {...example().user,identities:[]},
  ]) assert.deepEqual(await claims(example({user})), []);
});
test('no event, no mutation', async () => {
  assert.deepEqual(await claims(null), []);
});
