# Pokemon Card Collection Manager - Design Document

> **⚠️ NOTE:** This document is being updated for v2 architecture. Some sections still reference v1 concepts (JSON files, card_cache table). See [docs/schema_v2.md](docs/schema_v2.md) for current v2 schema details.
>
> **v2 Key Changes:**
> - All data in database (cards, card_names, owned_cards tables)
> - No JSON file caching (database-only storage)
> - Price tracking with sync command
> - Migration script for v1→v2 upgrade

## Overview

A CLI tool for managing Pokemon TCG card collections in 11 languages using the TCGdex API. The tool allows users to track their physical cards with support for different variants (normal, reverse, holo, etc.) and stores the collection in a configurable local SQLite database.

## Problem Statement

Pokemon card collectors need a simple way to:
1. Track their card collection locally across multiple languages
2. Identify API set IDs from physical card markings (e.g., "MEG" → "me01")
3. Manage different card variants (normal, reverse, holo)
4. Query their collection efficiently
5. Backup and restore their collection data
6. Configure database location for cloud sync or backup drives

Physical cards show set abbreviations like "MEG" or "SVI" but the TCGdex API uses internal IDs like "me01" or "sv01". Users need a way to discover the correct API set ID.

## Architecture

### Tech Stack

- **Python 3.13+** - Core language
- **tcgdex-sdk** - Official Python SDK for TCGdex API
- **SQLite3** - Built-in database (no external DB needed)
- **uv** - Package manager (auto-installed by installer)
- **argparse** - Built-in CLI argument parsing
- **Standard library** - Minimal dependencies

### Installation

**One-line install:**
```bash
curl -fsSL https://raw.githubusercontent.com/cloonix/pkmdex/main/install.sh | bash
```

**Installation locations:**
- Executable: `~/.local/bin/pkm`
- Application: `~/.local/share/pkmdex-bin/`
- Config: `~/.config/pkmdex/config.json` (Linux/macOS)
- Database: `~/.pkmdex/pokedex.db` (default, configurable)
- Backups: `~/.pkmdex/backups/` (default, configurable)
- Raw JSON: `~/.pkmdex/raw_data/cards/` (language-specific card data)

### Project Structure

```
pkmdex/
├── src/
│   ├── __init__.py
│   ├── cli.py              # CLI interface and command handlers
│   ├── db.py               # Database operations and schema
│   ├── api.py              # TCGdex API wrapper
│   ├── config.py           # Configuration management
│   └── models.py           # Data models
├── tests/
│   ├── test_db.py          # Database tests
│   ├── test_config.py      # Configuration tests
│   └── ...
├── install.sh              # Installation script
├── uninstall.sh            # Uninstallation script
├── pyproject.toml          # Project metadata and dependencies
├── README.md
├── DESIGN.md               # This file
└── AGENTS.md               # Instructions for AI agents
```

## Supported Languages

The tool supports 11 languages from TCGdex API:

| Code | Language | Native Name |
|------|----------|-------------|
| `de` | German | Deutsch |
| `en` | English | English |
| `fr` | French | Français |
| `es` | Spanish | Español |
| `it` | Italian | Italiano |
| `pt` | Portuguese | Português |
| `ja` | Japanese | 日本語 |
| `ko` | Korean | 한국어 |
| `zh-tw` | Chinese Traditional | 繁體中文 |
| `th` | Thai | ไทย |
| `id` | Indonesian | Bahasa Indonesia |

Cards are stored with their language code, allowing collectors to track the same card in multiple languages.

## Database Schema

### Tables

#### `cards`
Stores owned cards in the collection.

```sql
CREATE TABLE cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id TEXT NOT NULL,           -- TCGdex set ID (e.g., "me01")
    card_number TEXT NOT NULL,      -- Card number (e.g., "136")
    tcgdex_id TEXT NOT NULL,        -- Full TCGdex ID (e.g., "me01-136")
    variant TEXT NOT NULL,          -- Variant: normal, reverse, holo, firstEdition
    language TEXT NOT NULL DEFAULT 'de', -- Language code (de, en, fr, etc.)
    quantity INTEGER DEFAULT 1,     -- Number of this variant owned
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tcgdex_id, variant, language)  -- One entry per card+variant+language
);

CREATE INDEX idx_set_id ON cards(set_id);
CREATE INDEX idx_tcgdex_id ON cards(tcgdex_id);
CREATE INDEX idx_language ON cards(language);
CREATE INDEX idx_cards_lookup ON cards(tcgdex_id, language); -- Composite index for analyzer
```

#### `set_cache`
Caches set information to help users discover set IDs.

```sql
CREATE TABLE set_cache (
    set_id TEXT PRIMARY KEY,        -- TCGdex set ID (e.g., "me01")
    name TEXT NOT NULL,             -- Set name
    card_count INTEGER,             -- Total cards in set
    release_date TEXT,              -- Release date
    serie_id TEXT,                  -- Serie ID (e.g., "me")
    serie_name TEXT,                -- Serie name
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Configuration

### Config File

Location: `~/.config/pkmdex/config.json` (Linux/macOS) or `%APPDATA%/pkmdex/config.json` (Windows)

```json
{
  "db_path": "/home/user/.pkmdex/pokedex.db",
  "backups_path": "/home/user/.pkmdex/backups"
}
```

**Note:** Raw JSON data is automatically stored in `{db_path.parent}/raw_data/cards/` with language-specific naming:
- English: `me01-136.json` (for analysis)
- German: `me01-136.de.json` (for display)
- French: `me01-136.fr.json` (for display)

### Configuration Commands

```bash
# Show current configuration
pkm setup --show

# Set custom database path (directory or file)
pkm setup --path ~/Documents/pokemon
pkm setup --path /mnt/backup/cards.db

# Reset to defaults
pkm setup --reset
```

## CLI Interface

### Command Syntax

The CLI uses a concise, typing-friendly format with language support:

```bash
# Format: pkm <command> <lang>:<set_id>:<card_number>[:<variant>]

# Add cards (language-specific)
pkm add de:me01:136              # German card, defaults to normal variant
pkm add de:me01:136:holo         # German card, holo variant
pkm add en:swsh3:136:reverse     # English card, reverse variant

# Remove cards
pkm rm de:me01:136               # Remove normal variant
pkm rm de:me01:136:holo          # Remove holo variant
pkm rm --all de:me01:136         # Remove all variants

# List collection
pkm list                         # All cards
pkm list de                      # Only German cards
pkm list me01                    # Only me01 set

# Search for sets
pkm sets mega                    # Search sets by name
pkm sets                         # List all sets

# Get card info
pkm info de:me01:136

# Show stats
pkm stats

# Export/Import
pkm export                       # Export to backups directory
pkm export -o backup.json        # Custom export path
pkm import backup.json           # Import collection
pkm import -y backup.json        # Skip confirmation

# Configuration
pkm setup --show                 # Show config
pkm setup --path ~/pokemon       # Set custom path
pkm setup --reset                # Reset to defaults
```

### Command Details

#### `setup` - Configure database location

```bash
pkm setup [--show | --reset | --path PATH]

Flags:
  --show     - Display current configuration
  --reset    - Reset to default OS-specific paths
  --path     - Set custom database directory or file path

Examples:
  pkm setup --show
  pkm setup --path ~/Documents/pokemon
  pkm setup --path /mnt/backup/pokemon/cards.db
  pkm setup --reset
```

**Behavior:**
- `--show`: Displays database path, backups path, and config file location
- `--path`: Sets custom path, creates backups subdirectory automatically
- `--reset`: Returns to default OS-specific paths
- Configuration is stored in OS-specific config directory

#### `add` - Add cards to collection

```bash
pkm add <lang>:<set_id>:<card_number>[:<variant>]

Arguments:
  lang        - Language code (de, en, fr, es, it, pt, ja, ko, zh-tw, th, id)
  set_id      - TCGdex set ID (e.g., me01, sv06)
  card_number - Card number in set (e.g., 136, 001)
  variant     - Optional: normal (default), reverse, holo, firstEdition

Examples:
  pkm add de:me01:136              # German, normal variant
  pkm add de:me01:136:holo         # German, holo variant
  pkm add en:swsh3:136:reverse     # English, reverse variant
  pkm add fr:sv06:045              # French, defaults to normal
```

**Behavior:**
1. Parse input format (validates language code)
2. Query TCGdex API for card info in specified language
3. Validate card exists
4. Check if variant is available for this card (optional with --force)
5. If card+variant+language exists in DB: increment quantity
6. If new: insert with quantity=1
7. Save language-specific raw JSON file (e.g., `me01-136.de.json`)
8. Also save English raw JSON file (e.g., `me01-136.json`) for analysis
9. Display success message with card name and image URL

#### `rm` - Remove cards from collection

```bash
pkm rm [--all] <lang>:<set_id>:<card_number>[:<variant>]

Arguments:
  --all       - Optional flag: remove all variants of the card
  lang        - Language code
  set_id      - TCGdex set ID
  card_number - Card number
  variant     - Optional: specific variant to remove

Examples:
  pkm rm de:me01:136              # Remove normal variant (qty -1)
  pkm rm de:me01:136:holo         # Remove holo variant
  pkm rm --all de:me01:136        # Remove all variants at once
```

**Behavior:**
1. Parse input
2. Find matching card+variant+language in DB
3. If `--all` flag: delete all variants for this card+language combo
4. Otherwise: decrement quantity by 1
5. If quantity reaches 0: delete record
6. Display updated quantity or "Removed" message

#### `list` - Display collection

```bash
pkm list [language_or_set_id]

Arguments:
  language_or_set_id - Optional: filter by language code or set ID

Examples:
  pkm list        # All cards
  pkm list de     # Only German cards
  pkm list en     # Only English cards
  pkm list me01   # Only me01 set
```

**Output Format:**
```
Set      Card#  Lang  Name                      Qty   Rarity          Variants
──────────────────────────────────────────────────────────────────────────────
me01     001    de    Bisasam                   1     Common          normal(1)
me01     003    de    Mega-Bisaflor-ex          1     Double rare     holo(1)
sv06     045    fr    Poissoroy                 1     Common          reverse(1)
──────────────────────────────────────────────────────────────────────────────
Total: 3 unique cards, 3 total cards
```

**Columns:**
- Set: TCGdex set ID
- Card#: Card number
- Lang: Language code
- Name: Card name in its language
- Qty: Total quantity across all variants
- Rarity: Card rarity (always in English)
- Variants: variant(quantity) format

#### `sets` - Search and list sets

```bash
pkm sets [search_term]

Arguments:
  search_term - Optional: filter sets by name (case-insensitive)

Examples:
  pkm sets           # List all sets
  pkm sets mega      # Search for "mega" in set names
  pkm sets scarlet   # Search for "scarlet"
```

**Output Format:**
```
Set ID    Name                      Cards  Released
────────────────────────────────────────────────────
me01      Mega-Entwicklung          132    2024-01-26
me02      Fatale Flammen            106    2024-03-22
```

**Behavior:**
1. Fetch all sets from TCGdex API (or from cache if recent)
2. Filter by search term if provided
3. Display in table format
4. Cache results for faster subsequent queries

#### `info` - Get card information

```bash
pkm info <lang>:<set_id>:<card_number>

Arguments:
  lang        - Language code
  set_id      - TCGdex set ID
  card_number - Card number

Examples:
  pkm info de:me01:136
  pkm info en:swsh3:136
```

**Output Format:**
```
Card: Furret (#136)
Set:  Darkness Ablaze (swsh3)
Type: Colorless
HP:   110
Rarity: Common

Available Variants:
  ✓ normal
  ✓ reverse
  ✗ holo
  ✗ firstEdition

In Collection:
  • normal: 2
  • reverse: 1

Image: https://assets.tcgdex.net/en/swsh/swsh3/136/high.png
```

#### `stats` - Collection statistics

```bash
pkm stats

Examples:
  pkm stats
```

**Output Format:**
```
Collection Statistics
────────────────────────────────────────
Total unique cards:     25
Total cards (all):      47
Sets represented:       5
Most collected set:     me01 (12 cards)

Variants breakdown:
  Normal               20
  Reverse              15
  Holo                 12

Rarity breakdown:
  Common               15
  Uncommon             8
  Rare                 2
```

#### `export` - Export collection

```bash
pkm export [-o OUTPUT_FILE]

Arguments:
  -o, --output - Optional: custom output file path

Examples:
  pkm export                    # Export to backups/pkmdex_export_YYYYMMDD_HHMMSS.json
  pkm export -o my_backup.json  # Custom filename
```

**Export Format (JSON):**
```json
{
  "version": "1.0",
  "exported_at": "2026-01-25T14:30:00.123456",
  "version": "1.0",
  "cards": [...],
  "set_cache": [...]
}
```

**Default Location:** `<database_dir>/backups/pkmdex_export_YYYYMMDD_HHMMSS.json`

#### `import` - Import collection

```bash
pkm import [-y] <file>

Arguments:
  file        - JSON file to import
  -y, --yes   - Skip confirmation prompt

Examples:
  pkm import backup.json        # With confirmation
  pkm import -y backup.json     # Skip confirmation
```

**Behavior:**
1. Read and validate JSON file
2. Show warning about replacing current collection
3. Prompt for confirmation (unless -y flag)
4. Replace entire database with imported data
5. Show import summary (cards, cache entries, timestamp)

## API Integration

### TCGdex SDK Usage

The application uses the official Python SDK from TCGdex.

**API Instance Management:**
- Multiple language instances cached globally
- Each language has its own SDK instance
- Singleton pattern prevents duplicate API clients

**Dual JSON Storage Strategy:**
When adding a card in any language:
1. Fetch card data in the requested language (e.g., German)
2. Save language-specific JSON: `me01-136.de.json` (for localized display)
3. Fetch English version and save: `me01-136.json` (for consistent analysis)

This ensures:
- Display shows correct localized names ("Bisasam" for German)
- Analysis uses consistent English data for filtering

### Caching Strategy

**Raw JSON Files:**
- Language-specific files saved when adding cards
- Format: `{tcgdex_id}.{lang}.json` (e.g., `me01-136.de.json`)
- English always saved: `{tcgdex_id}.json` (for analysis)
- No expiration (card data doesn't change)
- Auto-fallback: Load language-specific first, fall back to English

**Set Cache (Database Table):**
- Cached in `set_cache` table
- Refreshed on first `sets` command or when >24 hours old
- Enables fast set search without API calls

### Error Handling

**API Errors:**
- Card not found: "Card not found: me01-136. Try 'pkm sets me' to browse available cards."
- Set not found: "Set not found: me99. Try 'pkm sets' to browse available sets."
- Network errors: "Failed to fetch from API. Please check your internet connection."

**User Input Errors:**
- Invalid format: Show expected format with examples
- Invalid language: Show list of supported languages
- Invalid variant: Show available variants for that card

**Database Errors:**
- Permission issues: Suggest checking file permissions
- Disk full: Provide clear error message

## Data Models

### Python Classes

#### `OwnedCard`
Represents a card variant in the collection.

```python
@dataclass
class OwnedCard:
    tcgdex_id: str          # e.g., "me01-136"
    set_id: str             # e.g., "me01"
    card_number: str        # e.g., "136"
    variant: str            # normal, reverse, holo, firstEdition
    language: str           # de, en, fr, etc.
    quantity: int
    added_at: datetime
    updated_at: datetime
```

#### `CardInfo`
In-memory card information from TCGdex API.
**Note:** Not stored in database - data persisted as language-specific JSON files.

```python
@dataclass
class CardInfo:
    tcgdex_id: str
    name: str
    set_name: Optional[str]
    rarity: Optional[str]   # Always in English
    types: list[str]
    hp: Optional[int]
    available_variants: CardVariants
    image_url: Optional[str]  # High quality PNG
    cached_at: datetime       # Timestamp when fetched from API
```

#### `CardVariants`
Available variants for a card.

```python
@dataclass
class CardVariants:
    normal: bool = False
    reverse: bool = False
    holo: bool = False
    firstEdition: bool = False
```

#### `SetInfo`
Set information (cached in `set_cache` database table).

```python
@dataclass
class SetInfo:
    set_id: str
    name: str
    card_count: Optional[int]
    release_date: Optional[str]
    serie_id: Optional[str]
    serie_name: Optional[str]
    cached_at: datetime       # Timestamp when fetched from API
```

#### `Config`
Application configuration.

```python
@dataclass
class Config:
    db_path: Path
    backups_path: Path
```

## Variant Handling

### Variant Types

1. **normal** - Standard non-foil card
2. **reverse** - Reverse holofoil
3. **holo** - Holofoil
4. **firstEdition** - First edition printing

### Variant Validation

When adding a card:
1. Fetch card data from API
2. Check `variants` field in response
3. If requested variant not available: show error with available variants
4. Example error: "Variant 'holo' not available for Furret (swsh3-136). Available: normal, reverse"

### Multiple Variants

Users can own multiple variants of the same card:
- Each variant is a separate database row
- Same tcgdex_id, different variant value
- Each variant has its own quantity counter

Example:
```
me01-136, normal, de, quantity=2
me01-136, reverse, de, quantity=1
me01-136, holo, de, quantity=1
me01-136, normal, en, quantity=1
```

## Implementation Status

### ✅ Completed Features

- ✅ Core CLI commands (add, rm, list, sets, info, stats)
- ✅ Multi-language support (11 languages)
- ✅ Variant tracking and validation
- ✅ Database caching for performance
- ✅ Set discovery and search
- ✅ Export/import functionality
- ✅ Configurable database location
- ✅ OS-specific config directories
- ✅ One-line curl installation
- ✅ Automatic updates
- ✅ High-quality image URLs
- ✅ English rarity consistency
- ✅ Full test coverage (43 tests)
- ✅ Collection analysis and statistics

### 🔮 Future Enhancements

- Card value tracking
- Wishlist functionality
- Collection completion tracking
- Web interface
- Barcode scanning
- Price alerts
- Trade management
- Deck builder integration

## Testing

### Test Coverage

**Unit Tests:**
- `test_db.py` - Database operations (13 tests)
- `test_config.py` - Configuration management (11 tests)
- `test_analyzer.py` - Collection analysis and statistics (20 tests)

**Test Approach:**
- Temporary databases for isolation
- Mock API responses where needed
- Test error conditions
- Validate data integrity

**Running Tests:**
```bash
uv run pytest tests/ -v
```

## Performance Considerations

**Database:**
- Indexed columns for fast queries (set_id, tcgdex_id, language)
- Single-file SQLite for portability
- Configurable location for cloud sync

**API Calls:**
- Aggressive caching to minimize API requests
- Card metadata cached indefinitely (doesn't change)
- Batch operations where possible

**CLI Speed:**
- Lazy imports for faster startup
- Minimal dependencies
- Direct database queries (no ORM overhead)

## Security & Privacy

- All data stored locally
- No telemetry or tracking
- No authentication required
- Database permissions follow OS defaults
- Optional cloud sync via user-configured paths

## Upgrade Path

**Updating Installation:**
```bash
curl -fsSL https://raw.githubusercontent.com/cloonix/pkmdex/main/install.sh | bash
```

**Data Migration:**
- Export before major updates: `pkm export`
- Database schema migrations handled automatically
- Config preserved across updates

**Breaking Changes:**
- v0.3.0: Removed `card_cache` and `localized_names` database tables
  - Now using language-specific JSON files for card data
  - Export/import functionality remains compatible
  - No action needed - schema auto-migrates on startup
