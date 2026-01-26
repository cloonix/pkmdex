"""Data models for Pokemon card collection."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# Supported TCGdex languages
VALID_LANGUAGES = frozenset(
    [
        "de",  # German
        "en",  # English
        "fr",  # French
        "es",  # Spanish
        "it",  # Italian
        "pt",  # Portuguese
        "ja",  # Japanese
        "ko",  # Korean
        "zh-tw",  # Traditional Chinese
        "th",  # Thai
        "id",  # Indonesian
    ]
)


# Valid card variant types
VALID_VARIANTS = frozenset(["normal", "reverse", "holo", "firstEdition"])


def validate_language(language: str) -> None:
    """Validate language code.

    Args:
        language: ISO 639-1 language code to validate

    Raises:
        ValueError: If language is not supported
    """
    if language not in VALID_LANGUAGES:
        raise ValueError(
            f"Invalid language: {language}\n"
            f"Valid languages: {', '.join(sorted(VALID_LANGUAGES))}\n"
            f"Note: Use 'de' for German (default)"
        )


def validate_variant(variant: str) -> None:
    """Validate card variant type.

    Args:
        variant: Variant name to validate

    Raises:
        ValueError: If variant is not valid
    """
    if variant not in VALID_VARIANTS:
        raise ValueError(
            f"Invalid variant: {variant}\n"
            f"Valid variants: {', '.join(sorted(VALID_VARIANTS))}"
        )


@dataclass
class CardVariants:
    """Available variants for a card from TCGdex API."""

    normal: bool = False
    reverse: bool = False
    holo: bool = False
    firstEdition: bool = False

    @classmethod
    def from_api_response(cls, data: dict) -> "CardVariants":
        """Parse variants from TCGdex API response.

        Args:
            data: Variants object from API response

        Returns:
            CardVariants instance
        """
        return cls(
            normal=data.get("normal", False),
            reverse=data.get("reverse", False),
            holo=data.get("holo", False),
            firstEdition=data.get("firstEdition", False),
        )

    def is_valid(self, variant: str) -> bool:
        """Check if a variant is available for this card.

        Args:
            variant: Variant name to check

        Returns:
            True if variant is available, False otherwise
        """
        return getattr(self, variant, False)

    def available_list(self) -> list[str]:
        """Get list of available variant names.

        Returns:
            List of variant names where the variant is available (sorted)
        """
        return sorted([v for v in VALID_VARIANTS if getattr(self, v)])

    def to_json(self) -> dict:
        """Convert to JSON-serializable dict.

        Returns:
            Dict with variant availability
        """
        return {
            "normal": self.normal,
            "reverse": self.reverse,
            "holo": self.holo,
            "firstEdition": self.firstEdition,
        }


@dataclass
class OwnedCard:
    """Card variant in user's collection."""

    id: Optional[int]
    set_id: str
    card_number: str
    tcgdex_id: str
    variant: str  # 'normal', 'reverse', 'holo', 'firstEdition'
    language: str  # 'de', 'en', 'fr', etc.
    quantity: int
    added_at: datetime
    updated_at: datetime

    @classmethod
    def from_db_row(cls, row: tuple) -> "OwnedCard":
        """Create from database row.

        Args:
            row: Database row tuple

        Returns:
            OwnedCard instance
        """
        return cls(
            id=row[0],
            set_id=row[1],
            card_number=row[2],
            tcgdex_id=row[3],
            variant=row[4],
            language=row[5],
            quantity=row[6],
            added_at=datetime.fromisoformat(row[7]),
            updated_at=datetime.fromisoformat(row[8]),
        )


@dataclass
class CardInfo:
    """Cached card metadata from TCGdex API."""

    tcgdex_id: str
    name: str
    set_name: Optional[str]
    rarity: Optional[str]
    types: list[str]
    hp: Optional[int]
    available_variants: CardVariants
    image_url: Optional[str]
    cached_at: datetime

    @classmethod
    def from_api_response(cls, data) -> "CardInfo":
        """Create from TCGdex API response.

        Args:
            data: Card data from API (dict or dataclass)

        Returns:
            CardInfo instance
        """
        # Handle both dict and dataclass responses
        if isinstance(data, dict):
            tcgdex_id = data["id"]
            name = data["name"]
            set_name = data.get("set", {}).get("name")
            rarity = data.get("rarity")
            types = data.get("types", [])
            hp = data.get("hp")
            variants_data = data.get("variants", {})
            image_url = data.get("image")
        else:
            # Dataclass from SDK
            tcgdex_id = data.id
            name = data.name
            set_name = data.set.name if hasattr(data, "set") and data.set else None
            rarity = getattr(data, "rarity", None)
            types = getattr(data, "types", [])
            hp = getattr(data, "hp", None)
            variants_data = getattr(data, "variants", None)
            image_url = getattr(data, "image", None)

        # Convert variants
        if isinstance(variants_data, dict):
            variants = CardVariants.from_api_response(variants_data)
        elif variants_data is not None:
            # Dataclass variants
            variants = CardVariants(
                normal=getattr(variants_data, "normal", False),
                reverse=getattr(variants_data, "reverse", False),
                holo=getattr(variants_data, "holo", False),
                firstEdition=getattr(variants_data, "firstEdition", False),
            )
        else:
            variants = CardVariants()

        # Add quality and format to image URL
        # TCGdex returns base URL like: https://assets.tcgdex.net/en/swsh/swsh3/136
        # We need to add: /high.png for high quality PNG
        if image_url and not image_url.endswith((".png", ".jpg", ".webp")):
            image_url = f"{image_url}/high.png"

        return cls(
            tcgdex_id=tcgdex_id,
            name=name,
            set_name=set_name,
            rarity=rarity,
            types=types if types else [],
            hp=hp,
            available_variants=variants,
            image_url=image_url,
            cached_at=datetime.now(),
        )

    @classmethod
    def from_db_row(cls, row: tuple) -> "CardInfo":
        """Create from database row.

        Args:
            row: Database row tuple

        Returns:
            CardInfo instance
        """
        import json

        return cls(
            tcgdex_id=row[0],
            name=row[1],
            set_name=row[2],
            rarity=row[3],
            types=json.loads(row[4]) if row[4] else [],
            hp=row[5],
            available_variants=CardVariants(**json.loads(row[6])),
            image_url=row[7],
            cached_at=datetime.fromisoformat(row[8]),
        )


@dataclass
class SetInfo:
    """Cached set information from TCGdex API."""

    set_id: str
    name: str
    card_count: int
    release_date: Optional[str]
    serie_id: Optional[str]
    serie_name: Optional[str]
    cached_at: datetime

    @classmethod
    def from_api_response(cls, data) -> "SetInfo":
        """Create from TCGdex API response.

        Args:
            data: Set data from API (dict or dataclass)

        Returns:
            SetInfo instance
        """
        # Handle both dict and dataclass responses
        if isinstance(data, dict):
            set_id = data["id"]
            name = data["name"]
            card_count = data.get("cardCount", {}).get("total", 0)
            release_date = data.get("releaseDate")
            serie_id = data.get("serie", {}).get("id") if "serie" in data else None
            serie_name = data.get("serie", {}).get("name") if "serie" in data else None
        else:
            # Dataclass from SDK
            set_id = data.id
            name = data.name
            card_count = data.cardCount.total if data.cardCount else 0
            release_date = getattr(data, "releaseDate", None)
            serie_id = (
                getattr(data.serie, "id", None)
                if hasattr(data, "serie") and data.serie
                else None
            )
            serie_name = (
                getattr(data.serie, "name", None)
                if hasattr(data, "serie") and data.serie
                else None
            )

        return cls(
            set_id=set_id,
            name=name,
            card_count=card_count,
            release_date=release_date,
            serie_id=serie_id,
            serie_name=serie_name,
            cached_at=datetime.now(),
        )

    @classmethod
    def from_db_row(cls, row: tuple) -> "SetInfo":
        """Create from database row.

        Args:
            row: Database row tuple

        Returns:
            SetInfo instance
        """
        return cls(
            set_id=row[0],
            name=row[1],
            card_count=row[2],
            release_date=row[3],
            serie_id=row[4],
            serie_name=row[5],
            cached_at=datetime.fromisoformat(row[6]),
        )
