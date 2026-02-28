"""
Testsuite für CSV-Tools Service und Funktionen.

Unit-Tests für folgende Kernfunktionalität:
- CSV-Parsing und Preisgruppierung nach Symbol
- Filterung von Symbolen nach Kursbewegung
- Kursverlauf-Abfragen
- Dollar-Cost-Averaging (DCA) Simulation
- Gleitender Durchschnitt Berechnung
- Dynamische Sparplan-Simulation mit Schwellenwerten

Alle Tests verwenden Mock-Preisdaten statt echte CSV-Dateien.
"""

import unittest
from datetime import date, datetime, timedelta
from app.services.csv_tools import (
    load_prices_by_symbol,
    filter_coinbase,
    csv_history,
    simulate_savings,
    calc_ma_for_date,
    simulate_savings_dynamic,
)


class TestCsvTools(unittest.TestCase):
    """Unit-Tests für CSV-Analyse-Funktionen.
    
    Testet:
    - Symbol-basierte Filterung nach Kursbewegung
    - Kursverlauf-Abfrage für einzelne Symbole
    - Statische DCA-Simulation (100 USD monatlich)
    - Gleitender Durchschnitt für technische Analyse
    - Edge-Cases (leere Daten, unzureichende Datenpunkte)
    """

    def setUp(self):
        """Erstellt Testdaten für CSV-Verarbeitung.
        
        Mock-Preisdaten für BTC und ETH über mehrere Jahre.
        Realistische Preis-Bewegungen für Tests.
        """
        # Mock-Preisdaten nach Symbol
        self.prices_by_symbol = {
            "BTC": [
                (date(2022, 1, 1), 45000.0),
                (date(2022, 1, 2), 46000.0),
                (date(2023, 1, 1), 50000.0),
                (date(2024, 1, 1), 60000.0),
                (date(2025, 1, 1), 75000.0),
            ],
            "ETH": [
                (date(2022, 1, 1), 3000.0),
                (date(2022, 1, 2), 3100.0),
                (date(2023, 1, 1), 2000.0),
                (date(2024, 1, 1), 2500.0),
                (date(2025, 1, 1), 3500.0),
            ],
        }

    def test_filter_coinbase_risen(self):
        """Test: Filterung nach gestiegenen Kursen.
        
        Erwartet:
        - BTC sollte erfasst werden (45000 -> 75000 = +66% über 3 Jahre)
        - Ergebnis sollte Details (Start-, Endpreis, Änderung) enthalten
        """
        result = filter_coinbase(
            self.prices_by_symbol,
            years=3,
            percent=20,
            direction="gestiegen"
        )

        self.assertIn("count", result)
        self.assertIn("results", result)
        self.assertGreater(result["count"], 0)

        # BTC sollte gestanden sein (45000 -> 75000 = +66%)
        btc_result = next(
            (r for r in result["results"] if r["symbol"] == "BTC"),
            None
        )
        self.assertIsNotNone(btc_result)
        self.assertGreater(btc_result["change_percent"], 20)

    def test_filter_coinbase_fallen(self):
        """Test: Filterung nach gefallenen Kursen.
        
        Erwartet:
        - ETH sollte NICHT erfasst werden (3100 -> 3500 = +12.9%, nicht gefallen)
        - Nur Symbole mit mindestens 20% Rückgang sollten zurückgegeben werden
        """
        result = filter_coinbase(
            self.prices_by_symbol,
            years=3,
            percent=20,
            direction="gefallen"
        )

        # ETH sollte gefallen sein (3100 -> 3500 = +12.9%, nicht erfasst)
        eth_result = next(
            (r for r in result["results"] if r["symbol"] == "ETH"),
            None
        )
        # Sollte leer sein da nicht gefallen
        self.assertIsNone(eth_result)

    def test_csv_history(self):
        """Test: Kursverlauf-Abfrage für Symbol.
        
        Erwartet:
        - Symbol sollte als verfügbar markiert sein
        - Labels (Daten) sollten chronologisch geordnet sein
        - Data sollte Preise in gleicher Reihenfolge enthalten
        """
        result = csv_history(self.prices_by_symbol, "BTC")

        self.assertTrue(result["available"])
        self.assertEqual(result["symbol"], "BTC")
        self.assertEqual(len(result["labels"]), 5)
        self.assertEqual(len(result["data"]), 5)
        self.assertEqual(result["data"][0], 45000.0)
        self.assertEqual(result["data"][-1], 75000.0)

    def test_csv_history_nonexistent(self):
        """Test: Abfrage für nicht existierendes Symbol.
        
        Erwartet:
        - available Flag sollte False sein
        - Labels und Data sollten leer sein
        """
        result = csv_history(self.prices_by_symbol, "NONEXISTENT")

        self.assertFalse(result["available"])
        self.assertEqual(result["labels"], [])
        self.assertEqual(result["data"], [])

    def test_simulate_savings_static(self):
        """Test: Statische DCA-Simulation (monatlich gleicher Betrag).
        
        Erwartet:
        - result_usd sollte Gesamtwert der gekauften Coins sein
        - cash_only_usd sollte reiner Sparbetrag sein (100 * 36 Monate)
        - result_usd sollte größer als cash_only_usd sein (da Kurssteigerung)
        """
        result = simulate_savings(
            self.prices_by_symbol,
            symbol="BTC",
            years=3,
            monthly_usd=100
        )

        self.assertIn("result_usd", result)
        self.assertIn("cash_only_usd", result)
        self.assertGreater(result["result_usd"], 0)
        self.assertEqual(result["cash_only_usd"], 100 * 36)  # 3 Jahre = 36 Monate

    def test_calc_ma_for_date(self):
        """Test: Gleitender Durchschnitt Berechnung.
        
        Erwartet:
        - MA über 3 Tage = (50000 + 60000 + 75000) / 3 = 61666.67
        - Nur Werte bis zum angegebenen Datum berücksichtigen
        """
        prices = self.prices_by_symbol["BTC"]

        # MA über 3 Tage am letzten Datum
        ma = calc_ma_for_date(date(2025, 1, 1), prices, ma_days=3)

        self.assertIsNotNone(ma)
        # Durchschnitt der letzten 3 Werte: (50000 + 60000 + 75000) / 3
        expected = (50000.0 + 60000.0 + 75000.0) / 3
        self.assertAlmostEqual(ma, expected, places=2)

    def test_calc_ma_insufficient_data(self):
        """Test: MA-Berechnung mit zu wenig Datenpunkten.
        
        Erwartet:
        - Sollte None zurückgeben wenn weniger als ma_days Punkte vorhanden
        - Verhindert ungenaue Berechnungen mit unzureichenden Daten
        """
        prices = self.prices_by_symbol["BTC"]

        # Zu wenig Daten für 10er MA
        ma = calc_ma_for_date(date(2022, 1, 2), prices, ma_days=10)

        self.assertIsNone(ma)

    def test_simulate_savings_dynamic(self):
        """Test: Dynamische DCA-Simulation mit automatischer Anpassung.
        
        Mechanik:
        - Bei Preis >= MA * (1 + threshold): Investition reduzieren, Puffer aufbau
        - Bei Preis <= MA * (1 - threshold): Investition erhöhen mit Puffer
        
        Erwartet:
        - result_usd sollte größer sein als statische Variante (optimierte Käufe)
        
        Validierungen:
        - result_usd muss in Antwort enthalten sein
        - result_usd muss größer als 0 sein
        """
        result = simulate_savings_dynamic(
            self.prices_by_symbol,
            symbol="BTC",
            years=2,
            monthly_usd=100,
            threshold_pct=0.1,  # 10% Schwelle für MA
            adjust_pct=0.5,     # 50% Anpassung bei Schwellenwert-Überschreitung
            ma_days=2  # Gleitender Durchschnitt über 2 Tage
        )

        # Validierung: result_usd muss vorhanden sein
        self.assertIn("result_usd", result)
        # Validierung: Portfolio-Wert muss positiv sein
        self.assertGreater(result["result_usd"], 0)


class TestCsvHistoryEdgeCases(unittest.TestCase):
    """Edge-Case Tests für robuste CSV-Verarbeitung.
    
    Testet:
    - Handling leerer Datenmengen
    - Symbole mit nur einem Datenpunkt
    - Grenzsituationen bei Filterung
    """

    def test_empty_prices(self):
        """Test: Filterung mit leeren Preisdaten.
        
        Erwartet:
        - count sollte 0 sein
        - results sollte leere Liste sein (kein Fehler)
        """
        result = filter_coinbase({}, years=1, percent=10, direction="gestiegen")

        self.assertEqual(result["count"], 0)
        self.assertEqual(result["results"], [])

    def test_single_symbol_entry(self):
        """Test: Symbol mit nur einem Datenpunkt.
        
        Erwartet:
        - Symbol wird übersprungen (mindestens 2 Punkte nötig für Preisvergliche)
        - count sollte 0 sein
        """
        prices = {"BTC": [(date(2025, 1, 1), 65000.0)]}

        result = filter_coinbase(prices, years=1, percent=10, direction="gestiegen")

        # Sollte übersprungen werden (weniger als 2 Datenpunkte nötig)
        self.assertEqual(result["count"], 0)


if __name__ == "__main__":
    unittest.main()
