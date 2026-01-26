"""Migration script from v1 schema to v2 schema.

v1 schema:
- cards table: Combined ownership + basic card info
- JSON files: Card metadata (name, types, hp, etc.) in raw_data/cards/

v2 schema:
- cards table: Canonical English card data with prices/legality
- card_names table: Localized names only
- owned_cards table: Ownership tracking
- No JSON files (all in database)
"""

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Optional

from .api import get_api
from .config import load_config
from .db import get_connection, get_db_path, parse_tcgdex_id


def detect_schema_version(db_path: Optional[Path] = None) -> int:
    """Detect which schema version the database uses.

    Args:
        db_path: Optional custom database path

    Returns:
        1 for v1 schema, 2 for v2 schema, 0 for empty/new database
    """
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}

        # No tables = new database
        if not tables:
            return 0

        # v2 has 'cards', 'card_names', 'owned_cards'
        if "card_names" in tables and "owned_cards" in tables:
            # Verify v2 schema by checking cards table structure
            cursor = conn.execute("PRAGMA table_info(cards)")
            columns = {row[1] for row in cursor.fetchall()}

            # v2 cards table has 'price_eur', 'legal_standard', etc.
            if "price_eur" in columns and "legal_standard" in columns:
                return 2

        # v1 has 'cards' table with 'quantity' column (ownership data)
        if "cards" in tables:
            cursor = conn.execute("PRAGMA table_info(cards)")
            columns = {row[1] for row in cursor.fetchall()}

            # v1 cards table has 'quantity' (ownership field)
            if "quantity" in columns:
                return 1

        # Unknown schema
        return -1


def create_backup(db_path: Path) -> Path:
    """Create backup of database before migration.

    Args:
        db_path: Path to database

    Returns:
        Path to backup file
    """
    import shutil
    from datetime import datetime

    config = load_config()
    config.backups_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = config.backups_path / f"pokedex_v1_backup_{timestamp}.db"

    shutil.copy2(db_path, backup_path)
    print(f"✓ Created backup: {backup_path}")

    return backup_path


async def migrate_v1_to_v2(
    db_path: Optional[Path] = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Migrate database from v1 to v2 schema.

    Strategy:
    1. Create backup
    2. Create v2 tables (cards, card_names, owned_cards)
    3. Migrate data:
       - Read v1 'cards' table (ownership data)
       - For each unique tcgdex_id:
         a. Load JSON file OR fetch from API
         b. Insert into v2 'cards' table (English data)
         c. Insert into v2 'card_names' table (localized name)
         d. Insert into v2 'owned_cards' table (ownership)
    4. Drop old v1 'cards' table
    5. Validate migration

    Args:
        db_path: Optional custom database path
        dry_run: If True, only report what would be done
        verbose: Show detailed progress

    Returns:
        Migration stats dictionary
    """
    path = db_path or get_db_path()

    # Detect current version
    version = detect_schema_version(path)
    if version == 0:
        return {
            "status": "skipped",
            "reason": "Database is empty (nothing to migrate)",
        }
    elif version == 2:
        return {
            "status": "skipped",
            "reason": "Database already uses v2 schema",
        }
    elif version == -1:
        return {
            "status": "error",
            "reason": "Unknown database schema (manual intervention required)",
        }

    print("🔄 Starting migration from v1 to v2 schema...")
    print(f"   Database: {path}")

    if dry_run:
        print("   Mode: DRY RUN (no changes will be made)")

    # Create backup (skip in dry run)
    backup_path = None
    if not dry_run:
        backup_path = create_backup(path)

    # Initialize API client
    en_api = get_api("en")
    config = load_config()

    stats = {
        "cards_migrated": 0,
        "cards_fetched_from_api": 0,
        "cards_loaded_from_json": 0,
        "cards_failed": 0,
        "names_migrated": 0,
        "ownership_records_migrated": 0,
    }

    failed_cards = []

    with get_connection(path) as conn:
        # Step 1: Read all v1 data
        if verbose:
            print("\n📖 Reading v1 data...")

        cursor = conn.execute(
            "SELECT tcgdex_id, variant, language, quantity FROM cards ORDER BY tcgdex_id"
        )
        v1_cards = cursor.fetchall()

        print(f"   Found {len(v1_cards)} ownership records")

        # Step 2: Rename old v1 tables first (to avoid conflicts)
        if not dry_run:
            if verbose:
                print("\n🔧 Renaming v1 tables...")

            try:
                # Check if card_cache exists (v1-specific table we no longer need)
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='card_cache'"
                )
                if cursor.fetchone():
                    conn.execute(
                        "ALTER TABLE card_cache RENAME TO card_cache_v1_backup"
                    )
                    if verbose:
                        print("   ✓ Renamed card_cache to card_cache_v1_backup")

                # Rename v1 cards table (ownership data)
                conn.execute("ALTER TABLE cards RENAME TO cards_v1_backup")
                if verbose:
                    print("   ✓ Renamed cards to cards_v1_backup")

                conn.commit()
            except Exception as e:
                print(f"   ⚠ Error renaming tables: {e}")
                raise

        # Step 3: Create v2 tables
        if not dry_run:
            if verbose:
                print("\n🏗️  Creating v2 tables...")

            # Import schema from db.py
            from .db import CREATE_SCHEMA

            conn.executescript(CREATE_SCHEMA)
            conn.commit()

        # Step 3: Migrate data
        if verbose:
            print("\n🔄 Migrating card data...")

        # Group by tcgdex_id to process each card once
        cards_by_id = {}
        for tcgdex_id, variant, language, quantity in v1_cards:
            if tcgdex_id not in cards_by_id:
                cards_by_id[tcgdex_id] = []
            cards_by_id[tcgdex_id].append((variant, language, quantity))

        # Process each unique card
        for idx, (tcgdex_id, ownership_records) in enumerate(cards_by_id.items(), 1):
            if verbose:
                print(f"   [{idx}/{len(cards_by_id)}] {tcgdex_id}")

            set_id, card_number = parse_tcgdex_id(tcgdex_id)

            # Try to get card data (JSON first, then API)
            card_data = None

            # Try loading from JSON file (English)
            json_path = config.raw_data_path / "cards" / f"{tcgdex_id}.json"
            if json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        card_data = json.load(f)
                    stats["cards_loaded_from_json"] += 1
                    if verbose:
                        print(f"      ✓ Loaded from JSON: {json_path.name}")
                except Exception as e:
                    if verbose:
                        print(f"      ⚠ Failed to load JSON: {e}")

            # Fallback to API
            if not card_data:
                try:
                    card_data = await en_api.get_card_raw(set_id, card_number)
                    stats["cards_fetched_from_api"] += 1
                    if verbose:
                        print(f"      ✓ Fetched from API")
                except Exception as e:
                    stats["cards_failed"] += 1
                    failed_cards.append((tcgdex_id, str(e)))
                    if verbose:
                        print(f"      ✗ Failed to fetch from API: {e}")
                    continue

            # Extract data for v2 tables
            try:
                name_en = card_data.get("name", "Unknown")
                rarity = card_data.get("rarity")
                hp = card_data.get("hp")
                stage = card_data.get("stage")
                category = card_data.get("category")
                image_url = card_data.get("image")

                # Types (JSON array)
                types_list = card_data.get("types", [])
                types_json = json.dumps(types_list) if types_list else None

                # Pricing (not implemented yet, set to None)
                price_eur = None
                price_usd = None

                # Legality (from card_data.legal if available)
                legal_data = card_data.get("legal", {})
                legal_standard = legal_data.get("standard", False)
                legal_expanded = legal_data.get("expanded", False)

            except Exception as e:
                stats["cards_failed"] += 1
                failed_cards.append((tcgdex_id, f"Data extraction failed: {e}"))
                if verbose:
                    print(f"      ✗ Failed to extract data: {e}")
                continue

            if not dry_run:
                try:
                    # Insert into v2 'cards' table
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO cards (
                            tcgdex_id, set_id, card_number, name, rarity,
                            types, hp, stage, category, image_url,
                            price_eur, price_usd, legal_standard, legal_expanded
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            tcgdex_id,
                            set_id,
                            card_number,
                            name_en,
                            rarity,
                            types_json,
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
                    stats["cards_migrated"] += 1

                except Exception as e:
                    stats["cards_failed"] += 1
                    failed_cards.append((tcgdex_id, f"Insert into cards failed: {e}"))
                    if verbose:
                        print(f"      ✗ Failed to insert into cards: {e}")
                    continue
            else:
                stats["cards_migrated"] += 1

            # Insert localized names for each language in ownership records
            languages_seen = set()
            for variant, language, quantity in ownership_records:
                if language in languages_seen:
                    continue
                languages_seen.add(language)

                # Try to load localized JSON
                localized_name = name_en  # Fallback to English

                if language != "en":
                    localized_json_path = (
                        config.raw_data_path / "cards" / f"{tcgdex_id}.{language}.json"
                    )
                    if localized_json_path.exists():
                        try:
                            with open(localized_json_path, "r", encoding="utf-8") as f:
                                localized_data = json.load(f)
                            localized_name = localized_data.get("name", name_en)
                            if verbose:
                                print(
                                    f"      ✓ Loaded {language} name from JSON: {localized_name}"
                                )
                        except Exception as e:
                            if verbose:
                                print(f"      ⚠ Failed to load {language} JSON: {e}")
                    else:
                        # Try fetching from API
                        try:
                            lang_api = get_api(language)
                            localized_data = await lang_api.get_card_raw(
                                set_id, card_number
                            )
                            localized_name = localized_data.get("name", name_en)
                            if verbose:
                                print(
                                    f"      ✓ Fetched {language} name from API: {localized_name}"
                                )
                        except Exception as e:
                            if verbose:
                                print(
                                    f"      ⚠ Failed to fetch {language} name from API: {e}"
                                )

                if not dry_run:
                    try:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO card_names (tcgdex_id, language, name)
                            VALUES (?, ?, ?)
                            """,
                            (tcgdex_id, language, localized_name),
                        )
                        stats["names_migrated"] += 1
                    except Exception as e:
                        if verbose:
                            print(f"      ✗ Failed to insert card_name: {e}")
                else:
                    stats["names_migrated"] += 1

            # Insert ownership records into v2 'owned_cards' table
            for variant, language, quantity in ownership_records:
                if not dry_run:
                    try:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO owned_cards (tcgdex_id, variant, language, quantity)
                            VALUES (?, ?, ?, ?)
                            """,
                            (tcgdex_id, variant, language, quantity),
                        )
                        stats["ownership_records_migrated"] += 1
                    except Exception as e:
                        if verbose:
                            print(f"      ✗ Failed to insert owned_card: {e}")
                else:
                    stats["ownership_records_migrated"] += 1

        if not dry_run:
            conn.commit()

    # Step 4: Validate migration
    if not dry_run:
        if verbose:
            print("\n✅ Validating migration...")

        validation = validate_migration(path)
        stats["validation"] = validation

    # Print summary
    print("\n📊 Migration Summary:")
    print(f"   Cards migrated: {stats['cards_migrated']}")
    print(f"   Names migrated: {stats['names_migrated']}")
    print(f"   Ownership records migrated: {stats['ownership_records_migrated']}")
    print(f"   Cards loaded from JSON: {stats['cards_loaded_from_json']}")
    print(f"   Cards fetched from API: {stats['cards_fetched_from_api']}")
    print(f"   Failed cards: {stats['cards_failed']}")

    if failed_cards:
        print("\n⚠️  Failed Cards:")
        for tcgdex_id, error in failed_cards:
            print(f"   {tcgdex_id}: {error}")

    if not dry_run:
        print("\n✅ Migration complete!")
        if backup_path:
            print(f"   Backup saved to: {backup_path}")
        print("\n⚠️  IMPORTANT: Test your collection with 'pkm list' and 'pkm stats'")
        print("   If everything looks good, you can manually drop the backup tables:")
        print("   sqlite3 pokedex.db 'DROP TABLE cards_v1_backup;'")
        print("   sqlite3 pokedex.db 'DROP TABLE card_cache_v1_backup;'")

    return stats


def validate_migration(db_path: Optional[Path] = None) -> dict:
    """Validate that migration was successful.

    Args:
        db_path: Optional custom database path

    Returns:
        Validation results dictionary
    """
    with get_connection(db_path) as conn:
        # Check table existence
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('cards', 'card_names', 'owned_cards')"
        )
        tables = {row[0] for row in cursor.fetchall()}

        # Count records
        cards_count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        names_count = conn.execute("SELECT COUNT(*) FROM card_names").fetchone()[0]
        owned_count = conn.execute("SELECT COUNT(*) FROM owned_cards").fetchone()[0]

        # Check for orphaned records (owned_cards without cards entry)
        cursor = conn.execute(
            """
            SELECT COUNT(*) FROM owned_cards o
            LEFT JOIN cards c ON o.tcgdex_id = c.tcgdex_id
            WHERE c.tcgdex_id IS NULL
            """
        )
        orphaned_owned = cursor.fetchone()[0]

        # Check for orphaned names
        cursor = conn.execute(
            """
            SELECT COUNT(*) FROM card_names n
            LEFT JOIN cards c ON n.tcgdex_id = c.tcgdex_id
            WHERE c.tcgdex_id IS NULL
            """
        )
        orphaned_names = cursor.fetchone()[0]

        validation = {
            "v2_tables_exist": len(tables) == 3,
            "cards_count": cards_count,
            "card_names_count": names_count,
            "owned_cards_count": owned_count,
            "orphaned_owned_cards": orphaned_owned,
            "orphaned_names": orphaned_names,
            "is_valid": (
                len(tables) == 3
                and cards_count > 0
                and owned_count > 0
                and orphaned_owned == 0
                and orphaned_names == 0
            ),
        }

        print(f"   Tables exist: {validation['v2_tables_exist']}")
        print(f"   Cards: {cards_count}")
        print(f"   Card names: {names_count}")
        print(f"   Owned cards: {owned_count}")

        if orphaned_owned > 0:
            print(f"   ⚠️  Orphaned owned_cards: {orphaned_owned}")

        if orphaned_names > 0:
            print(f"   ⚠️  Orphaned card_names: {orphaned_names}")

        return validation


def rollback_migration(backup_path: Path, db_path: Optional[Path] = None) -> None:
    """Rollback migration by restoring from backup.

    Args:
        backup_path: Path to backup file
        db_path: Optional custom database path
    """
    import shutil

    path = db_path or get_db_path()

    print(f"🔄 Rolling back migration...")
    print(f"   Restoring from: {backup_path}")
    print(f"   Target: {path}")

    if not backup_path.exists():
        print(f"❌ Backup file not found: {backup_path}")
        return

    # Create backup of current state (just in case)
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    current_backup = path.parent / f"pokedex_before_rollback_{timestamp}.db"
    shutil.copy2(path, current_backup)
    print(f"   Created backup of current state: {current_backup}")

    # Restore from backup
    shutil.copy2(backup_path, path)

    print("✅ Rollback complete!")
    print(f"   Database restored to v1 schema")
