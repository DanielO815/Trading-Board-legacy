from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from fastapi import HTTPException

from ..core.config import EXPORT_DIR_NAME


def get_export_dir() -> Path:
    """
    Ruft oder erstellt Standard-Exportverzeichnis ab.

    Nutzt Environment-Variable EXPORT_DIR zur Konfiguration oder Standard "exports".

    Returns:
        Pfad zum Exportverzeichnis (erstellt bei Bedarf).
    """
    backend_root = Path(__file__).resolve().parents[2]  # .../backend/app/infra -> .../backend
    export_dir = backend_root / EXPORT_DIR_NAME
    export_dir.mkdir(exist_ok=True)
    return export_dir


def cleanup_old_coinbase_exports(export_dir: Path) -> None:
    """
    Löscht alle vorhandenen Coinbase-Exportdateien im Verzeichnis.

    Args:
        export_dir: Verzeichnis für Bereinigung.
    """
    for f in export_dir.glob("coinbase_daily_*.csv"):
        try:
            f.unlink()
        except Exception:
            pass


def make_coinbase_export_filename(now: datetime | None = None) -> str:
    """
    Generiert standardisierte Dateiname für Coinbase-Exportdatei.

    Args:
        now: Datetime für Dateiname oder None für aktuelles UTC-Zeit.

    Returns:
        Dateiname im Format "coinbase_daily_YYYY-MM-DD_HHMMSS.csv".
    """
    now = now or datetime.now(timezone.utc)
    return f"coinbase_daily_{now.strftime('%Y-%m-%d_%H%M%S')}.csv"


def latest_coinbase_csv(export_dir: Path) -> Path:
    """
    Findet neueste Coinbase-Exportdatei nach Änderungszeit.

    Args:
        export_dir: Verzeichnis für Suche.

    Returns:
        Pfad zur neuesten coinbase_daily*.csv Datei.

    Raises:
        HTTPException: Wenn keine Exportdatei gefunden wird (Status 404).
    """
    files = sorted(
        export_dir.glob("coinbase_daily*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise HTTPException(status_code=404, detail="Keine Coinbase-CSV gefunden")
    return files[0]
