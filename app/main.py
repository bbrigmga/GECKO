"""FastAPI application — local Grok Portfolio replicator."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import Settings, load_settings, save_settings
from app.pipeline import list_runs, load_run, runner, _redact_run

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

app = FastAPI(title="Grok Portfolio Replicator", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


class SettingsPayload(BaseModel):
    api_provider: str = "xai"
    xai_api_key: str = ""
    stocknews_api_key: str = ""
    model: str = "grok-4.3"
    max_tickers: int = Field(default=0, ge=0)
    concurrency: int = Field(default=8, ge=1, le=32)
    stocknews_items_per_ticker: int = Field(default=15, ge=1, le=50)
    stocknews_macro_items: int = Field(default=25, ge=1, le=50)


class SettingsResponse(BaseModel):
    api_provider: str
    xai_api_key_set: bool
    stocknews_api_key_set: bool
    model: str
    max_tickers: int
    concurrency: int
    stocknews_items_per_ticker: int
    stocknews_macro_items: int


def _mask_settings(s: Settings) -> SettingsResponse:
    return SettingsResponse(
        api_provider=s.api_provider,
        xai_api_key_set=bool(s.xai_api_key),
        stocknews_api_key_set=bool(s.stocknews_api_key),
        model=s.model,
        max_tickers=s.max_tickers,
        concurrency=s.concurrency,
        stocknews_items_per_ticker=s.stocknews_items_per_ticker,
        stocknews_macro_items=s.stocknews_macro_items,
    )


@app.get("/favicon.ico")
async def favicon() -> FileResponse:
    return FileResponse(STATIC / "favicon.ico", media_type="image/svg+xml")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    return _mask_settings(load_settings())


@app.post("/api/settings", response_model=SettingsResponse)
async def update_settings(payload: SettingsPayload) -> SettingsResponse:
    current = load_settings()
    settings = Settings(
        api_provider=payload.api_provider,
        xai_api_key=payload.xai_api_key or current.xai_api_key,
        stocknews_api_key=payload.stocknews_api_key or current.stocknews_api_key,
        model=payload.model,
        max_tickers=payload.max_tickers,
        concurrency=payload.concurrency,
        stocknews_items_per_ticker=payload.stocknews_items_per_ticker,
        stocknews_macro_items=payload.stocknews_macro_items,
    )
    save_settings(settings)
    return _mask_settings(settings)


@app.get("/api/status")
async def status() -> dict[str, Any]:
    return {
        "is_running": runner.is_running,
        "current_run_id": runner.current_run_id,
    }


@app.post("/api/run")
async def start_run(resume: bool = False) -> dict[str, Any]:
    if runner.is_running:
        raise HTTPException(status_code=409, detail="A run is already in progress")
    try:
        resume_id = runner.find_resumable_run() if resume else None
        run_id = await runner.start(resume_run_id=resume_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run_id": run_id, "resumed": resume_id is not None}


@app.post("/api/run/cancel")
async def cancel_run() -> dict[str, str]:
    if not runner.is_running:
        raise HTTPException(status_code=400, detail="No run in progress")
    runner.cancel()
    return {"status": "cancelling"}


@app.get("/api/runs")
async def get_runs() -> list[dict[str, Any]]:
    return list_runs()


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    data = load_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="Run not found")
    return _redact_run(data)


@app.get("/api/events")
async def events() -> StreamingResponse:
    queue = runner.subscribe()

    async def stream():
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'connected', 'is_running': runner.is_running, 'run_id': runner.current_run_id})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("type") in ("complete", "error", "cancelled"):
                        break
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            runner.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
