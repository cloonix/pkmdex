# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-01-25

### Added
- **Multi-language support**: All 11 TCGdex languages now supported (de, en, fr, es, it, pt, ja, ko, zh-tw, th, id)
- **bd (bead) workflow**: Development task management tool (`./bd`)
- Default variant: Variant parameter now optional (defaults to 'normal')

### Changed
- **BREAKING**: Command format changed to `lang:set_id:card_number[:variant]`
  - Old: `pkm add me01:136:normal`
  - New: `pkm add de:me01:136` or `pkm add de:me01:136:holo`
- **BREAKING**: Can only add one variant per command (removed comma-separated variants)
- Language code now required for add/rm commands
- Updated all documentation with new format

### Migration
See [MIGRATION.md](MIGRATION.md) for detailed migration guide from v0.1.0

## [0.1.0] - 2026-01-25

### Project Renamed
- **Project name**: `pokedex` → `pkmdex`
- **CLI command**: `poke` → `pkm` (shorter, CLI-focused)
- **Database path**: `~/.pokedex/pokedex.db` → `~/.pkmdex/pkmdex.db`

### Initial Release

#### Added
- Core CLI commands:
  - `pkm add` - Add cards to collection with variant support
  - `pkm rm` - Remove cards from collection
  - `pkm list` - Display collection in table format
  - `pkm sets` - Search/browse available German sets
  - `pkm info` - Get detailed card information
  - `pkm stats` - Collection statistics
- Multi-variant support (normal, reverse, holo, firstEdition)
- Quantity tracking with automatic accumulation
- Smart caching (cards indefinitely, sets 24h)
- Case-insensitive set search (both ID and name)
- Automatic variant validation
- German language TCGdex API integration
- SQLite local storage
- Type-safe Python implementation with full type hints
- Comprehensive test suite (11 tests, all passing)

#### Technical
- Python 3.13+ required
- `uv sync --all-extras` for installation
- Minimal dependencies (tcgdex-sdk + stdlib)
- ~1,500 lines of code
- Production-ready

#### Documentation
- DESIGN.md - Complete architecture and design decisions
- AGENTS.md - AI agent development guidelines
- README.md - User documentation
- QUICKSTART.md - Getting started guide
- STATUS.md - Project status summary
- CHANGELOG.md - This file

### Migration Notes

If you were using the old `poke` command, update your muscle memory:

```bash
# Old (deprecated)
poke add me01:001:normal

# New
pkm add me01:001:normal
```

Database location changed:
- Old: `~/.pokedex/pokedex.db`
- New: `~/.pkmdex/pkmdex.db`

To migrate your existing collection:
```bash
mkdir -p ~/.pkmdex
mv ~/.pokedex/pokedex.db ~/.pkmdex/pkmdex.db
```

[0.1.0]: https://github.com/yourusername/pkmdex/releases/tag/v0.1.0
