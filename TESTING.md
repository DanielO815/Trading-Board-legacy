# Test-Setup und Ausführungsanleitung

## Backend Tests

### Installation

```bash
cd backend
pip install -r requirements-test.txt
```

### Tests ausführen

```bash
# Alle Tests
pytest

# Mit Coverage-Report
pytest --cov=app tests/

# Mit Verbose-Output
pytest -v

# Nur spezifische Test-Datei
pytest tests/test_csv_tools.py

# Nur spezifische Test-Klasse oder Funktion
pytest tests/test_csv_tools.py::TestCsvTools::test_filter_coinbase_risen
```

### Test-Struktur

**Unit-Tests:**
- `tests/test_csv_tools.py` - CSV-Analyse-Funktionen (Filter, Simulationen, MA)
- `tests/test_export_service.py` - Export-Service (Job-Verwaltung, Status)
- `tests/test_csv_tools_service.py` - CSV-Tools Service (Caching, Integration)

**Integration-Tests:**
- `tests/test_api_endpoints.py` - API-Endpoints (Health, BTC, Coins, Export, Filter)

### Wichtige Test-Cases

- **CSV-Tools**: Filterung nach Kursbewegungen, DCA-Simulation, dynamische Sparplan-Simulation
- **Export-Service**: Job-Erstellung, Status-Tracking, Fortschritt-Berechnung
- **API-Endpoints**: Request-Validierung, Error-Handling, Datenformat-Verarbeitung

---

## Frontend Tests

### Installation

```bash
cd frontend

# Aktualisiere package.json mit test dependencies
# Option 1: Manuell in package.json die Abhängigkeiten hinzufügen
npm install

# Option 2: Einzelne Test-Dependencies installieren
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

### Tests ausführen

```bash
# Alle Tests
npm run test

# Mit UI-Dashboard
npm run test:ui

# Mit Coverage-Report
npm run test:coverage

# Watch-Modus
npm run test -- --watch

# Spezifische Testdatei
npm run test -- api.test.js
```

### Test-Struktur

**Unit-Tests:**
- `tests/api.test.js` - API-Helper (GET, POST, Error-Handling)
- `tests/App.test.jsx` - Root-Komponente (Layout, Rendering)

**Integration-Tests:**
- `tests/integration.test.js` - Komplette Flows (BTC, Export, Filter, Simulation)

### Wichtige Test-Cases

- **API-Helper**: URL-Konstruktion, Request-Methoden, Error-Extraktion
- **App-Komponente**: Header-Rendering, Main-Struktur
- **Flows**: Bitcoin-Abfrage, Export-Job, Filter-Anwendung, Sparplan-Simulation

---

## Konfigurationsdateien

### Backend
- `requirements-test.txt` - Test-Dependencies (pytest, responses, etc.)
- `tests/conftest.py` - Pytest Fixtures (app, client, sample_prices)

### Frontend
- `vitest.config.js` - Vitest-Konfiguration (jsdom, globals, setup)
- `tests/setup.js` - Test-Setup (cleanup, fetch-mock, env-config)

---

## CI/CD Integration

### GitHub Actions Beispiel

```yaml
name: Tests

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - run: cd backend && pip install -r requirements-test.txt
      - run: cd backend && pytest --cov=app

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-node@v2
        with:
          node-version: 18
      - run: cd frontend && npm install
      - run: cd frontend && npm run test:coverage
```

---

## Best Practices

1. **Mock externe APIs** - CoinGecko, Coinbase Mock-Responses verwenden
2. **Temporäre Verzeichnisse** - FileSystem-Tests mit TemporaryDirectory / tempdir
3. **Environment-Variablen** - Test-spezifische Config in Fixtures
4. **Assertions schreiben** - Test-Namen sollten Erwartungen klar beschreiben
5. **Coverage überwachen** - Mindestens 70% Coverage für Kern-Features anstreben
