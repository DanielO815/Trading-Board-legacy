from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from ...services.csv_tools_service import CsvToolsService

router = APIRouter()


def get_csv_tools_service(request: Request) -> CsvToolsService:
    """
    Dependency: Ruft CsvToolsService aus Applikationszustand ab.

    Args:
        request: HTTP-Request mit Applikationszustand.

    Returns:
        CsvToolsService-Instanz.
    """
    return request.app.state.csv_tools_service


@router.post("/api/filter/coinbase")
def filter_coinbase_ep(
    payload: Dict[str, Any] = Body(...),
    csv_svc: CsvToolsService = Depends(get_csv_tools_service),
):
    """
    Endpoint: Filtert Symbole nach Preisänderungen in Zeitraum und Richtung.

    Request Body:
        - years: Zeitraum in Jahren (optional, Standard: 3).
        - percent: Mindestprozentsatz (optional, Standard: 20).
        - direction: "gestiegen" oder "gefallen" (optional, Standard: "gestiegen").

    Returns:
        Filterergebnisse mit Anzahl und Details gefundener Symbole.
    """
    years = float(payload.get("years", 3))
    percent = float(payload.get("percent", 20))
    direction = payload.get("direction", "gestiegen")
    return csv_svc.filter_coinbase(years=years, percent=percent, direction=direction)


@router.get("/api/csv/history/{symbol}")
def csv_history_ep(
    symbol: str,
    csv_svc: CsvToolsService = Depends(get_csv_tools_service),
):
    """
    Endpoint: Ruft Kursverlauf für einzelnes Symbol ab.

    Path Parameter:
        symbol: Krypto-Symbol (z.B. "BTC").

    Returns:
        Kursverlaufsdaten mit Datum und Preis-Einträgen.
    """
    return csv_svc.history(symbol)


@router.post("/api/simulate/savings")
def simulate_savings_ep(
    payload: Dict[str, Any] = Body(...),
    csv_svc: CsvToolsService = Depends(get_csv_tools_service),
):
    """
    Endpoint: Simuliert Dollar-Cost-Averaging-Strategie.

    Request Body:
        - symbol: Krypto-Symbol (erforderlich).
        - years: Sparzeitraum in Jahren (optional, Standard: 1).
        - monthly_usd: Monatlicher Sparbetrag in USD (erforderlich, > 0).

    Returns:
        Simulationsergebnis mit Gesamtwert und reinem Sparaufwand.

    Raises:
        HTTPException: Bei ungültigen Parametern (Status 400).
    """
    symbol = (payload.get("symbol", "") or "").upper()
    years = float(payload.get("years", 1))
    monthly_usd = float(payload.get("monthly_usd", 0))

    if not symbol or monthly_usd <= 0:
        raise HTTPException(status_code=400, detail="Ungültige Parameter")

    return csv_svc.simulate_savings(symbol=symbol, years=years, monthly_usd=monthly_usd)


@router.post("/api/simulate/savings_dynamic")
def simulate_savings_dynamic_ep(
    payload: Dict[str, Any] = Body(...),
    csv_svc: CsvToolsService = Depends(get_csv_tools_service),
):
    """
    Endpoint: Simuliert dynamische Sparstrategie mit gleitendem Durchschnitt.

    Request Body:
        - symbol: Krypto-Symbol (erforderlich).
        - years: Sparzeitraum in Jahren (erforderlich).
        - monthly_usd: Basis-Monatsbetrag in USD (erforderlich).
        - threshold_pct: Schwelle für Anpassung in Prozent (erforderlich).
        - adjust_pct: Anpassungsfaktor in Prozent (erforderlich).
        - ma_days: Tage für gleitenden Durchschnitt (erforderlich).

    Returns:
        Simulationsergebnis mit dynamisch angepasstem Gesamtwert.
    """
    symbol = payload["symbol"].upper()
    years = float(payload["years"])
    monthly_usd = float(payload["monthly_usd"])
    threshold_pct = float(payload["threshold_pct"]) / 100.0
    adjust_pct = float(payload["adjust_pct"]) / 100.0
    ma_days = int(payload["ma_days"])

    return csv_svc.simulate_savings_dynamic(
        symbol=symbol,
        years=years,
        monthly_usd=monthly_usd,
        threshold_pct=threshold_pct,
        adjust_pct=adjust_pct,
        ma_days=ma_days,
    )
