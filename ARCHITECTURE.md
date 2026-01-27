# Pokemon Card Collection - Complete System Overview

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Local Computer(s) - Synced via Syncthing                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  CLI (pkmdex)                                          │ │
│  │  - Fast, offline card management                       │ │
│  │  - Local SQLite database                               │ │
│  │  - Commands: add, list, search, analyze, export       │ │
│  │  - Data synced between computers via Syncthing        │ │
│  │                                                         │ │
│  │  ~/.local/share/pkmdex/pokedex.db                      │ │
│  │  ~/.config/pkmdex/config.json                          │ │
│  └────────────────┬───────────────────────────────────────┘ │
│                   │                                          │
│                   │ pkm export --push                        │
│                   │ (one-way sync)                           │
└───────────────────┼──────────────────────────────────────────┘
                    │
                    │ HTTPS POST /api/sync
                    │ (authenticated with API key)
                    ▼
┌──────────────────────────────────────────────────────────────┐
│  VPS / Cloud Server                                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Web App (Docker Container)                            │ │
│  │  - FastAPI backend                                     │ │
│  │  - Alpine.js frontend (no build step)                  │ │
│  │  - Read-only display + analytics                       │ │
│  │  - Separate SQLite database                            │ │
│  │                                                         │ │
│  │  /data/pokedex.db (container volume)                   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  https://your-domain.com (nginx reverse proxy + SSL)        │
└──────────────────────────────────────────────────────────────┘
                    ▲
                    │ HTTPS GET
                    │
┌───────────────────┴──────────────────────────────────────────┐
│  Access from Anywhere                                        │
│  - Desktop browsers                                          │
│  - Mobile devices (phone, tablet)                           │
│  - Share with friends                                        │
│  - View collection anywhere                                 │
└──────────────────────────────────────────────────────────────┘
```

## Components

### 1. CLI Tool (Primary Interface)
**Purpose**: Fast, offline card management
**Database**: Local SQLite (`~/.local/share/pkmdex/pokedex.db`)
**Sync**: Syncthing (between your computers)

**Key Commands**:
```bash
# Add cards
pkm add me01:136:normal,reverse

# Search and list
pkm list --set me01
pkm search alakazam

# Export with sync
pkm export --push

# Config management
pkm config set web_api_url https://your-domain.com/api/sync
pkm config set web_api_key your-secret-key
pkm config show
```

### 2. Web App (Display & Analytics)
**Purpose**: Beautiful gallery view, accessible anywhere
**Tech Stack**: FastAPI + Alpine.js + SQLite
**Database**: Separate SQLite in Docker volume
**Access**: Read-only (no adding cards via web)

**Features**:
- Dashboard with collection stats
- Gallery with 125px webp thumbnails (fast loading)
- Modal with high-quality images and metadata
- Language filters
- Set filters
- Future: Analytics charts and graphs

**API Endpoints**:
- `GET /` - Web interface
- `GET /api/stats` - Collection statistics
- `GET /api/cards?language=de&set_id=me01` - Card data
- `POST /api/sync` - Sync from CLI (requires API key)

### 3. Sync Mechanism
**Direction**: One-way (CLI → Web)
**Method**: JSON export pushed to API
**Authentication**: API key (X-API-Key header)
**Frequency**: Manual or automated (cron/systemd)

**Workflow**:
1. Local: Add/modify cards with CLI
2. Local: Run `pkm export --push`
3. CLI exports to JSON
4. CLI POSTs JSON to web API
5. Web imports and displays new data

## Deployment

### Local Development
```bash
# Start web app locally
./start_web.sh

# Or manually
export PKMDEX_API_KEY="your-secret-key"
uvicorn src.web:app --host 0.0.0.0 --port 8000 --reload
```

### Production (Docker)
```bash
# Set API key
export PKMDEX_API_KEY="$(openssl rand -hex 32)"

# Build and run
docker-compose up -d

# Check logs
docker-compose logs -f
```

### CLI Configuration
```bash
# One-time setup
pkm config set web_api_url https://your-domain.com/api/sync
pkm config set web_api_key your-secret-key-here

# Test sync
pkm export --push
```

### Automated Sync (Optional)
```bash
# Hourly sync via cron
0 * * * * /usr/local/bin/pkm export --push --quiet

# Or systemd timer (see DEPLOYMENT.md)
```

## Data Flow

### Adding Cards
```
User → CLI → Local SQLite → Syncthing → Other computers
                │
                └─→ pkm export --push → Web API → Web SQLite → Browsers
```

### Viewing Cards
```
Desktop/Mobile Browser → Web App → Web SQLite → Display
```

### Multi-Computer Sync
```
Computer A ←─ Syncthing ─→ Computer B
     │                          │
Local SQLite              Local SQLite
     │                          │
     └──→ Both can push to web ←┘
```

## Security

### CLI
- Local database (no network access)
- API key stored in `~/.config/pkmdex/config.json`
- File permissions: 600 (user only)

### Web App
- API key authentication required for sync
- Read-only for public viewing
- HTTPS required in production
- Rate limiting via reverse proxy
- API key in environment variable (not in code)

### Best Practices
1. **Strong API key**: Use `openssl rand -hex 32`
2. **HTTPS only**: Use Let's Encrypt
3. **Firewall**: Only expose 80/443 publicly
4. **Reverse proxy**: Use nginx with rate limiting
5. **Keep API key secret**: Never commit to git

## File Locations

### CLI
- Database: `~/.local/share/pkmdex/pokedex.db`
- Config: `~/.config/pkmdex/config.json`
- Backups: `~/.local/share/pkmdex/backups/`
- Cache: `~/.local/share/pkmdex/raw_data/`

### Web (Docker)
- Database: `./data/pokedex.db` (mounted volume)
- Logs: `docker-compose logs -f`
- Code: `/app/` inside container

## Technology Stack

### CLI
- **Language**: Python 3.13+
- **Database**: SQLite
- **API Client**: TCGdex SDK
- **HTTP**: urllib (stdlib)
- **Package Manager**: uv

### Web Backend
- **Framework**: FastAPI
- **Server**: Uvicorn
- **Database**: SQLite
- **Validation**: Pydantic

### Web Frontend
- **Framework**: Alpine.js (CDN, no build)
- **Styling**: Vanilla CSS
- **Images**: TCGdex API (webp/png)

### Infrastructure
- **Container**: Docker
- **Orchestration**: Docker Compose
- **Reverse Proxy**: nginx (your choice)
- **SSL**: Let's Encrypt (your setup)
- **File Sync**: Syncthing (between computers)

## Future Enhancements

### Web Analytics (Planned)
- Set completion percentage
- Rarity distribution charts
- Value over time graphs
- Type distribution
- Category breakdown
- Release year timeline
- Missing cards tracker

### Potential Features
- Mobile app (PWA)
- Wishlist management
- Trade tracker
- Deck builder
- Price alerts
- Collection sharing
- QR code scanner (add cards via camera)

## Development Workflow

### CLI Changes
```bash
# Make changes to src/
python -m pytest tests/
python -m mypy src/
pkm <command>  # Test locally
```

### Web Changes
```bash
# Make changes to src/web.py or src/templates/
./start_web.sh
# Test at http://localhost:8000
```

### Deployment
```bash
# Pull latest code
git pull origin alpine

# Rebuild container
docker-compose down
docker-compose build
docker-compose up -d
```

## Support & Troubleshooting

### CLI Issues
- Check config: `pkm config show`
- Test export: `pkm export` (without --push)
- Check API: `curl -I https://api.tcgdex.net/v2/de`

### Web Issues
- Check logs: `docker-compose logs -f`
- Test API: `curl http://localhost:8000/api/stats`
- Verify API key: Check `PKMDEX_API_KEY` env var

### Sync Issues
- Verify URL: `pkm config get web_api_url`
- Verify key matches: `pkm config get web_api_key`
- Test connection: `curl -I https://your-domain.com`
- Check auth: `curl -H "X-API-Key: key" https://your-domain.com/api/sync`

## Documentation

- `README.md` - Project overview
- `DESIGN.md` - Architecture decisions
- `AGENTS.md` - AI agent guidelines
- `DEPLOYMENT.md` - Deployment guide (detailed)
- `WEB_README.md` - Web app overview
- This file - Complete system overview

## License & Credits

- Built with TCGdex API (https://tcgdex.net)
- Card images © The Pokémon Company
- Licensed under project license (see LICENSE)

---

**Status**: Fully functional and production-ready!
- ✅ CLI tool complete
- ✅ Web interface complete  
- ✅ Sync mechanism working
- ✅ Docker deployment ready
- ✅ Documentation complete
