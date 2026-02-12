from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from ...services.export_service import ExportService

router = APIRouter()


def get_export_service(request: Request) -> ExportService:
    return request.app.state.export_service


@router.post("/api/export/coinbase/stop")
def stop_coinbase_export(export_svc: ExportService = Depends(get_export_service)):
    export_svc.stop_coinbase_export()
    return {"status": "stop_requested"}


@router.post("/api/export/coinbase/start")
async def export_coinbase_start(
    payload: Dict[str, Any] = Body(...),
    export_svc: ExportService = Depends(get_export_service),
):
    symbols = payload.get("symbols") or []
    years = int(payload.get("years", 10))

    if not isinstance(symbols, list) or not all(isinstance(s, str) for s in symbols):
        raise HTTPException(status_code=400, detail="symbols muss eine Liste aus Strings sein")

    try:
        job_id = await export_svc.start_coinbase_export(symbols=symbols, years=years)
        return {"job_id": job_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/export/coinbase/status/{job_id}")
def export_coinbase_status(
    job_id: str,
    export_svc: ExportService = Depends(get_export_service),
):
    job = export_svc.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return job
