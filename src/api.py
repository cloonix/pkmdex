"""TCGdex API wrapper for German Pokemon cards."""

from typing import Optional
from tcgdexsdk import TCGdex
from dataclasses import asdict, is_dataclass

from .models import CardInfo, SetInfo
from . import config


class PokedexAPIError(Exception):
    """Exception raised for API-related errors."""

    pass


class TCGdexAPI:
    """Wrapper around TCGdex SDK with German language support."""

    def __init__(self, language: str = "de"):
        """Initialize API client.

        Args:
            language: Language code for API responses (default: German)
        """
        self.language = language
        self.sdk = TCGdex(language)

    async def _fetch_english_rarity(self, tcgdex_id: str, card_data) -> None:
        """Fetch and replace rarity from English API for non-English cards.

        Modifies card_data in place by replacing rarity with English version.
        This ensures rarity values are consistent across languages.

        Args:
            tcgdex_id: Full TCGdex card ID
            card_data: Card data object (dict or dataclass) to modify
        """
        if self.language == "en":
            return  # Already English, no need to fetch

        try:
            en_api = get_api("en")
            en_card_data = await en_api.sdk.card.get(tcgdex_id)

            # Replace rarity with English version
            if isinstance(card_data, dict):
                card_data["rarity"] = (
                    getattr(en_card_data, "rarity", None)
                    if hasattr(en_card_data, "rarity")
                    else en_card_data.get("rarity")
                )
            else:
                # Card data is a dataclass
                card_data.rarity = getattr(en_card_data, "rarity", None)
        except (PokedexAPIError, AttributeError, KeyError) as e:
            # If English fetch fails, use translated rarity (silently)
            # Can fail if: API error, card not found, or rarity attribute missing
            pass
        self.language = language

        # Set custom base URL if configured
        base_url = config.get_api_base_url()
        if base_url:
            self.sdk.setEndpoint(base_url)

    async def get_card(self, set_id: str, card_number: str) -> CardInfo:
        """Fetch card information from API.

        Args:
            set_id: TCGdex set ID (e.g., "me01")
            card_number: Card number in set (e.g., "136")

        Returns:
            CardInfo instance with card metadata

        Raises:
            PokedexAPIError: If card is not found or API request fails
        """
        try:
            # Fetch card by full ID
            tcgdex_id = f"{set_id}-{card_number}"
            card_data = await self.sdk.card.get(tcgdex_id)

            # v2: No JSON file saving - all data goes to database via CLI layer

            # Fetch rarity from English API if not using English
            if self.language != "en":
                try:
                    en_api = get_api("en")
                    en_card_data = await en_api.sdk.card.get(tcgdex_id)
                    # Replace rarity with English version
                    if isinstance(card_data, dict):
                        card_data["rarity"] = (
                            getattr(en_card_data, "rarity", None)
                            if hasattr(en_card_data, "rarity")
                            else en_card_data.get("rarity")
                        )
                    else:
                        # Card data is a dataclass
                        card_data.rarity = getattr(en_card_data, "rarity", None)
                except:
                    # If English fetch fails, use translated rarity
                    pass

            return CardInfo.from_api_response(card_data)
        except Exception as e:
            raise PokedexAPIError(
                f"Set not found: {set_id}\nTry 'pkm sets' to browse available sets."
            ) from e

    async def get_card_by_id(self, tcgdex_id: str) -> CardInfo:
        """Fetch card by full TCGdex ID.

        Args:
            tcgdex_id: Full TCGdex card ID (e.g., "me01-136")

        Returns:
            CardInfo instance with card details

        Raises:
            PokedexAPIError: If card cannot be fetched
        """
        try:
            card_data = await self.sdk.card.get(tcgdex_id)

            # v2: No JSON file saving - all data goes to database via CLI layer

            # Fetch rarity from English API if not using English
            await self._fetch_english_rarity(tcgdex_id, card_data)

            return CardInfo.from_api_response(card_data)
        except Exception as e:
            raise PokedexAPIError(
                f"Card not found: {tcgdex_id}\nTry 'pkm sets' to browse available sets."
            ) from e

    async def get_card_raw(
        self, set_id: str, card_number: str, language: Optional[str] = None
    ) -> dict:
        """Fetch raw card data as dictionary.

        Args:
            set_id: TCGdex set ID (e.g., "me01")
            card_number: Card number in set (e.g., "136")
            language: Optional language override (defaults to API language)

        Returns:
            Dict with raw API response data

        Raises:
            PokedexAPIError: If card cannot be fetched
        """
        from .db import build_tcgdex_id

        try:
            tcgdex_id = build_tcgdex_id(set_id, card_number)
            card_data = await self.sdk.card.get(tcgdex_id)

            # Convert to dict
            if is_dataclass(card_data):
                raw_dict = asdict(card_data)
            else:
                raw_dict = dict(card_data)

            # Remove non-serializable SDK reference
            def remove_sdk(obj):
                if isinstance(obj, dict):
                    obj.pop("sdk", None)
                    for v in obj.values():
                        remove_sdk(v)
                elif isinstance(obj, list):
                    for item in obj:
                        remove_sdk(item)

            remove_sdk(raw_dict)
            return raw_dict

        except Exception as e:
            raise PokedexAPIError(
                f"Card not found: {set_id}-{card_number} (language: {language or self.language})"
            ) from e

    async def get_all_sets(self) -> list[SetInfo]:
        """Fetch all available sets from API.

        Returns:
            List of SetInfo instances

        Raises:
            PokedexAPIError: If API request fails
        """
        try:
            sets_data = await self.sdk.set.list()
            return [SetInfo.from_api_response(s) for s in sets_data]
        except Exception as e:
            raise PokedexAPIError(
                f"Failed to fetch sets from API: {e}\n"
                f"Please check your internet connection."
            ) from e

    async def get_set(self, set_id: str) -> SetInfo:
        """Fetch information about a specific set.

        Args:
            set_id: TCGdex set ID (e.g., "me01")

        Returns:
            SetInfo instance

        Raises:
            PokedexAPIError: If set is not found or API request fails
        """
        try:
            set_data = await self.sdk.set.get(set_id)
            return SetInfo.from_api_response(set_data)
        except Exception as e:
            raise PokedexAPIError(
                f"Set not found: {set_id}\nTry 'poke sets' to browse available sets."
            ) from e


# Global API instances (lazy-initialized per language)
_api_instances: dict[str, TCGdexAPI] = {}


def get_api(language: str = "de") -> TCGdexAPI:
    """Get or create API instance for specified language.

    Args:
        language: Language code (default: "de")

    Returns:
        TCGdexAPI instance for the specified language
    """
    global _api_instances
    if language not in _api_instances:
        _api_instances[language] = TCGdexAPI(language=language)
    return _api_instances[language]
