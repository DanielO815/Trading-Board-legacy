import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

# =========================
# CoinGecko (für Tabelle)
# =========================
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

COINS_CACHE_TTL = timedelta(minutes=5)
_price_cache: dict[str, Any] = {}
_coins_cache: dict[str, Any] = {"at": None, "payload": None}


def _cg_headers() -> dict[str, str]:
    """
    Generiert HTTP-Header für CoinGecko-API-Anfragen mit optionalen API-Schlüsseln.

    Returns:
        Wörterbuch mit Accept, User-Agent und optionalen API-Schlüsseln.
    """
    h = {"Accept": "application/json", "User-Agent": "onepager-fastapi/0.5"}
    demo = os.getenv("COINGECKO_DEMO_KEY")
    pro = os.getenv("COINGECKO_PRO_KEY")
    if demo:
        h["x-cg-demo-api-key"] = demo
    if pro:
        h["x-cg-pro-api-key"] = pro
        # Pro nutzt andere Domain – falls du Pro nutzt, setz COINGECKO_BASE in .env passend.
    return h


async def cg_get(url: str, params: dict[str, Any] | None = None) -> Any:
    """
    Führt CoinGecko-API-Anfrage mit automatischem Retry aus.

    Args:
        url: API-Endpunkt-URL.
        params: Optionale Query-Parameter.

    Returns:
        Geparste JSON-Antwort.

    Raises:
        HTTPException: Bei Netzwerkfehlern oder nach Ausschöpfung von Wiederholungsversuchen.
    """
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


@router.get("/api/coins")
async def coins(limit: int = 100, quote: str = "USD"):
    """
    Endpoint: Top-Kryptowährungen mit Marktkapitalisierung und Preisveränderung.

    Query Parameter:
        limit: Anzahl der rückzugebenden Coins (1-500, Standard: 100).
        quote: Währung für Preise (aktuell nur USD unterstützt).

    Returns:
        JSON mit Coin-Details (Symbol, Name, Preis, Marktkapitalisierung, 24h-Veränderung).
        Nutzt 5-Minuten-Cache zur Reduzierung von API-Anfragen.

    Raises:
        HTTPException: Bei ungültiger Quote-Währung (Status 400) oder API-Fehler (Status 502).
    """
    quote = (quote or "USD").upper()
    if quote != "USD":
        raise HTTPException(status_code=400, detail="Nur USD wird aktuell unterstützt (quote=USD).")

    limit = max(1, min(limit, 500))
    now = datetime.now(timezone.utc)

    if _coins_cache["at"] and _coins_cache["payload"] and (now - _coins_cache["at"]) < COINS_CACHE_TTL:
        payload = _coins_cache["payload"]
        return {"vs_currency": "usd", "count": min(limit, len(payload["coins"])), "coins": payload["coins"][:limit]}

    per_page = 250
    pages = (limit + per_page - 1) // per_page

    out: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        rows = await cg_get(
            f"{COINGECKO_BASE}/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": per_page,
                "page": page,
                "sparkline": "false",
                "price_change_percentage": "24h",
            },
        )
        for r in rows:
            out.append(
                {
                    "id": r.get("id"),
                    "symbol": (r.get("symbol") or "").upper(),
                    "name": r.get("name"),
                    "market_cap_rank": r.get("market_cap_rank"),
                    "current_price": r.get("current_price"),
                    "market_cap": r.get("market_cap"),
                    "total_volume": r.get("total_volume"),
                    "price_change_percentage_24h": r.get("price_change_percentage_24h"),
                }
            )
        if len(out) >= limit:
            break

    out = out[:limit]
    payload = {"vs_currency": "usd", "count": len(out), "coins": out}
    _coins_cache["at"] = now
    _coins_cache["payload"] = payload
    return payload
