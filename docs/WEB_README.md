# Pokemon Card Collection - Alpine.js/FastAPI Web UI

## Quick Start

Run the web interface:

```bash
./start_web.sh
```

Or manually:

```bash
uv run uvicorn src.web:app --host 0.0.0.0 --port 8000 --reload
```

Then open your browser to: http://localhost:8000

## Features

- **Dashboard**: Collection statistics (unique cards, total cards, sets, total value)
- **Gallery**: Card thumbnails in a responsive grid
  - 125px wide thumbnails using low-quality webp for fast loading
  - 6-column grid layout
  - Click any card to view details
- **Modal Details**: Full card information
  - High-quality PNG image (400px)
  - Card metadata: name, set, type, HP, stage, rarity
  - Your collection variants and quantities
  - Price information (if available)
- **Filters**: Language selector and set ID filter

## Tech Stack

- **Backend**: FastAPI (Python 3.13+)
- **Frontend**: Alpine.js (via CDN)
- **Database**: SQLite (existing pkmdex database)
- **Images**: TCGdex API (low.webp thumbnails, high.png details)

## API Endpoints

- `GET /` - Main HTML page
- `GET /api/stats` - Collection statistics
- `GET /api/cards?language=de&set_id=me01` - Owned cards with filters

## Architecture

```
src/
├── web.py              # FastAPI application
└── templates/
    └── index.html      # Alpine.js single-page app
```

The web UI reuses the existing database layer (`src/db.py`) and models, requiring no changes to the core CLI functionality.
