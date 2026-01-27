"""Configuration management for pkmdex.

Handles OS-specific config directories and user preferences.
"""

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    """Application configuration."""

    db_path: Path
    backups_path: Path
    api_base_url: Optional[str] = None  # Optional custom API base URL

    @classmethod
    def default(cls) -> "Config":
        """Create default configuration.

        Uses ~/.local/share/pkmdex for data storage on Linux/macOS,
        or %LOCALAPPDATA%/pkmdex on Windows.
        """
        data_dir = _get_data_dir()
        return cls(
            db_path=data_dir / "pokedex.db",
            backups_path=data_dir / "backups",
        )

    def to_dict(self) -> dict:
        """Convert config to dictionary for JSON serialization."""
        return {
            "db_path": str(self.db_path),
            "backups_path": str(self.backups_path),
            "api_base_url": self.api_base_url,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create config from dictionary."""
        return cls(
            db_path=Path(data["db_path"]),
            backups_path=Path(data["backups_path"]),
            api_base_url=data.get("api_base_url"),
        )


def _get_app_dir(subdir: str) -> Path:
    """Get OS-specific app directory (config or data).

    Args:
        subdir: 'config' for config files, 'data' for data files

    Returns:
        OS-specific directory path
    """
    if os.name == "nt":  # Windows
        base = Path(
            os.environ.get("APPDATA" if subdir == "config" else "LOCALAPPDATA", "~")
        )
    else:  # Linux/macOS
        base = Path.home() / (".config" if subdir == "config" else ".local/share")

    app_dir = base / "pkmdex"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def _get_config_dir() -> Path:
    """Get OS-specific configuration directory."""
    return _get_app_dir("config")


def _get_data_dir() -> Path:
    """Get OS-specific data directory."""
    return _get_app_dir("data")


def load_config() -> Config:
    """Load configuration from file or create default.

    Returns:
        Config object with user preferences or defaults.
    """
    config_file = _get_config_dir() / "config.json"

    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                return Config.from_dict(json.load(f))
        except (json.JSONDecodeError, KeyError, ValueError):
            # If config is corrupted, fall back to default
            return Config.default()

    return Config.default()


def save_config(config: Config) -> None:
    """Save configuration to file.

    Args:
        config: Config object to save.
    """
    config_file = _get_config_dir() / "config.json"
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

    # Determine db file and directory
    if path.is_dir() or not path.suffix:
        db_file = path / "pokedex.db"
        db_dir = path
    else:
        db_file = path
        db_dir = path.parent

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

    # Create and save config
    config = Config(db_path=db_file, backups_path=backups_dir)
    save_config(config)
    return config


def reset_config() -> Config:
    """Reset configuration to defaults.

    Returns:
        Default Config object.
    """
    config = Config.default()
    save_config(config)
    return config


def get_api_base_url() -> Optional[str]:
    """Get API base URL from config or environment.

    Priority:
    1. TCGDEX_API_URL environment variable
    2. api_base_url from config file
    3. None (use TCGdex default)

    Returns:
        Custom API base URL or None for default
    """
    # Check environment variable first
    env_url = os.environ.get("TCGDEX_API_URL")
    if env_url:
        return env_url

    # Check config file
    return load_config().api_base_url


def get_config_file_path() -> Path:
    """Get path to configuration file.

    Returns:
        Path to config.json file
    """
    return _get_config_dir() / "config.json"
