from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def root():
    """
    Endpoint: Health-Check und Applikations-Status.

    Returns:
        Nachricht Bestätigung dass Backend läuft und Datenquellen.
    """
    return {"message": "Backend läuft (Tabelle=CoinGecko, Export/History=Coinbase)."}
