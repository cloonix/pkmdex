"""Mapping between TCGdex set IDs and official PTCG set codes.

TCGdex uses its own set ID system (e.g., 'me01', 'me02'), but the official
Pokemon TCG game (PTCG Live, PTCGO) uses different abbreviations.

This module provides the mapping using the SQLite database.
"""

from typing import Optional

from . import db


def get_ptcg_set_code(tcgdex_set_id: str) -> str:
    """Get official PTCG set code from TCGdex set ID.

    Args:
        tcgdex_set_id: TCGdex set identifier (e.g., "me01")

    Returns:
        Official PTCG set code (e.g., "ME1")
        Falls back to uppercase TCGdex ID if mapping not found
    """
    # Check database first
    code = db.get_ptcg_set_code(tcgdex_set_id)

    if code:
        return code

    # Fallback to uppercase TCGdex ID
    return tcgdex_set_id.upper()


def add_set_code_mapping(
    tcgdex_id: str,
    ptcg_code: str,
    set_name_en: Optional[str] = None,
    set_name_de: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    """Add a new set code mapping to database.

    Args:
        tcgdex_id: TCGdex set identifier
        ptcg_code: Official PTCG set code
        set_name_en: Optional English set name
        set_name_de: Optional German set name
        notes: Optional notes
    """
    db.add_set_code_mapping(tcgdex_id, ptcg_code, set_name_en, set_name_de, notes)
