# pkmdex - Technical Specification

**Version**: 1.0  
**Last Updated**: 2026-01-25  
**Target Audience**: Future developers, maintainers, and contributors

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Data Flow](#data-flow)
4. [Module Specifications](#module-specifications)
5. [Database Schema](#database-schema)
6. [API Integration](#api-integration)
7. [Raw JSON Storage Strategy](#raw-json-storage-strategy)
8. [Cache System](#cache-system)
9. [Collection Analysis](#collection-analysis)
10. [Configuration Management](#configuration-management)
11. [Error Handling](#error-handling)
12. [Testing Strategy](#testing-strategy)
13. [Design Decisions](#design-decisions)
14. [Future Enhancements](#future-enhancements)

---

## Overview

**pkmdex** is a command-line interface (CLI) tool for managing Pokemon Trading Card Game (TCG) collections with multi-language support. It integrates with the TCGdex API to fetch card metadata and provides powerful analysis capabilities.

### Core Principles

1. **Simplicity**: Keep the codebase minimal and focused
2. **Performance**: Aggressive caching, minimal API calls
3. **Multi-language**: Support 11 languages while maintaining analysis consistency
4. **Type Safety**: Use Python type hints throughout
5. **User Experience**: Fast typing-friendly CLI, helpful error messages

### Key Features

- Multi-language card collection management (11 languages)
- Local SQLite database with configurable location
- Card metadata caching (reduce API calls)
- English raw JSON storage for consistent analysis
- Powerful filtering and analysis engine
- Export/import for backups and migration

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
│                        (cli.py)                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Commands: add, rm, list, info, analyze, cache, etc. │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────┬─────────────────────────────────┬──────────────┘
             │                                 │
             ▼                                 ▼
┌──────────────────────────┐      ┌──────────────────────────┐
│    Business Logic Layer   │      │    Analysis Layer       │
│  ┌────────┐  ┌─────────┐ │      │   (analyzer.py)         │
│  │ db.py  │  │ api.py  │ │      │  - Filtering            │
│  │        │  │         │ │      │  - Statistics           │
│  └────────┘  └─────────┘ │      │  - Querying             │
│  ┌─────────────────────┐ │      └──────────────────────────┘
│  │ config.py           │ │
│  └─────────────────────┘ │
└──────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────┐
│                     Data Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   SQLite DB  │  │  Raw JSON    │  │  TCGdex API  │       │
│  │  (pokedex.db)│  │  (cards/*..) │  │  (REST API)  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└──────────────────────────────────────────────────────────────┘
```

### Module Organization

```
src/
├── cli.py          # Entry point, argument parsing, command routing
├── db.py           # Database operations, schema, CRUD
├── api.py          # TCGdex API wrapper, HTTP client
├── analyzer.py     # Collection analysis, filtering, statistics
├── config.py       # Configuration management, file I/O
└── models.py       # Dataclasses, type definitions
```

---

## Data Flow

### Adding a Card

```
User: pkm add de:me01:136:holo
         │
         ▼
    CLI Parser (cli.py)
         │
         ├─→ parse_card_input("de:me01:136:holo")
         │   Returns: (lang="de", set_id="me01", card_num="136", variant="holo")
         ▼
    fetch_and_cache_card(lang, set_id, card_num)
         │
         ├─→ Check cache: db.get_cached_card("me01-136")
         │   └─→ If found: Return cached CardInfo ✓
         │
         ├─→ If not cached: api.get_card(set_id, card_num)
         │   ├─→ Fetch from German API (for UI display)
         │   ├─→ Fetch from English API (for raw JSON + rarity)
         │   ├─→ Save English raw JSON: config.save_raw_card_data()
         │   └─→ Cache metadata: db.cache_card()
         ▼
    db.add_card_variant("me01-136", "holo", lang="de", qty=1)
         │
         ├─→ INSERT INTO cards (...) ON CONFLICT DO UPDATE
         │   (Accumulates quantity if already owned)
         ▼
    Display: "✓ Added: Pottrott (me01-136) [de] - holo"
```

### Analyzing Collection

```
User: pkm analyze --stage Stage1 --type Fire
         │
         ▼
    CLI Parser (cli.py)
         │
         └─→ AnalysisFilter(stage="Stage1", type="Fire", ...)
         │
         ▼
    analyzer.analyze_collection(filter_criteria)
         │
         ├─→ db.get_owned_card_ids()
         │   Returns: [(tcgdex_id, language), ...]
         │
         ├─→ For each card:
         │   ├─→ config.load_raw_card_data(tcgdex_id)  # English JSON
         │   ├─→ db.get_owned_cards() # Ownership info
         │   ├─→ Apply filters (stage, type, HP, rarity, etc.)
         │   └─→ Create CardAnalysis object
         │
         ▼
    Display card list or statistics
```

---

## Module Specifications

### cli.py

**Purpose**: Command-line interface entry point, argument parsing, user interaction

**Key Functions**:

- `main()` - Entry point, initializes DB, routes commands
- `create_parser()` - Creates argparse ArgumentParser with all commands
- `parse_card_input(card_str)` - Parses "lang:set:num:variant" format
- `handle_add(args)` - Adds card to collection
- `handle_rm(args)` - Removes card from collection
- `handle_list(args)` - Lists collection with filters
- `handle_info(args)` - Shows card details
- `handle_analyze(args)` - Analyzes collection with filters
- `handle_cache(args)` - Manages cache (show, refresh, update, clear)
- `handle_stats(args)` - Shows collection statistics
- `handle_setup(args)` - Configures database path
- `handle_export(args)` - Exports collection to JSON
- `handle_import(args)` - Imports collection from JSON
- `fetch_and_cache_card(lang, set_id, card_num)` - Fetches from API or cache

**Input Format**: `<lang>:<set_id>:<card_number>[:<variant>[,<variant>]]`

Examples:
- `de:me01:136` - German card, normal variant (default)
- `en:swsh3:025:holo` - English card, holo variant
- `fr:me01:001:normal,reverse` - French card, multiple variants

**Error Handling**:
- Returns exit code 0 for success, 1 for errors
- User-friendly error messages with suggestions
- Validates input format before API calls

---

### db.py

**Purpose**: Database operations, schema management, CRUD functions

**Key Functions**:

- `init_database(db_path)` - Creates schema, runs migrations
- `get_connection()` - Context manager for DB connections
- `add_card_variant(tcgdex_id, variant, lang, qty)` - Adds/updates owned card
- `remove_card_variant(tcgdex_id, variant, lang, qty)` - Removes card
- `remove_all_card_variants(tcgdex_id, lang)` - Removes all variants
- `get_owned_cards(set_id, language)` - Lists owned cards with filters
- `get_owned_card_ids()` - Returns unique (tcgdex_id, language) pairs
- `cache_card(card_info)` - Caches card metadata
- `get_cached_card(tcgdex_id)` - Retrieves cached card
- `cache_sets(set_infos)` - Caches set information
- `get_cached_sets(search_term)` - Retrieves cached sets
- `clear_card_cache()` - Clears card cache
- `clear_set_cache()` - Clears set cache
- `get_cache_stats()` - Returns cache statistics
- `get_collection_stats()` - Returns collection statistics
- `export_to_json(output_path)` - Exports collection
- `import_from_json(input_path)` - Imports collection
- `parse_tcgdex_id(tcgdex_id)` - Parses "me01-136" → ("me01", "136")

**Database Path Resolution**:
1. Check `DB_PATH` global (set by tests)
2. Load from config file
3. Fallback to default: `~/.local/share/pkmdex/pokedex.db`

**Transaction Handling**:
- All write operations use transactions
- Context manager ensures commit/rollback
- No manual transaction management needed

---

### api.py

**Purpose**: TCGdex API integration, HTTP client wrapper

**Key Classes**:

- `TCGdexAPI(language)` - API client for specific language
- `PokedexAPIError` - Custom exception for API errors

**Key Functions**:

- `get_card(set_id, card_number)` - Fetches card by set and number
  - Fetches from language-specific API (for UI display)
  - **ALWAYS fetches from English API** (for raw JSON + rarity)
  - Saves English raw JSON to file
  - Returns CardInfo with localized display data
- `get_card_by_id(tcgdex_id)` - Fetches card by full ID
- `get_all_sets()` - Fetches all available sets
- `get_set(set_id)` - Fetches specific set information
- `get_api(language)` - Singleton factory for API instances

**API Endpoints** (TCGdex v2):
- Base URL: `https://api.tcgdex.net/v2/{lang}/`
- Card: `sets/{set_id}/{card_number}`
- Set: `sets/{set_id}`
- All Sets: `sets`

**English Data Strategy**:
- **UI Display**: Uses language-specific API response
- **Raw JSON**: Always saves English API response
- **Rarity**: Always uses English rarity value
- **Why**: Consistent analysis across all languages

---

### analyzer.py

**Purpose**: Collection analysis, filtering, statistics

**Key Dataclasses**:

- `AnalysisFilter` - Filter criteria for queries
  - `stage: Optional[str]` - Evolution stage
  - `type: Optional[str]` - Pokemon type
  - `rarity: Optional[str]` - Card rarity
  - `hp_min: Optional[int]` - Minimum HP
  - `hp_max: Optional[int]` - Maximum HP
  - `category: Optional[str]` - Card category
  - `language: Optional[str]` - Language filter
  - `set_id: Optional[str]` - Set filter

- `CardAnalysis` - Analysis result
  - `tcgdex_id: str` - Card ID
  - `name: str` - Card name (English)
  - `language: str` - UI language
  - `set_name: str` - Set name (English)
  - `stage: Optional[str]` - Evolution stage
  - `types: Optional[list[str]]` - Pokemon types
  - `hp: Optional[int]` - Health points
  - `rarity: Optional[str]` - Rarity
  - `category: str` - Category
  - `quantity: int` - Owned quantity
  - `variants: list[str]` - Owned variants

**Key Functions**:

- `load_card_with_ownership(tcgdex_id, language)` - Loads raw JSON + ownership
- `analyze_collection(filter_criteria)` - Filters collection
- `get_collection_statistics(cards)` - Generates statistics

**Filter Logic**:
- All filters are optional (AND logic)
- `None` values are handled gracefully
- Case-sensitive matching (e.g., "Stage1" not "stage1")

**Statistics**:
- Total cards/quantity
- Average HP
- Count by: stage, type, rarity, category, set

---

### config.py

**Purpose**: Configuration management, file I/O, paths

**Key Dataclass**:

- `Config`
  - `db_path: Path` - Database file path
  - `backups_path: Path` - Backup directory
  - `raw_data_path: Path` - Raw JSON directory

**Key Functions**:

- `get_config_dir()` - Returns `~/.config/pkmdex/`
- `get_data_dir()` - Returns `~/.local/share/pkmdex/`
- `get_config_file()` - Returns config file path
- `load_config()` - Loads config from JSON
- `save_config(config)` - Saves config to JSON
- `setup_database_path(db_path)` - Configures custom DB location
- `reset_config()` - Resets to default configuration
- `save_raw_card_data(tcgdex_id, data)` - Saves English raw JSON
- `load_raw_card_data(tcgdex_id)` - Loads English raw JSON

**File Locations** (XDG Base Directory Specification):
- Config: `~/.config/pkmdex/config.json`
- Data: `~/.local/share/pkmdex/`
  - Database: `pokedex.db`
  - Backups: `backups/`
  - Raw JSON: `raw_data/cards/{tcgdex_id}.json`

**Backward Compatibility**:
- `from_dict()` handles missing `raw_data_path` field
- Defaults to `db_path.parent / "raw_data"`

---

### models.py

**Purpose**: Type definitions, data models, dataclasses

**Key Classes**:

- `OwnedCard` - Represents a card in the collection
- `CardInfo` - Card metadata from API
- `SetInfo` - Set metadata from API
- `CardVariants` - Available variants for a card

**Conversion Methods**:
- `from_db_row(row)` - Creates instance from SQLite row
- `from_api_response(data)` - Creates instance from API JSON

---

## Database Schema

### Schema Version: 2

```sql
-- Owned cards table
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id TEXT NOT NULL,              -- e.g., "me01"
    card_number TEXT NOT NULL,         -- e.g., "136"
    tcgdex_id TEXT NOT NULL,           -- e.g., "me01-136"
    variant TEXT NOT NULL,             -- normal, reverse, holo, firstEdition
    language TEXT NOT NULL DEFAULT 'de', -- de, en, fr, es, it, pt, ja, ko, zh-tw, th, id
    quantity INTEGER DEFAULT 1,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(tcgdex_id, variant, language)
);

CREATE INDEX IF NOT EXISTS idx_cards_set_id ON cards(set_id);
CREATE INDEX IF NOT EXISTS idx_cards_tcgdex_id ON cards(tcgdex_id);
CREATE INDEX IF NOT EXISTS idx_cards_language ON cards(language);

-- Card metadata cache
CREATE TABLE IF NOT EXISTS card_cache (
    tcgdex_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    set_name TEXT,
    rarity TEXT,
    types TEXT,                        -- JSON array: ["Fire", "Dragon"]
    hp INTEGER,
    available_variants TEXT,           -- JSON: {"normal": true, "holo": false}
    image_url TEXT,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_card_cache_cached_at ON card_cache(cached_at);

-- Set information cache
CREATE TABLE IF NOT EXISTS set_cache (
    set_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    card_count INTEGER,
    release_date TEXT,
    logo_url TEXT,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_set_cache_cached_at ON set_cache(cached_at);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Migrations

**Version 1 → 2**: Add `language` column to `cards` table
- Default value: `'de'` (backward compatible)
- Allows multi-language collections

---

## API Integration

### TCGdex API v2

**Base URL**: `https://api.tcgdex.net/v2/{lang}/`

**Supported Languages**:
- `de` - German (Deutsch)
- `en` - English
- `fr` - French (Français)
- `es` - Spanish (Español)
- `it` - Italian (Italiano)
- `pt` - Portuguese (Português)
- `ja` - Japanese (日本語)
- `ko` - Korean (한국어)
- `zh-tw` - Chinese Traditional (繁體中文)
- `th` - Thai (ไทย)
- `id` - Indonesian (Bahasa Indonesia)

**Key Endpoints**:

1. **Get Card**:
   - URL: `GET /v2/{lang}/sets/{set_id}/{card_number}`
   - Example: `GET /v2/de/sets/me01/136`
   - Returns: Card object with metadata

2. **Get Set**:
   - URL: `GET /v2/{lang}/sets/{set_id}`
   - Example: `GET /v2/en/sets/swsh3`
   - Returns: Set object with card list

3. **List All Sets**:
   - URL: `GET /v2/{lang}/sets`
   - Returns: Array of set objects

**Response Structure** (Card):
```json
{
  "id": "me01-136",
  "localId": "136",
  "name": "Furret",
  "category": "Pokemon",
  "hp": 110,
  "types": ["Colorless"],
  "stage": "Stage1",
  "evolveFrom": "Sentret",
  "rarity": "Uncommon",
  "set": {
    "id": "swsh3",
    "name": "Darkness Ablaze",
    "cardCount": {"total": 201, "official": 189}
  },
  "variants": {
    "normal": true,
    "reverse": true,
    "holo": false,
    "firstEdition": false
  },
  "image": "https://assets.tcgdex.net/en/swsh/swsh3/136/high.png"
}
```

### SDK Usage

```python
from tcgdexsdk import TCGdex

# Initialize SDK
sdk = TCGdex("de")  # German

# Fetch card
card = await sdk.card.get("me01-136")

# Fetch set
set_info = await sdk.set.get("me01")

# List all sets
sets = await sdk.set.list()
```

**Important**: TCGdex SDK returns dataclass instances, not dicts. Use `dataclasses.asdict()` for serialization.

---

## Raw JSON Storage Strategy

### Architecture Decision: English-Only Raw JSON

**Decision**: Store only English raw JSON data, regardless of UI language.

**Rationale**:

1. **Consistent Analysis**:
   - Filters work uniformly: `--stage Stage1` matches all cards
   - No translation needed for query terms
   - Predictable field values across languages

2. **Single Source of Truth**:
   - One canonical format for all cards
   - Simpler data model (one file per card)
   - Easier maintenance and debugging

3. **Localization Separation**:
   - **Display Data**: Stored in `card_cache` table (localized)
   - **Analysis Data**: Stored in raw JSON files (English)
   - Clean separation of concerns

4. **Performance**:
   - Smaller storage footprint
   - Faster file I/O (one read instead of N language files)
   - No translation layer needed

**Trade-offs**:

❌ **Cons**:
- Can't see German card names in raw JSON
- Lost translation study capability
- Extra API call for English data

✅ **Pros** (outweigh cons):
- Consistent analysis queries
- Simpler codebase
- Better performance
- Single source of truth

### Implementation

**When English JSON is Saved**:
1. `pkm add de:me01:136` - Fetches German (display) + English (JSON)
2. `pkm info de:me01:136` - Uses cached display data
3. `pkm info de:me01:136 --raw` - Shows English JSON (fetches if missing)
4. `pkm cache --update` - Refetches English JSON for all owned cards

**File Naming**:
- Format: `{tcgdex_id}.json`
- Example: `me01-136.json`
- No language suffix (always English)

**Data Structure**:
```json
{
  "name": "Bulbasaur",         // English
  "types": ["Grass"],          // English
  "stage": "Basic",            // English
  "rarity": "Common",          // English
  "category": "Pokemon",       // English
  "set": {
    "name": "Mega Evolution"   // English
  }
}
```

---

## Cache System

### Three-Tier Caching

1. **Card Metadata Cache** (SQLite `card_cache` table)
   - Stores: Name, rarity, types, HP, variants, image URL
   - Purpose: Fast display without API calls
   - Invalidation: Manual (`pkm cache --clear --type cards`)

2. **Set Information Cache** (SQLite `set_cache` table)
   - Stores: Set name, card count, release date, logo URL
   - Purpose: Fast set lookups, search
   - Invalidation: Automatic (24 hours) or manual
   - Auto-refresh: `pkm sets` command

3. **Raw JSON Cache** (File system)
   - Stores: Complete English API response
   - Purpose: Analysis, debugging, offline access
   - Invalidation: Manual (`rm` files) or `pkm cache --update`

### Cache Commands

```bash
# View cache statistics
pkm cache

# Refresh set cache from API
pkm cache --refresh

# Update card cache for all owned cards
pkm cache --update

# Clear specific cache
pkm cache --clear --type cards   # Clear card metadata
pkm cache --clear --type sets    # Clear set information
pkm cache --clear --type all     # Clear all caches
```

### Cache Statistics

```bash
$ pkm cache

Cache Statistics
────────────────────────────────────────────────────────────

Card Cache:
  Entries: 42
  Oldest:  2026-01-25 10:30:15
  Newest:  2026-01-25 14:22:03

Set Cache:
  Entries: 138
  Oldest:  2026-01-20 08:15:42
  Newest:  2026-01-20 08:15:42

💡 Tip: Set cache is 5 days old. Run 'pkm cache --refresh' to update.
```

### Cache Update Strategy

**`pkm cache --update` Workflow**:
1. Get all owned card IDs from database
2. For each card:
   - Fetch from English API
   - Save raw JSON file
   - Update card_cache table
3. Report: X updated, Y errors

**When to Update**:
- New card data available (errata, fixes)
- Want latest English translations
- Migrating from old German JSON files
- Rebuilding after data corruption

---

## Collection Analysis

### Analysis Engine

**Purpose**: Query collection using English raw JSON data with powerful filters.

**Filter Capabilities**:

| Filter | Type | Example | Description |
|--------|------|---------|-------------|
| `--stage` | String | `Basic`, `Stage1`, `Stage2` | Evolution stage |
| `--type` | String | `Fire`, `Water`, `Grass` | Pokemon type |
| `--rarity` | String | `Common`, `Rare`, `Ultra Rare` | Card rarity |
| `--hp-min` | Integer | `100` | Minimum HP |
| `--hp-max` | Integer | `200` | Maximum HP |
| `--category` | String | `Pokemon`, `Trainer` | Card category |
| `--language` | String | `de`, `en`, `fr` | UI language filter |
| `--set` | String | `me01`, `swsh3` | Set ID filter |
| `--stats` | Flag | - | Show statistics mode |

**Filter Logic**:
- All filters use **AND** logic (must match all specified filters)
- Filters are optional (omit = no filter applied)
- Case-sensitive matching
- `None` values handled gracefully

### Common Stages

- `Basic` - Basic Pokemon (no evolution)
- `Stage1` - First evolution (e.g., Ivysaur)
- `Stage2` - Second evolution (e.g., Venusaur)
- `BREAK` - Pokemon BREAK
- `V` - Pokemon V
- `VMAX` - Pokemon VMAX
- `VSTAR` - Pokemon VSTAR
- `GX` - Pokemon GX
- `EX` - Pokemon EX

### Common Types

`Fire`, `Water`, `Grass`, `Electric`, `Psychic`, `Fighting`, `Darkness`, `Metal`, `Fairy`, `Dragon`, `Colorless`

### Analysis Examples

```bash
# Find all Stage1 Fire-type cards
pkm analyze --stage Stage1 --type Fire

# Find high HP cards (100+)
pkm analyze --hp-min 100

# Find German collection cards only
pkm analyze --language de

# Find cards in a specific set
pkm analyze --set me01

# Complex query: Stage2 Water-type with HP 120-180
pkm analyze --stage Stage2 --type Water --hp-min 120 --hp-max 180

# Statistics for all Fire types
pkm analyze --type Fire --stats
```

### Output Modes

**1. Card List (default)**:
```
Collection Analysis (5 cards)
────────────────────────────────────────────────────────────────
ID           Name          Stage      Type       HP   Rarity     Qty
────────────────────────────────────────────────────────────────
me01-001     Bulbasaur     Basic      Grass      80   Common     1  
me01-002     Ivysaur       Stage1     Grass      110  Common     1  
swsh3-136    Furret        Stage1     Colorless  110  Uncommon   1  
────────────────────────────────────────────────────────────────
Total: 5 cards
```

**2. Statistics Mode (`--stats`)**:
```
Collection Analysis (5 cards)
────────────────────────────────────────────────────────────

Total Cards:    5
Total Quantity: 8
Average HP:     105

By Stage:
  Basic             2
  Stage1            3

By Type:
  Colorless         1
  Fire              1
  Grass             3

By Rarity:
  Common            3
  Rare              1
  Uncommon          1
```

---

## Configuration Management

### Configuration File

**Location**: `~/.config/pkmdex/config.json`

**Structure**:
```json
{
  "db_path": "/home/user/.local/share/pkmdex/pokedex.db",
  "backups_path": "/home/user/.local/share/pkmdex/backups",
  "raw_data_path": "/home/user/.local/share/pkmdex/raw_data"
}
```

### Configuration Commands

```bash
# Show current configuration
pkm setup --show

# Set custom database path (directory)
pkm setup --path ~/Documents/pokemon

# Set custom database path (file)
pkm setup --path ~/pokemon-collection.db

# Reset to default configuration
pkm setup --reset
```

### Path Resolution

**Database Path** (`db_path`):
1. Check config file
2. Fallback to: `~/.local/share/pkmdex/pokedex.db`

**Backups Path** (`backups_path`):
1. Check config file
2. Fallback to: `{db_path.parent}/backups`

**Raw Data Path** (`raw_data_path`):
1. Check config file
2. Fallback to: `{db_path.parent}/raw_data`

### Custom Locations

**Directory Input**:
```bash
pkm setup --path ~/pokemon
# Creates:
#   ~/pokemon/pokedex.db
#   ~/pokemon/backups/
#   ~/pokemon/raw_data/
```

**File Input**:
```bash
pkm setup --path ~/my-cards.db
# Creates:
#   ~/my-cards.db
#   ~/backups/
#   ~/raw_data/
```

---

## Error Handling

### Error Categories

1. **User Input Errors** (`ValueError`)
   - Invalid format: "Expected lang:set:card"
   - Missing required fields
   - Invalid variant name

2. **API Errors** (`PokedexAPIError`)
   - Card not found
   - Set not found
   - Network connection failed
   - API rate limiting

3. **Database Errors** (`DatabaseError`)
   - File permission issues
   - Disk space full
   - Corrupted database

4. **File I/O Errors** (`IOError`)
   - Cannot create directory
   - Cannot write config
   - Cannot read raw JSON

### Error Messages

**Good Error Messages**:
- What went wrong
- Why it happened (if known)
- How to fix it
- Suggest alternative commands

**Example**:
```
Error: Card not found: me01-999

Possible causes:
  - Card number doesn't exist in this set
  - Set ID is incorrect

Try 'pkm sets mega' to search for the right set ID.
```

### Exit Codes

- `0` - Success
- `1` - Error (any kind)

---

## Testing Strategy

### Test Organization

```
tests/
├── test_config.py    # Configuration management tests
├── test_db.py        # Database operations tests
└── test_api.py       # API integration tests (future)
```

### Test Coverage

**Current Coverage**: 24 tests, all passing

**Key Test Areas**:

1. **Configuration** (`test_config.py`)
   - Default config creation
   - Save/load config
   - Custom paths (directory and file)
   - Config reset
   - Backward compatibility

2. **Database** (`test_db.py`)
   - Schema initialization
   - Add/remove cards
   - Variant accumulation
   - Query filters
   - Cache operations
   - Export/import
   - Statistics

3. **Future Tests**:
   - API mocking
   - Analysis filtering
   - Multi-language scenarios

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_db.py

# Run with verbose output
pytest tests/ -v

# Run specific test
pytest tests/test_db.py::test_add_card_variant_new -v
```

### Test Database

Tests use in-memory SQLite (`:memory:`) for speed and isolation.

---

## Design Decisions

### 1. English-Only Raw JSON

**Decision**: Store only English raw JSON, not language-specific JSON.

**Alternatives Considered**:
- Store language-specific JSON
- Store both English and language-specific JSON

**Rationale**:
- Consistent analysis queries
- Single source of truth
- Simpler codebase
- Better performance

**Trade-offs**: Lost native language data, but gained consistency.

---

### 2. SQLite for Storage

**Decision**: Use SQLite for owned cards and cache.

**Alternatives Considered**:
- JSON files for everything
- PostgreSQL/MySQL
- Plain text files

**Rationale**:
- Zero configuration
- Single file portability
- ACID transactions
- Fast queries
- Standard library support

**Trade-offs**: Not suitable for concurrent multi-user access (not a requirement).

---

### 3. Aggressive Caching

**Decision**: Cache card metadata, set information, and raw JSON files.

**Rationale**:
- Reduce API calls
- Faster response times
- Offline capability
- Respect API rate limits

**Trade-offs**: Stale data possible, but acceptable for card collections.

---

### 4. CLI Over GUI

**Decision**: Command-line interface only.

**Alternatives Considered**:
- Web UI
- Desktop GUI (Qt/Tkinter)
- Mobile app

**Rationale**:
- Faster for power users
- Scriptable and automatable
- Minimal dependencies
- Cross-platform compatible
- Easy to maintain

**Trade-offs**: Less accessible for non-technical users.

---

### 5. Type Hints Throughout

**Decision**: Use Python type hints for all functions.

**Rationale**:
- Better IDE support
- Catch errors early with mypy
- Self-documenting code
- Easier refactoring

**Trade-offs**: Slightly more verbose, but worth it.

---

### 6. Dataclasses Over Dicts

**Decision**: Use dataclasses for data models.

**Alternatives Considered**:
- Named tuples
- Plain dicts
- Pydantic models

**Rationale**:
- Type safety
- Clear structure
- Easy serialization
- Standard library (no deps)

**Trade-offs**: More boilerplate, but clearer code.

---

### 7. Multi-Language Support

**Decision**: Support 11 languages via TCGdex API.

**Rationale**:
- Pokemon is global
- Users collect in native language
- TCGdex supports it natively

**Implementation**:
- UI displays in user's language
- Raw JSON always in English
- Analysis works across languages

---

## Future Enhancements

### Planned Features

1. **Wishlist Management**
   - Track cards you want to acquire
   - Mark as "wanted" with priority
   - Generate shopping lists

2. **Price Tracking**
   - Integrate with price APIs
   - Show collection value
   - Track price history

3. **Set Completion Tracking**
   - Show X/Y cards owned per set
   - Highlight missing cards
   - Progress bars

4. **Image Gallery**
   - Terminal image viewer (if supported)
   - Export to HTML gallery
   - QR codes for quick lookup

5. **Import from Other Tools**
   - Import from CSV
   - Import from Excel
   - Import from other managers

6. **Advanced Statistics**
   - Rarity distribution charts
   - Type distribution pie charts
   - Value over time graphs

7. **Trade Management**
   - Track trades with other collectors
   - Trade history
   - Trade value calculations

8. **Deck Building**
   - Create decks from collection
   - Validate deck legality
   - Export to PTCGO format

### Technical Debt

1. **API Tests**
   - Add comprehensive API mocking tests
   - Test error scenarios
   - Test rate limiting

2. **Analyzer Tests**
   - Unit tests for filter logic
   - Edge case coverage
   - Performance benchmarks

3. **Documentation**
   - Add docstring coverage check
   - Generate API docs with Sphinx
   - Add architecture diagrams

4. **Performance**
   - Profile analysis queries
   - Optimize large collections (1000+ cards)
   - Add database indices as needed

5. **Error Handling**
   - More granular exception types
   - Better error recovery
   - Retry logic for API calls

---

## Contributing Guidelines

### Code Style

- **Python**: PEP 8 compliant
- **Line length**: 100 characters max
- **Type hints**: Required for all functions
- **Docstrings**: Google style
- **Imports**: Grouped (stdlib, third-party, local)

### Git Workflow

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes with atomic commits
3. Run tests: `pytest tests/`
4. Run type checker: `mypy src/`
5. Create pull request with description

### Commit Messages

Format: `<type>: <subject>`

Types:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `refactor:` - Code restructuring
- `perf:` - Performance improvements

Example:
```
feat: add price tracking integration

- Integrate with TCGPlayer API
- Add price column to card cache
- Display prices in list command
```

---

## Appendix

### Glossary

- **TCGdex**: Pokemon TCG API and database
- **tcgdex_id**: Card identifier format: `{set_id}-{card_number}` (e.g., `me01-136`)
- **Variant**: Card printing variation (normal, reverse, holo, firstEdition)
- **Set**: Collection of cards released together (e.g., "Mega Evolution")
- **Stage**: Evolution level (Basic, Stage1, Stage2, etc.)
- **XDG**: X Desktop Group (standards for config/data directories)

### External Resources

- [TCGdex API Documentation](https://www.tcgdex.dev/)
- [TCGdex Python SDK](https://github.com/tcgdex/python-sdk)
- [Pokemon TCG Official](https://www.pokemon.com/us/pokemon-tcg/)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)

### Contact

For questions, issues, or contributions:
- GitHub: https://github.com/cloonix/pkmdex
- Issues: https://github.com/cloonix/pkmdex/issues

---

**End of Specification**
