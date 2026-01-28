"""FastAPI web application for Pokemon card collection."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from datetime import datetime
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db

app = FastAPI(title="Pokemon Card Collection")


def api_error(status_code: int, error_type: str, detail: str) -> HTTPException:
    """Standardized error response for API endpoints.
    
    Makes error responses consistent and more helpful for debugging.
    
    Args:
        status_code: HTTP status code
        error_type: Short error type identifier
        detail: Human-readable error message
        
    Returns:
        HTTPException with standardized format
    """
    return HTTPException(
        status_code=status_code,
        detail={
            "error": error_type,
            "message": detail,
            "timestamp": datetime.now().isoformat()
        }
    )

# Mount static files directory
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

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
        raise api_error(500, "server_config", "API key not set in server configuration")
    if x_api_key != API_KEY:
        raise api_error(403, "invalid_api_key", "The provided API key is invalid")


class CardFilterParams(BaseModel):
    """Query parameters for card filtering with validation."""
    
    language: str = "de"
    set_id: Optional[str] = None
    card_type: Optional[str] = None
    category: Optional[str] = None
    rarity: Optional[str] = None
    stage: Optional[str] = None
    name: Optional[str] = None
    regulation_mark: Optional[str] = None
    legal_standard: Optional[bool] = None


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
async def get_cards(params: CardFilterParams = Depends()) -> list[dict]:
    """Get owned cards with optional filters.

    Args:
        language: Language code (e.g., 'de', 'en')
        set_id: Filter by set ID
        card_type: Filter by Pokemon type (e.g., 'Fire', 'Water')
        category: Filter by category (e.g., 'Pokémon', 'Trainer', 'Energy')
        rarity: Filter by rarity (e.g., 'Common', 'Rare', 'Ultra Rare')
        stage: Filter by stage (e.g., 'Basic', 'Stage1', 'Stage2')
        name: Search by card name (partial match, case-insensitive)
        regulation_mark: Filter by regulation mark (e.g., 'D', 'E', 'F', 'G', 'H')
        legal_standard: Filter by standard format legality (true for legal only, false for not legal)

    Returns:
        List of owned cards matching filters
    """
    return db.get_v2_owned_cards(
        language=params.language,
        set_id=params.set_id,
        card_type=params.card_type,
        category=params.category,
        rarity=params.rarity,
        stage=params.stage,
        name=params.name,
        regulation_mark=params.regulation_mark,
        legal_standard=params.legal_standard,
    )


@app.get("/api/filter-options")
async def get_filter_options() -> dict:
    """Get available filter options from the collection.

    Returns:
        Dict with available types, categories, rarities, stages, sets, and regulation marks
    """
    return db.get_filter_options()


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
