# pkmdex - Pokemon Card Collection Manager

A Pokemon TCG collection manager with both CLI and web interface, supporting 11 languages using the TCGdex API.

## Features

- 🌍 Multi-language support (de, en, fr, es, it, pt, ja, ko, zh-tw, th, id)
- 🎴 Track card variants (normal, reverse, holo, firstEdition)
- 💰 Price tracking (EUR/USD) with automatic sync
- 🔍 Collection analysis with powerful filters
- 📤 Export/import for backups
- 💾 Local SQLite database (configurable location)
- 🌐 **NEW:** Web interface for visual browsing and analytics

## Installation

**One-line install:**
```bash
curl -fsSL https://raw.githubusercontent.com/cloonix/pkmdex/main/install.sh | bash
```

Creates `pkm` command in `~/.local/bin/`. Re-run to update. [Uninstall script](https://raw.githubusercontent.com/cloonix/pkmdex/main/uninstall.sh)

**Manual install:**
```bash
git clone https://github.com/cloonix/pkmdex.git && cd pkmdex
uv sync --all-extras  # or: pip install -e ".[dev,web]"
```

## Quick Start

```bash
# Find set IDs
pkm sets mega                    # Search for "mega" in set names

# Add cards (format: lang:set:number[:variant])
pkm add de:me01:136              # German card, normal variant (default)
pkm add de:me01:136:holo         # With specific variant
pkm add en:swsh3:136:reverse     # English card

# View collection
pkm list                         # All cards
pkm list de                      # Filter by language
pkm list me01                    # Filter by set

# Analyze collection
pkm analyze --stage Stage1       # Filter by evolution stage
pkm analyze --type Fire --stats  # Statistics for Fire types
pkm stats                        # Overall statistics

# Sync & maintain
pkm sync                         # Update prices/data from API
pkm export                       # Backup to JSON
pkm import backup.json           # Restore from backup

# Remove cards
pkm rm de:me01:136               # Remove normal variant
pkm rm --all de:me01:136         # Remove all variants

# Launch web interface
pkm-web                          # Opens browser at http://localhost:8080
```

## Web Interface

Launch the web UI with:
```bash
pkm-web
```

The web interface provides:
- **Dashboard**: Collection overview with stats, value tracking, and breakdowns
- **Gallery**: Visual card browser with filters (language, set, search)
- **Analytics**: Interactive filtering and statistics (stage, type, rarity, HP ranges)

All data comes from the same SQLite database used by the CLI - changes are instantly reflected in both interfaces.

## CLI Commands

| Command | Description |
|---------|-------------|
| `add` | Add card to collection |
| `rm` | Remove card from collection |
| `list` | Display collection (filterable by language/set) |
| `sets` | Search/list available sets |
| `info` | Get card information (`--raw` for full API data) |
| `analyze` | Analyze collection with filters (stage, type, rarity, HP, etc.) |
| `stats` | Show collection statistics |
| `sync` | Update prices/data from API (`--stale N` for selective sync) |
| `export/import` | Backup/restore collection |
| `setup` | Configure database path and API URL |
| `cache` | Manage API cache (`--refresh`, `--clear`) |

## Supported Languages

`de` `en` `fr` `es` `it` `pt` `ja` `ko` `zh-tw` `th` `id`

**Card Variants:** `normal` (default) | `reverse` | `holo` | `firstEdition`

## Data Sync

Use `pkm sync` to update prices, legality, and metadata:
- `pkm sync` - Sync all cards
- `pkm sync --stale 7` - Only cards older than 7 days
- `pkm sync --show-changes` - Show price changes

## Analysis Filters

```bash
pkm analyze --stage Stage1           # Evolution stage (Basic, Stage1, Stage2, VMAX, etc.)
pkm analyze --type Fire              # Type (Fire, Water, Grass, Electric, etc.)
pkm analyze --rarity Rare            # Rarity
pkm analyze --hp-min 100             # HP range
pkm analyze --category Pokemon       # Pokemon/Trainer/Energy
pkm analyze --language de --set me01 # Language and set
pkm analyze --type Fire --stats      # Statistics mode
```

**Combine filters:** `pkm analyze --stage Stage1 --type Fire --hp-min 80`

### Statistics Mode

Add `--stats` to show collection statistics instead of a card list:

```bash
# Show overall statistics
pkm analyze --stats

# Statistics for filtered subset
pkm analyze --type Fire --stats
pkm analyze --set me01 --stats
pkm analyze --regulation F --stats --language de
```

### Common Analysis Examples

```bash
# All Stage 1 Fire-type cards
pkm analyze --stage Stage1 --type Fire

# High-HP cards (150+)
pkm analyze --hp-min 150

# Rare cards in German
pkm analyze --rarity Rare --language de

# Complete breakdown by type
pkm analyze --type Grass --stats
```

### Analysis Output

**Card List Mode (default):**
```
Collection Analysis (2 cards)
────────────────────────────────────────────────────────────────────────────────────────────────────
ID           Name                      Stage      Type            HP   Rarity       Qty
────────────────────────────────────────────────────────────────────────────────────────────────────
me01-002     Ivysaur                   Stage1     Grass           110  Common       1  
swsh3-136    Furret                    Stage1     Colorless       110  Uncommon     1  
────────────────────────────────────────────────────────────────────────────────────────────────────
Total: 2 cards
```

**Statistics Mode (`--stats`):**
```
Collection Analysis (2 cards)
────────────────────────────────────────────────────────────

Total Cards:    2
Total Quantity: 2
Average HP:     110

By Stage:
  Stage1            2

By Type:
  Colorless         1
  Grass             1

By Rarity:
  Common            1
  Uncommon          1

By Category:
  Pokemon           2

By Set:
  me01              1
  swsh3             1
```

### Important Notes

- Analysis uses **database queries** for fast, consistent results
- Your collection displays **localized names** from the card_names table
- Filters are case-sensitive (use `Stage1`, not `stage1`)
- Common stages: `Basic`, `Stage1`, `Stage2`, `VMAX`, `VSTAR`, etc.
- Common types: `Fire`, `Water`, `Grass`, `Electric`, `Psychic`, `Fighting`, `Darkness`, `Metal`, `Fairy`, `Dragon`, `Colorless`


## Finding Set IDs

Physical German Pokemon cards often show abbreviations like "MEG" or "SVI", but the TCGdex API uses internal IDs like "me01" or "sv01". Use the `sets` command to discover the correct ID:

```bash
# Search for sets containing "mega"
pkm sets mega

# Output:
# Set ID    Name                Cards  Released
# ─────────────────────────────────────────────
# me01      Mega-Entwicklung    132    2024-01-26
# me02      Fatale Flammen      106    2024-03-22
```

## Examples

### Basic Workflow

```bash
# 1. Find the set ID for your card
pkm sets mega
# → Shows "me01" is "Mega-Entwicklung"

# 2. Add a German card (defaults to normal variant)
pkm add de:me01:136
# → Added: Pottrott (me01-136) - normal

# 3. Add another copy (accumulates)
pkm add de:me01:136
# → Updated: Pottrott - normal (qty: 2)

# 4. Add different variant
pkm add de:me01:136:reverse
# → Added: Pottrott (me01-136) - reverse

# 5. View your collection
pkm list me01
# Set      Card#  Lang  Name                      Qty   Rarity          Variants
# ──────────────────────────────────────────────────────────────────────────────
# me01     136    de    Pottrott                  3     Uncommon        normal(2), reverse(1)
```

## Configuration

```bash
pkm setup --show                              # Show current config
pkm setup --path ~/Documents/pokemon         # Custom database path
pkm setup --api-url https://your-api.com     # Custom API (or use TCGDEX_API_URL env var)
pkm setup --reset                             # Reset to defaults
```

**Default locations:**
- Database: `~/.pkmdex/pokedex.db`
- Backups: `~/.pkmdex/backups/`
- Config: `~/.config/pkmdex/config.json`

## Development

**Requirements:** Python 3.13+, tcgdex-sdk

```bash
python -m pytest tests/  # Run tests
python -m mypy src/      # Type checking
```

**Documentation:** See [DESIGN.md](DESIGN.md) and [AGENTS.md](AGENTS.md)

## Technical Stack

- Python 3.13+ | SQLite3 | TCGdex API | uv package manager
- Minimal dependencies: standard library + tcgdex-sdk

## Roadmap

**Current:** Multi-language support • Price tracking • Collection analysis • Export/import • Smart sync

**Future:** Wishlist • Set completion tracking • Web interface • Barcode scanning • Trade tracking
