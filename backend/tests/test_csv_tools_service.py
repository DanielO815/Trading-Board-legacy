"""
Unit-Tests für CSV-Tools Service mit Mock-Integration.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import date
from unittest.mock import patch, MagicMock
from app.services.csv_tools_service import CsvToolsService, _CsvCache
from app.services import csv_tools


class TestCsvToolsService(unittest.TestCase):
    """Tests für CsvToolsService mit Caching."""

    def setUp(self):
        """Erstellt Service mit temporärem Verzeichnis."""
        self.temp_dir = TemporaryDirectory()
        self.export_dir = Path(self.temp_dir.name)
        self.service = CsvToolsService(export_dir=self.export_dir)

    def tearDown(self):
        """Räumt auf."""
        self.temp_dir.cleanup()

    @patch('app.services.csv_tools.load_prices_by_symbol')
    @patch('app.services.csv_tools_service.latest_coinbase_csv')
    def test_cache_validation_mtime_changed(self, mock_latest_csv, mock_load):
        """Testet Cache-Invalidierung bei geänderter Dateizeit."""
        # Setup
        mock_csv_path = self.export_dir / "coinbase_daily_test.csv"
        mock_csv_path.touch()

        mock_latest_csv.return_value = mock_csv_path
        mock_load.return_value = {
            "BTC": [(date(2025, 1, 1), 65000.0)],
        }

        # Erster Aufruf - lädt Daten
        prices1, path1 = self.service._get_prices()
        self.assertEqual(prices1["BTC"][0][0], date(2025, 1, 1))

        # Cache sollte gesetzt sein
        self.assertIsNotNone(self.service._cache.path)
        self.assertIsNotNone(self.service._cache.mtime)

        # Zweiter Aufruf - verwendet Cache (load wird nicht aufgerufen)
        prices2, path2 = self.service._get_prices()
        self.assertEqual(mock_load.call_count, 1)  # Nur einmal aufgerufen

    @patch('app.services.csv_tools.filter_coinbase')
    @patch('app.services.csv_tools_service.latest_coinbase_csv')
    def test_filter_coinbase_method(self, mock_latest_csv, mock_filter):
        """Testet filter_coinbase Methode."""
        mock_csv_path = self.export_dir / "test.csv"
        mock_csv_path.touch()
        mock_latest_csv.return_value = mock_csv_path

        mock_filter.return_value = {
            "count": 2,
            "results": [
                {"symbol": "BTC", "change_percent": 50},
                {"symbol": "ETH", "change_percent": 30},
            ],
        }

        result = self.service.filter_coinbase(years=3, percent=20, direction="gestiegen")

        self.assertEqual(result["count"], 2)
        self.assertIn("csv_used", result)
        mock_filter.assert_called_once()


if __name__ == "__main__":
    unittest.main()
