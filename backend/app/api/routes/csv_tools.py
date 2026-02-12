from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from ...services.csv_tools_service import CsvToolsService

router = APIRouter()


def get_csv_tools_service(request: Request) -> CsvToolsService:
    return request.app.state.csv_tools_service


@router.post("/api/filter/coinbase")
def filter_coinbase_ep(
    payload: Dict[str, Any] = Body(...),
    csv_svc: CsvToolsService = Depends(get_csv_tools_service),
):
    years = float(payload.get("years", 3))
    percent = float(payload.get("percent", 20))
    direction = payload.get("direction", "gestiegen")
    return csv_svc.filter_coinbase(years=years, percent=percent, direction=direction)


@router.get("/api/csv/history/{symbol}")
def csv_history_ep(
    symbol: str,
    csv_svc: CsvToolsService = Depends(get_csv_tools_service),
):
    return csv_svc.history(symbol)


@router.post("/api/simulate/savings")
def simulate_savings_ep(
    payload: Dict[str, Any] = Body(...),
    csv_svc: CsvToolsService = Depends(get_csv_tools_service),
):
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
