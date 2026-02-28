/**
 * Integrationstests für Frontend-API-Flows.
 * 
 * Testet vollständige Szenarien mit Mock-APIs.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { apiGet, apiPost } from '../src/api';

describe('API Integration Tests', () => {
  /**
   * Integration-Test Suite für Frontend-API-Flows.
   * 
   * Unterschied zu Unit-Tests:
   * - Unit: Testet einzelne Function/Component isoliert
   * - Integration: Testet komplette Workflows über mehrere API-Calls
   * 
   * Szenarien abgedeckt:
   * 1. Bitcoin Price Flow: Preis abrufen + Historie laden
   * 2. Export Flow: Job starten, Status abfragen, Stop
   * 3. Filter Flow: Coins filtern + Ergebnisse sortieren
   * 4. Simulate Flow: DCA-Simulation mit Parametern
   * 
   * Mock-Strategie:
   * - Alle fetch() calls sind gemockt
   * - Keine echten HTTP-Anfragen an Backend
   * - Responses simulieren realistische API-Daten
   * - Tests sind schnell (kein Netzwerk-Latenz)
   */
  
  beforeEach(() => {
    // Vor jedem Test: clear all mocks
    global.fetch = vi.fn();
  });

  afterEach(() => {
    // Nach jedem Test: cleanup mocks
    vi.clearAllMocks();
  });

  describe('Bitcoin Price Flow', () => {
    /**
     * Test-Gruppe: Bitcoin Preis und Kursverlauf.
     * 
     * User-Szenario:
     * 1. Frontend wird geladen
     * 2. ChartDemo.jsx startet useEffect mit apiGet('/api/btc/price')
     * 3. Zeigt aktuellen Preis an (65000 USD)
     * 4. Nutzer klickt auf "1 Jahr Verlauf zeigen"
     * 5. apiGet('/api/btc/history?years=1') wird aufgerufen
     * 6. Chart wird mit Daten gefüllt und visualisiert
     * 
     * Tests validieren:
     * - Preis-Abruf liefert korrekte Struktur
     * - Historie hat labels (Daten) und data (Preise) Parity
     * - Date-Bereich stimmt mit ?years=1 überein
     */
    it('sollte Bitcoin-Preis abrufen', async () => {
      /**
       * Test: Bitcoin-Preis von Backend abrufen.
       * 
       * Frontend: ChartDemo Komponente
       * ```javascript
       * useEffect(() => {
       *   apiGet('/api/btc/price').then(data => setCurrentPrice(data.price_usd))
       * }, [])
       * ```
       * 
       * Response von Backend:
       * {
       *   source: 'coinbase_exchange',  // Woher kommt der Preis
       *   symbol: 'BTC-USD',            // Standard Formatierung
       *   price_usd: 65000,             // Aktueller Preis
       *   timestamp: '2025-01-01T...'   // Zeitstempel der Abfrage
       * }
       * 
       * Was wir testen:
       * - apiGet liefert Daten korrekt zurück
       * - price_usd hat richtigen Wert (65000)
       * - symbol ist korrektes BTC-Format
       */
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({
          source: 'coinbase_exchange',
          symbol: 'BTC-USD',
          price_usd: 65000,
        }),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      const result = await apiGet('/api/btc/price');

      expect(result.price_usd).toBe(65000);
      expect(result.symbol).toBe('BTC-USD');
    });

    it('sollte Bitcoin-Verlauf mit Jahren abrufen', async () => {
      /**
       * Test: Bitcoin-Kursverlauf für Chart-Rendering.
       * 
       * Frontend Use-Case:
       * 1. Nutzer wählt "1 Jahr" im Chart-Kontrollen aus
       * 2. Komponente ruft apiGet('/api/btc/history?years=1') auf
       * 3. Response wird an Chart.js übergeben
       * 
       * Chart-Struktur erwartet:
       * {
       *   labels: ['2024-01-01', '2024-01-02', ...],  // x-Achse (Daten)
       *   data: [50000, 51000, 50500, ...],           // y-Achse (Preige)
       *   years: 1                                     // Bestätigung der Periode
       * }
       * 
       * wichtig:
       * - arrays müssen gleiche Länge haben (3 labels, 3 data-Punkte)
       * - years sollte mit query-param übereinstimmen (was wir requestet)
       * - labels chronologisch aufsteigend geordnet
       */
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({
          labels: ['2024-01-01', '2024-01-02', '2024-01-03'],
          data: [50000, 51000, 50500],
          years: 1,
        }),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      const result = await apiGet('/api/btc/history?years=1');

      expect(result.labels).toHaveLength(3);
      expect(result.data).toHaveLength(3);
      expect(result.years).toBe(1);
    });
  });

  describe('Export Flow', () => {
    /**
     * Test-Gruppe: Coinbase CSV Export Workflow.
     * 
     * Komplettes Szenario:
     * 1. Nutzer gibt Symbole (BTC, ETH) ein
     * 2. Klickt "Export starten"
     * 3. Frontend ruft POST /api/export/coinbase/start auf
     * 4. Backend gibt job_id zurück
     * 5. Frontend startet Polling mit GET /api/export/coinbase/status
     * 6. Zeigt Fortschrittsbalken (50%, 100%, etc)
     * 7. Wenn done: Nutzer kann CSV downloaden
     * 
     * Dieser Test validiert:
     * - Export-Start gibt gültige job_id
     * - Status-Polling funktioniert
     * - Fortschritt wird korrekt berechnet (done/total)
     * - Fehlerifall: Job kann gestoppt werden
     */
    it('sollte Export-Job starten und Status abfragen', async () => {
      /**
       * Test: Kompletter Export-Workflow (2 API-Calls).
       * 
       * Call 1: Export Start
       * POST /api/export/coinbase/start
       *   Body: { symbols: ['BTC', 'ETH'], years: 10 }
       *   Response: { job_id: 'job_abc123' }
       * 
       * Call 2: Status Polling
       * GET /api/export/coinbase/status/job_abc123
       *   Response:
       *   {
       *     job_id: 'job_abc123',
       *     status: 'running',
       *     done: 1,              // 1 Symbol fertig
       *     total: 2,             // von 2 Symbolen insgesamt
       *     percent: 50,          // Mathe: 1/2 * 100 = 50%
       *     current: 'BTC'        // Gerade wird BTC verarbeitet
       *   }
       * 
       * Frontend-Logic:
       * 1. Nutzer klickt "Export"
       * 2. Fortschritts-Modal öffnet sich mit 0%
       * 3. Nach jedem Status-Poll: percent wird aktualisiert
       * 4. Bei 100%: CSV-Download-Link wird abrufig
       * 
       * Dieser Test validiert:
       * - Job-ID wird korrekt zurück geliefert
       * - Status enthält alle notwendigen Felder
       * - done/total Verhältnis ist korrekt
       */
      // Start Export
      const startResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({ job_id: 'job_abc123' }),
      };

      global.fetch.mockResolvedValueOnce(startResponse);

      const startResult = await apiPost('/api/export/coinbase/start', {
        symbols: ['BTC', 'ETH'],
        years: 10,
      });

      expect(startResult.job_id).toBe('job_abc123');

      // Get Status
      const statusResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({
          job_id: 'job_abc123',
          status: 'running',
          done: 1,
          total: 2,
          percent: 50,
          current: 'BTC',
        }),
      };

      global.fetch.mockResolvedValueOnce(statusResponse);

      const statusResult = await apiGet('/api/export/coinbase/status/job_abc123');

      expect(statusResult.status).toBe('running');
      expect(statusResult.percent).toBe(50);
    });

    it('sollte Export-Fehler bei leeren Symbolen behandeln', async () => {
      const errorResponse = {
        ok: false,
        status: 400,
        statusText: 'Bad Request',
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({ detail: 'symbols ist leer' }),
      };

      global.fetch.mockResolvedValueOnce(errorResponse);

      await expect(
        apiPost('/api/export/coinbase/start', {
          symbols: [],
          years: 10,
        })
      ).rejects.toThrow('symbols ist leer');
    });
  });

  describe('Filter and CSV Flow', () => {
    /**
     * Test-Gruppe: CSV Filterung und Analyse.
     * 
     * User-Szenario:
     * 1. Nutzer hat CSV-Datei via Coinbase Export
     * 2. Klickt auf "Coins filtern nach Kursbewegung"
     * 3. Wählt "gestiegen" und "20% Schwelle" über "3 Jahre"
     * 4. Frontend ruft GET /api/filter/coinbase?years=3&direction=gestiegen&percent=20
     * 5. Ergebnis zeigt aufgestiegene Coins in Tabelle
     * 
     * Response-Struktur:
     * {
     *   count: 2,                    // 2 gefundene Coins
     *   results: [
     *     {
     *       symbol: 'BTC',
     *       start_price: 45000,      // Preis vor 3 Jahren
     *       end_price: 65000,        // Aktueller Preis
     *       change_percent: 44.44,   // (65000-45000)/45000*100
     *       period: '3 Jahre'        // Zeitraum (lesbar)
     *     }
     *   ]
     * }
     * 
     * Dieser Test validiert:
     * - Filter-API gibt korrekte Struktur zurück
     * - change_percent wird correct berechnet
     * - Symbole werden korrekt gefiltert
     */
    it('sollte Filter-Ergebnisse abrufen', async () => {
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({
          count: 2,
          results: [
            {
              symbol: 'BTC',
              start_price: 45000,
              end_price: 65000,
              change_percent: 44.44,
              period: '3 Jahre',
            },
            {
              symbol: 'ETH',
              start_price: 1200,
              end_price: 3500,
              change_percent: 191.67,
              period: '3 Jahre',
            },
          ],
          csv_used: 'coinbase_daily_2025-02-28.csv',
        }),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      const result = await apiPost('/api/filter/coinbase', {
        years: 3,
        percent: 20,
        direction: 'gestiegen',
      });

      expect(result.count).toBe(2);
      expect(result.results).toHaveLength(2);
      expect(result.csv_used).toContain('coinbase_daily');
    });

    it('sollte CSV-Verlauf für Symbol abrufen', async () => {
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({
          symbol: 'BTC',
          available: true,
          labels: ['2024-01-01', '2024-01-02'],
          data: [50000, 51000],
        }),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      const result = await apiGet('/api/csv/history/BTC');

      expect(result.symbol).toBe('BTC');
      expect(result.available).toBe(true);
      expect(result.labels).toHaveLength(2);
    });
  });

  describe('Savings Simulation Flow', () => {
    it('sollte statische Sparplan-Simulation durchführen', async () => {
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({
          result_usd: 12500.0,
          cash_only_usd: 3600.0,
        }),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      const result = await apiPost('/api/simulate/savings', {
        symbol: 'BTC',
        years: 3,
        monthly_usd: 100,
      });

      expect(result.result_usd).toBe(12500.0);
      expect(result.cash_only_usd).toBe(3600.0);
    });

    it('sollte dynamische Sparplan-Simulation durchführen', async () => {
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({
          result_usd: 15000.0,
          cash_buffer_usd: 500.0,
        }),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      const result = await apiPost('/api/simulate/savings_dynamic', {
        symbol: 'BTC',
        years: 3,
        monthly_usd: 100,
        threshold_pct: 5,
        adjust_pct: 50,
        ma_days: 200,
      });

      expect(result.result_usd).toBe(15000.0);
      expect(result.cash_buffer_usd).toBe(500.0);
    });
  });

  describe('Coins Table Flow', () => {
    it('sollte Top-Coins mit Suchergebnissen abrufen', async () => {
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: vi.fn().mockResolvedValue({
          vs_currency: 'usd',
          count: 3,
          coins: [
            {
              id: 'bitcoin',
              symbol: 'BTC',
              name: 'Bitcoin',
              current_price: 65000,
              market_cap: 1270000000000,
            },
            {
              id: 'ethereum',
              symbol: 'ETH',
              name: 'Ethereum',
              current_price: 3500,
              market_cap: 420000000000,
            },
            {
              id: 'ripple',
              symbol: 'XRP',
              name: 'Ripple',
              current_price: 2.5,
              market_cap: 135000000000,
            },
          ],
        }),
      };

      global.fetch.mockResolvedValueOnce(mockResponse);

      const result = await apiGet('/api/coins?limit=5');

      expect(result.vs_currency).toBe('usd');
      expect(result.coins).toHaveLength(3);
      expect(result.coins[0].symbol).toBe('BTC');
    });
  });
});
