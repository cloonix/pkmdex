# Migration Guide - v0.2.0

## Breaking Changes

### New Command Format (v0.2.0)

The command format has changed to support multiple languages and simplify variant handling.

#### Old Format (v0.1.0)
```bash
pkm add me01:136:normal,reverse    # Multiple variants
pkm add me01:136:normal            # Single variant
```

#### New Format (v0.2.0)
```bash
pkm add de:me01:136                # Single variant (defaults to normal)
pkm add de:me01:136:holo           # Specific variant
pkm add en:swsh3:136:reverse       # English language
```

### Key Changes

1. **Language Parameter Required**: All commands now require a language code (e.g., `de`, `en`, `fr`)
2. **Single Variant Only**: Can only add one variant at a time (no comma-separated lists)
3. **Default Variant**: If no variant specified, defaults to `normal`

### Supported Languages

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

### Examples

#### Adding Cards
```bash
# German card (most common)
pkm add de:me01:136

# German card with specific variant
pkm add de:me01:136:holo

# English card
pkm add en:swsh3:136:reverse

# French card
pkm add fr:swsh3:136:normal
```

#### Removing Cards
```bash
# Remove with default variant
pkm rm de:me01:136

# Remove specific variant
pkm rm de:me01:136:holo
```

#### Getting Card Info
```bash
# With language
pkm info de:me01:136

# Legacy format still works (uses German)
pkm info me01:136
```

### Migration Steps

If you have existing cards in your collection:
1. No database migration needed - existing cards are compatible
2. Update your command syntax when adding new cards
3. Use the new `lang:set:card[:variant]` format going forward

### What Stayed the Same

- `pkm list` - No changes
- `pkm sets` - No changes  
- `pkm stats` - No changes
- Database location: `~/.pkmdex/pkmdex.db`
- Variant types: normal, reverse, holo, firstEdition
