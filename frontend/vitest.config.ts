/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';
import path from 'node:path';

// Minimal vitest bootstrap (Epic 14, story 14.5). Node environment — the Epic-14
// tests exercise pure spec-mapping logic + the localStorage cache (stubbed), so
// no jsdom is needed. This harness is load-bearing for FR1.2 and every later
// component test (16.4 parity, etc.).
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
});
