"""Database operations for Pokemon card collection."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Generator

from .models import OwnedCard, CardInfo, SetInfo, CardVariants


# Database file location - can be overridden for testing
_DEFAULT_DB_PATH = None
DB_PATH = None


def get_db_path() -> Path:
    """Get the configured database path.

    Returns:
        Path to database file from config or default.
    """
    global DB_PATH, _DEFAULT_DB_PATH

    # If DB_PATH has been manually set (e.g., by tests), use it
    if DB_PATH is not None and DB_PATH != _DEFAULT_DB_PATH:
        return DB_PATH

    # Import here to avoid circular dependency
    from . import config

    cfg = config.load_config()
    _DEFAULT_DB_PATH = cfg.db_path
    DB_PATH = cfg.db_path
    return cfg.db_path


# Schema definition - v2 (Option B: Smart Sync)
CREATE_SCHEMA = """
-- Table 1: Canonical card data (English only) with prices and legality
CREATE TABLE IF NOT EXISTS cards (
    -- Identity
    tcgdex_id TEXT PRIMARY KEY,
    set_id TEXT NOT NULL,
    card_number TEXT NOT NULL,
    
    -- Card information (English only)
    name TEXT NOT NULL,
    rarity TEXT,
    types TEXT,              -- JSON array: ["Grass", "Poison"]
    hp INTEGER,
    stage TEXT,              -- Basic, Stage1, Stage2, ex, VMAX, etc.
    category TEXT,           -- Pokémon, Trainer, Energy
    
    -- Media
    image_url TEXT,
    
    -- Pricing (from TCGdex API)
    price_eur REAL,
    price_usd REAL,
    
    -- Legality (from TCGdex API)
    legal_standard BOOLEAN,
    legal_expanded BOOLEAN,
    
    -- Metadata
    last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cards_set_id ON cards(set_id);
CREATE INDEX IF NOT EXISTS idx_cards_synced ON cards(last_synced);

-- Table 2: Localized card names (name-only translations)
CREATE TABLE IF NOT EXISTS card_names (
    tcgdex_id TEXT NOT NULL,
    language TEXT NOT NULL,   -- ISO 639-1: de, fr, es, en, etc.
    name TEXT NOT NULL,
    
    PRIMARY KEY (tcgdex_id, language),
    FOREIGN KEY (tcgdex_id) REFERENCES cards(tcgdex_id) ON DELETE CASCADE
);

-- Table 3: User's owned cards (tracks ownership + language of physical card)
CREATE TABLE IF NOT EXISTS owned_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tcgdex_id TEXT NOT NULL,
    variant TEXT NOT NULL,
    language TEXT NOT NULL,   -- Language of physical card owned
    quantity INTEGER DEFAULT 1,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(tcgdex_id, variant, language),
    FOREIGN KEY (tcgdex_id) REFERENCES cards(tcgdex_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_owned_tcgdex ON owned_cards(tcgdex_id);

-- Set information cache (unchanged from v1)
CREATE TABLE IF NOT EXISTS set_cache (
    set_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    card_count INTEGER,
    release_date TEXT,
    serie_id TEXT,
    serie_name TEXT,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_database(db_path: Optional[Path] = None) -> None:
    """Initialize database with schema.

    Args:
        db_path: Optional custom database path
    """
    with get_connection(db_path) as conn:
        # Simply create schema - CREATE TABLE IF NOT EXISTS handles existing tables
        conn.executescript(CREATE_SCHEMA)
        conn.commit()


@contextmanager
def get_connection(
    db_path: Optional[Path] = None,
) -> Generator[sqlite3.Connection, None, None]:
    """Get database connection context manager.

    Args:
        db_path: Optional custom database path (defaults to configured path)

    Yields:
        SQLite connection
    """
    path = db_path or get_db_path()
    conn = sqlite3.connect(str(path))
    try:
        yield conn
    finally:
        conn.close()


def parse_tcgdex_id(tcgdex_id: str) -> tuple[str, str]:
    """Parse TCGdex ID into set_id and card_number.

    Args:
        tcgdex_id: Full TCGdex ID (e.g., "me01-136")

    Returns:
        Tuple of (set_id, card_number)

    Raises:
        ValueError: If ID format is invalid
    """
    parts = tcgdex_id.split("-", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid TCGdex ID format: {tcgdex_id}")
    return parts[0], parts[1]


# === v2 Schema Helper Functions ===


def upsert_card(
    tcgdex_id: str,
    name: str,
    set_id: str,
    card_number: str,
    rarity: Optional[str] = None,
    types: Optional[str] = None,
    hp: Optional[int] = None,
    stage: Optional[str] = None,
    category: Optional[str] = None,
    image_url: Optional[str] = None,
    price_eur: Optional[float] = None,
    price_usd: Optional[float] = None,
    legal_standard: Optional[bool] = None,
    legal_expanded: Optional[bool] = None,
) -> None:
    """Insert or update canonical card data (English).

    Args:
        tcgdex_id: Full TCGdex ID (e.g., "me01-136")
        name: English card name
        set_id: Set identifier (e.g., "me01")
        card_number: Card number in set (e.g., "136")
        rarity: Card rarity (English)
        types: JSON string of types (e.g., '["Grass"]')
        hp: Hit points
        stage: Card stage (Basic, Stage1, etc.)
        category: Card category (Pokémon, Trainer, Energy)
        image_url: High-res image URL
        price_eur: Cardmarket average price in EUR
        price_usd: TCGPlayer market price in USD
        legal_standard: Legal in Standard format
        legal_expanded: Legal in Expanded format
    """
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO cards (
                tcgdex_id, set_id, card_number, name, rarity, types, hp, stage,
                category, image_url, price_eur, price_usd, legal_standard, legal_expanded
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tcgdex_id) DO UPDATE SET
                name = excluded.name,
                rarity = excluded.rarity,
                types = excluded.types,
                hp = excluded.hp,
                stage = excluded.stage,
                category = excluded.category,
                image_url = excluded.image_url,
                price_eur = excluded.price_eur,
                price_usd = excluded.price_usd,
                legal_standard = excluded.legal_standard,
                legal_expanded = excluded.legal_expanded,
                last_synced = CURRENT_TIMESTAMP
            """,
            (
                tcgdex_id,
                set_id,
                card_number,
                name,
                rarity,
                types,
                hp,
                stage,
                category,
                image_url,
                price_eur,
                price_usd,
                legal_standard,
                legal_expanded,
            ),
        )
        conn.commit()


def get_card(tcgdex_id: str) -> Optional[dict]:
    """Get canonical card data.

    Args:
        tcgdex_id: Full TCGdex ID

    Returns:
        Dict with card data or None if not found
    """
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM cards WHERE tcgdex_id = ?", (tcgdex_id,))
        row = cursor.fetchone()
        if not row:
            return None

        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))


def get_cards_by_set(set_id: str) -> list[dict]:
    """Get all canonical cards in a set.

    Args:
        set_id: Set identifier (e.g., "me01")

    Returns:
        List of card data dicts
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM cards WHERE set_id = ? ORDER BY card_number", (set_id,)
        )
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_stale_cards(days: int = 7) -> list[str]:
    """Get tcgdex_ids of cards needing sync (owned and stale).

    Args:
        days: Cards older than this many days are stale

    Returns:
        List of tcgdex_ids
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT c.tcgdex_id
            FROM cards c
            WHERE c.tcgdex_id IN (SELECT DISTINCT tcgdex_id FROM owned_cards)
              AND (julianday('now') - julianday(c.last_synced)) > ?
            ORDER BY c.last_synced ASC
            """,
            (days,),
        )
        return [row[0] for row in cursor.fetchall()]


def upsert_card_name(tcgdex_id: str, language: str, name: str) -> None:
    """Insert or update localized card name.

    Args:
        tcgdex_id: Full TCGdex ID
        language: ISO 639-1 language code (e.g., "de", "fr")
        name: Localized card name
    """
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO card_names (tcgdex_id, language, name)
            VALUES (?, ?, ?)
            ON CONFLICT(tcgdex_id, language) DO UPDATE SET
                name = excluded.name
            """,
            (tcgdex_id, language, name),
        )
        conn.commit()


def get_card_name(tcgdex_id: str, language: str) -> Optional[str]:
    """Get localized card name.

    Args:
        tcgdex_id: Full TCGdex ID
        language: ISO 639-1 language code

    Returns:
        Localized name or None if not found
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT name FROM card_names WHERE tcgdex_id = ? AND language = ?",
            (tcgdex_id, language),
        )
        row = cursor.fetchone()
        return row[0] if row else None


def get_languages_for_card(tcgdex_id: str) -> list[str]:
    """Get all languages owned for a specific card.

    Args:
        tcgdex_id: Full TCGdex ID

    Returns:
        List of language codes
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT DISTINCT language FROM owned_cards WHERE tcgdex_id = ? ORDER BY language",
            (tcgdex_id,),
        )
        return [row[0] for row in cursor.fetchall()]


def add_owned_card(
    tcgdex_id: str, variant: str, language: str, quantity: int = 1
) -> None:
    """Add or update owned card.

    Args:
        tcgdex_id: Full TCGdex ID
        variant: Variant name (normal, reverse, holo, firstEdition)
        language: Language of physical card owned
        quantity: Quantity to add (default 1)
    """
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO owned_cards (tcgdex_id, variant, language, quantity)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tcgdex_id, variant, language) DO UPDATE SET
                quantity = quantity + ?
            """,
            (tcgdex_id, variant, language, quantity, quantity),
        )
        conn.commit()


def remove_owned_card(
    tcgdex_id: str, variant: str, language: str, quantity: int = 1
) -> Optional[int]:
    """Remove quantity from owned card, delete if reaches 0.

    Args:
        tcgdex_id: Full TCGdex ID
        variant: Variant name
        language: Language of physical card
        quantity: Quantity to remove (default 1)

    Returns:
        New quantity or None if deleted
    """
    with get_connection() as conn:
        # Get current quantity
        cursor = conn.execute(
            "SELECT quantity FROM owned_cards WHERE tcgdex_id = ? AND variant = ? AND language = ?",
            (tcgdex_id, variant, language),
        )
        row = cursor.fetchone()

        if not row:
            return None

        current_qty = row[0]
        new_qty = current_qty - quantity

        if new_qty <= 0:
            # Delete the record
            conn.execute(
                "DELETE FROM owned_cards WHERE tcgdex_id = ? AND variant = ? AND language = ?",
                (tcgdex_id, variant, language),
            )
            conn.commit()
            return None
        else:
            # Update quantity
            conn.execute(
                "UPDATE owned_cards SET quantity = ? WHERE tcgdex_id = ? AND variant = ? AND language = ?",
                (new_qty, tcgdex_id, variant, language),
            )
            conn.commit()
            return new_qty


def get_v2_owned_cards(
    set_id: Optional[str] = None, language: Optional[str] = None
) -> list[dict]:
    """Get owned cards with card data and localized names (v2 schema).

    Args:
        set_id: Optional set ID filter
        language: Optional language filter

    Returns:
        List of dicts with owned card data + card metadata + localized name
    """
    with get_connection() as conn:
        query = """
            SELECT 
                o.id,
                o.tcgdex_id,
                o.variant,
                o.language,
                o.quantity,
                o.added_at,
                c.set_id,
                c.card_number,
                c.name AS name_en,
                COALESCE(n.name, c.name) AS display_name,
                c.rarity,
                c.hp,
                c.stage,
                c.types,
                c.category,
                c.image_url,
                c.price_eur,
                c.price_usd,
                c.legal_standard,
                c.legal_expanded
            FROM owned_cards o
            JOIN cards c ON o.tcgdex_id = c.tcgdex_id
            LEFT JOIN card_names n ON o.tcgdex_id = n.tcgdex_id AND o.language = n.language
            WHERE 1=1
        """
        params = []

        if set_id:
            query += " AND c.set_id = ?"
            params.append(set_id)

        if language:
            query += " AND o.language = ?"
            params.append(language)

        query += " ORDER BY c.set_id, c.card_number"

        cursor = conn.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_owned_tcgdex_ids() -> list[str]:
    """Get all unique tcgdex_ids owned.

    Returns:
        List of tcgdex_ids
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT DISTINCT tcgdex_id FROM owned_cards ORDER BY tcgdex_id"
        )
        return [row[0] for row in cursor.fetchall()]


def get_v2_collection_stats() -> dict:
    """Get collection statistics (v2 schema).

    Returns:
        Dict with various statistics about the collection
    """
    with get_connection() as conn:
        # Total unique cards (count distinct tcgdex_id + language)
        cursor = conn.execute(
            "SELECT COUNT(DISTINCT tcgdex_id || '-' || language) FROM owned_cards"
        )
        unique_cards = cursor.fetchone()[0] or 0

        # Total quantity across all cards
        cursor = conn.execute("SELECT SUM(quantity) FROM owned_cards")
        total_cards = cursor.fetchone()[0] or 0

        # Sets represented (via JOIN with cards table)
        cursor = conn.execute(
            """
            SELECT COUNT(DISTINCT c.set_id)
            FROM owned_cards o
            JOIN cards c ON o.tcgdex_id = c.tcgdex_id
            """
        )
        sets_count = cursor.fetchone()[0] or 0

        # Most collected set
        cursor = conn.execute(
            """
            SELECT c.set_id, SUM(o.quantity) as qty
            FROM owned_cards o
            JOIN cards c ON o.tcgdex_id = c.tcgdex_id
            GROUP BY c.set_id
            ORDER BY qty DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        most_collected_set = row[0] if row else None
        most_collected_qty = row[1] if row else 0

        # Variant breakdown
        cursor = conn.execute(
            """
            SELECT variant, SUM(quantity) as qty
            FROM owned_cards
            GROUP BY variant
            """
        )
        variant_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

        # Rarity breakdown (now available from cards table!)
        cursor = conn.execute(
            """
            SELECT c.rarity, SUM(o.quantity) as qty
            FROM owned_cards o
            JOIN cards c ON o.tcgdex_id = c.tcgdex_id
            WHERE c.rarity IS NOT NULL
            GROUP BY c.rarity
            """
        )
        rarity_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

        # NEW: Total collection value (from prices in cards table)
        cursor = conn.execute(
            """
            SELECT SUM(c.price_eur * o.quantity) as total_value
            FROM owned_cards o
            JOIN cards c ON o.tcgdex_id = c.tcgdex_id
            WHERE c.price_eur IS NOT NULL
            """
        )
        row = cursor.fetchone()
        total_value_eur = row[0] if row and row[0] else 0.0

        # NEW: Average card value
        avg_card_value_eur = total_value_eur / unique_cards if unique_cards > 0 else 0.0

        # NEW: Most valuable card
        cursor = conn.execute(
            """
            SELECT c.tcgdex_id, c.name, c.price_eur
            FROM cards c
            JOIN owned_cards o ON c.tcgdex_id = o.tcgdex_id
            WHERE c.price_eur IS NOT NULL
            ORDER BY c.price_eur DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        most_valuable_card = (
            {"tcgdex_id": row[0], "name": row[1], "price_eur": row[2]} if row else None
        )

        return {
            "unique_cards": unique_cards,
            "total_cards": total_cards,
            "sets_count": sets_count,
            "most_collected_set": most_collected_set,
            "most_collected_qty": most_collected_qty,
            "variant_breakdown": variant_breakdown,
            "rarity_breakdown": rarity_breakdown,
            # NEW v2 fields:
            "total_value_eur": total_value_eur,
            "avg_card_value_eur": avg_card_value_eur,
            "most_valuable_card": most_valuable_card,
        }


# === v1 Compatibility Functions (Deprecated - Keep for migration) ===


def add_card_variant(
    tcgdex_id: str, variant: str, language: str = "de", quantity: int = 1
) -> OwnedCard:
    """Add or update a card variant in collection.

    Args:
        tcgdex_id: Full TCGdex ID (e.g., "me01-136")
        variant: Variant name
        language: Language code (e.g., 'de', 'en')
        quantity: Quantity to add (default 1)

    Returns:
        Updated OwnedCard instance
    """
    set_id, card_number = parse_tcgdex_id(tcgdex_id)

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO cards (tcgdex_id, variant, language, quantity, set_id, card_number)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tcgdex_id, variant, language) 
            DO UPDATE SET 
                quantity = quantity + ?,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            (tcgdex_id, variant, language, quantity, set_id, card_number, quantity),
        )
        row = cursor.fetchone()
        conn.commit()
        return OwnedCard.from_db_row(row)


def remove_card_variant(
    tcgdex_id: str, variant: str, language: str = "de", quantity: int = 1
) -> Optional[OwnedCard]:
    """Remove quantity from a card variant, or delete if reaches 0.

    Args:
        tcgdex_id: Full TCGdex ID
        variant: Variant name
        language: Language code (e.g., 'de', 'en')
        quantity: Quantity to remove (default 1)

    Returns:
        Updated OwnedCard if still exists, None if deleted
    """
    with get_connection() as conn:
        # Get current quantity
        cursor = conn.execute(
            "SELECT quantity FROM cards WHERE tcgdex_id = ? AND variant = ? AND language = ?",
            (tcgdex_id, variant, language),
        )
        row = cursor.fetchone()

        if not row:
            return None

        current_qty = row[0]
        new_qty = current_qty - quantity

        if new_qty <= 0:
            # Delete the record
            conn.execute(
                "DELETE FROM cards WHERE tcgdex_id = ? AND variant = ? AND language = ?",
                (tcgdex_id, variant, language),
            )
            conn.commit()
            return None
        else:
            # Update quantity
            cursor = conn.execute(
                """
                UPDATE cards 
                SET quantity = ?, updated_at = CURRENT_TIMESTAMP
                WHERE tcgdex_id = ? AND variant = ? AND language = ?
                RETURNING *
                """,
                (new_qty, tcgdex_id, variant, language),
            )
            row = cursor.fetchone()
            conn.commit()
            return OwnedCard.from_db_row(row)


def remove_all_card_variants(tcgdex_id: str, language: str = "de") -> int:
    """Remove all variants of a card in a specific language (v2 schema).

    Args:
        tcgdex_id: Full TCGdex ID
        language: Language code (e.g., 'de', 'en')

    Returns:
        Number of variants removed
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM owned_cards WHERE tcgdex_id = ? AND language = ? RETURNING *",
            (tcgdex_id, language),
        )
        deleted_rows = cursor.fetchall()
        conn.commit()
        return len(deleted_rows)


def get_owned_cards(
    set_id: Optional[str] = None, language: Optional[str] = None
) -> list[OwnedCard]:
    """Get all owned cards, optionally filtered by set and/or language.

    Args:
        set_id: Optional set ID to filter by
        language: Optional language code to filter by (e.g., 'de', 'en')

    Returns:
        List of OwnedCard instances
    """
    with get_connection() as conn:
        query = "SELECT * FROM cards WHERE 1=1"
        params = []

        if set_id:
            query += " AND set_id = ?"
            params.append(set_id)

        if language:
            query += " AND language = ?"
            params.append(language)

        query += " ORDER BY set_id, card_number"

        cursor = conn.execute(query, params)
        return [OwnedCard.from_db_row(row) for row in cursor.fetchall()]


def get_owned_card_ids() -> list[tuple[str, str]]:
    """Get all unique (tcgdex_id, language) pairs from owned cards.

    Returns:
        List of (tcgdex_id, language) tuples for all owned cards
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT DISTINCT tcgdex_id, language 
            FROM cards 
            ORDER BY tcgdex_id, language
            """
        )
        return cursor.fetchall()


def get_card_ownership(tcgdex_id: str, language: str) -> tuple[int, list[str]]:
    """Get quantity and variants for a specific card+language combination.

    This function is optimized for analyzer queries, avoiding the N+1 problem
    by doing a targeted lookup instead of loading all cards.

    Args:
        tcgdex_id: Full TCGdex ID (e.g., "me01-001")
        language: Language code (e.g., "de", "en", "fr")

    Returns:
        Tuple of (total_quantity, variant_list)
        Returns (0, []) if card not owned in this language

    Example:
        >>> get_card_ownership("me01-001", "de")
        (3, ["normal", "reverse"])  # 2 normal + 1 reverse = 3 total
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT variant, quantity FROM cards WHERE tcgdex_id = ? AND language = ?",
            (tcgdex_id, language),
        )
        rows = cursor.fetchall()

    if not rows:
        return (0, [])

    variants = [row[0] for row in rows]
    total_qty = sum(row[1] for row in rows)
    return (total_qty, variants)


# === Set Cache Operations ===


def cache_sets(set_infos: list[SetInfo]) -> None:
    """Cache multiple sets from API.

    Args:
        set_infos: List of SetInfo instances to cache
    """
    with get_connection() as conn:
        for set_info in set_infos:
            conn.execute(
                """
                INSERT OR REPLACE INTO set_cache
                (set_id, name, card_count, release_date, serie_id, serie_name, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    set_info.set_id,
                    set_info.name,
                    set_info.card_count,
                    set_info.release_date,
                    set_info.serie_id,
                    set_info.serie_name,
                    set_info.cached_at.isoformat(),
                ),
            )
        conn.commit()


def get_cached_sets(search_term: Optional[str] = None) -> list[SetInfo]:
    """Get cached sets, optionally filtered by search term.

    Args:
        search_term: Optional case-insensitive search term for set name

    Returns:
        List of SetInfo instances
    """
    with get_connection() as conn:
        if search_term:
            cursor = conn.execute(
                "SELECT * FROM set_cache WHERE LOWER(name) LIKE LOWER(?) OR LOWER(set_id) LIKE LOWER(?) ORDER BY set_id",
                (f"%{search_term}%", f"%{search_term}%"),
            )
        else:
            cursor = conn.execute("SELECT * FROM set_cache ORDER BY set_id")

        return [SetInfo.from_db_row(row) for row in cursor.fetchall()]


def get_set_cache_age() -> Optional[datetime]:
    """Get the age of the set cache.

    Returns:
        Datetime of oldest cached set, None if cache is empty
    """
    with get_connection() as conn:
        cursor = conn.execute("SELECT MIN(cached_at) FROM set_cache")
        row = cursor.fetchone()

        if row and row[0]:
            return datetime.fromisoformat(row[0])
        return None


def clear_set_cache() -> int:
    """Clear all cached set information.

    Returns:
        Number of cache entries cleared
    """
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM set_cache RETURNING *")
        deleted_rows = cursor.fetchall()
        conn.commit()
        return len(deleted_rows)


def get_cache_stats() -> dict:
    """Get cache statistics.

    Returns:
        Dict with cache counts and age information
    """
    with get_connection() as conn:
        # Set cache stats
        cursor = conn.execute(
            "SELECT COUNT(*), MIN(cached_at), MAX(cached_at) FROM set_cache"
        )
        row = cursor.fetchone()
        set_count = row[0] or 0
        set_oldest = datetime.fromisoformat(row[1]) if row[1] else None
        set_newest = datetime.fromisoformat(row[2]) if row[2] else None

    return {
        "set_cache_count": set_count,
        "set_cache_oldest": set_oldest,
        "set_cache_newest": set_newest,
    }


# === Collection Statistics ===


def get_collection_stats() -> dict:
    """Get collection statistics.

    Returns:
        Dict with various statistics about the collection
    """
    with get_connection() as conn:
        # Total unique cards (count distinct tcgdex_id + language combinations)
        cursor = conn.execute(
            "SELECT COUNT(DISTINCT tcgdex_id || '-' || language) FROM cards"
        )
        unique_cards = cursor.fetchone()[0] or 0

        # Total quantity across all cards
        cursor = conn.execute("SELECT SUM(quantity) FROM cards")
        total_cards = cursor.fetchone()[0] or 0

        # Sets represented
        cursor = conn.execute("SELECT COUNT(DISTINCT set_id) FROM cards")
        sets_count = cursor.fetchone()[0] or 0

        # Most collected set
        cursor = conn.execute(
            """
            SELECT set_id, SUM(quantity) as qty
            FROM cards
            GROUP BY set_id
            ORDER BY qty DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        most_collected_set = row[0] if row else None
        most_collected_qty = row[1] if row else 0

        # Variant breakdown
        cursor = conn.execute(
            """
            SELECT variant, SUM(quantity) as qty
            FROM cards
            GROUP BY variant
            """
        )
        variant_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

        # Rarity breakdown (no longer available without card_cache)
        rarity_breakdown = {}  # Deprecated - would need raw JSON parsing

        return {
            "unique_cards": unique_cards,
            "total_cards": total_cards,
            "sets_count": sets_count,
            "most_collected_set": most_collected_set,
            "most_collected_qty": most_collected_qty,
            "variant_breakdown": variant_breakdown,
            "rarity_breakdown": rarity_breakdown,
        }


# === Export/Import Operations ===


def export_to_json(output_path: Path) -> dict:
    """Export entire collection to JSON file.

    Args:
        output_path: Path to write JSON file

    Returns:
        Dict with export metadata (card count, timestamp, etc.)
    """
    with get_connection() as conn:
        # Export owned cards
        cursor = conn.execute("SELECT * FROM cards ORDER BY set_id, card_number")
        cards = [
            {
                "id": row[0],
                "set_id": row[1],
                "card_number": row[2],
                "tcgdex_id": row[3],
                "variant": row[4],
                "language": row[5],
                "quantity": row[6],
                "added_at": row[7],
                "updated_at": row[8],
            }
            for row in cursor.fetchall()
        ]

        # Export set cache
        cursor = conn.execute("SELECT * FROM set_cache")
        set_cache = [
            {
                "set_id": row[0],
                "name": row[1],
                "card_count": row[2],
                "release_date": row[3],
                "serie_id": row[4],
                "serie_name": row[5],
                "cached_at": row[6],
            }
            for row in cursor.fetchall()
        ]

    # Create export data
    export_data = {
        "exported_at": datetime.now().isoformat(),
        "version": "1.0",
        "cards": cards,
        "set_cache": set_cache,
    }

    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    return {
        "file_path": str(output_path),
        "cards_count": len(cards),
        "card_cache_count": 0,  # Deprecated - kept for compatibility
        "set_cache_count": len(set_cache),
        "exported_at": export_data["exported_at"],
    }


def import_from_json(input_path: Path) -> dict:
    """Import collection from JSON file, replacing existing database.

    Args:
        input_path: Path to JSON file to import

    Returns:
        Dict with import metadata (counts, etc.)

    Raises:
        ValueError: If JSON format is invalid
        FileNotFoundError: If input file doesn't exist
    """
    # Read JSON file
    with open(input_path, "r", encoding="utf-8") as f:
        import_data = json.load(f)

    # Validate format
    if "version" not in import_data or "cards" not in import_data:
        raise ValueError("Invalid export file format")

    with get_connection() as conn:
        # Clear existing data
        conn.execute("DELETE FROM cards")
        conn.execute("DELETE FROM set_cache")

        # Import cards
        for card in import_data["cards"]:
            conn.execute(
                """
                INSERT INTO cards 
                (id, set_id, card_number, tcgdex_id, variant, language, quantity, added_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card["id"],
                    card["set_id"],
                    card["card_number"],
                    card["tcgdex_id"],
                    card["variant"],
                    card["language"],
                    card["quantity"],
                    card["added_at"],
                    card["updated_at"],
                ),
            )

        # Skip card_cache import - it's deprecated (kept for compatibility with old exports)
        # (card_cache has been removed)

        # Import set cache
        for set_info in import_data.get("set_cache", []):
            conn.execute(
                """
                INSERT INTO set_cache
                (set_id, name, card_count, release_date, serie_id, serie_name, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    set_info["set_id"],
                    set_info["name"],
                    set_info["card_count"],
                    set_info["release_date"],
                    set_info["serie_id"],
                    set_info["serie_name"],
                    set_info["cached_at"],
                ),
            )

        conn.commit()

    return {
        "cards_count": len(import_data["cards"]),
        "card_cache_count": 0,  # Deprecated - kept for compatibility
        "set_cache_count": len(import_data.get("set_cache", [])),
        "exported_at": import_data.get("exported_at"),
    }
