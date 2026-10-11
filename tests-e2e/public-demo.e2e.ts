import { test } from '@e2e-dev/web';
import { expect } from 'e2e';

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
  await message.fill('Esto no debe activar inferencia sin Google autorizado');
  await expect(screen.getByRole('button', {name:'Enviar'})).toBeDisabled();
  await expect(browser.locator('#messages .msg.assistant:not(.error)')).toHaveCount(0);
  await expect(browser.locator('#messages .provider-pill')).toHaveCount(0);
  if (unauthorizedInferenceCalls !== 0) throw new Error('Unauthorized browser inference call');
});

if (mockDemo) {

  test('Google owner login entry is reachable without enabling anonymous chat', async ({app,browser,screen}) => {
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
    await browser.locator('.rail-btn[data-side="session"]').tap();
    const entry = screen.getByRole('button',{name:'Entrar con Google'});
    await expect(entry).toBeEnabled();
    await entry.tap();
    await expect(browser.locator('#oliviaGoogleLogin')).toBeVisible();
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
    await browser.locator('.rail-btn[data-side="session"]').tap();
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
}
