from dotenv import load_dotenv
load_dotenv()

# truststore optional (damit es auf anderen Rechnern nicht crasht)
try:
    import truststore
    truststore.inject_into_ssl()
except ModuleNotFoundError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import api_router
from .core.config import ALLOWED_ORIGINS
from .infra.storage import get_export_dir
from .services.export_service import ExportService
from .services.csv_tools_service import CsvToolsService


def create_app() -> FastAPI:
    """
    Erstellt und konfiguriert FastAPI-Applikationsinstanz.

    Konfiguriert CORS-Middleware, registriert Services und API-Router.

    Returns:
        Konfigurierte FastAPI-Applikation.
    """
    app = FastAPI(title="OnePager API", version="0.5.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    export_dir = get_export_dir()

    # Option B: Services an App-Lifecycle hängen
    app.state.export_service = ExportService(export_dir=export_dir)
    app.state.csv_tools_service = CsvToolsService(export_dir=export_dir)

    app.include_router(api_router)
    return app


app = create_app()
