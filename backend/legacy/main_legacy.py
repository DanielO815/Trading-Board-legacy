# backend/main.py
from dotenv import load_dotenv
load_dotenv()

import os
import csv
import asyncio
import uuid
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional


import truststore
truststore.inject_into_ssl()

import httpx
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# =========================
# App
# =========================
app = FastAPI(title="OnePager API", version="0.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173","https://DanielO815.github.io"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Export folder
# =========================
EXPORT_DIR = Path(__file__).resolve().parent / "exports"
EXPORT_DIR.mkdir(exist_ok=True)
# Stop-Flag für laufenden Coinbase-Export
EXPORT_STOP_REQUESTED = False


# =========================
# CoinGecko (für Tabelle)
# =========================
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

COINS_CACHE_TTL = timedelta(minutes=5)
_price_cache: dict[str, Any] = {}
_coins_cache: dict[str, Any] = {"at": None, "payload": None}


def _cg_headers() -> dict[str, str]:
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


@app.get("/")
def root():
    return {"message": "Backend läuft (Tabelle=CoinGecko, Export/History=Coinbase)."}


@app.get("/api/coins")
async def coins(limit: int = 100, quote: str = "USD"):
    """
    Coins für Tabelle (Preis + Marketcap).
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


# =========================
# Coinbase (echte BTC 10y + Export)
# =========================
COINBASE_BASE = "https://api.exchange.coinbase.com"
COINBASE_EXPORT_SLEEP = float(os.getenv("COINBASE_EXPORT_SLEEP", "0.15"))

_products_cache: dict[str, Any] = {"at": None, "payload": None}
_PRODUCTS_TTL = timedelta(hours=1)

_export_jobs: dict[str, dict[str, Any]] = {}


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
    """
    Holt nur Daily Close (close) für die letzten `years` Jahre.
    Coinbase: max 300 candles pro Request -> rückwärts in Blöcken.
    """
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
                # [time, low, high, open, close, volume?]
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

    # dedupe pro Tag (letzter gewinnt)
    by_day: dict[str, float] = {}
    for d, c in out:
        by_day[d] = c
    labels = sorted(by_day.keys())
    return [(d, by_day[d]) for d in labels]

def cleanup_old_coinbase_exports():
    """
    Löscht alle vorhandenen coinbase_daily_*.csv Dateien.
    """
    for f in EXPORT_DIR.glob("coinbase_daily_*.csv"):
        try:
            f.unlink()
        except Exception:
            pass

@app.post("/api/export/coinbase/stop")
def stop_coinbase_export():
    """
    Signalisiert dem laufenden Export, dass er abbrechen soll.
    """
    global EXPORT_STOP_REQUESTED
    EXPORT_STOP_REQUESTED = True
    return {"status": "stop_requested"}



@app.get("/api/btc/price")
async def btc_price():
    headers = {"Accept": "application/json", "User-Agent": "onepager-fastapi/0.5"}
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        r = await client.get(f"{COINBASE_BASE}/products/BTC-USD/ticker")
    r.raise_for_status()
    j = r.json()
    return {"source": "coinbase_exchange", "symbol": "BTC-USD", "price_usd": float(j["price"])}


@app.get("/api/btc/history")
async def btc_history(years: int = 10):
    years = max(1, min(years, 15))
    headers = {"Accept": "application/json", "User-Agent": "onepager-fastapi/0.5"}
    timeout = httpx.Timeout(30.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        closes = await cb_daily_closes(client, "BTC-USD", years=years)

    labels = [d for d, _ in closes]
    data = [c for _, c in closes]
    return {"labels": labels, "data": data, "years": years}


# =========================
# Coinbase Export Job: coins aus Tabelle -> CSV in exports/
# =========================
async def _run_coinbase_export_job(job_id: str, symbols: list[str], years: int):
    global EXPORT_STOP_REQUESTED
    # Alte Coinbase-CSV-Dateien löschen
    cleanup_old_coinbase_exports()
    
    EXPORT_STOP_REQUESTED = False
    job = _export_jobs[job_id]
    job["status"] = "running"
    job["total"] = len(symbols)
    job["done"] = 0
    job["errors"] = 0
    job["current"] = None

    now = datetime.now(timezone.utc)
    filename = f"coinbase_daily_{now.strftime('%Y-%m-%d_%H%M%S')}.csv"

    out_path = EXPORT_DIR / filename
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
                    if EXPORT_STOP_REQUESTED:
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
        EXPORT_STOP_REQUESTED = False
    


@app.post("/api/export/coinbase/start")
async def export_coinbase_start(payload: Dict[str, Any] = Body(...)):
    """
    Body: { "symbols": ["BTC","ETH",...], "years": 10 }
    -> speichert 1 CSV in backend/exports/ und liefert Fortschritt per Status-Endpoint.
    """
    symbols = payload.get("symbols") or []
    years = int(payload.get("years", 10))

    if not isinstance(symbols, list) or not all(isinstance(s, str) for s in symbols):
        raise HTTPException(status_code=400, detail="symbols muss eine Liste aus Strings sein")

    years = max(1, min(years, 15))
    symbols = [s.strip().upper() for s in symbols if s and s.strip()]
    symbols = list(dict.fromkeys(symbols))
    if not symbols:
        raise HTTPException(status_code=400, detail="symbols ist leer")

    job_id = uuid.uuid4().hex[:10]
    _export_jobs[job_id] = {
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

    asyncio.create_task(_run_coinbase_export_job(job_id, symbols, years))
    return {"job_id": job_id}


@app.get("/api/export/coinbase/status/{job_id}")
def export_coinbase_status(job_id: str):
    job = _export_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job_id")

    total = int(job.get("total") or 0)
    done = int(job.get("done") or 0)
    percent = round((done / total * 100.0), 1) if total else 0.0
    return {**job, "percent": percent}


#----------Filter nach Eingaben-----------------------------------

def latest_coinbase_csv() -> Path:
    """
    Gibt die neueste coinbase_daily*.csv Datei zurück.
    """
    files = sorted(
        EXPORT_DIR.glob("coinbase_daily*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise HTTPException(status_code=404, detail="Keine Coinbase-CSV gefunden")
    return files[0]


def load_prices_by_symbol(csv_path: Path) -> dict[str, list[tuple[datetime, float]]]:
    """
    Lädt CSV und gruppiert Preise nach Symbol.
    Rückgabe: { "BTC": [(date, price), ...], ... }
    """
    data: dict[str, list[tuple[datetime, float]]] = {}

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("error"):
                continue
            try:
                sym = row["symbol"]
                date = datetime.fromisoformat(row["date_utc"]).date()
                price = float(row["close_usd"])
                data.setdefault(sym, []).append((date, price))
            except Exception:
                continue

    # sortiere Preise pro Coin nach Datum
    for sym in data:
        data[sym].sort(key=lambda x: x[0])

    return data

def calc_ma_for_date(target_date: date, rows, ma_days: int) -> float | None:
    """
    Berechnet den gleitenden Durchschnitt relativ zu einem Ziel-Datum.
    Basis: die letzten ma_days Tage bis inkl. target_date.
    """
    # nur Daten bis zum Ziel-Datum
    relevant = [(d, p) for d, p in rows if d <= target_date]

    if len(relevant) < ma_days:
        return None

    window = [p for _, p in relevant[-ma_days:]]
    return sum(window) / ma_days

def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)



#-------- Filter Endpoints ------------------------------------
@app.post("/api/filter/coinbase")
def filter_coinbase(payload: Dict[str, Any] = Body(...)):
    """
    Filtert Coins aus der neuesten Coinbase-CSV anhand:
    - years
    - percent
    - direction (gestiegen / gefallen)
    """
    years = float(payload.get("years", 3))
    percent = float(payload.get("percent", 20))
    direction = payload.get("direction", "gestiegen")

    today = datetime.utcnow().date()
    days = int(365 * years)
    start_date = today - timedelta(days=days)

    csv_path = latest_coinbase_csv()
    prices_by_symbol = load_prices_by_symbol(csv_path)

    results = []

    for symbol, rows in prices_by_symbol.items():
        # Preise im Zeitraum
        in_range = [(d, p) for d, p in rows if d >= start_date]

        if len(in_range) < 2:
            continue

        start_price = in_range[0][1]
        end_price = in_range[-1][1]

        if start_price <= 0:
            continue

        change_pct = (end_price - start_price) / start_price * 100

        # Filter anwenden
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
        results.append({
            "symbol": symbol,
            "start_price": round(start_price, 2),
            "end_price": round(end_price, 2),
            "change_percent": round(change_pct, 2),
            "period": period,
        })

    return {
        "count": len(results),
        "results": results,
        "csv_used": csv_path.name,
    }


@app.get("/api/csv/history/{symbol}")
def csv_history(symbol: str):
    """
    Liefert Zeitverlauf (date, close) eines Coins aus der neuesten CSV.
    """
    symbol = symbol.upper()
    csv_path = latest_coinbase_csv()
    prices_by_symbol = load_prices_by_symbol(csv_path)

    rows = prices_by_symbol.get(symbol)
    if not rows:
        return {
            "symbol": symbol,
            "available": False,
            "labels": [],
            "data": [],
        }

    labels = [d.isoformat() for d, _ in rows]
    data = [p for _, p in rows]

    return {
        "symbol": symbol,
        "available": True,
        "labels": labels,
        "data": data,
    }
#-------Sparplan----------
@app.post("/api/simulate/savings")
def simulate_savings(payload: Dict[str, Any] = Body(...)):
    """
    Simuliert einen monatlichen Sparplan (DCA) auf Basis der neuesten CSV.
    Regeln:
    - Kauf NUR am 1. des Monats
    - Fehlt der 1. -> Monat wird übersprungen
    - Keine Gebühren
    """
    symbol = payload.get("symbol", "").upper()
    years = float(payload.get("years", 1))
    monthly_usd = float(payload.get("monthly_usd", 0))

    if not symbol or monthly_usd <= 0:
        raise HTTPException(status_code=400, detail="Ungültige Parameter")

    # CSV laden
    csv_path = latest_coinbase_csv()
    prices_by_symbol = load_prices_by_symbol(csv_path)
    rows = prices_by_symbol.get(symbol)

    if not rows:
        return {"result_usd": 0.0}

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=int(365 * years))

    # Nur relevanter Zeitraum
    rows = [(d, p) for d, p in rows if d >= start_date]

    total_coins = 0.0

    # Hilfsmap: Datum -> Preis
    price_map = {d: p for d, p in rows}

    # Alle Monate im Zeitraum durchgehen
    cur = date(start_date.year, start_date.month, 1)
    end_month = date(today.year, today.month, 1)

    while cur <= end_month:
        # exakt der 1. des Monats
        price = price_map.get(cur)
        if price and price > 0:
            total_coins += monthly_usd / price
        # nächster Monat
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)

    # letzter verfügbarer Preis
    last_price = rows[-1][1]
    result = total_coins * last_price

    months = int(years * 12)
    cash_only = monthly_usd * months

    return {
        "result_usd": round(result, 2),
        "cash_only_usd": round(cash_only, 2),
    }


@app.post("/api/simulate/savings_dynamic")
def simulate_savings_dynamic(payload: Dict[str, Any] = Body(...)):
    """
    Dynamischer Sparplan auf Basis gleitender Durchschnitte.
    """

    symbol = payload["symbol"].upper()
    years = float(payload["years"])
    monthly_usd = float(payload["monthly_usd"])
    threshold_pct = float(payload["threshold_pct"]) / 100.0
    adjust_pct = float(payload["adjust_pct"]) / 100.0
    ma_days = int(payload["ma_days"])

    print("\n--- DYNAMISCHER SPARPLAN START ---")
    print(f"Symbol: {symbol}")
    print(f"Zeitraum: {years} Jahre")
    print(f"Monatlich: {monthly_usd} USD")
    print(f"GD-Tage: {ma_days}")
    print(f"Trigger: {threshold_pct * 100:.1f}%")
    print(f"Adjust: {adjust_pct * 100:.1f}%")
    print("---------------------------------")

    csv_path = latest_coinbase_csv()
    prices_by_symbol = load_prices_by_symbol(csv_path)
    rows = prices_by_symbol.get(symbol)

    if not rows:
        return {"result_usd": 0.0}

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=int(365 * years))

    # relevante Daten
    rows = [(d, p) for d, p in rows if d >= start_date]
    if len(rows) < ma_days:
        return {"result_usd": 0.0}

    price_map = {d: p for d, p in rows}

    total_coins = 0.0
    cash_buffer = 0.0

    # 🔹 Start- & Endmonat als Zahlen
    start_year = start_date.year
    start_month = start_date.month
    end_year = today.year
    end_month = today.month

    total_months = (end_year - start_year) * 12 + (end_month - start_month)

    for i in range(total_months + 1):
        year = start_year + (start_month - 1 + i) // 12
        month = (start_month - 1 + i) % 12 + 1
        cur = date(year, month, 1)

        print(f"\n[{cur}]")

        price = price_map.get(cur)
        ma = calc_ma_for_date(cur, rows, ma_days)

        if not price:
            print("  ❌ Kein Preis am 1. → kein Kauf")
            continue

        if not ma:
            ma=price
            print("  ⚪ Kein GD → normal investieren")  

        print(f"  Preis: {price:.2f}")
        print(f"  GD:    {ma:.2f}")
        print(f"  Abw.:  {(price / ma - 1) * 100:.2f}%")

        invest = monthly_usd

        if price >= ma * (1 + threshold_pct):
            reduction = monthly_usd * adjust_pct
            invest -= reduction
            cash_buffer += reduction
            print(f"  🔺 Über GD → investiere {invest:.2f}, {reduction:.2f} in Cash-Puffer")

        elif price <= ma * (1 - threshold_pct):
            increase = monthly_usd * adjust_pct
            extra = min(increase, cash_buffer)
            invest += extra
            cash_buffer -= extra
            print(f"  🔻 Unter GD → investiere {invest:.2f}, {extra:.2f} aus Cash-Puffer")

        else:
            print(f"  ⚪ Neutral → investiere {invest:.2f}")

        if invest > 0:
            coins = invest / price
            total_coins += coins
            print(f"  Coins gekauft: {coins:.6f}")
            print(f"  Gesamt-Coins:  {total_coins:.6f}")
            print(f"  Cash-Puffer:   {cash_buffer:.2f}")

    last_price = rows[-1][1]
    result = total_coins * last_price

    print("\n--- ENDE DYNAMISCHER SPARPLAN ---")
    print(f"Coins: {total_coins:.6f}")
    print(f"Cash:  {cash_buffer:.2f}")
    print(f"Wert:  {result + cash_buffer:.2f}")
    print("--------------------------------")

    return {
        "result_usd": round(result, 2),
        "cash_buffer_usd": round(cash_buffer, 2),
        "total_value_usd": round(result + cash_buffer, 2),
    }


