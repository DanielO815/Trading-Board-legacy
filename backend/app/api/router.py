"""
Hauptrouter-Konfiguration.

Integriert alle API-Route-Module (Health, Coins, Bitcoin, Exports, CSV-Tools)
in zentralen API-Router.
"""

from fastapi import APIRouter

from .routes.health import router as health_router
from .routes.coins import router as coins_router
from .routes.btc import router as btc_router
from .routes.exports import router as exports_router
from .routes.csv_tools import router as csv_tools_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(coins_router)
api_router.include_router(btc_router)
api_router.include_router(exports_router)
api_router.include_router(csv_tools_router)
