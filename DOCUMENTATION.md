# Trading Board - Dokumentation

## Projektübersicht

Das Trading Board ist eine vollständige Full-Stack-Anwendung für Kryptowährungs-Analyse, Export und Simulation basierend auf CSV-Daten.

---

## Backend-Dokumentation

### Architektur

**Framework:** FastAPI (ASGI mit uvicorn)  
**Externe APIs:** Coinbase Exchange, CoinGecko  
**Kernmodule:**
- `app/services/btc_service.py` - Bitcoin-Preisabfrage (Coinbase → CoinGecko Fallback)
- `app/services/csv_tools.py` - CSV-Verarbeitung, Filterung, Simulationen
- `app/services/csv_tools_service.py` - Service-Layer mit mtime-basiertem Caching
- `app/services/export_service.py` - Export-Job-Management
- `app/services/coinbase.py` - Coinbase API-Wrapper

### Services im Detail

#### btc_service.py
```python
async def get_btc_price() -> float
```
- Ruft aktuellen BTC-Preis ab
- Primary: Coinbase Exchange API
- Fallback: CoinGecko API bei Ausfall
- Cache: 1 Stunde für Coinbase-Produkte

#### csv_tools.py
**Kernfunktionen:**

- `load_prices_by_symbol(file_path)` → Dict[str, List[Tuple[date, float]]]
  - Parsed CSV-Datei im Format: Symbol, Date, Price
  - Gruppiert Einträge nach Symbol

- `filter_coinbase(prices_by_symbol, years, percent, direction)` → Dict
  - Filtert Symbole nach Preisbewegung
  - direction: "gestiegen" | "gefallen"
  - Berechnet Prozentuale Änderung über Zeitfenster

- `csv_history(prices_by_symbol, symbol)` → Dict
  - Gibt Kursverlauf für einzelnes Symbol zurück
  - Format: {available, symbol, labels, data}

- `simulate_savings(prices_by_symbol, symbol, years, monthly_usd)` → Dict
  - Simuliert DCA (Dollar-Cost Averaging): Monatlich fester Betrag
  - Returns: result_usd (Portfolio-Wert), cash_only_usd (investiert)

- `simulate_savings_dynamic(prices_by_symbol, symbol, years, monthly_usd, threshold_pct, adjust_pct, ma_days)` → Dict
  - Intelligente DCA mit Schwellenwerten
  - Erhöht Investition bei Preis < MA * (1 - threshold)
  - Senkt Investition und puffert bei Preis >= MA * (1 + threshold)

- `calc_ma_for_date(date, prices, ma_days)` → float | None
  - Berechnet gleitenden Durchschnitt (Moving Average) für Datum
  - Returns None bei unzureichenden Datenpunkten

#### csv_tools_service.py
- Service-Layer mit mtime-basiertem Caching
- `get_history(symbol)` - Kursverlauf mit Cache
- `get_filter(years, percent, direction)` - Gefilterte Coins mit Cache
- Cache-Invalidation bei File-Änderung

#### export_service.py
```python
class ExportService:
    async def start_coinbase_export(symbols: List[str], years: int) → str
    def stop_coinbase_export() → None
    def get_status(job_id: str) → Dict | None
```

- In-Memory Job-Management
- Jeder Job-ID ist eindeutig (UUID)
- Status-Tracking mit Prozent-Fortschritt
- CSV-Export mit Headers: Symbol, Date, Price

---

## Frontend-Dokumentation

### Komponenten

#### api.js
HTTP-Helper für alle API-Anfragen.

```javascript
const result = await apiGet('/api/btc/price')
const result = await apiPost('/api/export/coinbase/start', {symbols: ['BTC'], years: 10})
```

- Automatische URL-Konstruktion (API_BASE + endpoint)
- Error-Handling mit Detail-Extraktion
- Unterstützt AbortController für Requests

#### App.jsx
Root-Layout-Komponente.
- Header mit Logo/Titel
- Main-Content Bereich
- Import ChartDemo für Trading-Board

#### ChartDemo.jsx (1133 Zeilen)
**Hauptkomponente mit folgenden Features:**

1. **Bitcoin-Preis Display**
   - Aktuellen BTC/USD Preis zeigen
   - Auto-Refresh

2. **Chart (Chart.js)**
   - Interaktives Kurs-Chart
   - Zoom, Pan, Export funktionalität

3. **Filter-Controls**
   - Nach gestiegenen/gefallenen Kursen filtern
   - Jahre-Selektor (1-15 Jahre)
   - Prozent-Schwellenwert

4. **Export-Funktion**
   - Symbol-Liste eingeben
   - Export starten/stoppen
   - Fortschritts-Tracking

5. **CSV Analytics**
   - Import von Coinbase CSV-Dateien
   - Histogramm-Visualisierung
   - Filter & Analyse

6. **Simulationen**
   - DCA-Simulation (statisch)
   - Dynamische Sparplan-Simulation
   - Gewinn/Verlust Berechnung

---

## API-Endpoints

### Bitcoin Service

**GET /api/btc/price**
```json
{
  "price_usd": 65000.0,
  "symbol": "BTC-USD",
  "timestamp": "2025-01-01T10:30:00Z",
  "source": "coinbase_exchange|coingecko"
}
```

**GET /api/btc/history?years=10**
```json
{
  "labels": ["2015-01-01", "2015-01-02", ...],
  "data": [435.0, 440.5, ...],
  "years": 10
}
```

### CSV Tools

**GET /api/filter/coinbase?years=3&percent=20&direction=gestiegen**
```json
{
  "count": 5,
  "results": [
    {
      "symbol": "BTC",
      "start_price": 45000.0,
      "end_price": 75000.0,
      "change_percent": 66.67
    }
  ]
}
```

**GET /api/csv/history/{symbol}**
```json
{
  "available": true,
  "symbol": "BTC",
  "labels": ["2022-01-01", ...],
  "data": [45000.0, ...]
}
```

### Simulationen

**POST /api/simulate/savings**
```json
{
  "symbol": "BTC",
  "years": 3,
  "monthly_usd": 100
}
```
Response:
```json
{
  "result_usd": 12000.0,
  "cash_only_usd": 3600.0,
  "gain_usd": 8400.0,
  "gain_percent": 233.33
}
```

**POST /api/simulate/savings_dynamic**
```json
{
  "symbol": "BTC",
  "years": 3,
  "monthly_usd": 100,
  "threshold_pct": 0.1,
  "adjust_pct": 0.5,
  "ma_days": 20
}
```

### Exports

**POST /api/export/coinbase/start**
```json
{
  "symbols": ["BTC", "ETH"],
  "years": 10
}
```
Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**GET /api/export/coinbase/status?job_id=550e8400...**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running|done|failed",
  "done": 50,
  "total": 100,
  "percent": 50.0,
  "errors": 0
}
```

**GET /api/export/coinbase/stop?job_id=550e8400...**
```json
{
  "stopped": true
}
```

---

## Testing

### Backend Tests

**test_csv_tools.py** (253 Zeilen, 13 Tests)
- CSV-Filterung (gestiegen/gefallen)
- Kursverlauf-Abfrage
- DCA-Simulation (statisch & dynamisch)
- Gleitender Durchschnitt Berechnung
- Edge-Cases (leere Daten, einzelne Einträge)

**test_export_service.py** (206 Zeilen, 9 Tests)
- Service-Initialisierung
- Stop-Signal Mechanik
- Status-Tracking mit Prozentfortschritt
- Symbol-Normalisierung

**test_api_endpoints.py** (189 Zeilen, 14+ Tests)
- Health Check
- BTC Price/History Endpoints
- Coins-Tabelle
- Export Endpoints (start, stop, status)
- Filter Endpoints
- Simulationen

**test_csv_tools_service.py** (80 Zeilen, 2+ Tests)
- Service-Caching
- Mock-Integration

### Frontend Tests

**api.test.js** (181 Zeilen)
- apiGet & apiPost Funktionen
- Error-Handling
- Signal-Parameter Support

**App.test.jsx** (26 Zeilen)
- Root-Komponente Rendering
- Child-imports

**integration.test.js** (284 Zeilen)
- Bitcoin Price Flow
- Export Flow
- Filter Flow
- Simulate Flow

---

## Local Development

### Backend
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:create_app() --reload
```
API läuft auf `http://localhost:8000`

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Dev-Server auf `http://localhost:5173`

---

## Deployment

### Backend Requirements
- Python 3.11+
- FastAPI, uvicorn
- httpx (für externe APIs)
- pytest (für Tests)

### Frontend Requirements
- Node.js 18+
- React 19, Vite 7
- Vitest (für Tests)
- Chart.js

---

## Error Handling

### Backend
- **502 Bad Gateway** - Externe API nicht erreichbar (Coinbase/CoinGecko)
- **400 Bad Request** - Invalid parameters (z.B. ungültige Quote)
- **404 Not Found** - Ressource nicht gefunden (z.B. kein Job)
- **500 Internal Server Error** - Server-Fehler

### Frontend
- API-Fehler → detail-String aus Response extrahiert
- Network-Fehler → generische Fehlermeldung
- AbortSignal → Request-Abbruch bei Component-Unmount

---

## Glossar

| Begriff | Erklärung |
|---------|-----------|
| DCA | Dollar-Cost Averaging: Regelmäßiger Kauf fester Beträge |
| MA | Moving Average (Gleitender Durchschnitt) |
| CSV | Comma-Separated Values Dateiformat |
| ASGI | Asynchronous Server Gateway Interface |
| mtime | Modification Time - Datei-Änderungszeit |
| UUID | Unique Identifier für Jobs |

---

## Zusätzliche Ressourcen

- [FastAPI Dokumentation](https://fastapi.tiangolo.com)
- [React Dokumentation](https://react.dev)
- [Coinbase API](https://docs.cloud.coinbase.com)
- [CoinGecko API](https://www.coingecko.com/api)
