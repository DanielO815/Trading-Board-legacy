import os

# --- CORS ---
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://DanielO815.github.io",
]

# --- Export / Filesystem ---
# Nur Ordnername; Pfad wird in infra/storage.py relativ zum backend/ Root gebaut.
EXPORT_DIR_NAME = os.getenv("EXPORT_DIR", "exports")

# --- Limits (damit keine Magic Numbers überall stehen) ---
MAX_YEARS = int(os.getenv("MAX_YEARS", "15"))
MAX_COINS_LIMIT = int(os.getenv("MAX_COINS_LIMIT", "500"))

# --- Rate limit / sleeps ---
COINBASE_EXPORT_SLEEP = float(os.getenv("COINBASE_EXPORT_SLEEP", "0.15"))
