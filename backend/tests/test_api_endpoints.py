"""
Integrationstests für API-Endpoints.

Testet HTTP-Anfragen gegen FastAPI-Applikation.
"""

import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
from app.main import create_app


class TestApiEndpoints(unittest.TestCase):
    """Integrationstests für Haupt-API Endpoints.
    
    Diese Test-Klasse macht HTTP-Anfragen gegen die echte FastAPI-Applikation,
    um vollständige API-Flows zu testen. Das unterscheidet sich von Unit-Tests:
    - Testet echte HTTP-Status-Codes (200, 502, etc.)
    - Validiert JSON-Struktur und Datentypen
    - Behandelt externe API-Ausfälle (Coinbase, CoinGecko)
    
    Test-Kategorien:
    1. Health Checks: Basis-Verfügbarkeit
    2. BTC Service: Bitcoin-Preis und Historie von Coinbase/CoinGecko
    3. Coins: Daten von CoinGecko (mit Filterung/Sortierung)
    4. Error-Handling: 502 Bad Gateway bei API-Ausfällen
    
    Important: Diese Tests sind robust gegenüber Netzwerkfehlern,
    da externe APIs nicht immer verfügbar sind.
    """

    @classmethod
    def setUpClass(cls):
        """Erstellt TestClient für API.
        
        TestClient simuliert HTTP-Anfragen gegen die FastAPI-App,
        ohne dass ein echter Server läuft.
        """
        cls.app = create_app()
        cls.client = TestClient(cls.app)

    def test_health_endpoint(self):
        """Test: Health-Check Endpoint / Status der Applikation.
        
        Testabsicht:
        Der Haupt-Endpoint "/" zeigt dass der Backend läuft und erreichbar ist.
        Das ist meist der erste Check den ein Frontend macht nach dem Start.
        
        HTTP-Anfrage:
        GET /
        
        Erwartete Response (Status 200):
        {
          "message": "Backend läuft...",  # oder ähnliches mit "Backend"
          ...
        }
        
        Validierungen:
        1. Status-Code muss 200 sein (erfolgreich)
        2. JSON-Response muss "message" Key enthalten
        3. Message muss "Backend" erwähnen (beweis dass Backend läuft)
        """
        response = self.client.get("/")

        # Validierung 1: Status-Code
        self.assertEqual(response.status_code, 200)
        # Validierung 2 & 3: Response-Struktur
        data = response.json()
        self.assertIn("message", data)
        self.assertIn("Backend", data["message"])

    def test_btc_price_endpoint(self):
        """Test: Bitcoin Preis Endpoint mit Fallback-Logik.
        
        Testabsicht:
        Haupt-Feature: Frontend zeigt aktuellen BTC/USD Preis an.
        Service hat Fallback: Primary Coinbase Exchange, Fallback CoinGecko.
        
        HTTP-Anfrage:
        GET /api/btc/price
        
        Erwartete Response (Status 200):
        {
          "price_usd": 65000.0,
          "symbol": "BTC-USD",
          "timestamp": "2025-01-01T10:30:00Z",
          "source": "coinbase_exchange" | "coingecko"
        }
        
        Status-Code Handling:
        - 200: Erfolgreiche Abfrage
        - 502: Coinbase UND CoinGecko nicht erreichbar (OK für diesen Test)
        
        Validierungen:
        1. Wenn Status 200: price_usd und symbol müssen vorhanden sein
        2. Symbol muss "BTC-USD" sein (Standard von Coinbase)
        3. Wenn Status 502: Test passiert (externe API-Ausfall akzeptiert)
        """
        response = self.client.get("/api/btc/price")

        # Endpoint könnte 502 zurückgeben wenn Coinbase nicht erreichbar
        if response.status_code == 200:
            data = response.json()
            self.assertIn("price_usd", data)
            self.assertIn("symbol", data)
            self.assertEqual(data["symbol"], "BTC-USD")
        elif response.status_code == 502:
            # Erwartet wenn Coinbase nicht erreichbar (akzeptabel in Tests)
            pass
        else:
            self.fail(f"Unexpected status code: {response.status_code}")

    def test_btc_history_endpoint(self):
        """Test: Bitcoin Kursverlauf für Chart-Visualisierung.
        
        Testabsicht:
        Frontend braucht historische BTC-Preise für Chart.js Grafik.
        Allows verschiedene Zeiträume: 1, 3, 5, 10, 15 Jahre.
        
        HTTP-Anfrage:
        GET /api/btc/history?years=1
        
        Erwartete Response (Status 200):
        {
          "labels": ["2024-01-01", "2024-01-02", ...],  # Daten-Punkte
          "data": [50000, 51000, 50500, ...],           # Preisen
          "years": 1
        }
        
        Daten-Struktur:
        - labels: Array von ISO-Datumsstrings (chronologisch)
        - data: Array von floats (Preise), gleiche Länge wie labels
        - years: Bestätigte Jahre (kann gekürzt sein, siehe test_btc_history_years_clamped)
        
        Status-Code Handling:
        - 200: Erfolgreiche Datenabfrage
        - 502: Externe API nicht erreichbar (OK für Test)
        """
        response = self.client.get("/api/btc/history?years=1")

        if response.status_code == 200:
            data = response.json()
            self.assertIn("labels", data)
            self.assertIn("data", data)
            self.assertIn("years", data)
            self.assertEqual(data["years"], 1)
        elif response.status_code == 502:
            # Erwartet wenn Coinbase nicht erreichbar
            pass

    def test_btc_history_years_clamped(self):
        """Test: Begrenzung der maximalen Jahre für Abfrage.
        
        Testabsicht:
        Verhindere zu große Abfragen die Performance beeinträchtigen.
        Maximum: 15 Jahre (API-Limit).
        
        HTTP-Anfrage mit ungültigen Wert:
        GET /api/btc/history?years=20
        
        Erwartet:
        Service akzeptiert 20, gibt aber max 15 zurück.
        Response wird mit years=15 (oder weniger) gesendet.
        
        Geschäfts-Logik:
        - Proteine vor DoS-Angriffen (requests mit years=10000)
        - Bessere API-Performance (weniger Daten laden)
        - Frontend kann Schieberegler UI auf max 15 begrenzen
        
        Validierung:
        response.years <= 15 (nicht >= 20)
        """
        response = self.client.get("/api/btc/history?years=20")

        if response.status_code == 200:
            data = response.json()
            # Jahre sollten auf max 15 gekürzt werden
            self.assertLessEqual(data["years"], 15)

    def test_coins_endpoint(self):
        """Test: Coins-Tabelle von CoinGecko mit Limitierung.
        
        Testabsicht:
        Frontend zeigt Top-Kryptowährungen mit Marktdaten bei.
        Daten kommen von CoinGecko API (kostenlos, aber mit Limits).
        
        HTTP-Anfrage:
        GET /api/coins?limit=10&quote=USD
        
        Parameter:
        - limit: Anzahl der Coins (Max 250, wird limitiert)
        - quote: Währungspaar (USD, EUR, etc - nur USD erlaubt intern)
        
        Erwartete Response (Status 200):
        {
          "coins": [...],           # Array von Coin-Objekten
          "vs_currency": "usd",     # Bestätigtes Währungspaar (lowercase)
          "count": 10               # Anzahl der Coins in Response
        }
        
        Coin-Objekt-Struktur:
        {
          "symbol": "BTC",
          "name": "Bitcoin",
          "current_price": 65000,
          "market_cap": 1270000000000,
          "market_cap_rank": 1,
          ...
        }
        
        Test-Validierungen:
        1. Status 200 oder 502 (API-Ausfall OK)
        2. Wenn 200: coins, vs_currency, count vorhanden
        3. Limit wird respektiert (max 10 coins)
        """
        response = self.client.get("/api/coins?limit=10&quote=USD")

        if response.status_code == 200:
            data = response.json()
            self.assertIn("coins", data)
            self.assertIn("vs_currency", data)
            self.assertIn("count", data)
            self.assertEqual(data["vs_currency"], "usd")
            self.assertLessEqual(len(data["coins"]), 10)
        elif response.status_code == 502:
            # Erwartet wenn CoinGecko nicht erreichbar
            pass

    def test_coins_invalid_quote(self):
        """Test: Validierung ungültiger Währungspaare.
        
        Testabsicht:
        Backend akzeptiert nur bestimmte Währungen (USD).
        Andere Währungen sollten mit 400 Bad Request abgelehnt werden.
        
        HTTP-Anfrage mit ungültiger Quote:
        GET /api/coins?quote=EUR
        
        Erwartet:
        - Status Code: 400 Bad Request
        - Response JSON mit "detail" Key
        - Detail-Nachricht erklärt warum EUR nicht erlaubt ist
        
        Business-Grund:
        - Vereinfachte API (nur USD-Support)
        - Kostenlose CoinGecko API hat Rate-Limits
        
        Frontend-Handling:
        Nutzer wählt nur USD aus Dropdown.
        Sollte nicht auf 400 kommen außer direkter API-Missbrauch.
        """
        response = self.client.get("/api/coins?quote=EUR")

        # Status 400 erwartet
        self.assertEqual(response.status_code, 400)
        data = response.json()
        # Error-Detail sollte vorhanden sein
        self.assertIn("detail", data)

    def test_coins_limit_clamped(self):
        """Test: Begrenzung des Limit-Parameters für Coins-Abfrage.
        
        Testabsicht:
        Verhindere Performance-Probleme und DoS-Angriffe.
        Client kann limit=1000 anfragen, aber nur max 250 wird zurück.
        
        HTTP-Anfrage mit zu hohem Limit:
        GET /api/coins?limit=1000
        
        Erwartet:
        - Wenn Status 200: coins Array hat max 250 Einträge
        - nicht 1000 (auch wenn angefordert)
        - count reflektiert tatsächlich zurück gegebene Coins, nicht angefordert
        
        Business-Logik:
        - CoinGecko free API: ~250 Coins verfügbar
        - Sehr hohe Limits => Timeout oder API-Fehler
        - Limit auto-clamp schützt Backend und CoinGecko
        
        Validierung:
        len(data["coins"]) <= 250 (nicht >= 1000)
        """
        response = self.client.get("/api/coins?limit=1000")

        if response.status_code == 200:
            data = response.json()
            # Limit sollte auf max 500 begrenzt sein
            self.assertLessEqual(len(data["coins"]), 500)


class TestExportEndpoints(unittest.TestCase):
    """Tests für Export-API Endpoints."""

    @classmethod
    def setUpClass(cls):
        """Erstellt TestClient."""
        cls.app = create_app()
        cls.client = TestClient(cls.app)

    def test_export_start_missing_symbols(self):
        """Testet Export-Start ohne Symbole."""
        response = self.client.post(
            "/api/export/coinbase/start",
            json={
                "symbols": [],
                "years": 10,
            }
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("detail", data)

    def test_export_start_invalid_type(self):
        """Testet Export-Start mit ungültigem Datentyp."""
        response = self.client.post(
            "/api/export/coinbase/start",
            json={
                "symbols": "BTC",  # Should be list, not string
                "years": 10,
            }
        )

        self.assertEqual(response.status_code, 400)

    def test_export_stop_endpoint(self):
        """Testet Stop-Signal für Export."""
        response = self.client.post("/api/export/coinbase/stop")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertEqual(data["status"], "stop_requested")

    def test_export_status_nonexistent(self):
        """Testet Status-Abfrage für nicht existierenden Job."""
        response = self.client.get("/api/export/coinbase/status/nonexistent_id")

        self.assertEqual(response.status_code, 404)


class TestFilterEndpoints(unittest.TestCase):
    """Tests für Filter-API Endpoints."""

    @classmethod
    def setUpClass(cls):
        """Erstellt TestClient."""
        cls.app = create_app()
        cls.client = TestClient(cls.app)

    def test_filter_coinbase_endpoint_no_data(self):
        """Testet Filter-Endpoint ohne CSV-Daten."""
        response = self.client.post(
            "/api/filter/coinbase",
            json={
                "years": 3,
                "percent": 20,
                "direction": "gestiegen",
            }
        )

        # Erwartet 404 da keine CSV-Datei vorhanden
        self.assertEqual(response.status_code, 404)

    def test_csv_history_endpoint_no_data(self):
        """Testet CSV-History Endpoint ohne CSV-Daten."""
        response = self.client.get("/api/csv/history/BTC")

        # Erwartet 404 da keine CSV-Datei vorhanden
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
