from __future__ import annotations

import csv
import uuid
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .coinbase import cb_get_products, cb_daily_closes, COINBASE_EXPORT_SLEEP


class ExportService:
    """
    Verwaltet Coinbase-Export-Jobs und deren Verwaltung im Memory mit gekapselt
    strukturiertem State statt globalen Variablen.
    """

    def __init__(self, export_dir: Path):
        """
        Initialisiert den Export-Service mit Exportverzeichnis.

        Args:
            export_dir: Pfad zum Verzeichnis für Export-Dateien.
        """
        self.export_dir = export_dir
        self.jobs: dict[str, dict[str, Any]] = {}
        self._stop_requested: bool = False

    def stop_coinbase_export(self) -> None:
        """
        Signalisiert Stopp-Anforderung für laufende Export-Operationen.
        """
        self._stop_requested = True

    def get_status(self, job_id: str) -> dict[str, Any] | None:
        """
        Ruft Status eines Export-Jobs mit Prozentfortschritt ab.

        Args:
            job_id: Eindeutige Job-Kennung.

        Returns:
            Wörterbuch mit Job-Status, Fortschritt und Metadaten oder None wenn nicht gefunden.
        """
        job = self.jobs.get(job_id)
        if not job:
            return None
        total = int(job.get("total") or 0)
        done = int(job.get("done") or 0)
        percent = round((done / total * 100.0), 1) if total else 0.0
        return {**job, "percent": percent}

    async def start_coinbase_export(self, symbols: list[str], years: int) -> str:
        """
        Startet asynchronen Coinbase-Export-Job für angegebene Symbole.

        Args:
            symbols: Liste von Krypto-Symbolen (z.B. ['BTC', 'ETH']).
            years: Anzahl der Jahre für Datenabfrage (begrenzt auf 1-15).

        Returns:
            Eindeutige Job-Kennung für Statusabfragen.

        Raises:
            ValueError: Wenn keine gültigen Symbole vorhanden sind.
        """
        years = max(1, min(int(years), 15))
        symbols = [s.strip().upper() for s in symbols if s and s.strip()]
        symbols = list(dict.fromkeys(symbols))
        if not symbols:
            raise ValueError("symbols ist leer")

        job_id = uuid.uuid4().hex[:10]
        self.jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "total": len(symbols),
            "done": 0,
            "errors": 0,
            "current": None,
            "years": years,
            "filename": None,
            "saved_to": None,
            "fail_reason": None,
        }

        asyncio.create_task(self._run_coinbase_export_job(job_id, symbols, years))
        return job_id

    async def _run_coinbase_export_job(self, job_id: str, symbols: list[str], years: int) -> None:
        """
        Führt Coinbase-Export im Hintergrund aus und speichert Daten in CSV-Datei.

        Args:
            job_id: Eindeutige Job-Kennung.
            symbols: Liste von Krypto-Symbolen für Export.
            years: Zeitraum in Jahren für Datenabfrage.
        """
        from ..infra.storage import cleanup_old_coinbase_exports, make_coinbase_export_filename

        # Alte Coinbase-CSV-Dateien löschen (wie legacy)
        cleanup_old_coinbase_exports(self.export_dir)

        self._stop_requested = False
        job = self.jobs[job_id]
        job["status"] = "running"
        job["total"] = len(symbols)
        job["done"] = 0
        job["errors"] = 0
        job["current"] = None

        filename = make_coinbase_export_filename()
        out_path = self.export_dir / filename
        job["filename"] = filename
        job["saved_to"] = str(out_path)

        headers = {"Accept": "application/json", "User-Agent": "onepager-fastapi/coinbase-export"}
        timeout = httpx.Timeout(30.0, connect=15.0)

        try:
            async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
                products = await cb_get_products(client)

                # map BASE -> product_id (USD, online)
                usd_map: dict[str, str] = {}
                for p in products:
                    if (p.get("quote_currency") == "USD") and (p.get("status") == "online"):
                        base = (p.get("base_currency") or "").upper()
                        pid = p.get("id")
                        if base and pid and base not in usd_map:
                            usd_map[base] = pid

                with open(out_path, "w", encoding="utf-8", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["symbol", "product_id", "date_utc", "close_usd", "error"])

                    for i, sym in enumerate(symbols, start=1):
                        if self._stop_requested:
                            break

                        job["current"] = sym
                        pid = usd_map.get(sym)

                        if not pid:
                            w.writerow([sym, "", "", "", "NO_COINBASE_USD_PAIR"])
                            job["errors"] += 1
                            job["done"] = i
                            continue

                        try:
                            closes = await cb_daily_closes(client, pid, years=years)
                            if not closes:
                                w.writerow([sym, pid, "", "", "NO_DATA"])
                                job["errors"] += 1
                            else:
                                for day, close in closes:
                                    w.writerow([sym, pid, day, close, ""])
                        except Exception as e:
                            w.writerow([sym, pid, "", "", str(e)])
                            job["errors"] += 1

                        job["done"] = i
                        await asyncio.sleep(COINBASE_EXPORT_SLEEP)

            job["status"] = "done"
        except Exception as e:
            job["status"] = "failed"
            job["fail_reason"] = str(e)
        finally:
            self._stop_requested = False
