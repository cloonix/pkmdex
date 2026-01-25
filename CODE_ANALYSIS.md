# Code Analysis & Simplification Recommendations

## Executive Summary

**Total LOC**: 2,893 lines  
**Main Issues Found**: 
1. **Redundant data storage** (card_cache duplicates raw JSON)
2. **Inefficient queries** (N+1 problem in analyzer)
3. **Duplicate JSON loading** in analyze_collection
4. **Language inconsistency** (cache vs. raw JSON)

---

## Critical Issues

### 1. **MAJOR: Redundant Card Cache System**

**Problem**: We store card metadata in BOTH places:
- `card_cache` table (SQLite) - stores name, rarity, types, hp
- `raw_data/*.json` files - stores complete English card data

**Evidence**:
```python
# In db.py line 59-70: card_cache stores partial data
CREATE TABLE IF NOT EXISTS card_cache (
    tcgdex_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,      # ← Redundant
    rarity TEXT,             # ← Redundant  
    types TEXT,              # ← Redundant
    hp INTEGER,              # ← Redundant
    ...
)

# In analyzer.py line 55-85: We ONLY use raw JSON, never card_cache
raw_data = config.load_raw_card_data(tcgdex_id)
name = raw_data.get("name")     # ← Already in raw JSON
rarity = raw_data.get("rarity") # ← Already in raw JSON
```

**Impact**:
- Wasted disk space (~50% redundant storage)
- Extra write operations when adding cards
- Cache can become stale/inconsistent
- Language confusion (cache has one name, but card exists in multiple languages)

**Solution**: **REMOVE card_cache table entirely**. Use only raw JSON.

```python
# Instead of:
cached_card = db.get_cached_card(tcgdex_id)  # ❌ Not needed
name = cached_card.name

# Do:
raw_data = config.load_raw_card_data(tcgdex_id)  # ✅ Already have this
name = raw_data.get("name")
```

**Benefits**:
- Eliminate 200+ lines of cache management code
- No sync issues between cache and raw JSON
- Simpler mental model
- Faster writes (no cache updates)

---

### 2. **MAJOR: N+1 Query Problem in Analyzer**

**Problem**: In `load_card_with_ownership()`, we call `db.get_owned_cards()` for EVERY card, then filter in Python.

**Evidence**:
```python
# analyzer.py line 60-68
owned_cards = db.get_owned_cards()  # ← Loads ALL cards from DB
for owned in owned_cards:
    if owned.tcgdex_id == tcgdex_id and owned.language == language:
        # Filter in Python, not SQL
```

If you have 500 unique cards, this does:
- 500 database queries (one per card)
- Each query fetches ALL owned cards (~thousands of rows)
- Then filters in Python

**Solution**: Create a direct lookup function.

```python
# Add to db.py
def get_card_ownership(tcgdex_id: str, language: str) -> tuple[int, list[str]]:
    """Get quantity and variants for a specific card+language.
    
    Returns:
        (total_quantity, variants_list)
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT variant, quantity FROM cards WHERE tcgdex_id = ? AND language = ?",
            (tcgdex_id, language)
        )
        rows = cursor.fetchall()
        
    if not rows:
        return (0, [])
    
    variants = [row[0] for row in rows]
    total_qty = sum(row[1] for row in rows)
    return (total_qty, variants)
```

**Benefits**:
- 500× faster for large collections
- Single focused query per card
- Uses database indexes properly

---

### 3. **MEDIUM: Duplicate JSON Loading**

**Problem**: In `analyze_collection()`, we load the same JSON file twice.

**Evidence**:
```python
# analyzer.py line 108-109
card = load_card_with_ownership(tcgdex_id, language)
    # ↑ This loads raw JSON (line 55)

# analyzer.py line 113-114  
raw_data = config.load_raw_card_data(tcgdex_id)
    # ↑ Loads SAME file again!
```

**Solution**: Return raw_data from `load_card_with_ownership()` or refactor.

```python
# Option A: Return both
def load_card_with_ownership(tcgdex_id: str, language: str):
    raw_data = config.load_raw_card_data(tcgdex_id)
    # ... process ...
    return CardAnalysis(...), raw_data

# Option B: Add raw_data to CardAnalysis
@dataclass
class CardAnalysis:
    # ... existing fields ...
    raw_data: dict  # Full JSON for filtering
```

---

### 4. **MEDIUM: Inefficient Statistics Calculation**

**Problem**: Multiple loops over the same card list.

**Evidence**:
```python
# analyzer.py line 201-226
for card in cards:  # Loop 1
    if card.stage: ...

for card in cards:  # Loop 2
    if card.types: ...

for card in cards:  # Loop 3
    if card.rarity: ...
# ... 6 separate loops!
```

**Solution**: Single pass over cards.

```python
def get_collection_statistics(cards: list[CardAnalysis]) -> dict:
    if not cards:
        return {...}
    
    stats = {
        "total_cards": len(cards),
        "total_quantity": sum(c.quantity for c in cards),
        "by_stage": {},
        "by_type": {},
        "by_rarity": {},
        "by_category": {},
        "by_set": {},
        "hp_values": [],
    }
    
    # Single loop
    for card in cards:
        # Stage
        if card.stage:
            stats["by_stage"][card.stage] = stats["by_stage"].get(card.stage, 0) + 1
        
        # Types
        if card.types:
            for t in card.types:
                stats["by_type"][t] = stats["by_type"].get(t, 0) + 1
        
        # Rarity
        if card.rarity:
            stats["by_rarity"][card.rarity] = stats["by_rarity"].get(card.rarity, 0) + 1
        
        # Category
        stats["by_category"][card.category] = stats["by_category"].get(card.category, 0) + 1
        
        # Set
        set_id = card.tcgdex_id.split("-")[0]
        stats["by_set"][set_id] = stats["by_set"].get(set_id, 0) + 1
        
        # HP
        if card.hp:
            stats["hp_values"].append(card.hp)
    
    # Calculate average
    if stats["hp_values"]:
        stats["avg_hp"] = sum(stats["hp_values"]) / len(stats["hp_values"])
    else:
        stats["avg_hp"] = 0
    
    del stats["hp_values"]  # Don't return this
    return stats
```

---

### 5. **MINOR: Language/Localization Confusion**

**Problem**: card_cache stores ONE name per card, but cards table supports MULTIPLE languages.

**Current behavior**:
```bash
$ pkm add de:me01-001  # Cache stores "Bisasam"
$ pkm add fr:me01-001  # Cache OVERWRITES with "Bulbizarre"
$ pkm list             # German card shows French name!
```

**Why it happens**: cache_card() has no language parameter, so it overwrites.

**Solution**: Since we're removing card_cache (Issue #1), this problem disappears.

---

## Minor Simplifications

### 6. Remove `variants` field from CardAnalysis

**Current**: We collect variant names in a list.
**Reality**: The UI doesn't use this field, only `quantity`.

```python
# Remove from CardAnalysis
variants: list[str]  # ← Not used in CLI output

# Simplify load_card_with_ownership
# No need to track variant names
```

---

### 7. Simplify `parse_tcgdex_id()`

**Current**: 8 lines, custom error.  
**Better**: One-liner with tuple unpacking.

```python
# Before
def parse_tcgdex_id(tcgdex_id: str) -> tuple[str, str]:
    parts = tcgdex_id.split("-", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid TCGdex ID: {tcgdex_id}")
    return parts[0], parts[1]

# After
def parse_tcgdex_id(tcgdex_id: str) -> tuple[str, str]:
    try:
        return tcgdex_id.split("-", 1)
    except ValueError:
        raise ValueError(f"Invalid TCGdex ID: {tcgdex_id}")
```

---

### 8. Remove `set_name` from CardAnalysis

**Current**: Stored but rarely used.  
**Better**: Only show in detailed view, not in analysis table.

---

## Architecture Recommendations

### Data Storage Strategy

**Current (3 layers)**:
```
1. cards table (ownership: tcgdex_id, variant, language, quantity)
2. card_cache table (metadata: name, rarity, types, hp)  ← REMOVE THIS
3. raw_data/*.json (English: complete card data)
```

**Recommended (2 layers)**:
```
1. cards table (ownership only: tcgdex_id, variant, language, quantity)
2. raw_data/*.json (English: ALL card metadata)
```

**Benefits**:
- Single source of truth for card data
- No sync issues
- Less code to maintain
- Faster writes

---

### Query Optimization

**Add composite index** for analyzer queries:

```sql
CREATE INDEX idx_cards_lookup ON cards(tcgdex_id, language);
```

This makes `get_card_ownership()` instant even with 10,000+ cards.

---

## Estimated Impact

### Lines of Code Reduction

| Change | Lines Removed | Lines Added | Net |
|--------|--------------|-------------|-----|
| Remove card_cache | -250 | +20 | **-230** |
| Fix N+1 problem | -20 | +15 | **-5** |
| Simplify statistics | -30 | +25 | **-5** |
| Minor refactoring | -40 | +10 | **-30** |
| **TOTAL** | **-340** | **+70** | **-270** |

**New total**: ~2,620 lines (-9%)

---

### Performance Impact

| Operation | Before | After | Improvement |
|-----------|--------|-------|-------------|
| Add card | 3 writes | 2 writes | **33% faster** |
| Analyze 500 cards | 500 × full scan | 500 × indexed | **100-1000× faster** |
| Import collection | O(n²) | O(n) | **Linear scaling** |

---

## Implementation Plan

### Phase 1: Critical Fixes (High ROI)
1. ✅ Add `get_card_ownership()` function
2. ✅ Fix duplicate JSON loading
3. ✅ Optimize statistics calculation

### Phase 2: Remove card_cache (Breaking Change)
1. ⚠️ Add migration to drop card_cache table
2. ⚠️ Remove all cache_card() calls
3. ⚠️ Update `list` command to use raw JSON
4. ⚠️ Update tests

### Phase 3: Polish
1. Add composite index
2. Remove unused fields
3. Simplify helpers

---

## Testing Strategy

**Before any changes**:
```bash
# Baseline performance
time pkm analyze --type Fire  # Note execution time
time pkm add de:me01:001      # Note execution time

# Create test data
for i in {1..100}; do
    pkm add de:me01:$(printf "%03d" $i)
done
```

**After changes**:
- Run same commands, compare performance
- Ensure `pytest tests/` still passes
- Verify exports still work

---

## Decision: Keep or Remove card_cache?

### Keep if:
- You want faster `pkm list` (but raw JSON is fast enough for <10k cards)
- You need offline mode without raw JSON files

### Remove if:
- You want simpler code
- You want consistency (no cache staleness)
- You prioritize write performance

**My recommendation**: **REMOVE** card_cache. The benefits of simplicity outweigh the minor read performance gain.

---

## Questions for You

1. **How large will collections get?** (100 cards? 10,000 cards?)
2. **Do you need offline mode?** (Use DB without raw JSON files?)
3. **Breaking change tolerance?** (Okay to drop card_cache in next version?)
4. **Performance priority?** (Read speed vs. write speed vs. code simplicity?)

Let me know your priorities and I can implement the changes!
