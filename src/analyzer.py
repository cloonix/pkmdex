"""Collection analysis functions using v2 schema."""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from . import config, db


@dataclass
class AnalysisFilter:
    """Filter criteria for collection analysis."""

    stage: Optional[str] = None
    type: Optional[str] = None
    rarity: Optional[str] = None
    hp_min: Optional[int] = None
    hp_max: Optional[int] = None
    category: Optional[str] = None
    language: Optional[str] = None
    set_id: Optional[str] = None
    regulation: Optional[str] = None
    artist: Optional[str] = None


@dataclass
class CardAnalysis:
    """Analysis result for a single card."""

    tcgdex_id: str
    name: str  # English name from raw JSON
    language: str
    set_name: str
    stage: Optional[str]
    types: Optional[list[str]]
    hp: Optional[int]
    rarity: Optional[str]
    category: str
    quantity: int
    variants: list[str]


def load_card_with_ownership(
    tcgdex_id: str, language: str
) -> Optional[tuple[CardAnalysis, dict]]:
    """Load card data from database (v2 schema) and combine with ownership info.

    Args:
        tcgdex_id: Card ID (e.g., "me01-001")
        language: Language code

    Returns:
        Tuple of (CardAnalysis, card_data_dict) or None if not found
        Returning card_data avoids duplicate queries in analyze_collection
    """
    # Get card data from database (English canonical data)
    card_data = db.get_card(tcgdex_id)
    if not card_data:
        return None

    # Get owned cards for this tcgdex_id + language
    owned_cards = db.get_v2_owned_cards(language=language)
    matching_cards = [c for c in owned_cards if c["tcgdex_id"] == tcgdex_id]

    if not matching_cards:
        return None

    # Calculate total quantity and get variants
    total_quantity = sum(c["quantity"] for c in matching_cards)
    card_variants = [c["variant"] for c in matching_cards]

    # Parse types from JSON string
    types = json.loads(card_data["types"]) if card_data.get("types") else []

    # Get localized name (for display)
    localized_name = db.get_card_name(tcgdex_id, language) or card_data["name"]

    # Build CardAnalysis from database data
    card = CardAnalysis(
        tcgdex_id=tcgdex_id,
        name=card_data["name"],  # English name for filtering
        language=language,
        set_name=matching_cards[0].get("set_name", "Unknown"),
        stage=card_data.get("stage"),
        types=types,
        hp=card_data.get("hp"),
        rarity=card_data.get("rarity"),
        category=card_data.get("category", "Unknown"),
        quantity=total_quantity,
        variants=card_variants,
    )

    return (card, card_data)


def analyze_collection(filter_criteria: AnalysisFilter) -> list[CardAnalysis]:
    """Analyze collection based on filter criteria (v2 schema).

    Args:
        filter_criteria: AnalysisFilter with filter options

    Returns:
        List of CardAnalysis objects matching the filters
    """
    # Get all owned cards with JOIN (v2 schema)
    owned_cards = db.get_v2_owned_cards(
        set_id=filter_criteria.set_id, language=filter_criteria.language
    )

    results = []
    processed_keys = set()  # Track (tcgdex_id, language) to avoid duplicates

    for card_dict in owned_cards:
        tcgdex_id = card_dict["tcgdex_id"]
        language = card_dict["language"]

        # Skip if already processed (multiple variants)
        key = (tcgdex_id, language)
        if key in processed_keys:
            continue
        processed_keys.add(key)

        # Parse types from JSON string
        types = json.loads(card_dict["types"]) if card_dict.get("types") else []

        # Get all variants for this card+language combo
        matching = [
            c
            for c in owned_cards
            if c["tcgdex_id"] == tcgdex_id and c["language"] == language
        ]
        total_quantity = sum(c["quantity"] for c in matching)
        card_variants = [c["variant"] for c in matching]

        # Build CardAnalysis from database row
        card = CardAnalysis(
            tcgdex_id=tcgdex_id,
            name=card_dict["name_en"],  # English name for filtering
            language=language,
            set_name=card_dict.get("set_name", "Unknown"),
            stage=card_dict.get("stage"),
            types=types,
            hp=card_dict.get("hp"),
            rarity=card_dict.get("rarity"),
            category=card_dict.get("category", "Unknown"),
            quantity=total_quantity,
            variants=card_variants,
        )

        # Store as dict for filter checks
        card_data = card_dict

        # Apply set_id filter
        if filter_criteria.set_id:
            set_id = tcgdex_id.split("-")[0]
            if set_id != filter_criteria.set_id:
                continue

        # Apply stage filter
        if filter_criteria.stage and card.stage != filter_criteria.stage:
            continue

        # Apply type filter
        if filter_criteria.type and (
            not card.types or filter_criteria.type not in card.types
        ):
            continue

        # Apply rarity filter
        if filter_criteria.rarity and card.rarity != filter_criteria.rarity:
            continue

        # Apply HP filters
        if filter_criteria.hp_min and (
            card.hp is None or card.hp < filter_criteria.hp_min
        ):
            continue

        if filter_criteria.hp_max and (
            card.hp is None or card.hp > filter_criteria.hp_max
        ):
            continue

        # Apply category filter
        if filter_criteria.category and card.category != filter_criteria.category:
            continue

        # NOTE: regulation and artist filters removed in v2 schema
        # These fields are not stored in the cards table
        # TODO: Add regulation_mark and illustrator columns if needed

        results.append(card)

    return results


def get_collection_statistics(cards: list[CardAnalysis]) -> dict:
    """Generate statistics from analyzed cards.

    Args:
        cards: List of CardAnalysis objects

    Returns:
        Dictionary with statistics
    """
    if not cards:
        return {
            "total_cards": 0,
            "total_quantity": 0,
            "by_stage": {},
            "by_type": {},
            "by_rarity": {},
            "by_category": {},
            "by_set": {},
            "avg_hp": 0,
        }

    # Initialize stats
    stats = {
        "total_cards": len(cards),
        "total_quantity": 0,
        "by_stage": {},
        "by_type": {},
        "by_rarity": {},
        "by_category": {},
        "by_set": {},
        "avg_hp": 0,
    }

    hp_values = []

    # Single loop to collect all statistics
    for card in cards:
        # Total quantity
        stats["total_quantity"] += card.quantity

        # Count by stage
        if card.stage:
            stats["by_stage"][card.stage] = stats["by_stage"].get(card.stage, 0) + 1

        # Count by type
        if card.types:
            for card_type in card.types:
                stats["by_type"][card_type] = stats["by_type"].get(card_type, 0) + 1

        # Count by rarity
        if card.rarity:
            stats["by_rarity"][card.rarity] = stats["by_rarity"].get(card.rarity, 0) + 1

        # Count by category
        stats["by_category"][card.category] = (
            stats["by_category"].get(card.category, 0) + 1
        )

        # Count by set
        set_id = card.tcgdex_id.split("-")[0]
        stats["by_set"][set_id] = stats["by_set"].get(set_id, 0) + 1

        # Collect HP values
        if card.hp is not None:
            hp_values.append(card.hp)

    # Calculate average HP
    if hp_values:
        stats["avg_hp"] = sum(hp_values) / len(hp_values)

    return stats
