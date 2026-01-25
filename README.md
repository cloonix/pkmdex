# pkmdex - Pokemon Card Collection Manager

A minimal CLI tool for managing Pokemon TCG card collections in 11 languages using the TCGdex API.

## Features

- 🌍 Support for 11 languages (de, en, fr, es, it, pt, ja, ko, zh-tw, th, id)
- 📦 Track your Pokemon card collection with multi-language support
- 🔍 Search for set IDs from physical card names
- 🎴 Manage different card variants (normal, reverse, holo, firstEdition)
- 💾 Local SQLite database with configurable location
- 📤 Export/import for backup and migration
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

# View statistics
pkm stats

# Export/import collection
pkm export                       # Exports to backups directory
pkm export -o backup.json        # Custom export path
pkm import backup.json           # Import collection

# Manage cache
pkm cache                        # Show cache statistics
pkm cache --refresh              # Refresh set cache from API
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
| `stats` | Show collection statistics | `pkm stats` |
| `cache` | Manage API cache | `pkm cache` or `pkm cache --refresh` |
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

## Cache Management

The tool automatically caches API data to improve performance and reduce API calls:

- **Card cache**: Stores metadata for individual cards (name, rarity, types, etc.)
- **Set cache**: Stores information about all available sets

### Cache Commands

```bash
# View cache statistics
pkm cache

# Refresh set cache from API (updates all set information)
pkm cache --refresh

# Clear specific cache
pkm cache --clear --type sets    # Clear only set cache
pkm cache --clear --type cards   # Clear only card cache
pkm cache --clear --type all     # Clear all caches (default)
```

**When to refresh cache:**
- New Pokemon TCG sets have been released
- Set information appears outdated
- The cache is several weeks old (tool will show a tip if >7 days old)

**Note:** The `sets` command automatically refreshes the set cache if it's older than 24 hours.

## Raw JSON Data Storage

The tool automatically saves complete API responses as JSON files for every card you fetch. This gives you access to the full, unprocessed data from TCGdex.

### Viewing Raw Data

```bash
# Display formatted JSON from the API
pkm info de:me01:136 --raw

# Raw data is automatically saved when you:
# - Add a card: pkm add de:me01:136
# - Get card info: pkm info de:me01:136
```

### Where Raw Data is Stored

Raw JSON files are saved in your data directory:
- **Default location**: `~/.local/share/pkmdex/raw_data/cards/`
- **Custom location**: `<your-custom-path>/raw_data/cards/`
- **File naming**: `{tcgdex_id}.json` (e.g., `me01-136.json`)

You can directly access these files for:
- Building custom tools
- Data analysis
- Offline reference
- Debugging API responses

**Example:**
```bash
# View raw data file directly
cat ~/.local/share/pkmdex/raw_data/cards/me01-136.json

# Pretty-print with jq
jq . ~/.local/share/pkmdex/raw_data/cards/me01-136.json
```


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
  Database:  ~/.local/share/pkmdex/pokedex.db
  Backups:   ~/.local/share/pkmdex/backups/
  Config:    ~/.config/pkmdex/config.json
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
- ✅ Collection statistics (stats command)
- ✅ Export/import functionality
- ✅ Configurable database location
- ✅ One-line curl installation
- ✅ Automatic updates

### Future Enhancements
- Card value tracking
- Wishlist functionality
- Collection completion tracking
- Web interface
- Barcode scanning support

## License

[To be determined]

## Contributing

This is currently a personal project. Design feedback and bug reports welcome!

## Support

For issues or questions, please check:
1. DESIGN.md for architectural decisions
2. AGENTS.md for development guidelines
3. TCGdex API documentation: https://tcgdex.dev
