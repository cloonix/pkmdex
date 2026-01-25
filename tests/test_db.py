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

        assert "cards" in tables
        assert "card_cache" in tables
        assert "set_cache" in tables


def test_add_card_variant_new(temp_db):
    """Test adding a new card variant."""
    result = db.add_card_variant("me01-136", "normal", "de", 1)

    assert result.tcgdex_id == "me01-136"
    assert result.set_id == "me01"
    assert result.card_number == "136"
    assert result.variant == "normal"
    assert result.language == "de"
    assert result.quantity == 1


def test_add_card_variant_accumulate(temp_db):
    """Test adding to existing card accumulates quantity."""
    db.add_card_variant("me01-136", "normal", "de", 1)
    result = db.add_card_variant("me01-136", "normal", "de", 2)

    assert result.quantity == 3


def test_add_multiple_variants(temp_db):
    """Test adding different variants of same card."""
    db.add_card_variant("me01-136", "normal", "de", 1)
    db.add_card_variant("me01-136", "reverse", "de", 1)

    owned = db.get_owned_cards()
    assert len(owned) == 2

    variants = {c.variant for c in owned}
    assert variants == {"normal", "reverse"}


def test_remove_card_variant(temp_db):
    """Test removing card variant."""
    db.add_card_variant("me01-136", "normal", "de", 3)

    result = db.remove_card_variant("me01-136", "normal", "de", 1)
    assert result is not None
    assert result.quantity == 2

    result = db.remove_card_variant("me01-136", "normal", "de", 2)
    assert result is None  # Should be deleted

    owned = db.get_owned_cards()
    assert len(owned) == 0


def test_remove_nonexistent_card(temp_db):
    """Test removing card that doesn't exist."""
    result = db.remove_card_variant("me01-999", "normal", "de")
    assert result is None


def test_get_owned_cards_filter(temp_db):
    """Test filtering owned cards by set and language."""
    db.add_card_variant("me01-136", "normal", "de", 1)
    db.add_card_variant("me01-137", "normal", "de", 1)
    db.add_card_variant("sv06-045", "holo", "en", 1)

    all_cards = db.get_owned_cards()
    assert len(all_cards) == 3

    me01_cards = db.get_owned_cards(set_id="me01")
    assert len(me01_cards) == 2

    sv06_cards = db.get_owned_cards(set_id="sv06")
    assert len(sv06_cards) == 1

    # Test language filtering
    de_cards = db.get_owned_cards(language="de")
    assert len(de_cards) == 2

    en_cards = db.get_owned_cards(language="en")
    assert len(en_cards) == 1


def test_cache_and_get_card(temp_db):
    """Test caching and retrieving card info."""
    card_info = CardInfo(
        tcgdex_id="me01-136",
        name="Furret",
        set_name="Mega-Entwicklung",
        rarity="Uncommon",
        types=["Colorless"],
        hp=110,
        available_variants=CardVariants(normal=True, reverse=True),
        image_url="https://example.com/image.png",
        cached_at=datetime.now(),
    )

    db.cache_card(card_info)

    cached = db.get_cached_card("me01-136")
    assert cached is not None
    assert cached.name == "Furret"
    assert cached.hp == 110
    assert cached.available_variants.normal is True
    assert cached.available_variants.reverse is True


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
    """Test collection statistics."""
    # Add some cards
    db.add_card_variant("me01-136", "normal", "de", 2)
    db.add_card_variant("me01-136", "reverse", "de", 1)
    db.add_card_variant("me01-137", "normal", "de", 1)
    db.add_card_variant("sv06-045", "holo", "en", 5)  # sv06 has more total

    # Cache some card info for rarity stats
    db.cache_card(
        CardInfo(
            tcgdex_id="me01-136",
            name="Furret",
            set_name="Mega-Entwicklung",
            rarity="Uncommon",
            types=[],
            hp=None,
            available_variants=CardVariants(),
            image_url=None,
            cached_at=datetime.now(),
        )
    )

    stats = db.get_collection_stats()

    assert stats["unique_cards"] == 3
    assert stats["total_cards"] == 9
    assert stats["sets_count"] == 2
    assert stats["most_collected_set"] == "sv06"
    assert stats["variant_breakdown"]["normal"] == 3
    assert stats["variant_breakdown"]["holo"] == 5


def test_parse_tcgdex_id(temp_db):
    """Test parsing TCGdex ID."""
    set_id, card_num = db.parse_tcgdex_id("me01-136")
    assert set_id == "me01"
    assert card_num == "136"

    with pytest.raises(ValueError):
        db.parse_tcgdex_id("invalid")


def test_remove_all_card_variants(temp_db):
    """Test removing all variants of a card."""
    # Add multiple variants
    db.add_card_variant("me01-136", "normal", "de", 2)
    db.add_card_variant("me01-136", "reverse", "de", 3)
    db.add_card_variant("me01-136", "holo", "de", 1)
    db.add_card_variant("me01-136", "normal", "en", 1)  # Different language

    # Remove all German variants
    removed = db.remove_all_card_variants("me01-136", "de")
    assert removed == 3  # Should remove 3 variants (normal, reverse, holo)

    # Check only English remains
    owned = db.get_owned_cards()
    assert len(owned) == 1
    assert owned[0].language == "en"
    assert owned[0].variant == "normal"

    # Try removing non-existent card
    removed = db.remove_all_card_variants("me01-999", "de")
    assert removed == 0
