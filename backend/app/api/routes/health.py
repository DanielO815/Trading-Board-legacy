from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def root():
    return {"message": "Backend läuft (Tabelle=CoinGecko, Export/History=Coinbase)."}
