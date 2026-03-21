/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import { resolve } from 'path';

export default defineConfig(({ command }) => {
  const isServe = command === 'serve';
  const base = process.env.VITE_BASE_URL ?? '/';
  const apiBase = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8080';

  const testConfig = {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  };

  // Common configuration for both dev and production
  const commonConfig = {
    base,
    appType: 'spa',
    plugins: [react()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
      },
    },
    build: {
      outDir: resolve(__dirname, 'dist'),
      emptyOutDir: true,
    },
    test: testConfig,
  };

  if (isServe) {
    return {
      ...commonConfig,
      server: {
        open: !process.env.VITE_E2E,
        // Omit the proxy entirely in E2E mode — all API calls are mocked by
        // Playwright's page.route(), so there is no backend to forward to.
        ...(!process.env.VITE_E2E && {
          proxy: {
            '^/(get-|select-|devos-|duty-|api/)': {
              target: apiBase,
              changeOrigin: true,
              secure: false,
            },
          },
        }),
      },
    };
  }

  // Preview server settings (e.g. when running `vite preview`)
  return {
    ...commonConfig,
    preview: {
      host: '0.0.0.0',
      port: Number(process.env.VITE_PREVIEW_PORT) || 4173,
      open: process.env.VITE_PREVIEW_OPEN === 'true',
    },
  };
});