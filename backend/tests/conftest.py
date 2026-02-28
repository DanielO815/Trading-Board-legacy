"""
Pytest Konfiguration und Fixtures für Backend-Tests.

Definiert gemeinsame Test-Setup und Mock-Objekte.
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def temp_export_dir():
    """Erstellt und räumt temporäres Exportverzeichnis auf."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_app():
    """Erstellt TestApp-Instanz für Integrationstests."""
    app = create_app()
    return app


@pytest.fixture
def test_client(test_app):
    """Erstellt TestClient für API-Tests."""
    return TestClient(test_app)


@pytest.fixture
def sample_prices():
    """Bereitstellung von Beispiel-Preisdaten für Tests."""
    from datetime import date

    return {
        "BTC": [
            (date(2023, 1, 1), 16500.0),
            (date(2023, 6, 1), 25000.0),
            (date(2024, 1, 1), 40000.0),
            (date(2024, 6, 1), 60000.0),
        ],
        "ETH": [
            (date(2023, 1, 1), 1200.0),
            (date(2023, 6, 1), 1500.0),
            (date(2024, 1, 1), 2000.0),
            (date(2024, 6, 1), 3500.0),
        ],
    }
