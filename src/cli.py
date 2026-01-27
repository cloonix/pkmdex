"""Command-line interface for Pokemon card collection manager."""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from . import db, api, config, analyzer
from .models import (
    CardInfo,
    VALID_LANGUAGES,
    VALID_VARIANTS,
    validate_language,
    validate_variant,
)


def parse_card_input(card_str: str) -> tuple[str, str, str, str]:
    """Parse user input like 'de:me01:136:normal' or 'de:me01:136'.

    Args:
        card_str: Input string in format lang:set_id:card_number[:variant]

    Returns:
        Tuple of (language, set_id, card_number, variant)

    Raises:
        ValueError: If format is invalid
    """
    parts = card_str.split(":")

    # Support both 3 parts (lang:set:card) and 4 parts (lang:set:card:variant)
    if len(parts) == 3:
        language, set_id, card_number = parts
        variant = "normal"  # Default variant
    elif len(parts) == 4:
        language, set_id, card_number, variant = parts
    else:
        raise ValueError(
            f"Invalid format: {card_str}\n"
            f"Expected: <lang>:<set_id>:<card_number>[:<variant>]\n"
            f"Examples:\n"
            f"  de:me01:136:normal\n"
            f"  de:me01:136          (defaults to normal variant)\n"
            f"  en:swsh3:136:holo"
        )

    # Normalize inputs
    language = language.strip().lower()
    set_id = set_id.strip().lower()
    card_number = card_number.strip()
    variant = variant.strip().lower()

    # Validate language
    validate_language(language)

    # Validate variant
    validate_variant(variant)

    return language, set_id, card_number, variant


def parse_card_input_flexible(
    card_str: str, require_variant: bool = True
) -> tuple[str, str, str, str | None]:
    """Parse card input supporting both full format and legacy 2-part format.

    Args:
        card_str: Input string (lang:set:card[:variant] or set:card for legacy)
        require_variant: If True, return 'normal' as default variant. If False, return None.

    Returns:
        Tuple of (language, set_id, card_number, variant)
        variant will be None if require_variant=False and not provided

    Raises:
        ValueError: If format is invalid
    """
    parts = card_str.split(":")

    if len(parts) == 2:
        # Legacy format: set:card (assume German)
        set_id, card_number = parts
        language = "de"
        variant = "normal" if require_variant else None
    elif len(parts) == 3:
        # New format: lang:set:card (no variant)
        language, set_id, card_number = parts
        variant = "normal" if require_variant else None
    elif len(parts) == 4:
        # Full format: lang:set:card:variant
        language, set_id, card_number, variant = parts
    else:
        raise ValueError(
            f"Invalid format: {card_str}\n"
            f"Expected: <lang>:<set_id>:<card_number>[:<variant>] or <set_id>:<card_number>\n"
            f"Examples:\n"
            f"  de:me01:136\n"
            f"  me01:136 (uses German)"
        )

    # Normalize inputs
    language = language.strip().lower()
    set_id = set_id.strip().lower()
    card_number = card_number.strip()
    if variant:
        variant = variant.strip().lower()
        validate_variant(variant)

    validate_language(language)

    return language, set_id, card_number, variant


def get_display_name(tcgdex_id: str, language: str) -> str:
    """Get localized card name with English fallback.

    Args:
        tcgdex_id: Full TCGdex ID
        language: Preferred language code

    Returns:
        Localized card name, or English name if not available,
        or tcgdex_id if card not found
    """
    return db.get_display_name(tcgdex_id, language)


def get_current_quantity(tcgdex_id: str, variant: str, language: str) -> int:
    """Get current quantity of a specific card variant in collection.

    Args:
        tcgdex_id: Full TCGdex ID
        variant: Variant name (normal, reverse, holo, firstEdition)
        language: Language code

    Returns:
        Current quantity (0 if not owned)
    """
    return db.get_card_quantity(tcgdex_id, variant, language)


def extract_extra_fields(raw_response) -> tuple[Optional[str], Optional[str]]:
    """Extract stage and category from raw API response.

    Args:
        raw_response: Raw API response object from TCGdex SDK

    Returns:
        Tuple of (stage, category) - both may be None
    """
    return (
        getattr(raw_response, "stage", None),
        getattr(raw_response, "category", None),
    )


async def fetch_and_store_card_metadata(
    set_id: str, card_number: str, language: str
) -> tuple[CardInfo, str]:
    """Fetch card from API and store canonical metadata in database.

    This function:
    1. Fetches English (canonical) card data
    2. Extracts extra fields (stage, category) from raw API
    3. Stores canonical data in cards table
    4. Fetches and stores localized name if not English

    Args:
        set_id: TCGdex set ID
        card_number: Card number
        language: Desired language for localized name

    Returns:
        Tuple of (english_card_info, localized_name)

    Raises:
        api.PokedexAPIError: If card cannot be fetched
    """
    tcgdex_id = db.build_tcgdex_id(set_id, card_number)

    # Fetch English card data (canonical)
    api_en = api.get_api("en")
    card_info_en = await api_en.get_card(set_id, card_number)

    # Get raw API response to extract extra fields
    raw_response_en = await api_en.sdk.card.get(tcgdex_id)
    stage, category = extract_extra_fields(raw_response_en)

    # Store canonical English data in cards table
    db.upsert_card(
        tcgdex_id=card_info_en.tcgdex_id,
        name=card_info_en.name,
        set_id=set_id,
        card_number=card_number,
        rarity=card_info_en.rarity,
        types=json.dumps(card_info_en.types) if card_info_en.types else None,
        hp=card_info_en.hp,
        stage=stage,
        category=category,
        image_url=card_info_en.image_url,
        price_eur=None,  # TODO: Extract from pricing when available
        price_usd=None,
        legal_standard=None,  # TODO: Extract from legal when available
        legal_expanded=None,
    )

    # Fetch and store localized name
    localized_name = card_info_en.name  # Default to English
    if language != "en":
        api_lang = api.get_api(language)
        card_info_lang = await api_lang.get_card(set_id, card_number)
        localized_name = card_info_lang.name
        db.upsert_card_name(tcgdex_id, language, localized_name)
    else:
        # Store English name in card_names too for consistency
        db.upsert_card_name(tcgdex_id, "en", card_info_en.name)

    return card_info_en, localized_name


def validate_variant_or_prompt(
    card_info: CardInfo, variant: str, force: bool, localized_name: str, card_input: str
) -> bool:
    """Validate variant is available, or show error/warning.

    Args:
        card_info: English card information with variant data
        variant: Variant to validate
        force: Whether --force flag was used
        localized_name: Card name for display
        card_input: Original user input for help message

    Returns:
        True if should proceed, False if should abort
    """
    is_valid = card_info.available_variants.is_valid(variant)

    # Abort if invalid and not forced
    if not force and not is_valid:
        available = ", ".join(card_info.available_variants.available_list())
        print(
            f"Error: Variant '{variant}' not available for {localized_name} ({card_info.tcgdex_id})\n"
            f"Available variants: {available}\n"
            f"Tip: If you have this physical card, use --force to override:\n"
            f"     pkm add --force {card_input}",
            file=sys.stderr,
        )
        return False

    # Show warning if forcing an unlisted variant
    if force and not is_valid:
        print(
            f"⚠ Warning: Adding variant '{variant}' not listed in API for {localized_name}",
            file=sys.stderr,
        )

    return True


def display_add_result(
    localized_name: str,
    tcgdex_id: str,
    language: str,
    variant: str,
    old_qty: int,
    new_qty: int,
    image_url: Optional[str],
) -> None:
    """Display success message after adding a card.

    Args:
        localized_name: Card name in user's language
        tcgdex_id: Full TCGdex ID
        language: Language code
        variant: Variant name
        old_qty: Quantity before adding
        new_qty: Quantity after adding
        image_url: Card image URL (optional)
    """
    if new_qty == 1:
        print(f"✓ Added: {localized_name} ({tcgdex_id}) [{language}] - {variant}")
    else:
        print(
            f"✓ Updated: {localized_name} ({tcgdex_id}) [{language}] - {variant} (qty: {new_qty})"
        )

    # Show image URL
    if image_url:
        print(f"  Image: {image_url}")


async def fetch_card_info(language: str, set_id: str, card_number: str) -> CardInfo:
    """Fetch card from API or cache.

    Args:
        language: Language code (e.g., 'de', 'en')
        set_id: TCGdex set ID
        card_number: Card number

    Returns:
        CardInfo instance

    Raises:
        api.PokedexAPIError: If card cannot be fetched
    """
    tcgdex_id = f"{set_id}-{card_number}"

    # Fetch from API with specified language (no caching needed, raw JSON is saved)
    api_client = api.get_api(language)
    card_info = await api_client.get_card(set_id, card_number)

    return card_info


async def handle_add(args: argparse.Namespace) -> int:
    """Handle 'add' command (v2 schema).

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    try:
        language, set_id, card_number, variant = parse_card_input(args.card)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        # Fetch and store card metadata
        card_info_en, localized_name = await fetch_and_store_card_metadata(
            set_id, card_number, language
        )

        # Validate variant availability
        if not validate_variant_or_prompt(
            card_info_en, variant, args.force, localized_name, args.card
        ):
            return 1

        # Update ownership
        tcgdex_id = db.build_tcgdex_id(set_id, card_number)
        current_qty = get_current_quantity(tcgdex_id, variant, language)
        db.add_owned_card(tcgdex_id, variant, language, quantity=1)
        new_qty = current_qty + 1

        # Display result
        display_add_result(
            localized_name,
            tcgdex_id,
            language,
            variant,
            current_qty,
            new_qty,
            card_info_en.image_url,
        )

        return 0

    except api.PokedexAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


async def handle_rm(args: argparse.Namespace) -> int:
    """Handle 'rm' command (v2 schema).

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    # For --all flag, we only need lang:set:card (no variant)
    if args.all:
        try:
            language, set_id, card_number, _ = parse_card_input_flexible(
                args.card, require_variant=False
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        tcgdex_id = db.build_tcgdex_id(set_id, card_number)

        # Get card name for display
        card_name = get_display_name(tcgdex_id, language)

        # Remove all variants for this language
        # Get all owned variants for this card+language
        all_cards = db.get_v2_owned_cards()
        removed_count = 0
        for card in all_cards:
            if card["tcgdex_id"] == tcgdex_id and card["language"] == language:
                db.remove_owned_card(
                    tcgdex_id, card["variant"], language, card["quantity"]
                )
                removed_count += 1

        if removed_count > 0:
            print(
                f"✓ Removed all variants: {card_name} [{language}] ({removed_count} variant{'s' if removed_count != 1 else ''})"
            )
        else:
            print(
                f"Warning: {card_name} [{language}] not in collection",
                file=sys.stderr,
            )

        return 0

    # Normal single variant removal
    try:
        language, set_id, card_number, variant = parse_card_input(args.card)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    tcgdex_id = db.build_tcgdex_id(set_id, card_number)

    # Get card name for display
    card_name = get_display_name(tcgdex_id, language)

    # Remove the variant
    result = db.remove_owned_card(tcgdex_id, variant, language, quantity=1)

    if result is None:
        print(f"✓ Removed: {card_name} [{language}] - {variant}")
    elif result > 0:
        print(f"✓ Updated: {card_name} [{language}] - {variant} (qty: {result})")
    else:
        print(
            f"Warning: {card_name} [{language}] - {variant} not in collection",
            file=sys.stderr,
        )

    return 0


def handle_list(args: argparse.Namespace) -> int:
    """Handle 'list' command (v2 schema).

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    # Check if first argument is a language code or set_id
    filter_arg = args.set_id if hasattr(args, "set_id") and args.set_id else None

    set_filter = None
    language_filter = None

    if filter_arg:
        filter_arg = filter_arg.lower()
        # Check if it's a valid language code
        if filter_arg in VALID_LANGUAGES:
            language_filter = filter_arg
        else:
            set_filter = filter_arg

    # Query from v2 schema (includes JOIN with cards and card_names)
    owned_cards = db.get_v2_owned_cards(set_filter, language_filter)

    if not owned_cards:
        if set_filter:
            print(f"No cards found in set: {set_filter}")
        elif language_filter:
            print(f"No cards found for language: {language_filter}")
        else:
            print("Your collection is empty.")
            print("\nAdd cards with: pkm add lang:set_id:card_number[:variant]")
        return 0

    # Group cards by tcgdex_id AND language to show variants together
    cards_by_id_lang: dict[tuple[str, str], list] = {}
    for card in owned_cards:
        key = (card["tcgdex_id"], card["language"])
        if key not in cards_by_id_lang:
            cards_by_id_lang[key] = []
        cards_by_id_lang[key].append(card)

    # Print header
    print(
        f"{'Set':<8} {'Card#':<6} {'Lang':<5} {'Name':<25} {'Qty':<5} {'Rarity':<15} {'Variants'}"
    )
    print("─" * 90)

    total_unique = 0
    total_quantity = 0

    # Print each card
    for (tcgdex_id, language), card_variants in sorted(cards_by_id_lang.items()):
        # Data already loaded from DB query (no JSON file needed!)
        first_card = card_variants[0]
        name = first_card["display_name"]  # Localized name from card_names table
        rarity = first_card["rarity"] or ""

        # Build variants string with quantities
        variant_strs = []
        card_total_qty = 0
        for card in sorted(card_variants, key=lambda c: c["variant"]):
            variant_strs.append(f"{card['variant']}({card['quantity']})")
            card_total_qty += card["quantity"]
            total_quantity += card["quantity"]

        variants_display = ", ".join(variant_strs)

        # Truncate name if too long
        if len(name) > 24:
            name = name[:21] + "..."

        print(
            f"{first_card['set_id']:<8} {first_card['card_number']:<6} {language:<5} {name:<25} {card_total_qty:<5} {rarity:<15} {variants_display}"
        )
        total_unique += 1

    # Print summary
    print("─" * 90)
    print(f"Total: {total_unique} unique cards, {total_quantity} total cards")

    return 0


async def handle_sets(args: argparse.Namespace) -> int:
    """Handle 'sets' command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    search_term = args.search if hasattr(args, "search") and args.search else None

    # Check if cache is fresh (< 24 hours old)
    cache_age = db.get_set_cache_age()
    cache_fresh = cache_age and (datetime.now() - cache_age) < timedelta(hours=24)

    if not cache_fresh:
        # Fetch fresh data from API
        print("Fetching sets from TCGdex API...", file=sys.stderr)
        try:
            api_client = api.get_api()
            sets = await api_client.get_all_sets()
            db.cache_sets(sets)
            print(f"Cached {len(sets)} sets", file=sys.stderr)
        except api.PokedexAPIError as e:
            print(f"Error: {e}", file=sys.stderr)
            # Try to use stale cache
            sets = db.get_cached_sets(search_term)
            if not sets:
                return 1
            print("Using cached data (may be outdated)", file=sys.stderr)
    else:
        # Use cache
        sets = db.get_cached_sets(search_term)

    if not sets:
        if search_term:
            print(f"No sets found matching: {search_term}")
        else:
            print("No sets available")
        return 0

    # Print header
    print(f"{'Set ID':<12} {'Name':<35} {'Cards':<8} {'Released':<12}")
    print("─" * 70)

    # Print each set
    for set_info in sets:
        release_date = set_info.release_date if set_info.release_date else "-"
        name = set_info.name
        if len(name) > 34:
            name = name[:31] + "..."

        print(
            f"{set_info.set_id:<12} {name:<35} {set_info.card_count:<8} {release_date:<12}"
        )

    print("─" * 70)
    print(f"Total: {len(sets)} sets")

    return 0


async def handle_info(args: argparse.Namespace) -> int:
    """Handle 'info' command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    try:
        # Parse lang:set_id:card_number (no variant needed for info)
        language, set_id, card_number, _ = parse_card_input_flexible(
            args.card, require_variant=False
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    tcgdex_id = db.build_tcgdex_id(set_id, card_number)

    # Show raw JSON if requested
    if args.raw:
        try:
            # Fetch fresh raw data from API (v2: no JSON file caching)
            api_client = api.get_api(language)
            raw_data = await api_client.get_card_raw(set_id, card_number)

            import json

            print(json.dumps(raw_data, indent=2, ensure_ascii=False))
            return 0
        except api.PokedexAPIError as e:
            print(f"Error fetching card: {e}", file=sys.stderr)
            return 1

    try:
        # Fetch card info
        card_info = await fetch_card_info(language, set_id, card_number)

        # Display card information
        print(f"Card: {card_info.name} (#{card_number})")
        if card_info.set_name:
            print(f"Set:  {card_info.set_name} ({set_id})")

        if card_info.types:
            print(f"Type: {', '.join(card_info.types)}")

        if card_info.hp:
            print(f"HP:   {card_info.hp}")

        if card_info.rarity:
            print(f"Rarity: {card_info.rarity}")

        # Show available variants
        print("\nAvailable Variants:")
        for variant in sorted(VALID_VARIANTS):
            available = card_info.available_variants.is_valid(variant)
            symbol = "✓" if available else "✗"
            print(f"  {symbol} {variant}")

        # Show owned variants (v2 schema)
        owned = db.get_v2_owned_cards()
        owned_variants = [c for c in owned if c["tcgdex_id"] == card_info.tcgdex_id]

        if owned_variants:
            print("\nIn Collection:")
            for card in owned_variants:
                print(f"  • {card['variant']}: {card['quantity']}")
        else:
            print("\nNot in collection")

        # Show image URL
        if card_info.image_url:
            print(f"\nImage: {card_info.image_url}")

        # Show hint about raw data
        print(
            f"\nTip: Use 'pkm info {language}:{set_id}:{card_number} --raw' to see complete API data"
        )

        return 0

    except api.PokedexAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_stats(args: argparse.Namespace) -> int:
    """Handle 'stats' command (v2 schema).

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    stats = db.get_v2_collection_stats()

    if stats["unique_cards"] == 0:
        print("Your collection is empty.")
        return 0

    print("Collection Statistics")
    print("─" * 40)
    print(f"Total unique cards:     {stats['unique_cards']}")
    print(f"Total cards (all):      {stats['total_cards']}")
    print(f"Sets represented:       {stats['sets_count']}")

    if stats["most_collected_set"]:
        print(
            f"Most collected set:     {stats['most_collected_set']} ({stats['most_collected_qty']} cards)"
        )

    # NEW: Collection value
    if stats["total_value_eur"] > 0:
        print(f"\nCollection Value")
        print(f"Total value:            €{stats['total_value_eur']:.2f}")
        print(f"Average per card:       €{stats['avg_card_value_eur']:.2f}")
        if stats["most_valuable_card"]:
            mvc = stats["most_valuable_card"]
            print(f"Most valuable:          {mvc['name']} (€{mvc['price_eur']:.2f})")

    # Variant breakdown
    if stats["variant_breakdown"]:
        print("\nVariants breakdown:")
        for variant, qty in sorted(stats["variant_breakdown"].items()):
            print(f"  {variant.capitalize():<20} {qty}")

    # Rarity breakdown
    if stats["rarity_breakdown"]:
        print("\nRarity breakdown:")
        for rarity, qty in sorted(
            stats["rarity_breakdown"].items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  {rarity:<20} {qty}")

    return 0


async def handle_sync(args: argparse.Namespace) -> int:
    """Handle 'sync' command - refresh card data from API.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    # Determine which cards to sync
    if hasattr(args, "stale") and args.stale:
        # Sync cards older than N days
        cards_to_sync = db.get_stale_cards(days=args.stale)
        if not cards_to_sync:
            print(f"✓ All cards synced within last {args.stale} days")
            return 0
        print(f"Found {len(cards_to_sync)} cards older than {args.stale} days")
    else:
        # Sync all owned cards
        cards_to_sync = db.get_owned_tcgdex_ids()
        if not cards_to_sync:
            print("No cards in collection to sync")
            return 0
        print(f"Syncing {len(cards_to_sync)} cards from collection...")

    price_changes = []
    synced_count = 0
    errors = []

    for tcgdex_id in cards_to_sync:
        try:
            set_id, card_number = db.parse_tcgdex_id(tcgdex_id)

            # Get old price for comparison
            old_card = db.get_card(tcgdex_id)
            old_price = old_card.get("price_eur") if old_card else None

            # Fetch fresh English data
            api_en = api.get_api("en")
            card_info_en = await api_en.get_card(set_id, card_number)

            # Get raw response for extra fields
            raw_response = await api_en.sdk.card.get(tcgdex_id)
            stage = (
                getattr(raw_response, "stage", None)
                if hasattr(raw_response, "stage")
                else None
            )
            category = (
                getattr(raw_response, "category", None)
                if hasattr(raw_response, "category")
                else None
            )

            # TODO: Extract price from raw_response
            # For now, keep old price or set to None
            new_price = old_price  # Placeholder

            # Update cards table
            db.upsert_card(
                tcgdex_id=tcgdex_id,
                name=card_info_en.name,
                set_id=set_id,
                card_number=card_number,
                rarity=card_info_en.rarity,
                types=json.dumps(card_info_en.types) if card_info_en.types else None,
                hp=card_info_en.hp,
                stage=stage,
                category=category,
                image_url=card_info_en.image_url,
                price_eur=new_price,
                price_usd=None,
                legal_standard=None,
                legal_expanded=None,
            )

            # Track price changes
            if old_price and new_price and abs(old_price - new_price) > 0.10:
                direction = "↑" if new_price > old_price else "↓"
                change_pct = ((new_price - old_price) / old_price) * 100
                price_changes.append(
                    f"  {direction} {card_info_en.name}: €{old_price:.2f} → €{new_price:.2f} ({change_pct:+.1f}%)"
                )

            # Update localized names for all languages owned
            languages = db.get_languages_for_card(tcgdex_id)
            for lang in languages:
                if lang == "en":
                    db.upsert_card_name(tcgdex_id, "en", card_info_en.name)
                else:
                    try:
                        api_lang = api.get_api(lang)
                        card_info_lang = await api_lang.get_card(set_id, card_number)
                        db.upsert_card_name(tcgdex_id, lang, card_info_lang.name)
                    except api.PokedexAPIError:
                        # Language not available, skip
                        pass

            synced_count += 1

            # Show progress every 50 cards
            if synced_count % 50 == 0:
                print(
                    f"  Synced {synced_count}/{len(cards_to_sync)}...", file=sys.stderr
                )

        except api.PokedexAPIError as e:
            errors.append(f"  Error syncing {tcgdex_id}: {e}")
        except Exception as e:
            errors.append(f"  Unexpected error for {tcgdex_id}: {e}")

    # Print summary
    print(f"\n✓ Synced {synced_count} cards")

    if hasattr(args, "show_changes") and args.show_changes and price_changes:
        print("\nPrice changes:")
        for change in price_changes:
            print(change)

    if errors:
        print(f"\n⚠ {len(errors)} errors occurred:", file=sys.stderr)
        for error in errors[:10]:  # Show first 10 errors
            print(error, file=sys.stderr)
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more", file=sys.stderr)

    return 0


def handle_setup(args: argparse.Namespace) -> int:
    """Handle 'setup' command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    # Show current configuration
    if args.show:
        current_config = config.load_config()
        print("Current configuration:")
        print(f"  Config file:    {config.get_config_file_path()}")
        print(f"  Database path:  {current_config.db_path}")
        print(f"  Backups path:   {current_config.backups_path}")
        print(f"  API base URL:   {current_config.api_base_url or '(default)'}")

        # Show effective API URL (considering env var)
        effective_url = config.get_api_base_url()
        if effective_url != current_config.api_base_url:
            print(f"  Effective URL:  {effective_url} (from TCGDEX_API_URL env var)")

        # Check if using defaults
        default_config = config.Config.default()
        if current_config.db_path == default_config.db_path:
            print("\n(Using default configuration)")

        return 0

    # Reset to defaults
    if args.reset:
        default_config = config.reset_config()
        print("✓ Configuration reset to defaults")
        print(f"  Database path:  {default_config.db_path}")
        print(f"  Backups path:   {default_config.backups_path}")
        print(f"  API base URL:   (default)")
        return 0

    # Set custom API URL
    if args.api_url:
        current_config = config.load_config()
        current_config.api_base_url = (
            args.api_url if args.api_url != "default" else None
        )
        config.save_config(current_config)

        if args.api_url == "default":
            print("✓ API URL reset to default")
        else:
            print("✓ Custom API URL configured")
            print(f"  API base URL:   {args.api_url}")
        print("\nNote: Restart any running instances to use the new API.")
        return 0

    # Set custom database path
    if args.path:
        try:
            new_config = config.setup_database_path(args.path)
            print("✓ Configuration updated")
            print(f"  Database path:  {new_config.db_path}")
            print(f"  Backups path:   {new_config.backups_path}")
            print(f"\nNote: Restart any running instances to use the new path.")
            return 0
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # No arguments - show help
    print("Usage: pkm setup [--show | --reset | --path PATH | --api-url URL]")
    print("\nOptions:")
    print("  --show           Show current configuration")
    print("  --reset          Reset to default configuration")
    print("  --path PATH      Set custom database directory or file path")
    print("  --api-url URL    Set custom TCGdex API base URL (use 'default' to reset)")
    print("\nExamples:")
    print("  pkm setup --show")
    print("  pkm setup --path ~/Documents/pokemon")
    print("  pkm setup --path /mnt/backup/pokemon/cards.db")
    print("  pkm setup --api-url https://homer.tail150adf.ts.net:3443")
    print("  pkm setup --api-url default  # Reset to default API")
    print("  pkm setup --reset")
    return 0


def handle_export(args: argparse.Namespace) -> int:
    """Handle 'export' command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    # Generate filename with timestamp if not provided
    if args.output:
        output_path = Path(args.output)
    else:
        # Use backups directory from config
        cfg = config.load_config()
        cfg.backups_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = cfg.backups_path / f"pkmdex_export_{timestamp}.json"

    try:
        result = db.export_to_json(output_path)
        print(f"✓ Exported collection to: {result['file_path']}")
        print(f"  Cards: {result['cards_count']}")
        print(f"  Set cache: {result['set_cache_count']}")
        return 0
    except Exception as e:
        print(f"Error exporting collection: {e}", file=sys.stderr)
        return 1


def handle_import(args: argparse.Namespace) -> int:
    """Handle 'import' command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    input_path = Path(args.file)

    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        return 1

    # Warn user about replacement
    print(f"⚠ WARNING: This will REPLACE your current collection with data from:")
    print(f"  {input_path}")

    if not args.yes:
        response = input("Continue? (yes/no): ").strip().lower()
        if response not in ("yes", "y"):
            print("Import cancelled.")
            return 0

    try:
        result = db.import_from_json(input_path)
        print(f"✓ Imported collection from: {input_path}")
        print(f"  Cards: {result['cards_count']}")
        print(f"  Set cache: {result['set_cache_count']}")
        if result.get("exported_at"):
            print(f"  Original export date: {result['exported_at']}")

        # Show sync hint for v1 imports
        if result.get("needs_sync"):
            print(
                f"\n⚠ Imported v1 backup: ownership data restored, but card metadata is missing."
            )
            print(f"  Run 'pkm sync' to fetch card details from the API.")
            print(f"  ({result.get('cards_to_sync', 0)} unique cards to sync)")

        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error importing collection: {e}", file=sys.stderr)
        return 1


async def handle_cache(args: argparse.Namespace) -> int:
    """Handle 'cache' command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    # Show cache statistics
    if args.show or (not args.refresh and not args.clear and not args.update):
        stats = db.get_cache_stats()

        print("Cache Statistics")
        print("─" * 60)

        # Set cache
        print("\nSet Cache:")
        print(f"  Entries: {stats['set_cache_count']}")
        if stats["set_cache_oldest"]:
            print(
                f"  Oldest:  {stats['set_cache_oldest'].strftime('%Y-%m-%d %H:%M:%S')}"
            )
        if stats["set_cache_newest"]:
            print(
                f"  Newest:  {stats['set_cache_newest'].strftime('%Y-%m-%d %H:%M:%S')}"
            )

        # Show refresh hint
        if stats["set_cache_count"] > 0 and stats["set_cache_oldest"]:
            age = datetime.now() - stats["set_cache_oldest"]
            if age > timedelta(days=7):
                print(
                    f"\n💡 Tip: Set cache is {age.days} days old. Run 'pkm cache --refresh' to update."
                )

        return 0

    # Update cache for owned cards
    if args.update:
        print("Updating cache for all owned cards...")

        # Get all unique card IDs from owned cards
        card_ids = db.get_owned_card_ids()

        if not card_ids:
            print("No owned cards found in collection.")
            return 0

        print(f"Found {len(card_ids)} unique cards to update")

        updated_count = 0
        error_count = 0

        # Update each card
        for tcgdex_id, language in card_ids:
            try:
                # Parse the tcgdex_id to get set_id and card_number
                set_id, card_number = db.parse_tcgdex_id(tcgdex_id)

                # Fetch card from API with the correct language
                api_client = api.get_api(language)
                card_info = await api_client.get_card(set_id, card_number)

                # Card is already saved as raw JSON by API layer
                updated_count += 1
                print(f"  ✓ Updated: {tcgdex_id} ({language})")

            except Exception as e:
                error_count += 1
                print(f"  ✗ Failed: {tcgdex_id} ({language}) - {e}", file=sys.stderr)

        print(
            f"\n✓ Cache update complete: {updated_count} updated, {error_count} errors"
        )
        return 0

    # Refresh caches
    if args.refresh:
        print("Refreshing cache from TCGdex API...")

        # Refresh set cache
        try:
            api_client = api.get_api()
            sets = await api_client.get_all_sets()
            db.cache_sets(sets)
            print(f"✓ Refreshed set cache: {len(sets)} sets")
        except api.PokedexAPIError as e:
            print(f"Error refreshing set cache: {e}", file=sys.stderr)
            return 1

        print("\n✓ Cache refresh complete")
        return 0

    # Clear caches
    if args.clear:
        if args.type in ("cards", "all"):
            print("ℹ Card cache no longer exists (using raw JSON files)")

        if args.type in ("sets", "all"):
            count = db.clear_set_cache()
            print(f"✓ Cleared set cache: {count} entries")

        return 0

    return 0


def handle_analyze(args: argparse.Namespace) -> int:
    """Handle 'analyze' command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Build filter criteria
    filter_criteria = analyzer.AnalysisFilter(
        stage=args.stage,
        type=args.type,
        rarity=args.rarity,
        hp_min=args.hp_min,
        hp_max=args.hp_max,
        category=args.category,
        language=args.language,
        set_id=args.set,
        regulation=args.regulation,
        artist=args.artist,
        name=args.name,
    )

    # Analyze collection
    results = analyzer.analyze_collection(filter_criteria)

    if not results:
        print("No cards found matching the filter criteria.")
        print("\n💡 Tip: Make sure you have raw JSON data for your cards.")
        print("   Run 'pkm cache --update' to fetch English data for analysis.")
        return 0

    # Show statistics
    if args.stats:
        stats = analyzer.get_collection_statistics(results)

        print(f"Collection Analysis ({len(results)} cards)")
        print("─" * 60)

        print(f"\nTotal Cards:    {stats['total_cards']}")
        print(f"Total Quantity: {stats['total_quantity']}")

        if stats["avg_hp"] > 0:
            print(f"Average HP:     {stats['avg_hp']:.0f}")

        if stats["by_stage"]:
            print("\nBy Stage:")
            for stage, count in sorted(stats["by_stage"].items()):
                print(f"  {stage:15} {count:3}")

        if stats["by_type"]:
            print("\nBy Type:")
            for card_type, count in sorted(stats["by_type"].items()):
                print(f"  {card_type:15} {count:3}")

        if stats["by_rarity"]:
            print("\nBy Rarity:")
            for rarity, count in sorted(stats["by_rarity"].items()):
                print(f"  {rarity:15} {count:3}")

        if stats["by_category"]:
            print("\nBy Category:")
            for category, count in sorted(stats["by_category"].items()):
                print(f"  {category:15} {count:3}")

        if stats["by_set"]:
            print("\nBy Set:")
            for set_id, count in sorted(stats["by_set"].items()):
                print(f"  {set_id:15} {count:3}")

        return 0

    # Show card list as table
    print(f"Collection Analysis ({len(results)} cards)")
    print("─" * 133)
    print(
        f"{'ID':<12} {'Name (Localized)':<45} {'Lang':<6} {'Stage':<10} {'Type':<12} {'HP':<4} {'Rarity':<18} {'Qty':<3}"
    )
    print("─" * 133)

    for card in results:
        stage_str = card.stage or "—"
        type_str = ", ".join(card.types[:2]) if card.types else "—"
        hp_str = str(card.hp) if card.hp else "—"
        rarity_str = card.rarity or "—"

        # Show both English and localized name if different
        if card.name != card.localized_name:
            name_display = f"{card.name} ({card.localized_name})"
        else:
            name_display = card.name

        # Truncate name if too long
        if len(name_display) > 44:
            name_display = name_display[:41] + "..."

        print(
            f"{card.tcgdex_id:<12} {name_display:<45} {card.language:<6} {stage_str:<10} {type_str:<12} {hp_str:<4} {rarity_str:<18} {card.quantity:<3}"
        )

    print("─" * 133)
    print(f"Total: {len(results)} cards")

    return 0


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="pkm",
        description="Manage your Pokemon TCG card collection (supports multiple languages)",
        epilog="Examples: pkm add de:me01:136  or  pkm add de:me01:136:holo  or  pkm cache --refresh",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a card to collection")
    add_parser.add_argument(
        "card",
        help="Card in format: lang:set_id:card_number[:variant] (variant defaults to normal)",
    )
    add_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force add variant even if not listed in API (use when you have a physical card not in database)",
    )

    # Remove command
    rm_parser = subparsers.add_parser("rm", help="Remove a card from collection")
    rm_parser.add_argument(
        "card",
        help="Card in format: lang:set_id:card_number[:variant] or just lang:set_id:card_number with --all",
    )
    rm_parser.add_argument(
        "--all",
        action="store_true",
        help="Remove all variants of the card (no variant needed in card spec)",
    )

    # List command
    list_parser = subparsers.add_parser("list", help="Display collection")
    list_parser.add_argument(
        "set_id",
        nargs="?",
        help="Optional: filter by language code (de, en, etc.) or set ID",
    )

    # Sets command
    sets_parser = subparsers.add_parser("sets", help="Search and list available sets")
    sets_parser.add_argument(
        "search", nargs="?", help="Optional: search term for set names"
    )

    # Info command
    info_parser = subparsers.add_parser("info", help="Get card information")
    info_parser.add_argument(
        "card",
        help="Card in format: lang:set_id:card_number or set_id:card_number (uses German)",
    )
    info_parser.add_argument(
        "--raw",
        action="store_true",
        help="Show complete raw JSON data from API",
    )

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show collection statistics")

    # Sync command
    sync_parser = subparsers.add_parser(
        "sync", help="Refresh card data from API (prices, legality)"
    )
    sync_parser.add_argument(
        "--stale",
        type=int,
        metavar="DAYS",
        help="Only sync cards older than N days (default: sync all)",
    )
    sync_parser.add_argument(
        "--show-changes",
        action="store_true",
        help="Show price changes after sync",
    )

    # Setup command
    setup_parser = subparsers.add_parser(
        "setup", help="Configure database path and settings"
    )
    setup_parser.add_argument(
        "--show", action="store_true", help="Show current configuration"
    )
    setup_parser.add_argument(
        "--reset", action="store_true", help="Reset to default configuration"
    )
    setup_parser.add_argument(
        "--path", help="Set custom database directory or file path"
    )
    setup_parser.add_argument("--api-url", help="Set custom TCGdex API base URL")

    # Export command
    export_parser = subparsers.add_parser(
        "export", help="Export collection to JSON file"
    )
    export_parser.add_argument(
        "-o",
        "--output",
        help="Output file path (default: pkmdex_export_YYYYMMDD_HHMMSS.json)",
    )

    # Import command
    import_parser = subparsers.add_parser(
        "import", help="Import collection from JSON file (replaces current collection)"
    )
    import_parser.add_argument("file", help="JSON file to import")
    import_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip confirmation prompt"
    )

    # Cache command
    cache_parser = subparsers.add_parser("cache", help="Manage API cache")
    cache_parser.add_argument(
        "--show", action="store_true", help="Show cache statistics (default)"
    )
    cache_parser.add_argument(
        "--refresh", action="store_true", help="Refresh set cache from API"
    )
    cache_parser.add_argument(
        "--update", action="store_true", help="Update cache for all owned cards"
    )
    cache_parser.add_argument(
        "--clear", action="store_true", help="Clear cache entries"
    )
    cache_parser.add_argument(
        "--type",
        choices=["cards", "sets", "all"],
        default="all",
        help="Which cache to clear (default: all)",
    )

    # Analyze command
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze collection using raw JSON data"
    )
    analyze_parser.add_argument(
        "--stage", help="Filter by evolution stage (e.g., Basic, Stage1, Stage2)"
    )
    analyze_parser.add_argument(
        "--type", help="Filter by Pokemon type (e.g., Fire, Water, Grass)"
    )
    analyze_parser.add_argument(
        "--rarity", help="Filter by rarity (e.g., Common, Rare)"
    )
    analyze_parser.add_argument("--hp-min", type=int, help="Minimum HP")
    analyze_parser.add_argument("--hp-max", type=int, help="Maximum HP")
    analyze_parser.add_argument(
        "--category", help="Filter by category (e.g., Pokemon, Trainer)"
    )
    analyze_parser.add_argument(
        "--language", help="Filter by language code (e.g., de, en)"
    )
    analyze_parser.add_argument("--set", help="Filter by set ID (e.g., me01)")
    analyze_parser.add_argument(
        "--regulation",
        help="Filter by regulation mark (e.g., A, B, C, D, E, F, G, H, I)",
    )
    analyze_parser.add_argument(
        "--artist",
        help="Filter by artist/illustrator name (partial match, case-insensitive)",
    )
    analyze_parser.add_argument(
        "--name",
        help="Filter by card name (partial match, case-insensitive, searches both English and localized names)",
    )
    analyze_parser.add_argument(
        "--stats", action="store_true", help="Show statistics instead of card list"
    )

    return parser


def main() -> None:
    """Main entry point for CLI."""
    # Parse arguments first
    parser = create_parser()
    args = parser.parse_args()

    # Initialize database
    db.init_database()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Route to command handler
    exit_code = 0

    if args.command == "add":
        exit_code = asyncio.run(handle_add(args))
    elif args.command == "rm":
        exit_code = asyncio.run(handle_rm(args))
    elif args.command == "list":
        exit_code = handle_list(args)
    elif args.command == "sets":
        exit_code = asyncio.run(handle_sets(args))
    elif args.command == "info":
        exit_code = asyncio.run(handle_info(args))
    elif args.command == "stats":
        exit_code = handle_stats(args)
    elif args.command == "sync":
        exit_code = asyncio.run(handle_sync(args))
    elif args.command == "setup":
        exit_code = handle_setup(args)
    elif args.command == "export":
        exit_code = handle_export(args)
    elif args.command == "import":
        exit_code = handle_import(args)
    elif args.command == "cache":
        exit_code = asyncio.run(handle_cache(args))
    elif args.command == "analyze":
        exit_code = handle_analyze(args)
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
