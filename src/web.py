"""FastAPI web application for Pokemon card collection."""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import db

app = FastAPI(title="Pokemon Card Collection")

# Initialize database
db.init_database()


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    """Serve the main page."""
    html_path = Path(__file__).parent / "templates" / "index.html"
    return html_path.read_text()


@app.get("/api/stats")
async def get_stats() -> dict:
    """Get collection statistics."""
    return db.get_v2_collection_stats()


@app.get("/api/cards")
async def get_cards(language: str = "de", set_id: Optional[str] = None) -> list[dict]:
    """Get owned cards with optional filters."""
    return db.get_v2_owned_cards(language=language, set_id=set_id)
