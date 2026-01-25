"""Command-line interface for Pokemon card collection manager."""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from typing import Optional

from . import db, api
from .models import CardInfo


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
    valid_languages = {
        "de",
        "en",
        "fr",
        "es",
        "it",
        "pt",
        "ja",
        "ko",
        "zh-tw",
        "th",
        "id",
    }
    if language not in valid_languages:
        raise ValueError(
            f"Invalid language: {language}\n"
            f"Valid languages: {', '.join(sorted(valid_languages))}\n"
            f"Note: Use 'de' for German (default)"
        )

    # Validate variant
    valid_variants = {"normal", "reverse", "holo", "firstEdition"}
    if variant not in valid_variants:
        raise ValueError(
            f"Invalid variant: {variant}\n"
            f"Valid variants: {', '.join(sorted(valid_variants))}"
        )

    return language, set_id, card_number, variant


async def fetch_and_cache_card(
    language: str, set_id: str, card_number: str
) -> CardInfo:
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

    # Check cache first
    cached = db.get_cached_card(tcgdex_id)
    if cached:
        return cached

    # Fetch from API with specified language
    api_client = api.get_api(language)
    card_info = await api_client.get_card(set_id, card_number)

    # Cache it
    db.cache_card(card_info)

    return card_info


async def handle_add(args: argparse.Namespace) -> int:
    """Handle 'add' command.

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
        # Fetch card info with specified language
        card_info = await fetch_and_cache_card(language, set_id, card_number)

        # Validate variant is available
        if not card_info.available_variants.is_valid(variant):
            available = ", ".join(card_info.available_variants.available_list())
            print(
                f"Error: Variant '{variant}' not available for {card_info.name} ({card_info.tcgdex_id})\n"
                f"Available variants: {available}",
                file=sys.stderr,
            )
            return 1

        # Add to collection
        owned_card = db.add_card_variant(card_info.tcgdex_id, variant, language)

        if owned_card.quantity == 1:
            print(
                f"✓ Added: {card_info.name} ({card_info.tcgdex_id}) [{language}] - {variant}"
            )
        else:
            print(
                f"✓ Updated: {card_info.name} ({card_info.tcgdex_id}) [{language}] - {variant} (qty: {owned_card.quantity})"
            )

        # Show image URL
        if card_info.image_url:
            print(f"  Image: {card_info.image_url}")

        return 0

    except api.PokedexAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


async def handle_rm(args: argparse.Namespace) -> int:
    """Handle 'rm' command.

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

    tcgdex_id = f"{set_id}-{card_number}"

    # Try to get card name from cache for better output
    card_info = db.get_cached_card(tcgdex_id)
    card_name = card_info.name if card_info else tcgdex_id

    # Remove the variant
    result = db.remove_card_variant(tcgdex_id, variant, language)

    if result is None:
        print(f"✓ Removed: {card_name} [{language}] - {variant}")
    elif result:
        print(
            f"✓ Updated: {card_name} [{language}] - {variant} (qty: {result.quantity})"
        )
    else:
        print(
            f"Warning: {card_name} [{language}] - {variant} not in collection",
            file=sys.stderr,
        )

    return 0


def handle_list(args: argparse.Namespace) -> int:
    """Handle 'list' command.

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
        valid_languages = {
            "de",
            "en",
            "fr",
            "es",
            "it",
            "pt",
            "ja",
            "ko",
            "zh-tw",
            "th",
            "id",
        }
        if filter_arg in valid_languages:
            language_filter = filter_arg
        else:
            set_filter = filter_arg

    owned_cards = db.get_owned_cards(set_filter, language_filter)

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
        key = (card.tcgdex_id, card.language)
        if key not in cards_by_id_lang:
            cards_by_id_lang[key] = []
        cards_by_id_lang[key].append(card)

    # Print header
    print(
        f"{'Set':<8} {'Card#':<6} {'Lang':<5} {'Name':<23} {'Variants':<18} {'Qty':<8} {'Rarity':<12}"
    )
    print("─" * 90)

    total_unique = 0
    total_quantity = 0

    # Print each card
    for (tcgdex_id, language), card_variants in sorted(cards_by_id_lang.items()):
        # Get card info from cache
        card_info = db.get_cached_card(tcgdex_id)
        name = card_info.name if card_info else "Unknown"
        rarity = card_info.rarity if card_info else ""

        # Build variants string with quantities
        variant_strs = []
        card_total_qty = 0
        for card in sorted(card_variants, key=lambda c: c.variant):
            variant_strs.append(f"{card.variant}({card.quantity})")
            card_total_qty += card.quantity
            total_quantity += card.quantity

        variants_display = ", ".join(variant_strs)

        # Truncate name if too long
        if len(name) > 22:
            name = name[:19] + "..."

        # Get language from first variant
        lang = card_variants[0].language

        print(
            f"{card_variants[0].set_id:<8} {card_variants[0].card_number:<6} {lang:<5} {name:<23} {variants_display:<18} {card_total_qty:<8} {rarity:<12}"
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
        parts = args.card.split(":")
        if len(parts) == 2:
            # Legacy format: set_id:card_number (use default German)
            set_id, card_number = parts
            language = "de"
        elif len(parts) == 3:
            # New format: lang:set_id:card_number
            language, set_id, card_number = parts
        else:
            raise ValueError(
                f"Invalid format: {args.card}\n"
                f"Expected: <lang>:<set_id>:<card_number> or <set_id>:<card_number>\n"
                f"Examples:\n"
                f"  de:me01:136\n"
                f"  me01:136 (uses German)"
            )

        language = language.strip().lower()
        set_id = set_id.strip().lower()
        card_number = card_number.strip()

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        # Fetch card info
        card_info = await fetch_and_cache_card(language, set_id, card_number)

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
        for variant in ["normal", "reverse", "holo", "firstEdition"]:
            available = card_info.available_variants.is_valid(variant)
            symbol = "✓" if available else "✗"
            print(f"  {symbol} {variant}")

        # Show owned variants
        owned = db.get_owned_cards()
        owned_variants = [c for c in owned if c.tcgdex_id == card_info.tcgdex_id]

        if owned_variants:
            print("\nIn Collection:")
            for card in owned_variants:
                print(f"  • {card.variant}: {card.quantity}")
        else:
            print("\nNot in collection")

        # Show image URL
        if card_info.image_url:
            print(f"\nImage: {card_info.image_url}")

        return 0

    except api.PokedexAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_stats(args: argparse.Namespace) -> int:
    """Handle 'stats' command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    stats = db.get_collection_stats()

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


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="pkm",
        description="Manage your Pokemon TCG card collection (supports multiple languages)",
        epilog="Examples: pkm add de:me01:136  or  pkm add de:me01:136:holo",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a card to collection")
    add_parser.add_argument(
        "card",
        help="Card in format: lang:set_id:card_number[:variant] (variant defaults to normal)",
    )

    # Remove command
    rm_parser = subparsers.add_parser("rm", help="Remove a card from collection")
    rm_parser.add_argument(
        "card",
        help="Card in format: lang:set_id:card_number[:variant] (variant defaults to normal)",
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

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show collection statistics")

    return parser


def main() -> None:
    """Main entry point for CLI."""
    # Initialize database
    db.init_database()

    # Parse arguments
    parser = create_parser()
    args = parser.parse_args()

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
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
