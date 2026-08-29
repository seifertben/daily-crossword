"""FastAPI application: serve the daily puzzle JSON + the SPA.

The serving app never calls Gemini and never runs the filler; it only reads
immutable puzzle blobs from the store (local disk in dev, GCS in prod). The
dev-only ``POST /api/dev/generate`` endpoint (enabled only when
``APP_ENV=dev``) lets you regenerate a puzzle from the browser.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from generator.pipeline import generate_puzzle
from generator.store import PuzzleStore, get_store

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="Daily Crossword")

_STATIC_DIR = Path(__file__).resolve().parents[1] / "web" / "dist"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)

_DATE_FMT = "%Y-%m-%d"


def _today() -> str:
    return dt.datetime.now(dt.UTC).date().strftime(_DATE_FMT)


def _valid_date(s: str) -> str:
    try:
        d = dt.datetime.strptime(s, _DATE_FMT).date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc
    return d.strftime(_DATE_FMT)


def _store() -> PuzzleStore:
    return get_store()


class HealthResponse(BaseModel):
    status: str
    store: str
    date: str
    gemini_configured: bool


class DevGenerateRequest(BaseModel):
    date: str | None = None
    difficulty: int = 3
    size: int = 10
    total_seconds: float = 25.0

    @field_validator("difficulty")
    @classmethod
    def _check_diff(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("difficulty must be 1-5")
        return v

    @field_validator("size")
    @classmethod
    def _check_size(cls, v: int) -> int:
        if not 9 <= v <= 21:
            raise ValueError("size must be 9-21")
        return v


def _is_dev() -> bool:
    return os.environ.get("APP_ENV", "dev").strip().lower() == "dev"


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        store=os.environ.get("PUZZLE_STORE", "local"),
        date=_today(),
        gemini_configured=bool(os.environ.get("GEMINI_API_KEY", "").strip()),
    )


@app.get("/api/puzzle")
async def puzzle_today() -> JSONResponse:
    return await _serve_puzzle(_today(), immutable=False)


@app.get("/api/puzzle/{date}")
async def puzzle_dated(date: str) -> JSONResponse:
    return await _serve_puzzle(_valid_date(date), immutable=True)


async def _serve_puzzle(date: str, *, immutable: bool) -> JSONResponse:
    payload = _store().get(date)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"No puzzle generated for {date}.",
        )
    data = json.loads(payload)
    headers = (
        {"Cache-Control": "public, max-age=300, s-maxage=31536000"}
        if immutable
        else {"Cache-Control": "no-cache"}
    )
    return JSONResponse(content=data, headers=headers)


@app.post("/api/dev/generate")
async def dev_generate(req: DevGenerateRequest) -> JSONResponse:
    """Regenerate a puzzle on demand (dev only). Never enabled in prod."""
    if not _is_dev():
        raise HTTPException(status_code=404, detail="Not found")
    date = _valid_date(req.date) if req.date else _today()
    try:
        result = await generate_puzzle(
            date,
            difficulty=req.difficulty,
            size=req.size,
            total_seconds=req.total_seconds,
        )
    except Exception as exc:  # noqa: BLE001 - surface any gen failure to dev
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse(content=result.payload, headers={"Cache-Control": "no-cache"})


@app.get("/")
async def index() -> Response:
    index_html = _STATIC_DIR / "index.html"
    if index_html.exists():
        return FileResponse(index_html, headers={"Cache-Control": "no-cache"})
    # placeholder shown until the frontend is built (phase 5)
    return Response(
        content=_PLACEHOLDER_HTML,
        media_type="text/html",
        headers={"Cache-Control": "no-cache"},
    )


if _STATIC_DIR.exists():
    _ASSETS_DIR = _STATIC_DIR / "assets"
    if _ASSETS_DIR.exists():
        app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="assets")


_PLACEHOLDER_HTML = """<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Daily Crossword</title>
<style>body{font-family:system-ui,sans-serif;max-width:42rem;margin:2rem auto;padding:0 1rem}
code{background:#eee;padding:.1em .3em;border-radius:3px}</style></head>
<body><h1>Daily Crossword</h1>
<p>The SPA build has not been produced yet. The puzzle API is live:</p>
<ul>
<li><code>GET /api/puzzle</code> &mdash; today's puzzle</li>
<li><code>GET /api/puzzle/YYYY-MM-DD</code> &mdash; a specific date</li>
<li><code>POST /api/dev/generate</code> &mdash; regenerate (dev)</li>
</ul>
<p>Generate a puzzle first: <code>make gen-stub</code></p>
</body></html>
"""
