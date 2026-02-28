/**
 * Vitest Setup-Datei.
 * 
 * Konfiguriert globale Test-Umgebung, Mocks und Utilities.
 */

import { expect, afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';

// Cleanup nach jedem Test
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// Mock für fetch (wenn nicht bereits gemockt)
if (!global.fetch) {
  global.fetch = vi.fn();
}

// Mock für import.meta.env
Object.defineProperty(import.meta, 'env', {
  value: {
    VITE_API_URL: 'http://localhost:8000',
    VITE_API_BASE: undefined,
  },
  configurable: true,
});
