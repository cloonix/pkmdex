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


# Schema definition
CREATE_SCHEMA = """
-- Owned cards table
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id TEXT NOT NULL,
    card_number TEXT NOT NULL,
    tcgdex_id TEXT NOT NULL,
    variant TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'de',
    quantity INTEGER DEFAULT 1,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tcgdex_id, variant, language)
);

CREATE INDEX IF NOT EXISTS idx_set_id ON cards(set_id);
CREATE INDEX IF NOT EXISTS idx_tcgdex_id ON cards(tcgdex_id);
CREATE INDEX IF NOT EXISTS idx_language ON cards(language);

-- Composite index for analyzer lookups
CREATE INDEX IF NOT EXISTS idx_cards_lookup ON cards(tcgdex_id, language);

-- Localized card names cache (language-aware)
CREATE TABLE IF NOT EXISTS localized_names (
    tcgdex_id TEXT NOT NULL,
    language TEXT NOT NULL,
    name TEXT NOT NULL,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tcgdex_id, language)
);

-- Set information cache
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


def _migrate_add_language_column(conn: sqlite3.Connection) -> None:
    """Migrate existing database to add language column.

    Args:
        conn: Database connection
    """
    # Check if language column exists
    cursor = conn.execute("PRAGMA table_info(cards)")
    columns = [row[1] for row in cursor.fetchall()]

    if "language" not in columns:
        # SQLite doesn't support ALTER TABLE with constraints, so we need to recreate
        # First, rename the old table
        conn.execute("ALTER TABLE cards RENAME TO cards_old")

        # Create new table with language column
        conn.execute("""
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                set_id TEXT NOT NULL,
                card_number TEXT NOT NULL,
                tcgdex_id TEXT NOT NULL,
                variant TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'de',
                quantity INTEGER DEFAULT 1,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tcgdex_id, variant, language)
            )
        """)

        # Copy data from old table, adding 'de' as default language
        conn.execute("""
            INSERT INTO cards 
            (id, set_id, card_number, tcgdex_id, variant, language, quantity, added_at, updated_at)
            SELECT id, set_id, card_number, tcgdex_id, variant, 'de', quantity, added_at, updated_at
            FROM cards_old
        """)

        # Drop old table
        conn.execute("DROP TABLE cards_old")

        # Recreate indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_set_id ON cards(set_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tcgdex_id ON cards(tcgdex_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_language ON cards(language)")

        conn.commit()


def _migrate_drop_card_cache(conn: sqlite3.Connection) -> None:
    """Drop card_cache table as it's redundant with raw JSON files.

    Args:
        conn: Database connection
    """
    # Check if card_cache table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='card_cache'"
    )
    if cursor.fetchone():
        conn.execute("DROP TABLE card_cache")
        print("✓ Migrated: Removed redundant card_cache table (using raw JSON instead)")


def _migrate_add_composite_index(conn: sqlite3.Connection) -> None:
    """Add composite index for analyzer performance.

    Args:
        conn: Database connection
    """
    # Check if index exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_cards_lookup'"
    )
    if not cursor.fetchone():
        conn.execute("CREATE INDEX idx_cards_lookup ON cards(tcgdex_id, language)")
        print("✓ Migrated: Added composite index for faster analyzer queries")


def _migrate_add_localized_names_table(conn: sqlite3.Connection) -> None:
    """Add localized_names table for language-aware name caching.

    Args:
        conn: Database connection
    """
    # Check if table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='localized_names'"
    )
    if not cursor.fetchone():
        conn.execute("""
            CREATE TABLE localized_names (
                tcgdex_id TEXT NOT NULL,
                language TEXT NOT NULL,
                name TEXT NOT NULL,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tcgdex_id, language)
            )
        """)
        print("✓ Migrated: Added localized_names table for language-aware caching")


def init_database(db_path: Optional[Path] = None) -> None:
    """Initialize database with schema.

    Args:
        db_path: Optional custom database path
    """
    with get_connection(db_path) as conn:
        # Check if this is an existing database
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cards'"
        )
        table_exists = cursor.fetchone() is not None

        if table_exists:
            _migrate_add_language_column(conn)
            _migrate_drop_card_cache(conn)
            _migrate_add_composite_index(conn)
            _migrate_add_localized_names_table(conn)
        else:
            # New database - create schema
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


# === Card Operations ===


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
    """Remove all variants of a card in a specific language.

    Args:
        tcgdex_id: Full TCGdex ID
        language: Language code (e.g., 'de', 'en')

    Returns:
        Number of variants removed
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM cards WHERE tcgdex_id = ? AND language = ? RETURNING *",
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


# === Card Cache Operations (DEPRECATED - Use raw JSON files instead) ===


def cache_card(card_info: CardInfo) -> None:
    """DEPRECATED: Card caching removed. Use raw JSON files instead.

    This function is kept as a no-op stub for backward compatibility.
    Raw JSON files are saved automatically by the API layer.

    Args:
        card_info: CardInfo instance (ignored)
    """
    pass  # No-op - raw JSON is saved by api.py


def get_cached_card(tcgdex_id: str) -> Optional[CardInfo]:
    """DEPRECATED: Card cache removed. Use config.load_raw_card_data() instead.

    This function is kept as a stub that returns None for backward compatibility.
    Callers should use config.load_raw_card_data(tcgdex_id) to get card data.

    Args:
        tcgdex_id: Full TCGdex ID

    Returns:
        None (cache no longer exists)
    """
    return None  # Cache table removed


# === Localized Names Cache Operations ===


def cache_localized_name(tcgdex_id: str, language: str, name: str) -> None:
    """Cache a card's localized name.

    Args:
        tcgdex_id: Full TCGdex ID (e.g., 'me01-136')
        language: Language code (e.g., 'de', 'en', 'fr')
        name: Localized card name
    """
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO localized_names (tcgdex_id, language, name)
            VALUES (?, ?, ?)
            ON CONFLICT(tcgdex_id, language) 
            DO UPDATE SET name = ?, cached_at = CURRENT_TIMESTAMP
            """,
            (tcgdex_id, language, name, name),
        )
        conn.commit()


def get_localized_name(tcgdex_id: str, language: str) -> Optional[str]:
    """Get a card's localized name from cache.

    Args:
        tcgdex_id: Full TCGdex ID (e.g., 'me01-136')
        language: Language code (e.g., 'de', 'en', 'fr')

    Returns:
        Localized name if cached, None otherwise
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT name FROM localized_names WHERE tcgdex_id = ? AND language = ?",
            (tcgdex_id, language),
        )
        row = cursor.fetchone()
        return row[0] if row else None


def clear_localized_names() -> int:
    """Clear all localized name cache.

    Returns:
        Number of entries removed
    """
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM localized_names")
        return cursor.rowcount


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


def clear_card_cache() -> int:
    """DEPRECATED: Card cache removed.

    This function is kept as a stub for backward compatibility.
    Returns 0 since there is no cache to clear.

    Returns:
        0 (cache no longer exists)
    """
    return 0  # Cache table removed


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

        # Localized names cache stats
        cursor = conn.execute(
            "SELECT COUNT(*), MIN(cached_at), MAX(cached_at) FROM localized_names"
        )
        row = cursor.fetchone()
        names_count = row[0] or 0
        names_oldest = datetime.fromisoformat(row[1]) if row[1] else None
        names_newest = datetime.fromisoformat(row[2]) if row[2] else None

    return {
        "card_cache_count": 0,  # Deprecated - kept for compatibility
        "card_cache_oldest": None,
        "card_cache_newest": None,
        "set_cache_count": set_count,
        "set_cache_oldest": set_oldest,
        "set_cache_newest": set_newest,
        "localized_names_count": names_count,
        "localized_names_oldest": names_oldest,
        "localized_names_newest": names_newest,
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

        # Import card cache
        for card in import_data.get("card_cache", []):
            conn.execute(
                """
                INSERT INTO card_cache
                (tcgdex_id, name, set_name, rarity, types, hp, available_variants, image_url, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card["tcgdex_id"],
                    card["name"],
                    card["set_name"],
                    card["rarity"],
                    card["types"],
                    card["hp"],
                    card["available_variants"],
                    card["image_url"],
                    card["cached_at"],
                ),
            )

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
