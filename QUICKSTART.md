# Quick Start Guide

## Installation

**Option 1: Using `uv` (recommended - fastest)**

```bash
# Clone the repository
git clone <repo-url>
cd pkmdex

# Sync dependencies (creates venv with Python 3.13 + installs everything)
uv sync --all-extras

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

**Option 2: Using pip**

```bash
# Clone the repository
git clone <repo-url>
cd pkmdex

# Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## First Steps

### 1. Find Your Set ID

Physical German Pokemon cards show abbreviations like "MEG". Use the `sets` command to find the API set ID:

```bash
$ pkm sets meg

Set ID       Name                  Cards    Released    
─────────────────────────────────────────────────────────
me01         Mega-Entwicklung      188      -           
─────────────────────────────────────────────────────────
```

So "MEG" → `me01`

### 2. Add Your First Card

```bash
# Format: pkm add <lang>:<set_id>:<card_number>[:<variant>]
# Variant is optional and defaults to 'normal'
$ pkm add de:me01:001

✓ Added: Bisasam (me01-001) - normal
  Image: https://assets.tcgdex.net/de/me/me01/001

# Or specify a variant
$ pkm add de:me01:003:holo

✓ Added: Mega-Bisaflor-ex (me01-003) - holo
  Image: https://assets.tcgdex.net/de/me/me01/003
```

### 3. View Your Collection

```bash
$ pkm list

Set      Card#  Name       Variants       Qty   Rarity         
──────────────────────────────────────────────────────────────
me01     001    Bisasam    normal(1)      1     Häufig         
──────────────────────────────────────────────────────────────
Total: 1 unique cards, 1 total cards
```

### 4. Get Card Information

```bash
$ pkm info de:me01:001

Card: Bisasam (#001)
Set:  Mega-Entwicklung (me01)
Type: Pflanze
HP:   80
Rarity: Häufig

Available Variants:
  ✓ normal
  ✓ reverse
  ✗ holo
  ✗ firstEdition
```

## Common Workflows

### Adding Multiple Variants

Add both normal and reverse variants of the same card (one at a time):

```bash
pkm add de:me01:001              # Adds normal (default)
pkm add de:me01:001:reverse      # Adds reverse variant
```

### Accumulating Duplicates

Running the same add command multiple times increases quantity:

```bash
pkm add de:me01:001   # Adds 1 (normal)
pkm add de:me01:001   # Now you have 2
pkm add de:me01:001   # Now you have 3
```

### Filtering by Set

```bash
pkm list me01            # Show only cards from me01
```

### Searching Sets

```bash
pkm sets scarlet         # Search for "Scarlet"
pkm sets sv              # Search for "sv" sets
pkm sets                 # List all sets
```

### Collection Statistics

```bash
pkm stats

Collection Statistics
────────────────────────────────────────
Total unique cards:     5
Total cards (all):      12
Sets represented:       2
Most collected set:     me01 (10 cards)

Variants breakdown:
  Normal               8
  Reverse              3
  Holo                 1
```

### Removing Cards

```bash
pkm rm de:me01:001           # Remove 1 copy (normal variant)
pkm rm de:me01:001:reverse   # Remove reverse variant
```

### Multi-Language Support

```bash
# Add German version
pkm add de:me01:001          # Bisasam

# Add English version
pkm add en:me01:001          # Bulbasaur

# Add French version
pkm add fr:me01:001          # Bulbizarre
```

Supported languages: `de`, `en`, `fr`, `es`, `it`, `pt`, `ja`, `ko`, `zh-tw`, `th`, `id`

## Variant Types

- `normal` - Standard non-foil card
- `reverse` - Reverse holofoil (foil background, normal artwork)
- `holo` - Holofoil (foil artwork)
- `firstEdition` - First edition printing

## Tips

1. **Case doesn't matter** for set IDs: `ME01`, `me01`, and `Me01` all work
2. **Search is smart**: Both set ID and set name are searched
3. **Card numbers can have letters**: Some cards use `001a`, `TG01`, etc.
4. **Validation is automatic**: You can't add unavailable variants
5. **Data is cached**: Once fetched from API, card info is stored locally

## Troubleshooting

### "Card not found" error

```bash
Error: Card not found: me01:999
Possible causes:
  - Card number doesn't exist in this set
  - Set ID is incorrect

Try 'pkm sets mega' to search for the right set ID.
```

### "Invalid format" error

```bash
Error: Invalid format: me01:136
Expected: <lang>:<set_id>:<card_number>[:<variant>]
Examples:
  de:me01:136:normal
  de:me01:136          (defaults to normal variant)
  en:swsh3:136:holo
```

**Solution**: Add the language code at the beginning (e.g., `de:` for German)

**Solution**: Double-check your card number and set ID.

### "Variant not available" error

```bash
Error: Variant 'holo' not available for Bisasam (me01-001)
Available variants: normal, reverse
```

**Solution**: Use the `info` command to see available variants for that card.

### Database location

The SQLite database is stored at: `~/.pkmdex/pkmdex.db`

To reset your collection, simply delete this directory.

## Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_db.py -v

# Run with coverage
pytest --cov=src tests/
```

## Development

See [AGENTS.md](AGENTS.md) for detailed development guidelines.

## Next Steps

- Read [DESIGN.md](DESIGN.md) for architecture details
- Check out [README.md](README.md) for full documentation
- Explore the TCGdex API: https://tcgdex.dev
