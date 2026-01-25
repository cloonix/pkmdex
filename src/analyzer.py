"""Collection analysis functions using raw JSON data."""

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


def load_card_with_ownership(tcgdex_id: str, language: str) -> Optional[CardAnalysis]:
    """Load card data from raw JSON and combine with ownership info.

    Args:
        tcgdex_id: Card ID (e.g., "me01-001")
        language: Language code

    Returns:
        CardAnalysis object or None if not found
    """
    # Load raw JSON data (English)
    raw_data = config.load_raw_card_data(tcgdex_id)
    if not raw_data:
        return None

    # Get ownership info from database
    owned_cards = db.get_owned_cards()
    card_variants = []
    total_quantity = 0

    for owned in owned_cards:
        if owned.tcgdex_id == tcgdex_id and owned.language == language:
            card_variants.append(owned.variant)
            total_quantity += owned.quantity

    if total_quantity == 0:
        return None

    # Extract data from raw JSON
    return CardAnalysis(
        tcgdex_id=tcgdex_id,
        name=raw_data.get("name", "Unknown"),  # English name
        language=language,
        set_name=raw_data.get("set", {}).get("name", "Unknown"),
        stage=raw_data.get("stage"),
        types=raw_data.get("types", []),
        hp=raw_data.get("hp"),
        rarity=raw_data.get("rarity"),
        category=raw_data.get("category", "Unknown"),
        quantity=total_quantity,
        variants=card_variants,
    )


def analyze_collection(filter_criteria: AnalysisFilter) -> list[CardAnalysis]:
    """Analyze collection based on filter criteria.

    Args:
        filter_criteria: AnalysisFilter with filter options

    Returns:
        List of CardAnalysis objects matching the filters
    """
    # Get all owned card IDs
    card_ids = db.get_owned_card_ids()

    results = []

    for tcgdex_id, language in card_ids:
        # Apply language filter
        if filter_criteria.language and language != filter_criteria.language:
            continue

        # Load card with ownership info
        card = load_card_with_ownership(tcgdex_id, language)
        if not card:
            continue

        # Load raw JSON for additional filtering
        raw_data = config.load_raw_card_data(tcgdex_id)
        if not raw_data:
            continue

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

        # Apply regulation mark filter
        if filter_criteria.regulation:
            regulation_mark = raw_data.get("regulationMark")
            if regulation_mark != filter_criteria.regulation:
                continue

        # Apply artist filter (case-insensitive partial match)
        if filter_criteria.artist:
            illustrator = raw_data.get("illustrator", "")
            if filter_criteria.artist.lower() not in illustrator.lower():
                continue

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

    stats = {
        "total_cards": len(cards),
        "total_quantity": sum(c.quantity for c in cards),
        "by_stage": {},
        "by_type": {},
        "by_rarity": {},
        "by_category": {},
        "by_set": {},
        "avg_hp": 0,
    }

    # Count by stage
    for card in cards:
        if card.stage:
            stats["by_stage"][card.stage] = stats["by_stage"].get(card.stage, 0) + 1

    # Count by type
    for card in cards:
        if card.types:
            for card_type in card.types:
                stats["by_type"][card_type] = stats["by_type"].get(card_type, 0) + 1

    # Count by rarity
    for card in cards:
        if card.rarity:
            stats["by_rarity"][card.rarity] = stats["by_rarity"].get(card.rarity, 0) + 1

    # Count by category
    for card in cards:
        stats["by_category"][card.category] = (
            stats["by_category"].get(card.category, 0) + 1
        )

    # Count by set
    for card in cards:
        set_id = card.tcgdex_id.split("-")[0]
        stats["by_set"][set_id] = stats["by_set"].get(set_id, 0) + 1

    # Calculate average HP
    hp_values = [c.hp for c in cards if c.hp is not None]
    if hp_values:
        stats["avg_hp"] = sum(hp_values) / len(hp_values)

    return stats
