/**
 * Vitest-Konfiguration für Frontend Unit-Tests.
 * 
 * Konfiguriert Test-Environment, Setup-Dateien und Module-Auflösung.
 */

import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.js'],
  },
});
