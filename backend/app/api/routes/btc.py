from fastapi import APIRouter, HTTPException

from ...services.coinbase import get_btc_price_usd, get_history_daily_closes

router = APIRouter()

@router.get("/api/btc/price")
async def btc_price():
    """
    Endpoint: Aktueller Bitcoin-Preis in USD.

    Returns:
        JSON mit aktuellem Preis, Quelle und Symbol.

    Raises:
        HTTPException: Bei Abruffehler mit Status 502.
    """
    try:
        price = await get_btc_price_usd()
        return {"source": "coinbase_exchange", "symbol": "BTC-USD", "price_usd": price}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Coinbase error: {e}")


@router.get("/api/btc/history")
async def btc_history(years: int = 10):
    """
    Endpoint: Bitcoin-Kursverlauf über angegebene Anzahl von Jahren.

    Query Parameter:
        years: Zeitraum in Jahren (begrenzt auf 1-15, Standard: 10).

    Returns:
        JSON mit Datenlisten (labels) und Preisen (data).

    Raises:
        HTTPException: Bei Abruffehler mit Status 502.
    """
    years = max(1, min(years, 15))
    try:
        labels, data = await get_history_daily_closes("BTC-USD", years=years)
        return {"labels": labels, "data": data, "years": years}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Coinbase error: {e}")
