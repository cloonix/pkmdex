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
    """Wrapper around TCGdex SDK for German Pokemon cards."""

    def __init__(self, language: str = "de"):
        """Initialize TCGdex API client.

        Args:
            language: Language code (default: "de" for German)
        """
        self.sdk = TCGdex(language)
        self.language = language

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

            # Save raw data for current language
            if is_dataclass(card_data):
                raw_dict = asdict(card_data)

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
                config.save_raw_card_data(tcgdex_id, raw_dict, self.language)

            # Also fetch and save English raw data for analysis (if not already English)
            if self.language != "en":
                try:
                    en_api = get_api("en")
                    en_card_data = await en_api.sdk.card.get(tcgdex_id)

                    if is_dataclass(en_card_data):
                        en_raw_dict = asdict(en_card_data)

                        # Remove non-serializable SDK reference
                        def remove_sdk_en(obj):
                            if isinstance(obj, dict):
                                obj.pop("sdk", None)
                                for v in obj.values():
                                    remove_sdk_en(v)
                            elif isinstance(obj, list):
                                for item in obj:
                                    remove_sdk_en(item)

                        remove_sdk_en(en_raw_dict)
                        config.save_raw_card_data(tcgdex_id, en_raw_dict, "en")
                except:
                    pass  # If English fetch/save fails, continue anyway

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
            CardInfo instance with card metadata

        Raises:
            PokedexAPIError: If card is not found or API request fails
        """
        try:
            card_data = await self.sdk.card.get(tcgdex_id)

            # Save raw data for current language
            if is_dataclass(card_data):
                raw_dict = asdict(card_data)

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
                config.save_raw_card_data(tcgdex_id, raw_dict, self.language)

            # Also fetch and save English raw data for analysis (if not already English)
            if self.language != "en":
                try:
                    en_api = get_api("en")
                    en_card_data = await en_api.sdk.card.get(tcgdex_id)

                    if is_dataclass(en_card_data):
                        en_raw_dict = asdict(en_card_data)

                        # Remove non-serializable SDK reference
                        def remove_sdk_en(obj):
                            if isinstance(obj, dict):
                                obj.pop("sdk", None)
                                for v in obj.values():
                                    remove_sdk_en(v)
                            elif isinstance(obj, list):
                                for item in obj:
                                    remove_sdk_en(item)

                        remove_sdk_en(en_raw_dict)
                        config.save_raw_card_data(tcgdex_id, en_raw_dict, "en")
                except:
                    pass  # If English fetch/save fails, continue anyway

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
            Raw card data dictionary

        Raises:
            PokedexAPIError: If card is not found or API request fails
        """
        try:
            # Use different API client if language specified
            if language and language != self.language:
                api = get_api(language)
                return await api.get_card_raw(set_id, card_number, language)

            tcgdex_id = f"{set_id}-{card_number}"
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
