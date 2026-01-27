"""FastAPI web application for Pokemon card collection."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db

app = FastAPI(title="Pokemon Card Collection")

# Initialize database
db.init_database()

# API Key from environment variable
API_KEY = os.environ.get("PKMDEX_API_KEY", "")


def verify_api_key(x_api_key: str = Header(...)) -> None:
    """Verify API key from request header.

    Args:
        x_api_key: API key from X-API-Key header

    Raises:
        HTTPException: If API key is invalid or missing
    """
    if not API_KEY:
        raise HTTPException(
            status_code=500, detail="Server configuration error: API key not set"
        )
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


class SyncRequest(BaseModel):
    """Request body for sync endpoint."""

    exported_at: str
    version: str
    schema_version: Optional[int] = None
    cards: list[dict]
    card_names: list[dict]
    owned_cards: list[dict]
    set_cache: list[dict]


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


@app.post("/api/sync")
async def sync_collection(
    sync_data: SyncRequest, _: None = Depends(verify_api_key)
) -> dict:
    """Sync collection from CLI export.

    Accepts JSON export from 'pkm export' and imports into web database.
    Requires X-API-Key header for authentication.

    Args:
        sync_data: Export data from CLI

    Returns:
        Dict with sync results and metadata
    """
    try:
        # Convert Pydantic model to dict for import
        export_dict = sync_data.model_dump()

        # Import into database (replaces existing data)
        result = db.import_from_json_dict(export_dict)

        return {
            "success": True,
            "synced_at": datetime.now().isoformat(),
            "cards_imported": result.get("total_cards", 0),
            "owned_cards_imported": result.get("owned_cards_count", 0),
            "original_export_time": sync_data.exported_at,
            "message": "Collection synced successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to sync collection: {str(e)}"
        )
