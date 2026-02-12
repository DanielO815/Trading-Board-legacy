from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_prices_by_symbol(csv_path: Path) -> dict[str, list[tuple[date, float]]]:
    """
    Lädt CSV und gruppiert Preise nach Symbol.
    Rückgabe: { "BTC": [(date, price), ...], ... }
    (Legacy: ignoriert Zeilen mit error)
    """
    data: dict[str, list[tuple[date, float]]] = {}

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("error"):
                continue
            try:
                sym = (row["symbol"] or "").upper()
                d = datetime.fromisoformat(row["date_utc"]).date()
                price = float(row["close_usd"])
                data.setdefault(sym, []).append((d, price))
            except Exception:
                continue

    for sym in data:
        data[sym].sort(key=lambda x: x[0])

    return data


def filter_coinbase(
    prices_by_symbol: dict[str, list[tuple[date, float]]],
    years: float = 3,
    percent: float = 20,
    direction: str = "gestiegen",
) -> dict[str, Any]:
    """
    Legacy-Filter:
    - Zeitraum: years * 365 Tage
    - Prozentänderung start->end innerhalb Zeitraum
    - direction: "gestiegen" / "gefallen"
    """
    years = float(years)
    percent = float(percent)
    direction = direction or "gestiegen"

    today = datetime.utcnow().date()
    days = int(365 * years)
    start_date = today - timedelta(days=days)

    results: list[dict[str, Any]] = []

    for symbol, rows in prices_by_symbol.items():
        in_range = [(d, p) for d, p in rows if d >= start_date]
        if len(in_range) < 2:
            continue

        start_price = in_range[0][1]
        end_price = in_range[-1][1]
        if start_price <= 0:
            continue

        change_pct = (end_price - start_price) / start_price * 100

        if direction == "gestiegen" and change_pct < percent:
            continue
        if direction == "gefallen" and change_pct > -percent:
            continue

        if years == 0.25:
            period = "3 Monate"
        elif years == 0.5:
            period = "6 Monate"
        else:
            period = f"{years:g} Jahre"

        results.append(
            {
                "symbol": symbol,
                "start_price": round(start_price, 2),
                "end_price": round(end_price, 2),
                "change_percent": round(change_pct, 2),
                "period": period,
            }
        )

    return {"count": len(results), "results": results}


def csv_history(prices_by_symbol: dict[str, list[tuple[date, float]]], symbol: str) -> dict[str, Any]:
    """
    Legacy: liefert labels/data für ein Symbol aus der CSV.
    """
    symbol = (symbol or "").upper()
    rows = prices_by_symbol.get(symbol)
    if not rows:
        return {"symbol": symbol, "available": False, "labels": [], "data": []}

    labels = [d.isoformat() for d, _ in rows]
    data = [p for _, p in rows]

    return {"symbol": symbol, "available": True, "labels": labels, "data": data}


def simulate_savings(
    prices_by_symbol: dict[str, list[tuple[date, float]]],
    symbol: str,
    years: float,
    monthly_usd: float,
) -> dict[str, Any]:
    """
    Legacy DCA:
    - Kauf NUR am 1. des Monats
    - fehlt der 1. -> Monat überspringen
    - keine Gebühren
    """
    symbol = (symbol or "").upper()
    years = float(years)
    monthly_usd = float(monthly_usd)

    rows = prices_by_symbol.get(symbol)
    if not rows:
        return {"result_usd": 0.0}

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=int(365 * years))

    rows = [(d, p) for d, p in rows if d >= start_date]
    if not rows:
        return {"result_usd": 0.0}

    price_map = {d: p for d, p in rows}

    total_coins = 0.0

    cur = date(start_date.year, start_date.month, 1)
    end_month = date(today.year, today.month, 1)

    while cur <= end_month:
        price = price_map.get(cur)
        if price and price > 0:
            total_coins += monthly_usd / price

        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)

    last_price = rows[-1][1]
    result = total_coins * last_price

    months = int(years * 12)
    cash_only = monthly_usd * months

    return {"result_usd": round(result, 2), "cash_only_usd": round(cash_only, 2)}


def calc_ma_for_date(target_date: date, rows: list[tuple[date, float]], ma_days: int) -> float | None:
    """
    Legacy: gleitender Durchschnitt der letzten ma_days Einträge <= target_date.
    """
    relevant = [(d, p) for d, p in rows if d <= target_date]
    if len(relevant) < ma_days:
        return None
    window = [p for _, p in relevant[-ma_days:]]
    return sum(window) / ma_days


def simulate_savings_dynamic(
    prices_by_symbol: dict[str, list[tuple[date, float]]],
    symbol: str,
    years: float,
    monthly_usd: float,
    threshold_pct: float,  # kommt als Prozent/100 rein (z.B. 0.05)
    adjust_pct: float,     # kommt als Prozent/100 rein (z.B. 0.50)
    ma_days: int,
) -> dict[str, Any]:
    """
    Legacy dynamic:
    - nur Kauf am 1. des Monats (wenn kein price am 1. -> skip)
    - MA über ma_days bis inkl. Datum
    - if price >= MA*(1+threshold): invest reduktion, rest in cash_buffer
    - if price <= MA*(1-threshold): invest + min(increase, cash_buffer)
    """
    symbol = (symbol or "").upper()
    years = float(years)
    monthly_usd = float(monthly_usd)
    threshold_pct = float(threshold_pct)
    adjust_pct = float(adjust_pct)
    ma_days = int(ma_days)

    rows = prices_by_symbol.get(symbol)
    if not rows:
        return {"result_usd": 0.0}

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=int(365 * years))

    rows = [(d, p) for d, p in rows if d >= start_date]
    if len(rows) < ma_days:
        return {"result_usd": 0.0}

    price_map = {d: p for d, p in rows}

    total_coins = 0.0
    cash_buffer = 0.0

    start_year = start_date.year
    start_month = start_date.month
    end_year = today.year
    end_month = today.month

    total_months = (end_year - start_year) * 12 + (end_month - start_month)

    for i in range(total_months + 1):
        year = start_year + (start_month - 1 + i) // 12
        month = (start_month - 1 + i) % 12 + 1
        cur = date(year, month, 1)

        price = price_map.get(cur)
        ma = calc_ma_for_date(cur, rows, ma_days)

        if not price:
            continue

        if not ma:
            ma = price

        invest = monthly_usd

        if price >= ma * (1 + threshold_pct):
            reduction = monthly_usd * adjust_pct
            invest -= reduction
            cash_buffer += reduction

        elif price <= ma * (1 - threshold_pct):
            increase = monthly_usd * adjust_pct
            extra = min(increase, cash_buffer)
            invest += extra
            cash_buffer -= extra

        if invest > 0:
            total_coins += invest / price

    last_price = rows[-1][1]
    result = total_coins * last_price

    return {
        "result_usd": round(result, 2),
        "cash_buffer_usd": round(cash_buffer, 2),
        "total_value_usd": round(result + cash_buffer, 2),
    }
