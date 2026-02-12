from __future__ import annotations

import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Tuple

import httpx
from fastapi import HTTPException

from .coinbase import (
    get_btc_price_usd as cb_get_btc_price_usd,
    get_history_daily_closes as cb_get_history_daily_closes,
)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# kleine Caches, damit dein Frontend nicht jede Sekunde externe APIs spammt
_btc_price_cache: dict[str, Any] = {"at": None, "price": None, "source": None}
_BTC_PRICE_TTL = timedelta(seconds=10)

_btc_history_cache: dict[tuple[int], dict[str, Any]] = {}  # key: (years,)
_BTC_HISTORY_TTL = timedelta(minutes=5)


def _cg_headers() -> dict[str, str]:
    h = {"Accept": "application/json", "User-Agent": "onepager-fastapi/0.5"}
    demo = os.getenv("COINGECKO_DEMO_KEY")
    pro = os.getenv("COINGECKO_PRO_KEY")
    if demo:
        h["x-cg-demo-api-key"] = demo
    if pro:
        h["x-cg-pro-api-key"] = pro
    return h


async def _cg_get(url: str, params: dict[str, Any] | None = None) -> Any:
    for attempt in range(4):
        try:
            async with httpx.AsyncClient(timeout=30, headers=_cg_headers()) as client:
                r = await client.get(url, params=params)

            if r.status_code == 429 or 500 <= r.status_code <= 599:
                await asyncio.sleep(1 + attempt * 2)
                continue

            r.raise_for_status()
            return r.json()

        except httpx.HTTPError as e:
            if attempt == 3:
                raise HTTPException(status_code=502, detail=f"CoinGecko error: {e}")
            await asyncio.sleep(1 + attempt * 2)

    raise HTTPException(status_code=502, detail="CoinGecko: retries exhausted")


async def _coingecko_btc_price_usd() -> float:
    j = await _cg_get(
        f"{COINGECKO_BASE}/simple/price",
        params={"ids": "bitcoin", "vs_currencies": "usd"},
    )
    try:
        return float(j["bitcoin"]["usd"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"CoinGecko parse error: {e}")


async def _coingecko_btc_history_daily_closes(years: int) -> tuple[list[str], list[float]]:
    years = max(1, min(int(years), 15))
    days = int(years * 365)

    j = await _cg_get(
        f"{COINGECKO_BASE}/coins/bitcoin/market_chart",
        params={"vs_currency": "usd", "days": days, "interval": "daily"},
    )

    prices = j.get("prices") or []
    if not isinstance(prices, list) or not prices:
        return [], []

    # date -> last price for that date
    by_day: dict[str, float] = {}
    for row in prices:
        if not isinstance(row, list) or len(row) < 2:
            continue
        ts_ms, price = row[0], row[1]
        try:
            d = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc).date().isoformat()
            by_day[d] = float(price)
        except Exception:
            continue

    # today raus (wie bei dir auch in anderen Stellen stabiler)
    today = datetime.now(timezone.utc).date().isoformat()
    by_day.pop(today, None)

    labels = sorted(by_day.keys())
    data = [by_day[d] for d in labels]
    return labels, data


async def get_btc_price_usd_with_fallback() -> tuple[str, float]:
    """
    1) Coinbase Exchange versuchen
    2) wenn 403/blocked/etc.: CoinGecko fallback
    """
    now = datetime.now(timezone.utc)

    if _btc_price_cache["at"] and _btc_price_cache["price"] is not None:
        if (now - _btc_price_cache["at"]) < _BTC_PRICE_TTL:
            return str(_btc_price_cache["source"]), float(_btc_price_cache["price"])

    # Primary: Coinbase
    try:
        price = await cb_get_btc_price_usd()
        _btc_price_cache.update({"at": now, "price": price, "source": "coinbase_exchange"})
        return "coinbase_exchange", float(price)
    except Exception:
        # Fallback: CoinGecko
        price = await _coingecko_btc_price_usd()
        _btc_price_cache.update({"at": now, "price": price, "source": "coingecko"})
        return "coingecko", float(price)


async def get_btc_history_with_fallback(years: int) -> tuple[str, list[str], list[float]]:
    """
    1) Coinbase Exchange candles versuchen
    2) wenn 403/blocked/etc.: CoinGecko fallback
    """
    years = max(1, min(int(years), 15))
    now = datetime.now(timezone.utc)

    cache_key = (years,)
    cached = _btc_history_cache.get(cache_key)
    if cached and cached.get("at") and (now - cached["at"]) < _BTC_HISTORY_TTL:
        return str(cached["source"]), list(cached["labels"]), list(cached["data"])

    # Primary: Coinbase
    try:
        labels, data = await cb_get_history_daily_closes("BTC-USD", years=years)
        _btc_history_cache[cache_key] = {"at": now, "labels": labels, "data": data, "source": "coinbase_exchange"}
        return "coinbase_exchange", labels, data
    except Exception:
        labels, data = await _coingecko_btc_history_daily_closes(years=years)
        _btc_history_cache[cache_key] = {"at": now, "labels": labels, "data": data, "source": "coingecko"}
        return "coingecko", labels, data
