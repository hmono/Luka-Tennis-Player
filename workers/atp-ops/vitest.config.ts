import { cloudflareTest, readD1Migrations } from '@cloudflare/vitest-plugin';
import { defineConfig } from 'vitest/config';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [cloudflareTest(async () => ({
    wrangler: { configPath: './wrangler.local.jsonc' },
    miniflare: {
      bindings: {
        TEST_MIGRATIONS: await readD1Migrations(fileURLToPath(new URL('./migrations', import.meta.url))),
      },
    },
  }))],
  test: {
    // workerd cannot read Vitest's host filesystem module cache.
    fsModuleCache: false,
    include: ['test/**/*.test.ts'],
    setupFiles: ['./test/setup.ts'],
    maxWorkers: 1,
    testTimeout: 60000,
    hookTimeout: 30000,
  },
});
