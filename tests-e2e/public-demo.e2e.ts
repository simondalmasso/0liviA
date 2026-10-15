import { test } from '@e2e-dev/web';
import { expect } from 'e2e';
import { createHash } from 'node:crypto';

// This is a browser contract test, NEVER a model inference or cost attestation.
// Real owner E2E requires a separately approved Auth0 session and Free account check.
const mockDemo = process.env.OLIVIA_E2E_MOCK_DEMO === '1';

test('anonymous cannot spend owner inference even if backend reports demo ready', async ({ app, screen, browser }) => {
  await app.clearState();
  if (mockDemo) {
    await browser.route('**/healthz*', route => route.fulfill({json:{
      process_alive:true,api_mode:'public_shell',public_shell:true,
      bridge_enabled:false,provider_ready:false,inference_enabled:false,
      demo_inference_enabled:true,demo_provider_ready:true,
      demo_provider:'workers-ai-demo',demo_model:'@cf/zai-org/glm-4.7-flash',
      demo_daily_request_limit:25,web_read:false,hard_zero_cost:false,
      demo_cost_guaranteed:false,canonical_backend:'self_hosted_python_core'
    }}));
    await browser.route('**/api/auth/public-config*', route => route.fulfill({
      json:{enabled:false}
    }));
  }
  // This explicit route would expose any unexpected outbound model request.
  let unauthorizedInferenceCalls = 0;
  await browser.route('**/api/demo-chat*', route => {
    unauthorizedInferenceCalls++;
    return route.fulfill({status:403,json:{error:'unexpected_anonymous_inference'}});
  });

  await app.open('/');
  await expect(browser.locator('#publicDemoBtn')).toHaveCount(0);
  await expect(browser.locator('#publicLoginBtn')).toHaveCount(0);
  await expect(browser.locator('#modeChat')).toHaveCount(0);
  await expect(browser.locator('#modeWork')).toHaveCount(0);
  const message = screen.getByRole('textbox', {name:'Mensaje'});
  await expect(message).toBeEnabled();
  await message.fill('Esto no debe activar inferencia sin email propietario autorizado');
  await expect(screen.getByRole('button', {name:'Enviar'})).toBeDisabled();
  await expect(browser.locator('#messages .msg.assistant:not(.error)')).toHaveCount(0);
  await expect(browser.locator('#messages .provider-pill')).toHaveCount(0);
  if (unauthorizedInferenceCalls !== 0) throw new Error('Unauthorized browser inference call');
});

if (mockDemo) {

  test('Passwordless email owner login entry is reachable without enabling anonymous chat', async ({app,browser,screen}) => {
    await app.clearState();
    await browser.route('**/healthz*', route => route.fulfill({json:{
      process_alive:true,api_mode:'public_shell',public_shell:true,
      demo_provider_ready:true,demo_inference_enabled:true,provider_ready:false,
      demo_provider:'workers-ai-demo',demo_model:'@cf/zai-org/glm-4.7-flash'
    }}));
    await browser.route('**/api/auth/public-config*', route => route.fulfill({json:{
      enabled:true,issuer:'https://tenant.us.auth0.com/',
      audience:'https://0livia.example/api',client_id:'publicClient012345678901'
    }}));
    let attempted = 0;
    await browser.route('**/api/demo-chat*', route => {
      attempted++;
      return route.fulfill({status:403,json:{error:'unexpected_anonymous_inference'}});
    });
    await app.open('/');
    await expect(screen.getByRole('button',{name:'Enviar'})).toBeDisabled();
    // Owner-only passwordless-email gate is shown automatically on unauthenticated load.
    await expect(browser.locator('#ownerLogin.open')).toBeVisible();
    await expect(browser.locator('#oliviaEmailLogin')).toBeVisible();
    await expect(browser.locator('#oliviaEmailLogin')).toBeEnabled();
    await expect(screen.getByRole('button',{name:'Enviar'})).toBeDisabled();
    if (attempted !== 0) throw new Error('Anonymous login attempted model inference');
  });

  test('guest cannot unlock private demo via visible login placeholder', async ({app,screen,browser}) => {
    await app.clearState();
    await browser.route('**/healthz*', route => route.fulfill({json:{
      process_alive:true,api_mode:'public_shell',provider_ready:false,
      demo_provider_ready:true,demo_inference_enabled:true,bridge_enabled:false
    }}));
    await browser.route('**/api/auth/public-config*', route => route.fulfill({
      json:{enabled:false}
    }));
    await app.open('/');
    await expect(browser.locator('#ownerLogin.open')).toBeVisible();
    await expect(browser.locator('#oliviaEmailLogin')).not.toBeVisible();
    await expect(browser.locator('#messages .msg.assistant:not(.error)')).toHaveCount(0);
    await expect(screen.getByRole('button',{name:'Enviar'})).toBeDisabled();
    await expect(browser.locator('.app')).toHaveCount(1);
  });

  test('reload preserves public landing but does not grant owner privileges', async ({app,browser,screen}) => {
    await app.clearState();
    await browser.route('**/healthz*', route => route.fulfill({json:{
      process_alive:true,api_mode:'public_shell',provider_ready:false,
      demo_provider_ready:true,demo_inference_enabled:true,bridge_enabled:false
    }}));
    await browser.route('**/api/auth/public-config*', route => route.fulfill({
      json:{enabled:false}
    }));
    await app.open('/');
    await expect(screen.getByRole('button',{name:'Enviar'})).toBeDisabled();
    await app.open('/');
    await expect(browser.locator('.landing-mark')).toHaveCount(1);
    await expect(browser.locator('.landing-greeting')).toContainText('Hola, ¿en qué puedo ayudarte?');
    await expect(browser.locator('.app.is-landing')).toHaveCount(1);
    await expect(screen.getByRole('button',{name:'Enviar'})).toBeDisabled();
  });

  test('owner passwordless-email PKCE callback enables one mocked GLM reply without paid or external AI', async ({app,screen,browser}) => {
    // Deterministic browser integration: NO Auth0 credentials, AI.run, or model providers.
    await app.clearState();
    const base = (process.env.OLIVIA_E2E_URL || 'http://127.0.0.1:8767').replace(/\/$/, '');
    const fakeAccessToken = 'offline_owner_access_token_no_live_credentials_123456789';
    const expectedAnswer = 'Respuesta GLM simulada y autorizada.';
    let state = '', nonce = '', pkceChallenge = '', tokenExchanges = 0, ownerChecks = 0, demoPosts = 0;

    await browser.route('**/healthz*', route => route.fulfill({json:{
      process_alive:true,api_mode:'public_shell',public_shell:true,
      demo_provider_ready:true,demo_inference_enabled:true,provider_ready:false,
      demo_provider:'workers-ai-demo',demo_model:'@cf/zai-org/glm-4.7-flash',
      demo_qwen_ready:false,demo_gemma_ready:false
    }}));
    await browser.route('**/api/auth/public-config*', route => route.fulfill({json:{
      enabled:true,issuer:'https://tenant.us.auth0.com/',
      audience:'https://0livia.example/api',client_id:'publicClient012345678901'
    }}));
    await browser.route('**/api/auth/owner-status*', route => {
      ownerChecks++;
      if (route.request.headers.authorization !== 'Bearer ' + fakeAccessToken)
        throw Error('Owner-status did not receive the exact OAuth access token');
      return route.fulfill({json:{owner:true,demo_ready:true}});
    });
    await browser.route('**/api/demo-chat*', route => {
      demoPosts++;
      if (route.request.method !== 'POST' ||
          route.request.headers.authorization !== 'Bearer ' + fakeAccessToken)
        throw Error('Demo POST missing owner bearer authorization');
      const payload = JSON.parse(route.request.postData || '{}');
      if (payload.model !== 'glm' ||
          !Array.isArray(payload.messages) ||
          payload.messages.at(-1)?.content !== 'Probá el chat privado')
        throw Error('Demo POST did not use GLM with the owner prompt');
      return route.fulfill({json:{
        answer:expectedAnswer,model:'@cf/zai-org/glm-4.7-flash',
        provider:'workers-ai-demo',canonical:false
      }});
    });

    // Fail closed for unexpected tenant requests. More specific handlers take precedence.
    await browser.route('https://tenant.us.auth0.com/**', route => route.abort());
    await browser.route('**/oauth/token', route => {
      tokenExchanges++;
      if (route.request.method !== 'POST') throw Error('OAuth code exchange must POST');
      const form = new URLSearchParams(route.request.postData || '');
      const verifier = form.get('code_verifier') || '';
      if (form.get('grant_type') !== 'authorization_code' ||
          form.get('code') !== 'offline_single_use_code' ||
          form.get('client_id') !== 'publicClient012345678901' ||
          form.get('redirect_uri') !== base + '/' ||
          !/^[A-Za-z0-9_-]{64}$/.test(verifier))
        throw Error('OAuth token exchange did not preserve PKCE state');
      const challenge = createHash('sha256').update(verifier).digest('base64url');
      if (challenge !== pkceChallenge) throw Error('PKCE S256 challenge does not match verifier');
      const idToken = 'e30.' + Buffer.from(JSON.stringify({nonce})).toString('base64url') + '.c2ln';
      return route.fulfill({
        headers:{'Access-Control-Allow-Origin':'*'},
        json:{token_type:'Bearer',access_token:fakeAccessToken,id_token:idToken}
      });
    });
    await browser.route('**/authorize*', route => {
      const url = new URL(route.request.url);
      if (url.origin !== 'https://tenant.us.auth0.com' ||
          url.searchParams.get('response_type') !== 'code' ||
          url.searchParams.get('client_id') !== 'publicClient012345678901' ||
          url.searchParams.get('connection') !== 'email' ||
          url.searchParams.get('audience') !== 'https://0livia.example/api' ||
          url.searchParams.get('redirect_uri') !== base + '/' ||
          url.searchParams.get('code_challenge_method') !== 'S256')
        throw Error('Invalid OAuth authorization request');
      state = url.searchParams.get('state') || '';
      nonce = url.searchParams.get('nonce') || '';
      pkceChallenge = url.searchParams.get('code_challenge') || '';
      if (!/^[A-Za-z0-9_-]{32}$/.test(state) ||
          !/^[A-Za-z0-9_-]{32}$/.test(nonce) ||
          !/^[A-Za-z0-9_-]{43}$/.test(pkceChallenge))
        throw Error('OAuth state, nonce or code challenge missing');
      return route.fulfill({
        status:302,
        headers:{Location:base + '/?code=offline_single_use_code&state=' + state},
        body:''
      });
    });

    await app.open('/');
    await expect(screen.getByRole('button',{name:'Enviar'})).toBeDisabled();
    await expect(browser.locator('#ownerLogin.open')).toBeVisible();
    await expect(browser.locator('#oliviaEmailLogin')).toBeVisible();
    await browser.locator('#oliviaEmailLogin').tap();

    // This is the actual app document after an intercepted OAuth redirect.
    await expect(screen.getByRole('button',{name:'Enviar'})).toBeEnabled();
    const prompt = screen.getByRole('textbox',{name:'Mensaje'});
    await prompt.fill('Probá el chat privado');
    await screen.getByRole('button',{name:'Enviar'}).tap();
    await expect(browser.locator('#messages .msg.assistant:not(.error)')).toContainText(expectedAnswer);
    if (tokenExchanges !== 1 || ownerChecks !== 1 || demoPosts !== 1)
      throw Error('Expected one OAuth token exchange, owner gate, and GLM mock POST');

    const leaked = await browser.evaluate((value: string) =>
      JSON.stringify(Object.entries(localStorage)).includes(value) ||
      JSON.stringify(Object.entries(sessionStorage)).includes(value),
      fakeAccessToken
    );
    if (leaked) throw Error('OAuth access token leaked into browser storage');
    await browser.locator('.rail-btn[data-side="session"]').tap();
    await screen.getByRole('button',{name:'Cerrar sesión privada'}).tap();
    await expect(screen.getByRole('button',{name:'Enviar'})).toBeDisabled();
    if (demoPosts !== 1) throw Error('Logout unexpectedly repeated inference');
  });


  test('signed-in non-owner email identity remains blocked after offline OAuth callback and spends zero AI calls', async ({app,screen,browser}) => {
    await app.clearState();
    const state='g'.repeat(32), nonce='n'.repeat(32), verifier='A'.repeat(64);
    const guestToken='offline_guest_token_never_owner_012345678901234567890';
    let ownerChecks=0, demoPosts=0, exchanges=0;

    // Seed only a temporary PKCE transaction, not an access token or login session.
    await browser.addInitScript((seed: {state:string;nonce:string;verifier:string}) => {
      sessionStorage.setItem('olivia:auth0:pkce:v1',JSON.stringify({...seed,created:Date.now()}));
    },{state,nonce,verifier});
    await browser.route('**/healthz*', route => route.fulfill({json:{
      process_alive:true,api_mode:'public_shell',public_shell:true,
      demo_provider_ready:true,demo_inference_enabled:true,provider_ready:false
    }}));
    await browser.route('**/api/auth/public-config*', route => route.fulfill({json:{
      enabled:true,issuer:'https://tenant.us.auth0.com/',
      audience:'https://0livia.example/api',client_id:'publicClient012345678901'
    }}));
    await browser.route('**/api/demo-chat*', route => {
      demoPosts++;
      return route.fulfill({status:403,json:{error:'guest_inference_forbidden'}});
    });
    await browser.route('**/api/auth/owner-status*', route => {
      ownerChecks++;
      if (route.request.headers.authorization !== 'Bearer ' + guestToken)
        throw Error('Guest must present the same token to the owner-only gate');
      return route.fulfill({status:403,json:{error:'owner_only'}});
    });
    await browser.route('https://tenant.us.auth0.com/**', route => route.abort());
    await browser.route('**/oauth/token', route => {
      exchanges++;
      const form=new URLSearchParams(route.request.postData || '');
      if (form.get('code') !== 'guest_code' ||
          form.get('code_verifier') !== verifier ||
          form.get('grant_type') !== 'authorization_code')
        throw Error('Guest OAuth callback lacked the matching PKCE verifier');
      const idToken='e30.'+Buffer.from(JSON.stringify({nonce})).toString('base64url')+'.c2ln';
      return route.fulfill({
        headers:{'Access-Control-Allow-Origin':'*'},
        json:{token_type:'Bearer',access_token:guestToken,id_token:idToken}
      });
    });

    await app.open('/?code=guest_code&state='+state);
    await expect(screen.getByRole('button',{name:'Enviar'})).toBeDisabled();
    await expect(browser.locator('#ownerLogin.open')).toBeVisible();
    await expect(browser.locator('#oliviaEmailLogin')).toBeVisible();
    const becameOwner=await browser.evaluate(() => window.OliviaOwnerAuth.isOwner());
    if (becameOwner || exchanges!==1 || ownerChecks!==1 || demoPosts!==0)
      throw Error('Non-owner email identity bypassed the owner gate or initiated inference');
  });

}
