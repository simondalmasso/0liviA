import type { E2EConfig } from 'e2e';
import { web } from '@e2e-dev/web';

const appUrl = process.env.OLIVIA_E2E_URL ?? 'http://127.0.0.1:8767';

export default {
  projectId: 'olivia-public-demo',
  tests: 'tests-e2e/**/*.e2e.ts',
  targets: [
    {
      name: 'chromium-mobile',
      engine: web({ viewport: { width: 390, height: 844 } }),
      app: {
        url: appUrl,
        readyUrl: appUrl,
        environment: process.env.OLIVIA_E2E_LIVE === '1' ? 'production' : 'test',
      },
    },
  ],
  timeout: 60_000,
  actionTimeout: 15_000,
  assertionTimeout: 30_000,
  workers: 1,
  retries: 0,
  trace: 'retain-on-failure',
} satisfies E2EConfig;
