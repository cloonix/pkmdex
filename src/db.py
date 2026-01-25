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

-- Card metadata cache
CREATE TABLE IF NOT EXISTS card_cache (
    tcgdex_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    set_name TEXT,
    rarity TEXT,
    types TEXT,
    hp INTEGER,
    available_variants TEXT NOT NULL,
    image_url TEXT,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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


def init_database(db_path: Optional[Path] = None) -> None:
    """Initialize database with schema.

    Args:
        db_path: Optional custom database path (defaults to DB_PATH)
    """
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(path) as conn:
        # First run migration if needed (for existing databases)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cards'"
        )
        table_exists = cursor.fetchone() is not None

        if table_exists:
            _migrate_add_language_column(conn)
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


# === Card Cache Operations ===


def cache_card(card_info: CardInfo) -> None:
    """Cache card metadata from API.

    Args:
        card_info: CardInfo instance to cache
    """
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO card_cache 
            (tcgdex_id, name, set_name, rarity, types, hp, available_variants, image_url, cached_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card_info.tcgdex_id,
                card_info.name,
                card_info.set_name,
                card_info.rarity,
                json.dumps(card_info.types),
                card_info.hp,
                json.dumps(card_info.available_variants.to_json()),
                card_info.image_url,
                card_info.cached_at.isoformat(),
            ),
        )
        conn.commit()


def get_cached_card(tcgdex_id: str) -> Optional[CardInfo]:
    """Get cached card metadata.

    Args:
        tcgdex_id: Full TCGdex ID

    Returns:
        CardInfo if cached, None otherwise
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM card_cache WHERE tcgdex_id = ?", (tcgdex_id,)
        )
        row = cursor.fetchone()

        if row:
            return CardInfo.from_db_row(row)
        return None


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


# === Collection Statistics ===


def get_collection_stats() -> dict:
    """Get collection statistics.

    Returns:
        Dict with various statistics about the collection
    """
    with get_connection() as conn:
        # Total unique cards and total quantity
        cursor = conn.execute(
            """
            SELECT 
                COUNT(DISTINCT tcgdex_id) as unique_cards,
                SUM(quantity) as total_cards
            FROM cards
            """
        )
        row = cursor.fetchone()
        unique_cards, total_cards = row[0] or 0, row[1] or 0

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

        # Rarity breakdown (requires join with cache)
        cursor = conn.execute(
            """
            SELECT c.rarity, SUM(cards.quantity) as qty
            FROM cards
            LEFT JOIN card_cache c ON cards.tcgdex_id = c.tcgdex_id
            WHERE c.rarity IS NOT NULL
            GROUP BY c.rarity
            """
        )
        rarity_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

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

        # Export card cache
        cursor = conn.execute("SELECT * FROM card_cache")
        card_cache = [
            {
                "tcgdex_id": row[0],
                "name": row[1],
                "set_name": row[2],
                "rarity": row[3],
                "types": row[4],
                "hp": row[5],
                "available_variants": row[6],
                "image_url": row[7],
                "cached_at": row[8],
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
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "cards": cards,
        "card_cache": card_cache,
        "set_cache": set_cache,
    }

    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    return {
        "cards_count": len(cards),
        "card_cache_count": len(card_cache),
        "set_cache_count": len(set_cache),
        "file_path": str(output_path),
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
        conn.execute("DELETE FROM card_cache")
        conn.execute("DELETE FROM set_cache")

        # Import owned cards
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
        "card_cache_count": len(import_data.get("card_cache", [])),
        "set_cache_count": len(import_data.get("set_cache", [])),
        "version": import_data["version"],
        "exported_at": import_data.get("exported_at"),
    }
