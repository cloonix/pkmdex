"""Command-line interface for Pokemon card collection manager."""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from . import db, api, config
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

        # Validate variant is available (unless --force is used)
        if not args.force and not card_info.available_variants.is_valid(variant):
            available = ", ".join(card_info.available_variants.available_list())
            print(
                f"Error: Variant '{variant}' not available for {card_info.name} ({card_info.tcgdex_id})\n"
                f"Available variants: {available}\n"
                f"Tip: If you have this physical card, use --force to override:\n"
                f"     pkm add --force {args.card}",
                file=sys.stderr,
            )
            return 1

        # Show warning if forcing an unlisted variant
        if args.force and not card_info.available_variants.is_valid(variant):
            print(
                f"⚠ Warning: Adding variant '{variant}' not listed in API for {card_info.name}",
                file=sys.stderr,
            )

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
    # For --all flag, we only need lang:set:card (no variant)
    if args.all:
        parts = args.card.split(":")
        if len(parts) == 2:
            # Legacy format: set:card (use default German)
            set_id, card_number = parts
            language = "de"
        elif len(parts) == 3:
            # New format: lang:set:card
            language, set_id, card_number = parts
        else:
            print(
                f"Error: Invalid format for --all: {args.card}\n"
                f"Expected: <lang>:<set_id>:<card_number> or <set_id>:<card_number>\n"
                f"Examples:\n"
                f"  pkm rm --all de:me01:136\n"
                f"  pkm rm --all me01:136 (uses German)",
                file=sys.stderr,
            )
            return 1

        language = language.strip().lower()
        set_id = set_id.strip().lower()
        card_number = card_number.strip()
        tcgdex_id = f"{set_id}-{card_number}"

        # Try to get card name from cache for better output
        card_info = db.get_cached_card(tcgdex_id)
        card_name = card_info.name if card_info else tcgdex_id

        # Remove all variants
        removed_count = db.remove_all_card_variants(tcgdex_id, language)

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
        f"{'Set':<8} {'Card#':<6} {'Lang':<5} {'Name':<25} {'Qty':<5} {'Rarity':<15} {'Variants'}"
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
        if len(name) > 24:
            name = name[:21] + "..."

        # Get language from first variant
        lang = card_variants[0].language

        print(
            f"{card_variants[0].set_id:<8} {card_variants[0].card_number:<6} {lang:<5} {name:<25} {card_total_qty:<5} {rarity:<15} {variants_display}"
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

    # Show raw JSON if requested
    if args.raw:
        tcgdex_id = f"{set_id}-{card_number}"
        raw_data = config.load_raw_card_data(tcgdex_id)

        if raw_data:
            import json

            print(json.dumps(raw_data, indent=2, ensure_ascii=False))
            return 0
        else:
            print(
                f"No raw data found for {tcgdex_id}\n"
                f"Fetch the card first with: pkm info {language}:{set_id}:{card_number}",
                file=sys.stderr,
            )
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

        # Show hint about raw data
        print(
            f"\nTip: Use 'pkm info {language}:{set_id}:{card_number} --raw' to see complete API data"
        )

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


def handle_setup(args: argparse.Namespace) -> int:
    """Handle 'setup' command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Show current configuration
    if args.show:
        current_config = config.load_config()
        print("Current Configuration")
        print("─" * 60)
        print(f"Database path:  {current_config.db_path}")
        print(f"Backups path:   {current_config.backups_path}")
        print(f"Raw data path:  {current_config.raw_data_path}")
        print(f"Config file:    {config.get_config_file()}")

        # Check if using default
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
    print("Usage: pkm setup [--show | --reset | --path PATH]")
    print("\nOptions:")
    print("  --show         Show current configuration")
    print("  --reset        Reset to default configuration")
    print("  --path PATH    Set custom database directory or file path")
    print("\nExamples:")
    print("  pkm setup --show")
    print("  pkm setup --path ~/Documents/pokemon")
    print("  pkm setup --path /mnt/backup/pokemon/cards.db")
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
        print(f"  Card cache: {result['card_cache_count']}")
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
        print(f"  Card cache: {result['card_cache_count']}")
        print(f"  Set cache: {result['set_cache_count']}")
        if result.get("exported_at"):
            print(f"  Original export date: {result['exported_at']}")
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

        # Card cache
        print("\nCard Cache:")
        print(f"  Entries: {stats['card_cache_count']}")
        if stats["card_cache_oldest"]:
            print(
                f"  Oldest:  {stats['card_cache_oldest'].strftime('%Y-%m-%d %H:%M:%S')}"
            )
        if stats["card_cache_newest"]:
            print(
                f"  Newest:  {stats['card_cache_newest'].strftime('%Y-%m-%d %H:%M:%S')}"
            )

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

                # Cache the card
                db.cache_card(card_info)

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
            count = db.clear_card_cache()
            print(f"✓ Cleared card cache: {count} entries")

        if args.type in ("sets", "all"):
            count = db.clear_set_cache()
            print(f"✓ Cleared set cache: {count} entries")

        return 0

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
    elif args.command == "setup":
        exit_code = handle_setup(args)
    elif args.command == "export":
        exit_code = handle_export(args)
    elif args.command == "import":
        exit_code = handle_import(args)
    elif args.command == "cache":
        exit_code = asyncio.run(handle_cache(args))
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
