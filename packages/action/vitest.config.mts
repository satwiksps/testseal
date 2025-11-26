import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    coverage: {
      include: ['src/**/*.ts'],
      provider: 'v8',
      reportsDirectory: '../../.testseal/action-coverage',
      reporter: ['text', 'lcov'],
      thresholds: {
        branches: 80,
        functions: 85,
        lines: 85,
        statements: 85,
      },
    },
    environment: 'node',
    include: ['test/**/*.test.ts'],
    mockReset: true,
    restoreMocks: true,
  },
});
