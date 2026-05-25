import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.BASE_URL || 'http://localhost:5173';
const useExternalBaseURL = Boolean(process.env.BASE_URL);

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  retries: 0,
  reporter: 'html',
  use: {
    baseURL,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'mobile',
      use: { ...devices['Pixel 5'] },
    },
  ],
  // Snapshot directory for visual regression baselines
  snapshotDir: './tests/e2e/snapshots',
  webServer: useExternalBaseURL
    ? undefined
    : {
        command: 'VITE_E2E=true npm run dev',
        url: baseURL,
        reuseExistingServer: true,
        timeout: 30000,
      },
});
