import { test } from '@e2e-dev/web';
import { expect } from 'e2e';

const localStatic = process.env.OLIVIA_E2E_STATIC_ONLY === '1';

test('static public shell is usable but clearly refuses inference', async ({ app, screen, browser }) => {
  await app.clearState();

  if (localStatic) {
    await browser.route('**/healthz*', (route) => route.fulfill({ json: {
      process_alive: true,
      release_sha: 'a'.repeat(40),
      api_mode: 'public_shell',
      public_shell: true,
      static_only: true,
      bridge_enabled: false,
      provider_ready: false,
      inference_enabled: false,
      demo_inference_enabled: false,
      demo_provider_ready: false,
      demo_provider: null,
      demo_model: null,
      demo_qwen_ready: false,
      demo_gemma_ready: false,
      demo_daily_request_limit: 0,
      web_read: false,
      hard_zero_cost: true,
      demo_cost_guaranteed: false,
      canonical_backend: 'self_hosted_python_core',
    } }));
    await browser.route('**/api/**', (route) => route.fulfill({
      status: 503,
      json: { error: 'bridge_disabled', message: 'Static-only release; inference unavailable.' },
    }));
  }

  await app.open('/');
  await expect(browser.locator('#publicDemoBtn')).toHaveCount(0);
  await expect(browser.locator('#publicLoginBtn')).toHaveCount(0);
  await expect(browser.locator('#modeChat')).toHaveCount(0);
  await expect(browser.locator('#modeWork')).toHaveCount(0);
  await expect(browser.locator('#entryIntro')).toBeVisible();

  const message = screen.getByRole('textbox', { name: 'Mensaje' });
  await expect(message).toBeEnabled();
  await expect(browser.locator('#publicStatus')).toBeVisible();
  await expect(browser.locator('#publicStatus')).toContainText('Chat IA no conectado');
  await expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled();
  await expect(browser.locator('#messages .msg.assistant')).toHaveCount(0);
  await expect(browser.locator('#messages .provider-pill')).toHaveCount(0);
});
