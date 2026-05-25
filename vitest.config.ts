import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  esbuild: {
    // Enable React automatic JSX runtime so test files don't need
    // `import React from 'react'` and match Next.js's transform.
    jsx: 'automatic',
    jsxImportSource: 'react',
  },
  test: {
    // Default environment for lib unit tests.
    // Component test files override to jsdom via @vitest-environment pragma.
    environment: 'node',
    globals: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
});
