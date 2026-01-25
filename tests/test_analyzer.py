"""Tests for collection analysis functions."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src import db, config, analyzer
from src.analyzer import AnalysisFilter, CardAnalysis


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


@pytest.fixture
def temp_data_dir(monkeypatch):
    """Create temporary data directory for raw JSON files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        raw_data_dir = data_dir / "raw_data" / "cards"
        raw_data_dir.mkdir(parents=True)

        # Mock the load_config function to return our temp config
        temp_config = config.Config(
            db_path=data_dir / "test.db",
            backups_path=data_dir / "backups",
            raw_data_path=data_dir / "raw_data",
        )
        monkeypatch.setattr(config, "load_config", lambda: temp_config)

        yield raw_data_dir


def create_mock_card_data(
    tcgdex_id: str,
    name: str = "Test Card",
    stage: str | None = "Basic",
    types: list[str] | None = None,
    hp: int | None = 60,
    rarity: str = "Common",
    category: str = "Pokemon",
    set_name: str = "Test Set",
) -> dict:
    """Create mock card data dictionary."""
    data = {
        "id": tcgdex_id,
        "name": name,
        "rarity": rarity,
        "category": category,
        "set": {"name": set_name, "id": tcgdex_id.split("-")[0]},
    }

    # Add optional fields only if not None
    if stage is not None:
        data["stage"] = stage
    if types is not None:
        data["types"] = types
    else:
        data["types"] = ["Fire"] if category == "Pokemon" else []
    if hp is not None:
        data["hp"] = hp

    return data


def test_analysis_filter_defaults():
    """Test AnalysisFilter with default values."""
    filter_obj = AnalysisFilter()

    assert filter_obj.stage is None
    assert filter_obj.type is None
    assert filter_obj.rarity is None
    assert filter_obj.hp_min is None
    assert filter_obj.hp_max is None
    assert filter_obj.category is None
    assert filter_obj.language is None
    assert filter_obj.set_id is None


def test_analysis_filter_with_values():
    """Test AnalysisFilter with custom values."""
    filter_obj = AnalysisFilter(
        stage="Stage1",
        type="Fire",
        rarity="Rare",
        hp_min=50,
        hp_max=100,
        category="Pokemon",
        language="de",
        set_id="me01",
    )

    assert filter_obj.stage == "Stage1"
    assert filter_obj.type == "Fire"
    assert filter_obj.rarity == "Rare"
    assert filter_obj.hp_min == 50
    assert filter_obj.hp_max == 100
    assert filter_obj.category == "Pokemon"
    assert filter_obj.language == "de"
    assert filter_obj.set_id == "me01"


def test_load_card_with_ownership_success(temp_db, temp_data_dir):
    """Test loading card with ownership info."""
    # Add card to database
    db.add_card_variant("me01-001", "normal", "de", 2)
    db.add_card_variant("me01-001", "reverse", "de", 1)

    # Create raw JSON file
    card_data = create_mock_card_data("me01-001", "Bulbasaur", "Basic", ["Grass"], 60)
    json_path = temp_data_dir / "me01-001.json"
    json_path.write_text(json.dumps(card_data))

    # Load card with ownership
    result = analyzer.load_card_with_ownership("me01-001", "de")

    assert result is not None
    card, raw_data = result
    assert card.tcgdex_id == "me01-001"
    assert card.name == "Bulbasaur"
    assert card.language == "de"
    assert card.stage == "Basic"
    assert card.types == ["Grass"]
    assert card.hp == 60
    assert card.quantity == 3  # 2 normal + 1 reverse
    assert set(card.variants) == {"normal", "reverse"}
    # Check raw_data is also returned
    assert raw_data is not None
    assert raw_data["name"] == "Bulbasaur"


def test_load_card_with_ownership_no_raw_json(temp_db, temp_data_dir):
    """Test loading card when raw JSON is missing."""
    # Add card to database
    db.add_card_variant("me01-001", "normal", "de", 1)

    # Don't create raw JSON file
    result = analyzer.load_card_with_ownership("me01-001", "de")

    assert result is None


def test_load_card_with_ownership_not_owned(temp_db, temp_data_dir):
    """Test loading card that is not in the collection."""
    # Create raw JSON file but don't add to database
    card_data = create_mock_card_data("me01-001", "Bulbasaur")
    json_path = temp_data_dir / "me01-001.json"
    json_path.write_text(json.dumps(card_data))

    result = analyzer.load_card_with_ownership("me01-001", "de")

    assert result is None


def test_load_card_with_ownership_null_types(temp_db, temp_data_dir):
    """Test loading card with null types (Trainer/Energy cards)."""
    # Add card to database
    db.add_card_variant("me01-100", "normal", "de", 1)

    # Create raw JSON file with null types
    card_data = create_mock_card_data(
        "me01-100", "Professor Oak", stage=None, types=[], category="Trainer"
    )
    json_path = temp_data_dir / "me01-100.json"
    json_path.write_text(json.dumps(card_data))

    result = analyzer.load_card_with_ownership("me01-100", "de")

    assert result is not None
    card, raw_data = result
    assert card.types == []
    assert card.stage is None
    assert card.category == "Trainer"


def test_analyze_collection_no_filters(temp_db, temp_data_dir):
    """Test analyze collection with no filters."""
    # Add multiple cards
    db.add_card_variant("me01-001", "normal", "de", 1)
    db.add_card_variant("me01-002", "normal", "de", 1)

    # Create raw JSON files
    for i, name in enumerate(["Bulbasaur", "Ivysaur"], 1):
        card_data = create_mock_card_data(f"me01-00{i}", name)
        json_path = temp_data_dir / f"me01-00{i}.json"
        json_path.write_text(json.dumps(card_data))

    # Analyze with no filters
    results = analyzer.analyze_collection(AnalysisFilter())

    assert len(results) == 2
    assert {c.name for c in results} == {"Bulbasaur", "Ivysaur"}


def test_analyze_collection_stage_filter(temp_db, temp_data_dir):
    """Test analyze collection with stage filter."""
    # Add cards
    db.add_card_variant("me01-001", "normal", "de", 1)
    db.add_card_variant("me01-002", "normal", "de", 1)

    # Create raw JSON files with different stages
    card1 = create_mock_card_data("me01-001", "Bulbasaur", stage="Basic")
    card2 = create_mock_card_data("me01-002", "Ivysaur", stage="Stage1")

    (temp_data_dir / "me01-001.json").write_text(json.dumps(card1))
    (temp_data_dir / "me01-002.json").write_text(json.dumps(card2))

    # Filter by Stage1
    results = analyzer.analyze_collection(AnalysisFilter(stage="Stage1"))

    assert len(results) == 1
    assert results[0].name == "Ivysaur"
    assert results[0].stage == "Stage1"


def test_analyze_collection_type_filter(temp_db, temp_data_dir):
    """Test analyze collection with type filter."""
    # Add cards
    db.add_card_variant("me01-001", "normal", "de", 1)
    db.add_card_variant("me01-002", "normal", "de", 1)

    # Create raw JSON files with different types
    card1 = create_mock_card_data("me01-001", "Charmander", types=["Fire"])
    card2 = create_mock_card_data("me01-002", "Squirtle", types=["Water"])

    (temp_data_dir / "me01-001.json").write_text(json.dumps(card1))
    (temp_data_dir / "me01-002.json").write_text(json.dumps(card2))

    # Filter by Fire type
    results = analyzer.analyze_collection(AnalysisFilter(type="Fire"))

    assert len(results) == 1
    assert results[0].name == "Charmander"
    assert results[0].types is not None and "Fire" in results[0].types


def test_analyze_collection_rarity_filter(temp_db, temp_data_dir):
    """Test analyze collection with rarity filter."""
    # Add cards
    db.add_card_variant("me01-001", "normal", "de", 1)
    db.add_card_variant("me01-002", "normal", "de", 1)

    # Create raw JSON files with different rarities
    card1 = create_mock_card_data("me01-001", "Common Card", rarity="Common")
    card2 = create_mock_card_data("me01-002", "Rare Card", rarity="Rare")

    (temp_data_dir / "me01-001.json").write_text(json.dumps(card1))
    (temp_data_dir / "me01-002.json").write_text(json.dumps(card2))

    # Filter by Rare
    results = analyzer.analyze_collection(AnalysisFilter(rarity="Rare"))

    assert len(results) == 1
    assert results[0].name == "Rare Card"
    assert results[0].rarity == "Rare"


def test_analyze_collection_hp_filter(temp_db, temp_data_dir):
    """Test analyze collection with HP filters."""
    # Add cards
    db.add_card_variant("me01-001", "normal", "de", 1)
    db.add_card_variant("me01-002", "normal", "de", 1)
    db.add_card_variant("me01-003", "normal", "de", 1)

    # Create raw JSON files with different HP values
    card1 = create_mock_card_data("me01-001", "Low HP", hp=50)
    card2 = create_mock_card_data("me01-002", "Mid HP", hp=100)
    card3 = create_mock_card_data("me01-003", "High HP", hp=150)

    (temp_data_dir / "me01-001.json").write_text(json.dumps(card1))
    (temp_data_dir / "me01-002.json").write_text(json.dumps(card2))
    (temp_data_dir / "me01-003.json").write_text(json.dumps(card3))

    # Filter by HP range
    results = analyzer.analyze_collection(AnalysisFilter(hp_min=80, hp_max=120))

    assert len(results) == 1
    assert results[0].name == "Mid HP"
    assert results[0].hp == 100


def test_analyze_collection_category_filter(temp_db, temp_data_dir):
    """Test analyze collection with category filter."""
    # Add cards
    db.add_card_variant("me01-001", "normal", "de", 1)
    db.add_card_variant("me01-100", "normal", "de", 1)

    # Create raw JSON files with different categories
    card1 = create_mock_card_data("me01-001", "Pikachu", category="Pokemon")
    card2 = create_mock_card_data(
        "me01-100", "Professor Oak", category="Trainer", stage=None, types=[]
    )

    (temp_data_dir / "me01-001.json").write_text(json.dumps(card1))
    (temp_data_dir / "me01-100.json").write_text(json.dumps(card2))

    # Filter by Trainer category
    results = analyzer.analyze_collection(AnalysisFilter(category="Trainer"))

    assert len(results) == 1
    assert results[0].name == "Professor Oak"
    assert results[0].category == "Trainer"


def test_analyze_collection_language_filter(temp_db, temp_data_dir):
    """Test analyze collection with language filter."""
    # Add cards in different languages
    db.add_card_variant("me01-001", "normal", "de", 1)
    db.add_card_variant("me01-001", "normal", "en", 1)

    # Create raw JSON file
    card_data = create_mock_card_data("me01-001", "Pikachu")
    (temp_data_dir / "me01-001.json").write_text(json.dumps(card_data))

    # Filter by German language
    results = analyzer.analyze_collection(AnalysisFilter(language="de"))

    assert len(results) == 1
    assert results[0].language == "de"


def test_analyze_collection_set_filter(temp_db, temp_data_dir):
    """Test analyze collection with set ID filter."""
    # Add cards from different sets
    db.add_card_variant("me01-001", "normal", "de", 1)
    db.add_card_variant("swsh1-001", "normal", "de", 1)

    # Create raw JSON files
    card1 = create_mock_card_data("me01-001", "Card 1")
    card2 = create_mock_card_data("swsh1-001", "Card 2")

    (temp_data_dir / "me01-001.json").write_text(json.dumps(card1))
    (temp_data_dir / "swsh1-001.json").write_text(json.dumps(card2))

    # Filter by set
    results = analyzer.analyze_collection(AnalysisFilter(set_id="me01"))

    assert len(results) == 1
    assert results[0].tcgdex_id == "me01-001"


def test_analyze_collection_multiple_filters(temp_db, temp_data_dir):
    """Test analyze collection with multiple filters combined."""
    # Add cards
    db.add_card_variant("me01-001", "normal", "de", 1)
    db.add_card_variant("me01-002", "normal", "de", 1)
    db.add_card_variant("me01-003", "normal", "de", 1)

    # Create raw JSON files
    card1 = create_mock_card_data(
        "me01-001", "Match", stage="Stage1", types=["Fire"], hp=90
    )
    card2 = create_mock_card_data(
        "me01-002", "No Match 1", stage="Basic", types=["Fire"], hp=90
    )
    card3 = create_mock_card_data(
        "me01-003", "No Match 2", stage="Stage1", types=["Water"], hp=90
    )

    (temp_data_dir / "me01-001.json").write_text(json.dumps(card1))
    (temp_data_dir / "me01-002.json").write_text(json.dumps(card2))
    (temp_data_dir / "me01-003.json").write_text(json.dumps(card3))

    # Filter by stage AND type
    results = analyzer.analyze_collection(AnalysisFilter(stage="Stage1", type="Fire"))

    assert len(results) == 1
    assert results[0].name == "Match"


def test_get_collection_statistics_empty():
    """Test statistics for empty collection."""
    stats = analyzer.get_collection_statistics([])

    assert stats["total_cards"] == 0
    assert stats["total_quantity"] == 0
    assert stats["by_stage"] == {}
    assert stats["by_type"] == {}
    assert stats["by_rarity"] == {}
    assert stats["by_category"] == {}
    assert stats["by_set"] == {}
    assert stats["avg_hp"] == 0


def test_get_collection_statistics_basic(temp_db, temp_data_dir):
    """Test statistics with basic collection."""
    # Add cards
    db.add_card_variant("me01-001", "normal", "de", 2)
    db.add_card_variant("me01-002", "normal", "de", 1)

    # Create raw JSON files
    card1 = create_mock_card_data(
        "me01-001", "Card 1", stage="Basic", types=["Fire"], hp=60
    )
    card2 = create_mock_card_data(
        "me01-002", "Card 2", stage="Stage1", types=["Water"], hp=80
    )

    (temp_data_dir / "me01-001.json").write_text(json.dumps(card1))
    (temp_data_dir / "me01-002.json").write_text(json.dumps(card2))

    # Get cards and statistics
    cards = analyzer.analyze_collection(AnalysisFilter())
    stats = analyzer.get_collection_statistics(cards)

    assert stats["total_cards"] == 2
    assert stats["total_quantity"] == 3  # 2 + 1
    assert stats["by_stage"] == {"Basic": 1, "Stage1": 1}
    assert stats["by_type"] == {"Fire": 1, "Water": 1}
    assert stats["avg_hp"] == 70.0  # (60 + 80) / 2


def test_get_collection_statistics_multi_type(temp_db, temp_data_dir):
    """Test statistics with multi-type cards."""
    # Add card
    db.add_card_variant("me01-001", "normal", "de", 1)

    # Create raw JSON file with multiple types
    card_data = create_mock_card_data("me01-001", "Dual Type", types=["Fire", "Dragon"])
    (temp_data_dir / "me01-001.json").write_text(json.dumps(card_data))

    # Get statistics
    cards = analyzer.analyze_collection(AnalysisFilter())
    stats = analyzer.get_collection_statistics(cards)

    # Both types should be counted
    assert stats["by_type"] == {"Fire": 1, "Dragon": 1}


def test_get_collection_statistics_null_hp(temp_db, temp_data_dir):
    """Test statistics with cards that have no HP (Trainers)."""
    # Add cards
    db.add_card_variant("me01-001", "normal", "de", 1)
    db.add_card_variant("me01-100", "normal", "de", 1)

    # Create raw JSON files
    card1 = create_mock_card_data("me01-001", "Pokemon", hp=60)
    card2 = create_mock_card_data(
        "me01-100", "Trainer", category="Trainer", hp=None, stage=None, types=[]
    )

    (temp_data_dir / "me01-001.json").write_text(json.dumps(card1))
    (temp_data_dir / "me01-100.json").write_text(json.dumps(card2))

    # Get statistics
    cards = analyzer.analyze_collection(AnalysisFilter())
    stats = analyzer.get_collection_statistics(cards)

    # Average HP should only include cards with HP
    assert stats["avg_hp"] == 60.0
    assert stats["by_category"] == {"Pokemon": 1, "Trainer": 1}


def test_get_collection_statistics_by_set(temp_db, temp_data_dir):
    """Test statistics grouped by set."""
    # Add cards from different sets
    db.add_card_variant("me01-001", "normal", "de", 1)
    db.add_card_variant("me01-002", "normal", "de", 1)
    db.add_card_variant("swsh1-001", "normal", "de", 1)

    # Create raw JSON files
    for tcgdex_id in ["me01-001", "me01-002", "swsh1-001"]:
        card_data = create_mock_card_data(tcgdex_id, f"Card {tcgdex_id}")
        (temp_data_dir / f"{tcgdex_id}.json").write_text(json.dumps(card_data))

    # Get statistics
    cards = analyzer.analyze_collection(AnalysisFilter())
    stats = analyzer.get_collection_statistics(cards)

    assert stats["by_set"] == {"me01": 2, "swsh1": 1}
