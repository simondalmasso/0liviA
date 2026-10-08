import { test } from '@e2e-dev/web';
import { expect } from 'e2e';

const mockDemo = process.env.OLIVIA_E2E_MOCK_DEMO === '1';

test('public demo opens and returns an AI answer', async ({ app, screen, browser }) => {
  await app.clearState();

  if (mockDemo) {
    await browser.route('**/healthz*', (route) =>
      route.fulfill({
        json: {
          process_alive: true,
          api_mode: 'public_shell',
          public_shell: true,
          bridge_enabled: false,
          provider_ready: false,
          inference_enabled: false,
          demo_inference_enabled: true,
          demo_provider_ready: true,
          demo_provider: 'workers-ai-demo',
          demo_model: '@cf/zai-org/glm-4.7-flash',
          demo_daily_request_limit: 25,
          web_read: false,
          hard_zero_cost: true,
          canonical_backend: 'self_hosted_python_core',
        },
      }),
    );

    await browser.route('**/api/demo-chat*', (route) =>
      route.fulfill({
        json: {
          answer: 'OLIVIA_E2E_OK',
          provider: 'workers-ai-demo',
          model: '@cf/zai-org/glm-4.7-flash',
          canonical: false,
        },
      }),
    );
  }

  await app.open('/');

  await expect(screen.getByRole('button', { name: 'Probar 0liviA ahora' })).toBeVisible();
  await expect(browser.locator('#publicLoginBtn')).toHaveCount(0);
  await expect(browser.locator('#modeChat')).toHaveCount(0);
  await expect(browser.locator('#modeWork')).toHaveCount(0);

  await screen.getByRole('button', { name: 'Probar 0liviA ahora' }).tap();

  const message = screen.getByRole('textbox', { name: 'Mensaje' });
  await expect(message).toBeEnabled();
  await message.fill(
    mockDemo
      ? 'Respondé exactamente: OLIVIA_E2E_OK'
      : 'Respondé con una frase breve.',
  );
  await screen.getByRole('button', { name: 'Enviar' }).tap();

  // Failures render as alerts, never as successful model answers.
  const answer = browser.locator('#messages .msg.assistant:not(.error) .bubble');
  await expect(answer).toHaveCount(1, { timeout: 30_000 });
  await expect(browser.locator('#messages .msg.error')).toHaveCount(0);
  await expect(browser.locator('#messages [role="alert"]')).toHaveCount(0);
  if (mockDemo) {
    await expect(answer).toContainText('OLIVIA_E2E_OK');
  }
  await expect(browser.locator('#messages .provider-pill')).toContainText('GLM 4.7 Flash');
});

if (mockDemo) {
  test('provider failure is an alert, never a successful AI answer', async ({ app, screen, browser }) => {
    await app.clearState();
    await browser.route('**/healthz*', (route) =>
      route.fulfill({
        json: {
          api_mode: 'public_shell',
          demo_provider_ready: true,
          hard_zero_cost: true,
          demo_provider: 'workers-ai-demo',
        },
      }),
    );
    await browser.route('**/api/demo-chat*', (route) =>
      route.fulfill({
        status: 503,
        json: { error: 'demo_provider_unavailable' },
      }),
    );
    await app.open('/');
    await screen.getByRole('button', { name: 'Probar 0liviA ahora' }).tap();
    await screen.getByRole('textbox', { name: 'Mensaje' }).fill('Verificar fallo explícito');
    await screen.getByRole('button', { name: 'Enviar' }).tap();
    await expect(browser.locator('#messages [role="alert"]')).toContainText('La IA demo $0 no respondió');
    await expect(browser.locator('#messages .msg.assistant:not(.error)')).toHaveCount(0);
    await expect(browser.locator('#messages .provider-pill')).toHaveCount(0);
  });
}
