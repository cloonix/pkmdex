"""NiceGUI web interface for Pokemon card collection manager.

This module provides an interactive web UI that complements the CLI tool.
It reuses all existing business logic from db.py, api.py, analyzer.py, and config.py.

Usage:
    python -m src.web
    # or after installation: pkm-web
"""

from typing import Optional
from nicegui import ui, app
from . import db, config, analyzer


# Initialize database on startup
@app.on_startup
def init_app() -> None:
    """Initialize database connection on app startup."""
    db.init_database()


def create_header() -> None:
    """Create the app header with title and navigation."""
    with ui.header().classes("items-center justify-between"):
        ui.label("🎴 Pokemon Card Collection Manager").classes("text-2xl font-bold")
        with ui.row():
            ui.link("Dashboard", "/").classes("text-white hover:text-gray-300")
            ui.link("Gallery", "/gallery").classes("text-white hover:text-gray-300")
            ui.link("Analytics", "/analytics").classes("text-white hover:text-gray-300")


@ui.page("/")
def dashboard_page() -> None:
    """Dashboard page showing collection statistics."""
    create_header()

    with ui.column().classes("w-full p-8"):
        ui.label("📊 Collection Dashboard").classes("text-3xl font-bold mb-6")

        # Get statistics from database
        stats = db.get_v2_collection_stats()

        # Key metrics in cards
        with ui.row().classes("w-full gap-4 mb-8"):
            with ui.card().classes("flex-1"):
                ui.label("Unique Cards").classes("text-gray-500")
                ui.label(str(stats["unique_cards"])).classes("text-4xl font-bold")

            with ui.card().classes("flex-1"):
                ui.label("Total Cards").classes("text-gray-500")
                ui.label(str(stats["total_cards"])).classes("text-4xl font-bold")

            with ui.card().classes("flex-1"):
                ui.label("Sets").classes("text-gray-500")
                ui.label(str(stats["sets_count"])).classes("text-4xl font-bold")

            with ui.card().classes("flex-1"):
                ui.label("Total Value").classes("text-gray-500")
                ui.label(f"€{stats['total_value_eur']:.2f}").classes(
                    "text-4xl font-bold text-green-600"
                )

        # Most collected set
        if stats["most_collected_set"]:
            with ui.card().classes("w-full mb-4"):
                ui.label("Most Collected Set").classes("text-xl font-bold mb-2")
                ui.label(
                    f"{stats['most_collected_set']}: {stats['most_collected_qty']} cards"
                )

        # Most valuable card
        if stats["most_valuable_card"]:
            mvc = stats["most_valuable_card"]
            with ui.card().classes("w-full mb-4"):
                ui.label("Most Valuable Card").classes("text-xl font-bold mb-2")
                ui.label(f"{mvc['name']} ({mvc['tcgdex_id']}): €{mvc['price_eur']:.2f}")

        # Variant breakdown
        if stats["variant_breakdown"]:
            with ui.card().classes("w-full mb-4"):
                ui.label("Variants").classes("text-xl font-bold mb-2")
                for variant, count in sorted(stats["variant_breakdown"].items()):
                    ui.label(f"{variant.capitalize()}: {count}")

        # Rarity breakdown
        if stats["rarity_breakdown"]:
            with ui.card().classes("w-full"):
                ui.label("Rarity Distribution").classes("text-xl font-bold mb-2")
                for rarity, count in sorted(
                    stats["rarity_breakdown"].items(), key=lambda x: x[1], reverse=True
                ):
                    ui.label(f"{rarity}: {count}")


@ui.page("/gallery")
def gallery_page() -> None:
    """Card gallery page with filters and image grid."""
    create_header()

    with ui.column().classes("w-full p-8"):
        ui.label("🎴 Card Gallery").classes("text-3xl font-bold mb-6")

        # Filter controls
        filter_language = ui.select(
            options=[
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
            ],
            value="de",
            label="Language",
        ).classes("mb-4")

        filter_set_id = ui.input(
            label="Set ID (optional)", placeholder="e.g., me01"
        ).classes("mb-4")

        card_container = ui.row().classes("w-full gap-4")

        def load_cards() -> None:
            """Load and display cards based on filters."""
            card_container.clear()

            language = filter_language.value
            set_id = filter_set_id.value.strip() or None

            cards = db.get_v2_owned_cards(language=language, set_id=set_id)

            with card_container:
                if not cards:
                    ui.label("No cards found with current filters.").classes(
                        "text-gray-500"
                    )
                    return

                # Group cards by tcgdex_id to show all variants together
                from collections import defaultdict

                grouped = defaultdict(list)
                for card in cards:
                    grouped[card["tcgdex_id"]].append(card)

                # Display cards in grid
                for tcgdex_id, card_variants in grouped.items():
                    # Use first variant for display info
                    card = card_variants[0]

                    with ui.card().classes("w-64"):
                        # Card image
                        if card.get("image_url"):
                            ui.image(card["image_url"]).classes(
                                "w-full h-64 object-contain"
                            )
                        else:
                            ui.label("No image").classes(
                                "text-gray-400 h-64 flex items-center justify-center"
                            )

                        # Card info
                        ui.label(card["display_name"]).classes("font-bold text-lg")
                        ui.label(
                            f"Set: {card['set_id']} #{card['card_number']}"
                        ).classes("text-sm text-gray-500")

                        if card.get("rarity"):
                            ui.label(f"Rarity: {card['rarity']}").classes("text-sm")

                        # Variants and quantities
                        total_qty = sum(v["quantity"] for v in card_variants)
                        variants_str = ", ".join(
                            [f"{v['variant']}({v['quantity']})" for v in card_variants]
                        )
                        ui.label(f"Qty: {total_qty}").classes("font-bold")
                        ui.label(f"Variants: {variants_str}").classes(
                            "text-xs text-gray-600"
                        )

                        # Price if available
                        if card.get("price_eur"):
                            ui.label(f"€{card['price_eur']:.2f}").classes(
                                "text-green-600 font-bold"
                            )

        # Connect filter changes to reload function
        filter_language.on_value_change(lambda: load_cards())
        filter_set_id.on("change", lambda: load_cards())

        # Initial load
        load_cards()


@ui.page("/analytics")
def analytics_page() -> None:
    """Analytics page with collection insights and filtering."""
    create_header()

    with ui.column().classes("w-full p-8"):
        ui.label("📈 Collection Analytics").classes("text-3xl font-bold mb-6")

        # Filter controls
        with ui.expansion("Filters", icon="filter_alt").classes("w-full mb-4"):
            with ui.row().classes("w-full gap-4"):
                filter_stage = ui.select(
                    options=["", "Basic", "Stage1", "Stage2", "VMAX", "VSTAR", "ex"],
                    value="",
                    label="Stage",
                ).classes("flex-1")

                filter_type = ui.select(
                    options=[
                        "",
                        "Fire",
                        "Water",
                        "Grass",
                        "Electric",
                        "Psychic",
                        "Fighting",
                        "Darkness",
                        "Metal",
                        "Fairy",
                        "Dragon",
                        "Colorless",
                    ],
                    value="",
                    label="Type",
                ).classes("flex-1")

                filter_rarity = ui.input(
                    label="Rarity (optional)", placeholder="e.g., Rare"
                ).classes("flex-1")
                filter_category = ui.select(
                    options=["", "Pokémon", "Trainer", "Energy"],
                    value="",
                    label="Category",
                ).classes("flex-1")

            with ui.row().classes("w-full gap-4"):
                filter_hp_min = ui.number(
                    label="HP Min", min=0, max=340, step=10, value=None
                ).classes("flex-1")
                filter_hp_max = ui.number(
                    label="HP Max", min=0, max=340, step=10, value=None
                ).classes("flex-1")
                filter_language = ui.select(
                    options=[
                        "",
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
                    ],
                    value="",
                    label="Language",
                ).classes("flex-1")
                filter_set_id = ui.input(
                    label="Set ID (optional)", placeholder="e.g., me01"
                ).classes("flex-1")

        # Display mode toggle
        stats_mode = ui.checkbox("Statistics Mode", value=False).classes("mb-4")

        results_container = ui.column().classes("w-full")

        def analyze() -> None:
            """Run analysis with current filters."""
            results_container.clear()

            # Build filter criteria
            filter_criteria = analyzer.AnalysisFilter(
                stage=filter_stage.value or None,
                type=filter_type.value or None,
                rarity=filter_rarity.value.strip() or None,
                hp_min=int(filter_hp_min.value) if filter_hp_min.value else None,
                hp_max=int(filter_hp_max.value) if filter_hp_max.value else None,
                category=filter_category.value or None,
                language=filter_language.value or None,
                set_id=filter_set_id.value.strip() or None,
            )

            # Get analyzed cards
            cards = analyzer.analyze_collection(filter_criteria)

            with results_container:
                ui.label(f"Collection Analysis ({len(cards)} cards)").classes(
                    "text-2xl font-bold mb-4"
                )

                if not cards:
                    ui.label("No cards match the current filters.").classes(
                        "text-gray-500"
                    )
                    return

                if stats_mode.value:
                    # Statistics mode
                    stats = analyzer.get_collection_statistics(cards)

                    with ui.card().classes("w-full mb-4"):
                        ui.label("Overview").classes("text-xl font-bold mb-2")
                        ui.label(f"Total Cards: {stats['total_cards']}")
                        ui.label(f"Total Quantity: {stats['total_quantity']}")
                        if stats["avg_hp"] > 0:
                            ui.label(f"Average HP: {stats['avg_hp']:.1f}")

                    # By Stage
                    if stats["by_stage"]:
                        with ui.card().classes("w-full mb-4"):
                            ui.label("By Stage").classes("text-xl font-bold mb-2")
                            for stage, count in sorted(
                                stats["by_stage"].items(),
                                key=lambda x: x[1],
                                reverse=True,
                            ):
                                ui.label(f"{stage}: {count}")

                    # By Type
                    if stats["by_type"]:
                        with ui.card().classes("w-full mb-4"):
                            ui.label("By Type").classes("text-xl font-bold mb-2")
                            for ptype, count in sorted(
                                stats["by_type"].items(),
                                key=lambda x: x[1],
                                reverse=True,
                            ):
                                ui.label(f"{ptype}: {count}")

                    # By Rarity
                    if stats["by_rarity"]:
                        with ui.card().classes("w-full mb-4"):
                            ui.label("By Rarity").classes("text-xl font-bold mb-2")
                            for rarity, count in sorted(
                                stats["by_rarity"].items(),
                                key=lambda x: x[1],
                                reverse=True,
                            ):
                                ui.label(f"{rarity}: {count}")

                    # By Category
                    if stats["by_category"]:
                        with ui.card().classes("w-full mb-4"):
                            ui.label("By Category").classes("text-xl font-bold mb-2")
                            for category, count in sorted(
                                stats["by_category"].items(),
                                key=lambda x: x[1],
                                reverse=True,
                            ):
                                ui.label(f"{category}: {count}")

                    # By Set
                    if stats["by_set"]:
                        with ui.card().classes("w-full"):
                            ui.label("By Set").classes("text-xl font-bold mb-2")
                            for set_id, count in sorted(
                                stats["by_set"].items(),
                                key=lambda x: x[1],
                                reverse=True,
                            )[:10]:
                                ui.label(f"{set_id}: {count}")

                else:
                    # Card list mode
                    with ui.table(
                        columns=[
                            {
                                "name": "id",
                                "label": "ID",
                                "field": "id",
                                "align": "left",
                            },
                            {
                                "name": "name",
                                "label": "Name",
                                "field": "name",
                                "align": "left",
                            },
                            {
                                "name": "stage",
                                "label": "Stage",
                                "field": "stage",
                                "align": "center",
                            },
                            {
                                "name": "types",
                                "label": "Type(s)",
                                "field": "types",
                                "align": "center",
                            },
                            {
                                "name": "hp",
                                "label": "HP",
                                "field": "hp",
                                "align": "center",
                            },
                            {
                                "name": "rarity",
                                "label": "Rarity",
                                "field": "rarity",
                                "align": "left",
                            },
                            {
                                "name": "qty",
                                "label": "Qty",
                                "field": "qty",
                                "align": "center",
                            },
                        ],
                        rows=[
                            {
                                "id": card.tcgdex_id,
                                "name": card.localized_name,
                                "stage": card.stage or "-",
                                "types": ", ".join(card.types) if card.types else "-",
                                "hp": card.hp or "-",
                                "rarity": card.rarity or "-",
                                "qty": card.quantity,
                            }
                            for card in cards
                        ],
                        row_key="id",
                    ).classes("w-full"):
                        pass

        # Apply button
        ui.button("Apply Filters", on_click=analyze).classes("mb-4")

        # Initial analysis (no filters)
        analyze()


def main() -> None:
    """Start the NiceGUI web application."""
    ui.run(
        title="Pokemon Card Collection Manager",
        favicon="🎴",
        dark=None,  # Auto-detect dark mode from system
        reload=False,
        show=True,  # Open browser automatically
        port=8080,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
