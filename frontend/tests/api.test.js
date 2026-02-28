/**
 * Unit-Tests für API-Helper Modul.
 * 
 * Testet URL-Konstruktion, Request-Handling und Error-Verarbeitung.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { API_BASE, apiGet, apiPost } from '../src/api';

describe('API Helper', () => {
  /**
   * Test-Gruppe: API-Helper Modul und Konfiguration.
   * 
   * Das API-Helper Modul bietet:
   * 1. API_BASE: Zentrale URL für alle Backend-Anfragen
   * 2. apiGet: HTTP GET mit automatischem Error-Handling
   * 3. apiPost: HTTP POST mit JSON-Body und Error-Handling
   * 
   * Ziel: Saubere Abstraktion für API-Kommunikation
   * ohne duplicate fetch()-Boilerplate im ganzen Frontend.
   */
  describe('API_BASE Configuration', () => {
    /**
     * Test-Gruppe: Basis-URL Konfiguration.
     * 
     * Testet dass API_BASE korrekt initialisiert ist.
     * Env-Priorität:
     * 1. VITE_API_URL (empfohlen)
     * 2. VITE_API_BASE (alt)
     * 3. Fallback: http://127.0.0.1:8000
     * 
     * Wichtig für:
     * - Development (localhost:8000)
     * - Production (z.B. api.example.com)
     */
    it('sollte API_BASE definieren', () => {
      /**
       * Test: API_BASE muss definiert sein.
       * 
       * Validierungen:
       * 1. API_BASE sollte nicht undefined/null sein
       * 2. API_BASE sollte string sein
       * 3. API_BASE sollte nicht leer sein (mind. 1 Zeichen)
       * 
       * Wenn dieser Test scheitert:
       * - .env/vite.config.js hat keine API_URL
       * - oder Imports sind broken
       */
      expect(API_BASE).toBeDefined();
      expect(typeof API_BASE).toBe('string');
      expect(API_BASE.length).toBeGreaterThan(0);
    });

    it('sollte kein abschließendes Slash enthalten', () => {
      /**
       * Test: API_BASE sollte nicht mit "/" enden.
       * 
       * Grund:
       * toUrl() hängt den Pfad direkt an: `${API_BASE}/api/btc`
       * Wenn API_BASE = "http://localhost:8000/" endet in Slash 
       * => doppelter Slash: "http://localhost:8000//api/btc"
       * 
       * Validierung:
       * API_BASE sollte "http://localhost:8000" sein (kein schließendes /)
       * 
       * Frontend-Handling:
       * Das api.js Module entfernt abschließende slashes automatisch
       * mit .replace(/\/$/, "")
       */
      expect(API_BASE).not.toMatch(/\/$/);
    });
  });

  describe('apiGet Function', () => {
    /**
     * Test-Gruppe: HTTP GET Anfragen.
     * 
     * Funktion: apiGet(path, options)
     * Zweck: GET-Anfragen mit automatischem Error-Handling
     * 
     * Interna:
     * - Baut URL zusammen: API_BASE + path
     * - Macht fetch() mit method: 'GET'
     * - Parsed JSON-Response automatisch
     * - Wirft Error mit Status-Nachricht bei fehlgeschlagenen Status
     * 
     * Feature:
     * - Unterstützt AbortSignal (für cleanup bei Component-Unmount)
     * - Error-Details Extraktion aus Response JSON
     */
    beforeEach(() => {
      vi.clearAllMocks();
      global.fetch = vi.fn();
    });

    it('sollte GET-Request ausführen', async () => {
      /**
       * Test: Normaler erfolgreicher GET-Request.
       * 
       * Setup:
       * - Mock fetch mit Response: ok=true, status=200
       * - JSON response: { price: 65000 }
       * 
       * Anfrage:
       * await apiGet('/api/btc/price')
       * 
       * Erwartet:
       * - returned { price: 65000 }
       * - fetch() wurde aufgerufen mit korrektem Pfad
       * - method war 'GET'
       * 
       * Business-Kontext:
       * Frontend ruft Preis-Endpoint auf, kriegt Coins-Daten zurück.
       */
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({ price: 65000 }),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      const result = await apiGet('/api/btc/price');

      expect(result).toEqual({ price: 65000 });
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/btc/price'),
        expect.objectContaining({ method: 'GET' })
      );
    });

    it('sollte Fehler bei fehlgeschlagenem Request werfen', async () => {
      /**
       * Test: Error-Handling bei HTTP-Fehlerstatus.
       * 
       * Szenario:
       * Backend antwortet mit 500 Internal Server Error.
       * Response JSON: { detail: 'Server error' }
       * 
       * Erwartet:
       * - apiGet() wirft Error (nicht stille promise reject)
       * - Error message sollte 'Internal Server Error' sein
       * - statusText vom Mock wird als Error-Message verwendet
       * 
       * Frontend-Handling:
       * try/catch um apiGet() kümmert sich um Fehler.
       * Mitteilung an Nutzer: "Server-Fehler, bitte später versuchen"
       * 
       * Details:
       * apiGet() prüft response.ok flag
       * Wenn false => wirft Error mit statusText
       */
      const mockResponse = {
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({ detail: 'Server error' }),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      await expect(apiGet('/api/btc/price')).rejects.toThrow('Internal Server Error');
    });

    it('sollte Signal-Parameter unterstützen', async () => {
      /**
       * Test: AbortSignal für Request-Abbruch.
       * 
       * Zweck:
       * Komponente wird während fetch() unmountet.
       * Signal ermöglicht es, laufende Anfrage abzubrechen.
       * 
       * Szenario:
       * 1. apiGet('/slow/endpoint', { signal })
       * 2. Nutzer navigiert weg (Component unmount)
       * 3. signal.abort() wird aufgerufen
       * 4. fetch wird abgebrochen (cleanup)
       * 
       * Nutzen:
       * - Verhindert Memory-Leak (dangling promises)
       * - API-Requests werden nicht unnötig abgeschlos
       * - Bessere Performance und Ressourcen-Nutzung
       * 
       * Implementation:
       * AbortController wird im useEffect cleanup aufgerufen
       * signal wird an apiGet() übergeben
       */
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({}),
      };

      const controller = new AbortController();
      global.fetch.mockResolvedValueOnce(mockResponse);

      await apiGet('/api/test', { signal: controller.signal });

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ signal: controller.signal })
      );
    });
  });

  describe('apiPost Function', () => {
    beforeEach(() => {
      vi.clearAllMocks();
      global.fetch = vi.fn();
    });

    it('sollte POST-Request mit JSON-Body ausführen', async () => {
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({ job_id: 'abc123' }),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      const body = { symbols: ['BTC', 'ETH'], years: 10 };
      const result = await apiPost('/api/export/coinbase/start', body);

      expect(result).toEqual({ job_id: 'abc123' });
      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      );
    });

    it('sollte POST ohne Body ermöglichen', async () => {
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({ status: 'ok' }),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      await apiPost('/api/export/coinbase/stop', undefined);

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: 'POST' })
      );
    });

    it('sollte Error-Detail aus Backend extrahieren', async () => {
      const mockResponse = {
        ok: false,
        status: 400,
        statusText: 'Bad Request',
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({ detail: 'symbols ist leer' }),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      await expect(
        apiPost('/api/export/coinbase/start', { symbols: [] })
      ).rejects.toThrow('symbols ist leer');
    });

    it('sollte Text-Responses verarbeiten', async () => {
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'text/plain']]),
        text: vi.fn().mockResolvedValue('Success'),
        json: vi.fn().mockRejectedValue(new Error('Not JSON')),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      const result = await apiPost('/api/test', { foo: 'bar' });

      expect(result).toBe('Success');
    });
  });

  describe('URL Construction', () => {
    it('sollte API_BASE mit Pfad kombinieren', async () => {
      const mockResponse = {
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({}),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      await apiGet('/api/coins');

      const calledUrl = global.fetch.mock.calls[0][0];
      expect(calledUrl).toContain(API_BASE);
      expect(calledUrl).toContain('/api/coins');
    });
  });
});
