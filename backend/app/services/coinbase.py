import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from ..core.config import COINBASE_EXPORT_SLEEP

COINBASE_BASE = "https://api.exchange.coinbase.com"

_products_cache: dict[str, Any] = {"at": None, "payload": None}
_PRODUCTS_TTL = timedelta(hours=1)


def iso_z(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")


async def cb_get_products(client: httpx.AsyncClient) -> list[dict]:
    now = datetime.now(timezone.utc)
    if _products_cache["at"] and _products_cache["payload"] and (now - _products_cache["at"]) < _PRODUCTS_TTL:
        return _products_cache["payload"]

    r = await client.get(f"{COINBASE_BASE}/products")
    r.raise_for_status()
    data = r.json()
    _products_cache["at"] = now
    _products_cache["payload"] = data
    return data


async def cb_get_candles(
    client: httpx.AsyncClient,
    product_id: str,
    start: datetime,
    end: datetime,
    granularity: int = 86400,
) -> list:
    params = {"start": iso_z(start), "end": iso_z(end), "granularity": granularity}
    r = await client.get(f"{COINBASE_BASE}/products/{product_id}/candles", params=params)
    r.raise_for_status()
    return r.json()


async def cb_daily_closes(
    client: httpx.AsyncClient,
    product_id: str,
    years: int,
) -> list[tuple[str, float]]:
    granularity = 86400
    block = timedelta(seconds=granularity * 300)

    end = datetime.now(timezone.utc)
    start_limit = end - timedelta(days=365 * years)

    seen_ts: set[int] = set()
    points: list[tuple[int, float]] = []

    empty_streak = 0
    for _ in range(400):
        start = end - block
        if start < start_limit:
            start = start_limit

        rows = await cb_get_candles(client, product_id, start, end, granularity=granularity)

        if not rows:
            empty_streak += 1
            if empty_streak >= 3:
                break
        else:
            empty_streak = 0
            oldest_ts: Optional[int] = None

            for row in rows:
                if not isinstance(row, list) or len(row) < 5:
                    continue
                ts = int(row[0])
                close = float(row[4])
                if ts not in seen_ts:
                    seen_ts.add(ts)
                    points.append((ts, close))
                if oldest_ts is None or ts < oldest_ts:
                    oldest_ts = ts

            if oldest_ts is None:
                break

            new_end = datetime.fromtimestamp(oldest_ts, tz=timezone.utc) - timedelta(seconds=1)
            if new_end >= end:
                break
            end = new_end

        if start <= start_limit:
            break

        await asyncio.sleep(COINBASE_EXPORT_SLEEP)

    points.sort(key=lambda x: x[0])

    today = datetime.now(timezone.utc).date().isoformat()
    out: list[tuple[str, float]] = []
    for ts, close in points:
        day = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        if day == today:
            continue
        out.append((day, close))

    by_day: dict[str, float] = {}
    for d, c in out:
        by_day[d] = c
    labels = sorted(by_day.keys())
    return [(d, by_day[d]) for d in labels]


async def get_btc_price_usd() -> float:
    headers = {"Accept": "application/json", "User-Agent": "onepager-fastapi/0.5"}
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        r = await client.get(f"{COINBASE_BASE}/products/BTC-USD/ticker")
        r.raise_for_status()
        j = r.json()
        return float(j["price"])


async def get_history_daily_closes(product_id: str, years: int) -> tuple[list[str], list[float]]:
    headers = {"Accept": "application/json", "User-Agent": "onepager-fastapi/0.5"}
    timeout = httpx.Timeout(30.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        closes = await cb_daily_closes(client, product_id, years=years)

    labels = [d for d, _ in closes]
    data = [c for _, c in closes]
    return labels, data
