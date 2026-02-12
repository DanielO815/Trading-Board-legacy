from fastapi import APIRouter, HTTPException

from ...services.coinbase import get_btc_price_usd, get_history_daily_closes

router = APIRouter()

@router.get("/api/btc/price")
async def btc_price():
    try:
        price = await get_btc_price_usd()
        return {"source": "coinbase_exchange", "symbol": "BTC-USD", "price_usd": price}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Coinbase error: {e}")


@router.get("/api/btc/history")
async def btc_history(years: int = 10):
    years = max(1, min(years, 15))
    try:
        labels, data = await get_history_daily_closes("BTC-USD", years=years)
        return {"labels": labels, "data": data, "years": years}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Coinbase error: {e}")
