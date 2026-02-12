from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..infra.storage import latest_coinbase_csv
from . import csv_tools


@dataclass
class _CsvCache:
    path: Path | None = None
    mtime: float | None = None
    prices_by_symbol: dict[str, list[tuple]] | None = None


class CsvToolsService:
    """
    - Findet die neueste Coinbase-CSV
    - Parst sie nur neu, wenn sich Datei/mtime geändert hat (Cache)
    - Ruft die bestehende Legacy-Logik aus services/csv_tools.py auf
    """

    def __init__(self, export_dir: Path):
        self.export_dir = export_dir
        self._cache = _CsvCache()

    def _get_prices(self) -> tuple[Path, dict[str, list[tuple]]]:
        csv_path = latest_coinbase_csv(self.export_dir)
        mtime = csv_path.stat().st_mtime

        if (
            self._cache.path == csv_path
            and self._cache.mtime == mtime
            and self._cache.prices_by_symbol is not None
        ):
            return csv_path, self._cache.prices_by_symbol

        prices_by_symbol = csv_tools.load_prices_by_symbol(csv_path)
        self._cache = _CsvCache(path=csv_path, mtime=mtime, prices_by_symbol=prices_by_symbol)
        return csv_path, prices_by_symbol

    # --- Methoden für Routes ---
    def filter_coinbase(self, years: float, percent: float, direction: str) -> dict[str, Any]:
        csv_path, prices = self._get_prices()
        out = csv_tools.filter_coinbase(prices, years=years, percent=percent, direction=direction)
        out["csv_used"] = csv_path.name
        return out

    def history(self, symbol: str) -> dict[str, Any]:
        _, prices = self._get_prices()
        return csv_tools.csv_history(prices, symbol)

    def simulate_savings(self, symbol: str, years: float, monthly_usd: float) -> dict[str, Any]:
        _, prices = self._get_prices()
        return csv_tools.simulate_savings(prices, symbol, years, monthly_usd)

    def simulate_savings_dynamic(
        self,
        symbol: str,
        years: float,
        monthly_usd: float,
        threshold_pct: float,
        adjust_pct: float,
        ma_days: int,
    ) -> dict[str, Any]:
        _, prices = self._get_prices()
        return csv_tools.simulate_savings_dynamic(
            prices_by_symbol=prices,
            symbol=symbol,
            years=years,
            monthly_usd=monthly_usd,
            threshold_pct=threshold_pct,
            adjust_pct=adjust_pct,
            ma_days=ma_days,
        )
