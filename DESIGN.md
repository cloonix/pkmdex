# Pokemon Card Collection Manager - Design Document

## Overview

A CLI tool for managing German Pokemon TCG card collections using the TCGdex API. The tool allows users to track their physical cards with support for different variants (normal, reverse, holo, etc.) and stores the collection in a local SQLite database.

## Problem Statement

German Pokemon card collectors need a simple way to:
1. Track their card collection locally
2. Identify API set IDs from physical card markings (e.g., "MEG" → "me01")
3. Manage different card variants (normal, reverse, holo)
4. Query their collection efficiently

Physical cards show set abbreviations like "MEG" but the TCGdex API uses internal IDs like "me01". Users need a way to discover the correct API set ID.

## Architecture

### Tech Stack

- **Python 3.13** - Core language
- **tcgdex-sdk** - Official Python SDK for TCGdex API
- **SQLite3** - Built-in database (no external DB needed)
- **argparse** - Built-in CLI argument parsing (minimal, no dependencies)
- **Standard library only** for MVP - keeping it minimal

Optional future enhancements:
- Rich/Tabulate for better table formatting
- Click/Typer for advanced CLI features

### Project Structure

```
pkmdex/
├── src/
│   ├── __init__.py
│   ├── cli.py              # CLI interface and command handlers
│   ├── db.py               # Database operations and schema
│   ├── api.py              # TCGdex API wrapper
│   └── models.py           # Data models
├── tests/
│   ├── __init__.py
│   ├── test_db.py
│   ├── test_api.py
│   └── test_cli.py
├── pyproject.toml          # Project metadata and dependencies
├── README.md
├── DESIGN.md               # This file
└── AGENTS.md               # Instructions for AI agents

Database stored at: ~/.pkmdex/pkmdex.db (auto-created)
```

## Database Schema

### Tables

#### `cards`
Stores owned cards in the collection.

```sql
CREATE TABLE cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id TEXT NOT NULL,           -- TCGdex set ID (e.g., "me01")
    card_number TEXT NOT NULL,      -- Local card number (e.g., "136")
    tcgdex_id TEXT NOT NULL,        -- Full TCGdex ID (e.g., "me01-136")
    variant TEXT NOT NULL,          -- Variant: normal, reverse, holo, firstEdition
    quantity INTEGER DEFAULT 1,     -- Number of this variant owned
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tcgdex_id, variant)      -- One entry per card+variant combo
);

CREATE INDEX idx_set_id ON cards(set_id);
CREATE INDEX idx_tcgdex_id ON cards(tcgdex_id);
```

#### `card_cache`
Caches card metadata from TCGdex API to reduce API calls.

```sql
CREATE TABLE card_cache (
    tcgdex_id TEXT PRIMARY KEY,     -- Full TCGdex ID (e.g., "me01-136")
    name TEXT NOT NULL,             -- Card name in German
    set_name TEXT,                  -- Set name in German
    rarity TEXT,                    -- Card rarity
    types TEXT,                     -- JSON array of types
    hp INTEGER,                     -- Hit points (Pokemon only)
    available_variants TEXT,        -- JSON object of available variants
    image_url TEXT,                 -- Card image URL
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `set_cache`
Caches set information to help users discover set IDs.

```sql
CREATE TABLE set_cache (
    set_id TEXT PRIMARY KEY,        -- TCGdex set ID (e.g., "me01")
    name TEXT NOT NULL,             -- German set name
    card_count INTEGER,             -- Total cards in set
    release_date TEXT,              -- Release date
    serie_id TEXT,                  -- Serie ID (e.g., "me")
    serie_name TEXT,                -- Serie name
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## CLI Interface

### Command Syntax

The CLI uses a concise, typing-friendly format:

```bash
# Format: pkm <command> <set_id>:<card_number>:<variant>[,<variant>...]

# Add single variant
pkm add me01:136:normal

# Add multiple variants of same card
pkm add me01:136:normal,reverse

# Remove variants
pkm rm me01:136:normal

# Add additional copy (accumulates)
pkm add me01:136:normal  # If exists, increments quantity

# List all cards
pkm list

# List cards from specific set
pkm list me01

# Search for sets (when you don't know the set ID)
pkm sets mega          # Search sets by name
pkm sets               # List all sets

# Get card info without adding
pkm info me01:136

# Show stats
pkm stats
```

### Command Details

#### `add` - Add cards to collection

```bash
pkm add <set_id>:<card_number>:<variants>

Arguments:
  set_id      - TCGdex set ID (e.g., me01, sv06)
  card_number - Card number in set (e.g., 136, 001)
  variants    - Comma-separated variants: normal, reverse, holo, firstEdition

Examples:
  pkm add me01:136:normal
  pkm add me01:136:normal,reverse
  pkm add sv06:045:holo
```

**Behavior:**
1. Parse input format
2. Query TCGdex API for card info (use German language)
3. Validate card exists
4. Check if variant is available for this card
5. If card+variant exists in DB: increment quantity
6. If new: insert with quantity=1
7. Cache card metadata
8. Display success message with card name and image URL

#### `rm` - Remove cards from collection

```bash
pkm rm <set_id>:<card_number>:<variants>

Arguments:
  Same as 'add'

Examples:
  pkm rm me01:136:normal
  pkm rm me01:136:normal,reverse
```

**Behavior:**
1. Parse input
2. Find matching card+variant in DB
3. Decrement quantity by 1
4. If quantity reaches 0: delete record
5. Display updated quantity or "Removed" message

#### `list` - Display collection

```bash
pkm list [set_id]

Arguments:
  set_id - Optional: filter by set ID

Examples:
  pkm list           # All cards
  pkm list me01      # Only cards from me01
```

**Output Format (compact table):**
```
Set    Card#  Name              Variants             Qty  Rarity
─────────────────────────────────────────────────────────────────
me01   136    Furret            normal, reverse      2/1  Uncommon
me01   045    Pikachu           holo                 1    Rare
sv06   012    Charizard ex      normal               3    Ultra Rare
─────────────────────────────────────────────────────────────────
Total: 3 unique cards, 6 total cards
```

**Implementation:**
- Query cards from DB with JOIN to card_cache for metadata
- Group by tcgdex_id to show all variants on one line
- Sort by set_id, then card_number
- Use simple ASCII table format (or Rich if we add it later)

#### `sets` - Search and list sets

```bash
pkm sets [search_term]

Arguments:
  search_term - Optional: search in set names

Examples:
  pkm sets              # List all German sets
  pkm sets mega         # Search for "mega" in set names
  pkm sets MEG          # Search for "MEG"
```

**Output Format:**
```
Set ID    Name                          Cards  Released
──────────────────────────────────────────────────────────
me01      Mega-Entwicklung             132    2024-01-26
me02      Fatale Flammen               106    2024-03-22
mep       MEP Black Star Promos        34     -
──────────────────────────────────────────────────────────
```

**Behavior:**
1. Check set_cache for freshness (cache for 24h)
2. If stale or empty: fetch all sets from API (German language)
3. Store in set_cache
4. Filter by search term if provided (case-insensitive)
5. Display results

**This solves the "MEG" problem:** User can run `pkm sets MEG` to discover that "me01" or "me02" contains "Mega" in the name.

#### `info` - Get card information

```bash
pkm info <set_id>:<card_number>

Arguments:
  set_id      - TCGdex set ID
  card_number - Card number

Examples:
  pkm info me01:136
```

**Output:**
```
Card: Furret (#136)
Set:  Mega-Entwicklung (me01)
Type: Colorless
HP:   110
Rarity: Uncommon

Available Variants:
  ✓ normal
  ✓ reverse
  ✗ holo
  ✗ firstEdition

In Collection:
  • normal: 2
  • reverse: 1

Image: https://assets.tcgdex.net/de/me/me01/136
```

#### `stats` - Collection statistics

```bash
pkm stats
```

**Output:**
```
Collection Statistics
────────────────────────────────────
Total unique cards:     45
Total cards (all):      127
Sets represented:       8
Most collected set:     me01 (23 cards)

Variants breakdown:
  Normal:               89
  Reverse:              28
  Holo:                 10
  First Edition:        0

Rarity breakdown:
  Common:               45
  Uncommon:             38
  Rare:                 25
  Ultra Rare:           12
  Secret Rare:          7
```

## API Integration

### TCGdex SDK Usage

```python
from tcgdexsdk import TCGdex

# Initialize with German language
tcgdex = TCGdex("de")

# Get card by set and number
card = await tcgdex.fetch('sets/me01/136')

# Get all sets
sets = await tcgdex.fetch('sets')

# Search cards (if needed later)
from tcgdexsdk import Query
cards = await tcgdex.card.list(Query().equal("name", "Pikachu"))
```

### Caching Strategy

1. **Card Metadata**: Cache indefinitely (cards don't change)
2. **Set List**: Cache for 24 hours (new sets release occasionally)
3. **Check cache first**: Always check local DB before API call
4. **Lazy loading**: Only fetch when needed

### Error Handling

- **API unreachable**: Use cached data if available, show warning
- **Card not found**: Display helpful error with suggestion to use `poke sets`
- **Invalid variant**: Show available variants for that card
- **Invalid format**: Show usage example

## Data Models

### Python Classes

```python
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass
class CardVariants:
    """Available variants for a card"""
    normal: bool = False
    reverse: bool = False
    holo: bool = False
    firstEdition: bool = False

@dataclass
class OwnedCard:
    """Card in user's collection"""
    id: Optional[int]
    set_id: str
    card_number: str
    tcgdex_id: str
    variant: str  # 'normal', 'reverse', 'holo', 'firstEdition'
    quantity: int
    added_at: datetime
    updated_at: datetime

@dataclass
class CardInfo:
    """Cached card metadata from API"""
    tcgdex_id: str
    name: str
    set_name: Optional[str]
    rarity: Optional[str]
    types: List[str]
    hp: Optional[int]
    available_variants: CardVariants
    image_url: Optional[str]
    cached_at: datetime

@dataclass
class SetInfo:
    """Cached set information"""
    set_id: str
    name: str
    card_count: int
    release_date: Optional[str]
    serie_id: Optional[str]
    serie_name: Optional[str]
    cached_at: datetime
```

## Variant Handling

### Variant Types

Based on TCGdex API:
- `normal` - Standard non-foil card
- `reverse` - Reverse holofoil
- `holo` - Holofoil
- `firstEdition` - First edition printing

### Variant Validation

When adding a card:
1. Fetch card from API
2. Check `card.variants` object
3. Validate requested variant is available
4. If not available, show error with available variants

Example:
```
Error: Variant 'holo' not available for Furret (me01-136)
Available variants: normal, reverse
```

### Multiple Variants

Users can own multiple variants of the same card:
- Each variant is a separate DB row
- Tracked independently with separate quantities
- Display shows all variants grouped by card

## Phase 1 Implementation Plan

### Milestone 1: Core Infrastructure
- [ ] Project setup with pyproject.toml
- [ ] Database module with schema creation
- [ ] API wrapper for TCGdex SDK
- [ ] Data models

### Milestone 2: Basic Commands
- [ ] `poke add` command
- [ ] `poke list` command
- [ ] `poke rm` command
- [ ] Card caching

### Milestone 3: Discovery Features
- [ ] `poke sets` command with search
- [ ] `poke info` command
- [ ] Set caching

### Milestone 4: Polish
- [ ] `poke stats` command
- [ ] Error handling and validation
- [ ] Unit tests
- [ ] Documentation (README)

## Future Enhancements (Not Phase 1)

- Export to CSV/JSON
- Import from file
- Bulk operations (`poke add me01:136,137,138:normal`)
- Card value tracking (pricing from API)
- Wishlist functionality
- Web UI
- Sync across devices
- Trade tracking
- Search within collection
- Filters (by type, rarity, etc.)
- Collection completion percentage per set

## Non-Goals (Explicitly Out of Scope)

- Multi-user support
- Cloud sync (Phase 1)
- Card scanning/OCR
- Trading platform integration
- Price tracking (Phase 1)
- Authentication/accounts
- Mobile app

## Success Criteria

Phase 1 is successful when a user can:

1. ✓ Add a card using `pkm add me01:136:normal`
2. ✓ See their collection with `pkm list`
3. ✓ Remove cards with `pkm rm`
4. ✓ Discover set IDs using `pkm sets MEG`
5. ✓ View card details with `pkm info`
6. ✓ Track multiple variants separately
7. ✓ Accumulate quantities when adding duplicates
8. ✓ View collection statistics

## Technical Decisions

### Why Python 3.13?
- Latest stable version
- Excellent standard library
- Native async support for API calls
- Good SQLite integration
- Type hints for better code quality

### Why SQLite?
- Zero configuration
- No server needed
- Fast for local queries
- Perfect for single-user desktop app
- Built into Python

### Why Minimal Dependencies?
- Faster installation
- Fewer breaking changes
- Easier maintenance
- Standard library is powerful enough for MVP

### Why argparse over Click/Typer?
- Built-in to Python
- Sufficient for simple CLI
- Can migrate later if needed
- Reduces dependency count

### Why TCGdex API?
- Official Pokemon TCG data
- Multilingual support (German!)
- Free and open source
- Active maintenance
- Comprehensive card data
- Official Python SDK

## Security & Privacy

- All data stored locally
- No user accounts
- No data sent to external services (except TCGdex API)
- API calls use HTTPS
- No sensitive data stored

## Performance Considerations

- Cache aggressively to minimize API calls
- Index database on frequently queried fields
- Keep CLI response time < 200ms for cached operations
- Batch API calls when possible
- Use async for API operations

## Testing Strategy

### Unit Tests
- Database operations (CRUD)
- API wrapper functions
- Input parsing
- Variant validation

### Integration Tests
- End-to-end CLI commands
- Database + API interaction
- Caching behavior

### Manual Testing
- Real German card additions
- Set discovery workflow
- Error scenarios

## Documentation

### README.md
- Quick start guide
- Installation instructions
- Command reference
- Example workflows
- Troubleshooting

### AGENTS.md
- Instructions for AI coding agents (like Aider)
- Architecture overview
- Code style guidelines
- Testing requirements
- Common tasks

## Open Questions & Decisions

1. **Date format**: Use ISO 8601 or locale-specific?
   - **Decision**: ISO 8601 for consistency

2. **Card number padding**: Store "001" or "1"?
   - **Decision**: Store as provided, compare numerically

3. **Case sensitivity**: me01 vs ME01?
   - **Decision**: Case-insensitive, normalize to lowercase

4. **Sync indicator**: Show if using cached vs fresh data?
   - **Decision**: Not in Phase 1, add later if needed

5. **Confirmation prompts**: Ask before removing cards?
   - **Decision**: No confirmation for single cards, direct removal
