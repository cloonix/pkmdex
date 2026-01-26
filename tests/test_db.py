"""Tests for database operations."""

import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from src import db
from src.models import CardInfo, CardVariants, SetInfo


@pytest.fixture
def temp_db():
    """Create temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    db.init_database(db_path)

    # Store original path and replace with temp path
    original_path = db.DB_PATH
    db.DB_PATH = db_path

    yield db_path

    # Restore original path and cleanup
    db.DB_PATH = original_path
    db_path.unlink(missing_ok=True)


def test_init_database(temp_db):
    """Test database initialization creates all tables."""
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        # v2 schema tables
        assert "cards" in tables
        assert "card_names" in tables
        assert "owned_cards" in tables
        assert "set_cache" in tables


def test_add_card_variant_new(temp_db):
    """Test adding a new card variant (v2 API)."""
    # v2: Insert card data first
    db.upsert_card(
        tcgdex_id="me01-136",
        name="Bulbasaur",
        set_id="me01",
        card_number="136",
        rarity="Common",
        types='["Grass"]',
    )
    # Insert localized name
    db.upsert_card_name("me01-136", "de", "Bisasam")

    # Add ownership
    db.add_owned_card("me01-136", "normal", "de", 1)

    # Verify ownership
    owned = db.get_v2_owned_cards()
    assert len(owned) == 1
    assert owned[0]["tcgdex_id"] == "me01-136"
    assert owned[0]["set_id"] == "me01"
    assert owned[0]["card_number"] == "136"
    assert owned[0]["variant"] == "normal"
    assert owned[0]["language"] == "de"
    assert owned[0]["quantity"] == 1
    assert owned[0]["display_name"] == "Bisasam"


def test_add_card_variant_accumulate(temp_db):
    """Test adding to existing card accumulates quantity (v2 API)."""
    # Setup card
    db.upsert_card("me01-136", "Bulbasaur", "me01", "136")
    db.upsert_card_name("me01-136", "de", "Bisasam")

    # Add first ownership
    db.add_owned_card("me01-136", "normal", "de", 1)

    # Add more quantity
    db.add_owned_card("me01-136", "normal", "de", 2)

    # Verify accumulated
    owned = db.get_v2_owned_cards()
    assert len(owned) == 1
    assert owned[0]["quantity"] == 3


def test_add_multiple_variants(temp_db):
    """Test adding different variants of same card (v2 API)."""
    # Setup card
    db.upsert_card("me01-136", "Bulbasaur", "me01", "136")
    db.upsert_card_name("me01-136", "de", "Bisasam")

    # Add different variants
    db.add_owned_card("me01-136", "normal", "de", 1)
    db.add_owned_card("me01-136", "reverse", "de", 1)

    owned = db.get_v2_owned_cards()
    assert len(owned) == 2

    variants = {c["variant"] for c in owned}
    assert variants == {"normal", "reverse"}


def test_remove_card_variant(temp_db):
    """Test removing card variant (v2 API)."""
    # Setup card
    db.upsert_card("me01-136", "Bulbasaur", "me01", "136")
    db.upsert_card_name("me01-136", "de", "Bisasam")
    db.add_owned_card("me01-136", "normal", "de", 3)

    # Remove some quantity
    result = db.remove_owned_card("me01-136", "normal", "de", 1)
    assert result == 2  # v2 returns new quantity

    # Remove remaining
    result = db.remove_owned_card("me01-136", "normal", "de", 2)
    assert result is None  # Should be deleted

    owned = db.get_v2_owned_cards()
    assert len(owned) == 0


def test_remove_nonexistent_card(temp_db):
    """Test removing card that doesn't exist (v2 API)."""
    result = db.remove_owned_card("me01-999", "normal", "de")
    assert result is None


def test_get_owned_cards_filter(temp_db):
    """Test filtering owned cards by set and language (v2 API)."""
    # Setup cards
    db.upsert_card("me01-136", "Bulbasaur", "me01", "136")
    db.upsert_card("me01-137", "Ivysaur", "me01", "137")
    db.upsert_card("sv06-045", "Pikachu", "sv06", "045")

    db.upsert_card_name("me01-136", "de", "Bisasam")
    db.upsert_card_name("me01-137", "de", "Bisaknosp")
    db.upsert_card_name("sv06-045", "en", "Pikachu")

    # Add ownership
    db.add_owned_card("me01-136", "normal", "de", 1)
    db.add_owned_card("me01-137", "normal", "de", 1)
    db.add_owned_card("sv06-045", "holo", "en", 1)

    all_cards = db.get_v2_owned_cards()
    assert len(all_cards) == 3

    me01_cards = db.get_v2_owned_cards(set_id="me01")
    assert len(me01_cards) == 2

    sv06_cards = db.get_v2_owned_cards(set_id="sv06")
    assert len(sv06_cards) == 1

    # Test language filtering
    de_cards = db.get_v2_owned_cards(language="de")
    assert len(de_cards) == 2

    en_cards = db.get_v2_owned_cards(language="en")
    assert len(en_cards) == 1


def test_cache_sets(temp_db):
    """Test caching and retrieving sets."""
    sets = [
        SetInfo(
            set_id="me01",
            name="Mega-Entwicklung",
            card_count=132,
            release_date="2024-01-26",
            serie_id="me",
            serie_name="Mega Evolution",
            cached_at=datetime.now(),
        ),
        SetInfo(
            set_id="sv06",
            name="Twilight Masquerade",
            card_count=226,
            release_date="2024-05-24",
            serie_id="sv",
            serie_name="Scarlet & Violet",
            cached_at=datetime.now(),
        ),
    ]

    db.cache_sets(sets)

    cached = db.get_cached_sets()
    assert len(cached) == 2

    # Test search
    mega_sets = db.get_cached_sets("mega")
    assert len(mega_sets) == 1
    assert mega_sets[0].set_id == "me01"


def test_collection_stats(temp_db):
    """Test collection statistics (v2 API)."""
    # Setup cards
    db.upsert_card("me01-136", "Bulbasaur", "me01", "136", rarity="Common")
    db.upsert_card("me01-137", "Ivysaur", "me01", "137", rarity="Uncommon")
    db.upsert_card("sv06-045", "Pikachu", "sv06", "045", rarity="Rare")

    # Add ownership
    db.add_owned_card("me01-136", "normal", "de", 2)
    db.add_owned_card("me01-136", "reverse", "de", 1)
    db.add_owned_card("me01-137", "normal", "de", 1)
    db.add_owned_card("sv06-045", "holo", "en", 5)  # sv06 has more total

    stats = db.get_v2_collection_stats()

    assert stats["unique_cards"] == 3  # 3 unique tcgdex_id + language combos
    assert stats["total_cards"] == 9
    assert stats["sets_count"] == 2
    assert stats["most_collected_set"] == "sv06"
    assert stats["variant_breakdown"]["normal"] == 3
    assert stats["variant_breakdown"]["holo"] == 5
    # v2 now has rarity breakdown (from cards table)
    # Note: rarity breakdown counts total quantity, not unique cards
    assert stats["rarity_breakdown"]["Common"] == 3  # 2 normal + 1 reverse
    assert stats["rarity_breakdown"]["Uncommon"] == 1
    assert stats["rarity_breakdown"]["Rare"] == 5


def test_parse_tcgdex_id(temp_db):
    """Test parsing TCGdex ID."""
    set_id, card_num = db.parse_tcgdex_id("me01-136")
    assert set_id == "me01"
    assert card_num == "136"

    with pytest.raises(ValueError):
        db.parse_tcgdex_id("invalid")


def test_remove_all_card_variants(temp_db):
    """Test removing all variants of a card (v2 API)."""
    # Setup card
    db.upsert_card("me01-136", "Bulbasaur", "me01", "136")
    db.upsert_card_name("me01-136", "de", "Bisasam")
    db.upsert_card_name("me01-136", "en", "Bulbasaur")

    # Add multiple variants
    db.add_owned_card("me01-136", "normal", "de", 2)
    db.add_owned_card("me01-136", "reverse", "de", 3)
    db.add_owned_card("me01-136", "holo", "de", 1)
    db.add_owned_card("me01-136", "normal", "en", 1)  # Different language

    # Remove all German variants
    removed = db.remove_all_card_variants("me01-136", "de")
    assert removed == 3  # Should remove 3 variants (normal, reverse, holo)

    # Check only English remains
    owned = db.get_v2_owned_cards()
    assert len(owned) == 1
    assert owned[0]["language"] == "en"
    assert owned[0]["variant"] == "normal"

    # Try removing non-existent card
    removed = db.remove_all_card_variants("me01-999", "de")
    assert removed == 0


def test_export_import_json(temp_db):
    """Test exporting and importing collection to/from JSON (v2 schema)."""
    import tempfile
    from pathlib import Path

    # Setup test data (v2 schema)
    # Add cards
    db.upsert_card("me01-136", "Bulbasaur", "me01", "136", rarity="Common")
    db.upsert_card("me01-137", "Ivysaur", "me01", "137", rarity="Uncommon")
    db.upsert_card("swsh3-045", "Pikachu", "swsh3", "045", rarity="Rare")

    # Add localized names
    db.upsert_card_name("me01-136", "de", "Bisasam")
    db.upsert_card_name("me01-136", "en", "Bulbasaur")
    db.upsert_card_name("me01-137", "de", "Bisaknosp")
    db.upsert_card_name("swsh3-045", "en", "Pikachu")

    # Add ownership
    db.add_owned_card("me01-136", "normal", "de", 2)
    db.add_owned_card("me01-136", "reverse", "de", 1)
    db.add_owned_card("swsh3-045", "holo", "en", 3)

    # Cache a set
    db.cache_sets(
        [
            SetInfo(
                set_id="me01",
                name="Mega-Entwicklung",
                card_count=132,
                release_date="2024-01-26",
                serie_id="me",
                serie_name="Mega Evolution",
                cached_at=datetime.now(),
            )
        ]
    )

    # Export to temporary file
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        export_path = Path(f.name)

    try:
        # Export
        result = db.export_to_json(export_path)
        assert result["cards_count"] == 3  # 3 cards in cards table
        assert result["card_names_count"] == 4  # 4 localized names
        assert result["owned_cards_count"] == 3  # 3 ownership records
        assert result["set_cache_count"] == 1
        assert result["version"] == "2.0"
        assert export_path.exists()

        # Add more data to verify it gets replaced
        db.upsert_card("sv06-001", "Charizard", "sv06", "001")
        db.add_owned_card("sv06-001", "normal", "fr", 5)

        # Import (should replace everything)
        result = db.import_from_json(export_path)
        assert result["cards_count"] == 3
        assert result["card_names_count"] == 4
        assert result["owned_cards_count"] == 3
        assert result["set_cache_count"] == 1
        assert result["version"] == "2.0"

        # Verify data matches original
        owned = db.get_v2_owned_cards()
        assert len(owned) == 3  # Back to original 3

        # Check specific card
        de_cards = db.get_v2_owned_cards(language="de")
        assert len(de_cards) == 2  # me01-136 normal and reverse

        # Verify French card was removed by import
        fr_cards = db.get_v2_owned_cards(language="fr")
        assert len(fr_cards) == 0

        # Verify card names were imported
        assert db.get_card_name("me01-136", "de") == "Bisasam"
        assert db.get_card_name("me01-136", "en") == "Bulbasaur"

    finally:
        # Cleanup
        export_path.unlink(missing_ok=True)
