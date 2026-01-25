# pkmdex - Pokemon Card Collection Manager

A minimal CLI tool for managing German Pokemon TCG card collections using the TCGdex API.

## Features

- 📦 Track your German Pokemon card collection
- 🔍 Search for set IDs from physical card names
- 🎴 Manage different card variants (normal, reverse, holo, firstEdition)
- 💾 Local SQLite database storage
- 🚀 Fast, typing-friendly CLI interface

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd pkmdex

# Install dependencies (recommended: using uv)
uv sync --all-extras

# Activate virtual environment
source .venv/bin/activate

# Or with pip
pip install -e ".[dev]"
```

### Usage

```bash
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

# List specific set
pkm list me01

# Get card information
pkm info de:me01:136

# View statistics
pkm stats

# Remove a card
pkm rm de:me01:136               # Removes normal variant
pkm rm de:me01:136:holo          # Removes holo variant
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
| `add` | Add a card to collection | `pkm add de:me01:136` or `pkm add de:me01:136:holo` |
| `rm` | Remove a card from collection | `pkm rm de:me01:136` or `pkm rm de:me01:136:holo` |
| `list` | Display collection | `pkm list` or `pkm list me01` |
| `sets` | Search/list available sets | `pkm sets mega` |
| `info` | Get card information | `pkm info de:me01:136` |
| `stats` | Show collection statistics | `pkm stats` |

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
# Set    Card#  Name       Variants         Qty  Rarity
# ─────────────────────────────────────────────────────
# me01   136    Pottrott   normal, reverse  2/1  Selten
```

## Project Structure

```
pkmdex/
├── src/
│   ├── cli.py      # CLI interface
│   ├── db.py       # Database operations
│   ├── api.py      # TCGdex API wrapper
│   └── models.py   # Data models
├── tests/          # Unit tests
├── DESIGN.md       # Design documentation
├── AGENTS.md       # Instructions for AI agents
└── README.md       # This file

Database: ~/.pkmdex/pkmdex.db (auto-created)
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

- **Language**: Python 3.13
- **Database**: SQLite3
- **API**: TCGdex (German language)
- **Dependencies**: Minimal - standard library + tcgdex-sdk

## Documentation

- **DESIGN.md** - Comprehensive design document with architecture, database schema, and CLI specification
- **AGENTS.md** - Instructions for AI coding agents working on this project

## Roadmap

### Phase 1 (Current)
- ✅ Design and architecture
- [ ] Core CLI commands (add, list, rm)
- [ ] Set discovery (sets command)
- [ ] Card information (info command)
- [ ] Collection statistics (stats command)

### Future Enhancements
- Export to CSV/JSON
- Bulk operations
- Card value tracking
- Wishlist functionality
- Collection completion tracking

## License

[To be determined]

## Contributing

This is currently a personal project. Design feedback and bug reports welcome!

## Support

For issues or questions, please check:
1. DESIGN.md for architectural decisions
2. AGENTS.md for development guidelines
3. TCGdex API documentation: https://tcgdex.dev
