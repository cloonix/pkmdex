"""Configuration management for pkmdex.

Handles OS-specific config directories and user preferences.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    """Application configuration."""

    db_path: Path
    backups_path: Path
    raw_data_path: Path

    @classmethod
    def default(cls) -> "Config":
        """Create default configuration.

        Uses ~/.local/share/pkmdex for data storage on Linux/macOS,
        or %LOCALAPPDATA%/pkmdex on Windows.
        """
        data_dir = get_data_dir()
        return cls(
            db_path=data_dir / "pokedex.db",
            backups_path=data_dir / "backups",
            raw_data_path=data_dir / "raw_data",
        )

    def to_dict(self) -> dict:
        """Convert config to dictionary for JSON serialization."""
        return {
            "db_path": str(self.db_path),
            "backups_path": str(self.backups_path),
            "raw_data_path": str(self.raw_data_path),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create config from dictionary."""
        # Handle old config files without raw_data_path
        raw_data_path = data.get("raw_data_path")
        if not raw_data_path:
            # Default to same directory as database
            db_path = Path(data["db_path"])
            raw_data_path = db_path.parent / "raw_data"

        return cls(
            db_path=Path(data["db_path"]),
            backups_path=Path(data["backups_path"]),
            raw_data_path=Path(raw_data_path),
        )


def get_config_dir() -> Path:
    """Get OS-specific configuration directory.

    Returns:
        ~/.config/pkmdex on Linux/macOS
        %APPDATA%/pkmdex on Windows
    """
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", "~"))
    else:  # Linux/macOS
        base = Path.home() / ".config"

    config_dir = base / "pkmdex"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_data_dir() -> Path:
    """Get OS-specific data directory.

    Returns:
        ~/.local/share/pkmdex on Linux/macOS
        %LOCALAPPDATA%/pkmdex on Windows
    """
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("LOCALAPPDATA", "~"))
    else:  # Linux/macOS
        base = Path.home() / ".local" / "share"

    data_dir = base / "pkmdex"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_config_file() -> Path:
    """Get path to configuration file."""
    return get_config_dir() / "config.json"


def load_config() -> Config:
    """Load configuration from file or create default.

    Returns:
        Config object with user preferences or defaults.
    """
    config_file = get_config_file()

    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                data = json.load(f)
            return Config.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            # If config is corrupted, fall back to default
            return Config.default()

    return Config.default()


def save_config(config: Config) -> None:
    """Save configuration to file.

    Args:
        config: Config object to save.
    """
    config_file = get_config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)

    with open(config_file, "w") as f:
        json.dump(config.to_dict(), f, indent=2)


def setup_database_path(db_path: str) -> Config:
    """Configure custom database path.

    Args:
        db_path: Path to database directory or file.
                 If directory, will use 'pokedex.db' inside it.
                 If file, will use that exact path.

    Returns:
        Updated Config object.

    Raises:
        ValueError: If path is invalid or not writable.
    """
    path = Path(db_path).expanduser().resolve()

    # If path is a directory, use pokedex.db inside it
    if path.is_dir() or not path.suffix:
        db_dir = path
        db_file = db_dir / "pokedex.db"
    else:
        db_dir = path.parent
        db_file = path

    # Create directory if it doesn't exist
    try:
        db_dir.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError) as e:
        raise ValueError(f"Cannot create directory: {db_dir}\n{e}")

    # Check if directory is writable
    if not os.access(db_dir, os.W_OK):
        raise ValueError(f"Directory not writable: {db_dir}")

    # Create backups subdirectory
    backups_dir = db_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    # Create raw_data subdirectory
    raw_data_dir = db_dir / "raw_data"
    raw_data_dir.mkdir(parents=True, exist_ok=True)

    # Create and save config
    config = Config(
        db_path=db_file, backups_path=backups_dir, raw_data_path=raw_data_dir
    )
    save_config(config)

    return config


def reset_config() -> Config:
    """Reset configuration to defaults.

    Returns:
        Default Config object.
    """
    config = Config.default()
    config.raw_data_path.mkdir(parents=True, exist_ok=True)
    save_config(config)
    return config


def save_raw_card_data(tcgdex_id: str, data: dict) -> Path:
    """Save raw card data to JSON file.

    Args:
        tcgdex_id: Card ID (e.g., "swsh3-136")
        data: Raw card data dictionary

    Returns:
        Path to saved JSON file
    """
    config = load_config()
    config.raw_data_path.mkdir(parents=True, exist_ok=True)

    # Save as cards/<tcgdex_id>.json
    cards_dir = config.raw_data_path / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    file_path = cards_dir / f"{tcgdex_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return file_path


def load_raw_card_data(tcgdex_id: str) -> Optional[dict]:
    """Load raw card data from JSON file.

    Args:
        tcgdex_id: Card ID (e.g., "swsh3-136")

    Returns:
        Raw card data dictionary, or None if not found
    """
    config = load_config()
    file_path = config.raw_data_path / "cards" / f"{tcgdex_id}.json"

    if not file_path.exists():
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
