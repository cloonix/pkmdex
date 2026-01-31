# PTCG Set Code Mapping

## Problem

TCGdex uses its own set ID system (e.g., `me01`, `sv01`), but the official Pokemon Trading Card Game uses different abbreviations (e.g., `ME1`, `SVI`, `PAL`).

When exporting decks for PTCG Live or PTCGO, we need to use the official codes.

## How to Find PTCG Set Codes

### Method 1: From PTCG Live

1. Open PTCG Live
2. Go to your collection
3. Filter by the set you want
4. Look at the card format: `NAME CODE NUMBER`
5. The CODE is what we need

### Method 2: From Limitless TCG

1. Visit https://play.limitlesstcg.com/decks
2. Find a deck list using cards from your set
3. Look at the card format
4. Note the set code

### Method 3: From PokeData

1. Visit https://www.pokedata.io/
2. Search for a card from your set
3. Look at the set abbreviation

## Managing Set Codes

Use the `pkm set-codes` command to manage set code mappings:

```bash
# List all current mappings
pkm set-codes list

# Add a new mapping
pkm set-codes add sv01 SVI --name-en "Scarlet & Violet" --name-de "Karmesin & Purpur"
pkm set-codes add energy Energy --name-en "Basic Energy" --name-de "Basis-Energie"

# Delete a mapping
pkm set-codes delete sv03
```

The mappings are stored in your SQLite database at `~/.local/share/pkmdex/pokedex.db` in the `set_code_mappings` table.

## Example Mappings

Here are some example mappings for Scarlet & Violet series:

| TCGdex ID | PTCG Code | English Name | German Name |
|-----------|-----------|--------------|-------------|
| `sv01` | `SVI` | Scarlet & Violet | Karmesin & Purpur |
| `sv02` | `PAL` | Paldea Evolved | Entwicklungen in Paldea |
| `sv03` | `OBF` | Obsidian Flames | Flammende Finsternis |
| `sv03.5` | `MEW` | 151 | 151 |
| `sv04` | `PAR` | Paradox Rift | Paradox-Spalte |
| `sv05` | `TEF` | Temporal Forces | Zeitschleife |
| `sv06` | `TWM` | Twilight Masquerade | Maskerade im Zwielicht |
| `sv07` | `SCR` | Stellar Crown | Sternenkrone |
| `svp` | `SVP` | Scarlet & Violet Promos | Karmesin & Purpur Promos |
| `energy` | `Energy` | Basic Energy | Basis-Energie |

## Database Storage

Set code mappings are stored in the `set_code_mappings` table:

```sql
CREATE TABLE set_code_mappings (
    tcgdex_set_id TEXT PRIMARY KEY,
    ptcg_code TEXT NOT NULL,
    set_name_en TEXT,
    set_name_de TEXT,
    notes TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

The table starts empty. Add mappings as you need them using `pkm set-codes add`.

## Fallback Behavior

If a set code is not found in the mapping:
- The TCGdex ID is used in uppercase (e.g., `me01` → `ME01`)
- This ensures exports work even without perfect mappings
- PTCG Live may not recognize these codes until they're corrected
