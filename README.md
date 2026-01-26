# pkmdex - Pokemon Card Collection Manager

A minimal CLI tool for managing Pokemon TCG card collections in 11 languages using the TCGdex API.

## Features

- 🌍 Support for 11 languages (de, en, fr, es, it, pt, ja, ko, zh-tw, th, id)
- 📦 Track your Pokemon card collection with multi-language support
- 🔍 Search for set IDs from physical card names
- 🎴 Manage different card variants (normal, reverse, holo, firstEdition)
- 💾 Local SQLite database with configurable location
- 💰 Price tracking (EUR/USD) with automatic sync
- 📤 Export/import for backup and migration
- 🔄 Smart sync to update prices and card data
- 🚀 Fast, typing-friendly CLI interface

## Quick Start

### Installation

**One-line install (recommended):**

```bash
curl -fsSL https://raw.githubusercontent.com/cloonix/pkmdex/main/install.sh | bash
```

This will:
- Install `uv` package manager if needed
- Download and install pkmdex
- Create `pkm` command in `~/.local/bin/`
- Support updates by running the same command again

**Manual installation:**

```bash
# Clone the repository
git clone https://github.com/cloonix/pkmdex.git
cd pkmdex

# Install dependencies (recommended: using uv)
uv sync --all-extras

# Run directly
uv run python -m src.cli --help

# Or with pip
pip install -e ".[dev]"
```

### Updating

```bash
# Using curl installer (re-run install command)
curl -fsSL https://raw.githubusercontent.com/cloonix/pkmdex/main/install.sh | bash
```

### Uninstalling

```bash
curl -fsSL https://raw.githubusercontent.com/cloonix/pkmdex/main/uninstall.sh | bash
```

### Usage

```bash
# Configure database location (optional)
pkm setup --show                     # Show current configuration
pkm setup --path ~/Documents/pokemon # Set custom database path

# Search for a set ID (e.g., find what "MEG" is in the API)
pkm sets mega

# Add a card to your collection (German)
pkm add de:me01:136              # Defaults to normal variant

# Add a card with specific variant
pkm add de:me01:136:holo

# Add English card
pkm add en:swsh3:136:reverse

# List your collection
pkm list

# List specific language or set
pkm list de                      # Show only German cards
pkm list me01                    # Show only me01 set

# Get card information
pkm info de:me01:136

# Analyze your collection (using English raw JSON data)
pkm analyze                      # Show all cards with details
pkm analyze --stage Basic        # Filter by evolution stage  
pkm analyze --type Fire          # Filter by Pokemon type
pkm analyze --rarity Rare        # Filter by rarity
pkm analyze --hp-min 100         # Filter by minimum HP
pkm analyze --stats              # Show collection statistics

# View statistics
pkm stats

# Sync card data (prices, legality) from API
pkm sync                         # Sync all cards
pkm sync --stale 7               # Only sync cards older than 7 days
pkm sync --show-changes          # Show price changes after sync

# Migrate from v1 to v2 schema (if upgrading)
pkm migrate --dry-run            # Preview migration
pkm migrate --verbose            # Run migration with detailed output

# Export/import collection
pkm export                       # Exports to backups directory
pkm export -o backup.json        # Custom export path
pkm import backup.json           # Import collection

# Manage cache
pkm cache                        # Show cache statistics
pkm cache --refresh              # Refresh set cache from API
pkm cache --update               # Update cache for all owned cards
pkm cache --clear --type sets    # Clear set cache
pkm cache --clear --type cards   # Clear card cache
pkm cache --clear --type all     # Clear all caches

# Remove a card
pkm rm de:me01:136               # Removes normal variant
pkm rm de:me01:136:holo          # Removes holo variant
pkm rm --all de:me01:136         # Removes all variants
```

## Command Format

The CLI uses a concise format optimized for fast typing with multi-language support:

```
pkm <command> <lang>:<set_id>:<card_number>[:<variant>]
```

**Examples:**
- `pkm add de:me01:136` - Add German card (defaults to normal variant)
- `pkm add de:me01:136:holo` - Add German card with holo variant
- `pkm add en:swsh3:136:reverse` - Add English card with reverse variant
- `pkm rm de:me01:136` - Remove card (defaults to normal variant)

## Available Commands

| Command | Description | Example |
|---------|-------------|---------|
| `setup` | Configure database path and settings | `pkm setup --show` or `pkm setup --path ~/pokemon` |
| `add` | Add a card to collection | `pkm add de:me01:136` or `pkm add de:me01:136:holo` |
| `rm` | Remove a card from collection | `pkm rm de:me01:136` or `pkm rm --all de:me01:136` |
| `list` | Display collection | `pkm list` or `pkm list de` or `pkm list me01` |
| `sets` | Search/list available sets | `pkm sets mega` |
| `info` | Get card information | `pkm info de:me01:136` or `pkm info de:me01:136 --raw` |
| `analyze` | Analyze collection with filters | `pkm analyze --stage Stage1` or `pkm analyze --stats` |
| `stats` | Show collection statistics | `pkm stats` |
| `sync` | Refresh card data from API | `pkm sync` or `pkm sync --stale 7` |
| `migrate` | Migrate v1 database to v2 | `pkm migrate --dry-run` or `pkm migrate --verbose` |
| `export` | Export collection to JSON | `pkm export` or `pkm export -o backup.json` |
| `import` | Import collection from JSON | `pkm import backup.json` |

## Supported Languages

The tool supports cards in multiple languages from the TCGdex API:

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

**Example:** Add the same card in different languages:
```bash
pkm add de:me01:001     # German: Bisasam
pkm add en:me01:001     # English: Bulbasaur
pkm add fr:me01:001     # French: Bulbizarre
```

## Card Variants

The tool tracks different printing variants:

- `normal` - Standard non-foil card (default if not specified)
- `reverse` - Reverse holofoil
- `holo` - Holofoil
- `firstEdition` - First edition printing

## Data Synchronization

The v2 architecture stores all card data in the database. Use the `sync` command to keep prices and legality information up-to-date:

```bash
# Sync all cards in your collection
pkm sync

# Only sync cards that haven't been updated in 7+ days
pkm sync --stale 7

# Show price changes after sync
pkm sync --show-changes
```

**What gets synced:**
- Card prices (EUR/USD from TCGdex API)
- Tournament legality (Standard/Expanded format)
- Localized card names
- Card metadata (HP, types, rarity, etc.)

**When to sync:**
- After adding many cards (to fetch latest prices)
- Periodically to track price changes
- Before exporting your collection with value data

## Database Migration

If you're upgrading from v1 to v2, use the migration command:

```bash
# Preview what will be migrated (recommended first step)
pkm migrate --dry-run --verbose

# Run actual migration
pkm migrate --verbose
```

The migration:
- ✅ Creates automatic backups before changes
- ✅ Migrates all ownership records from v1 tables
- ✅ Loads card data from existing JSON files OR fetches from API
- ✅ Preserves localized names for all languages
- ✅ Validates migration success
- ✅ Keeps old tables as `*_v1_backup` for safety

## Viewing Raw Card Data

In v2, card data is stored in the database. To view the complete raw JSON from the TCGdex API:

```bash
# Fetch and display raw JSON (not stored permanently)
pkm info de:me01:136 --raw

# This will show complete API response including:
# - Card name, HP, types, attacks, abilities
# - Rarity, regulation marks, artist info
# - Pricing data (if available)
# - All metadata from TCGdex

# Note: In v2, this fetches fresh from API each time
# Card metadata (name, HP, types, etc.) is stored in database
# Use 'pkm sync' to update stored data
```

### What's Stored in the Database

The v2 database schema stores:
- **Cards table**: English card data (name, HP, types, rarity, prices, legality)
- **Card names table**: Localized names for each language
- **Owned cards table**: Your ownership records (language, variant, quantity)

This provides:
- **Fast queries**: No file I/O needed for listing or filtering
- **Efficient storage**: No duplicate JSON files
- **Easy sync**: Update all cards with one command (`pkm sync`)

### Migration from v1

If you have v1 JSON files, the migration script will:
1. Read existing JSON files from `~/.pkmdex/raw_data/cards/`
2. Import card data into v2 database
3. Preserve all localized names
4. Keep old files for backup (you can delete after migration)

```bash
# Migrate v1 → v2 (reads JSON files, writes to database)
pkm migrate --verbose
```

## Collection Analysis

Analyze your collection with powerful filtering using database queries. All card data is stored consistently in English for reliable filtering.

### Available Filters

```bash
# Evolution stage
pkm analyze --stage Basic
pkm analyze --stage Stage1
pkm analyze --stage Stage2

# Pokemon type
pkm analyze --type Fire
pkm analyze --type Water

# Rarity
pkm analyze --rarity Common
pkm analyze --rarity Rare
pkm analyze --rarity "Ultra Rare"

# HP range
pkm analyze --hp-min 100 --hp-max 150

# Category (Pokemon, Trainer, Energy)
pkm analyze --category Pokemon
pkm analyze --category Trainer

# Language
pkm analyze --language de
pkm analyze --language en

# Set ID
pkm analyze --set me01

# Combine multiple filters
pkm analyze --stage Stage1 --type Fire --hp-min 80
pkm analyze --set me01 --rarity Rare
```

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

## Project Structure

```
pkmdex/
├── src/
│   ├── cli.py      # CLI interface
│   ├── db.py       # Database operations
│   ├── api.py      # TCGdex API wrapper
│   ├── config.py   # Configuration management
│   └── models.py   # Data models
├── tests/          # Unit tests
├── install.sh      # Installation script
├── uninstall.sh    # Uninstallation script
├── DESIGN.md       # Design documentation
├── AGENTS.md       # Instructions for AI agents
└── README.md       # This file

Default Locations (configurable with 'pkm setup'):
  Database:     ~/.pkmdex/pokedex.db
  Backups:      ~/.pkmdex/backups/
  Config:       ~/.config/pkmdex/config.json
```

## Development

### Requirements

- Python 3.13+
- tcgdex-sdk

### Running Tests

```bash
python -m pytest tests/
```

### Type Checking

```bash
python -m mypy src/
```

## Technical Details

- **Language**: Python 3.13+
- **Database**: SQLite3 (configurable location)
- **API**: TCGdex (multi-language support)
- **Package Manager**: uv (auto-installed)
- **Installation**: Portable, self-contained in ~/.local/share/pkmdex-bin
- **Dependencies**: Minimal - standard library + tcgdex-sdk

## Documentation

- **DESIGN.md** - Comprehensive design document with architecture, database schema, and CLI specification
- **AGENTS.md** - Instructions for AI coding agents working on this project

## Roadmap

### Completed Features
- ✅ Multi-language support (11 languages)
- ✅ Core CLI commands (add, list, rm)
- ✅ Set discovery (sets command)
- ✅ Card information (info command)
- ✅ Collection statistics with value tracking (stats command)
- ✅ Export/import functionality
- ✅ Configurable database location
- ✅ One-line curl installation
- ✅ Automatic updates
- ✅ Price tracking (EUR/USD)
- ✅ Smart sync for updating card data
- ✅ v1 to v2 database migration
- ✅ Collection analysis with filters

### Future Enhancements
- Wishlist functionality
- Collection completion tracking per set
- Web interface
- Barcode scanning support
- Trade tracking
- Custom price alerts

## License

[To be determined]

## Contributing

This is currently a personal project. Design feedback and bug reports welcome!

## Support

For issues or questions, please check:
1. DESIGN.md for architectural decisions
2. AGENTS.md for development guidelines
3. TCGdex API documentation: https://tcgdex.dev
