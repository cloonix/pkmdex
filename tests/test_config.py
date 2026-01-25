"""Tests for config module."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from src import config


def test_get_config_dir():
    """Test that config directory is created."""
    config_dir = config.get_config_dir()
    assert config_dir.exists()
    assert config_dir.is_dir()
    assert config_dir.name == "pkmdex"


def test_get_data_dir():
    """Test that data directory is created."""
    data_dir = config.get_data_dir()
    assert data_dir.exists()
    assert data_dir.is_dir()
    assert data_dir.name == "pkmdex"


def test_config_default():
    """Test default configuration."""
    cfg = config.Config.default()
    assert cfg.db_path.name == "pokedex.db"
    assert cfg.backups_path.name == "backups"
    assert cfg.raw_data_path.name == "raw_data"
    assert "pkmdex" in str(cfg.db_path)


def test_config_to_from_dict():
    """Test config serialization."""
    original = config.Config(
        db_path=Path("/tmp/test.db"),
        backups_path=Path("/tmp/backups"),
        raw_data_path=Path("/tmp/raw_data"),
    )

    # Convert to dict and back
    data = original.to_dict()
    restored = config.Config.from_dict(data)

    assert restored.db_path == original.db_path
    assert restored.backups_path == original.backups_path
    assert restored.raw_data_path == original.raw_data_path


def test_save_and_load_config():
    """Test saving and loading configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Override config directory for test
        original_get_config_file = config.get_config_file
        test_config_file = Path(tmpdir) / "config.json"

        def mock_get_config_file():
            return test_config_file

        config.get_config_file = mock_get_config_file

        try:
            # Create and save config
            test_config = config.Config(
                db_path=Path("/tmp/test.db"),
                backups_path=Path("/tmp/backups"),
                raw_data_path=Path("/tmp/raw_data"),
            )
            config.save_config(test_config)

            # Load it back
            loaded = config.load_config()

            assert loaded.db_path == test_config.db_path
            assert loaded.backups_path == test_config.backups_path
            assert loaded.raw_data_path == test_config.raw_data_path
        finally:
            # Restore original function
            config.get_config_file = original_get_config_file


def test_load_config_missing_file():
    """Test loading config when file doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Override config directory for test
        original_get_config_file = config.get_config_file
        test_config_file = Path(tmpdir) / "nonexistent.json"

        def mock_get_config_file():
            return test_config_file

        config.get_config_file = mock_get_config_file

        try:
            # Should return default config
            cfg = config.load_config()
            assert cfg.db_path.name == "pokedex.db"
        finally:
            config.get_config_file = original_get_config_file


def test_load_config_corrupted_file():
    """Test loading config when file is corrupted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Override config directory for test
        original_get_config_file = config.get_config_file
        test_config_file = Path(tmpdir) / "config.json"

        def mock_get_config_file():
            return test_config_file

        config.get_config_file = mock_get_config_file

        try:
            # Write corrupted JSON
            with open(test_config_file, "w") as f:
                f.write("{invalid json")

            # Should return default config
            cfg = config.load_config()
            assert cfg.db_path.name == "pokedex.db"
        finally:
            config.get_config_file = original_get_config_file


def test_setup_database_path_directory():
    """Test setting database path to a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "pokemon_data"

        # Override config functions for test
        original_get_config_file = config.get_config_file
        original_save_config = config.save_config
        test_config_file = Path(tmpdir) / "config.json"

        def mock_get_config_file():
            return test_config_file

        saved_config = None

        def mock_save_config(cfg):
            nonlocal saved_config
            saved_config = cfg
            # Also save to file for completeness
            original_save_config(cfg)

        config.get_config_file = mock_get_config_file
        config.save_config = mock_save_config

        try:
            cfg = config.setup_database_path(str(test_dir))

            # Check that directory was created
            assert test_dir.exists()
            assert test_dir.is_dir()

            # Check that backups subdirectory was created
            assert (test_dir / "backups").exists()

            # Check that raw_data subdirectory was created
            assert (test_dir / "raw_data").exists()

            # Check config values
            assert cfg.db_path == test_dir / "pokedex.db"
            assert cfg.backups_path == test_dir / "backups"
            assert cfg.raw_data_path == test_dir / "raw_data"

            # Check that config was saved
            assert saved_config is not None
            assert saved_config.db_path == cfg.db_path
        finally:
            config.get_config_file = original_get_config_file
            config.save_config = original_save_config


def test_setup_database_path_file():
    """Test setting database path to a specific file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "my_cards.db"

        # Override config functions for test
        original_get_config_file = config.get_config_file
        original_save_config = config.save_config
        test_config_file = Path(tmpdir) / "config.json"

        def mock_get_config_file():
            return test_config_file

        saved_config = None

        def mock_save_config(cfg):
            nonlocal saved_config
            saved_config = cfg
            original_save_config(cfg)

        config.get_config_file = mock_get_config_file
        config.save_config = mock_save_config

        try:
            cfg = config.setup_database_path(str(test_file))

            # Check config values
            assert cfg.db_path == test_file
            assert cfg.backups_path == test_file.parent / "backups"
            assert cfg.raw_data_path == test_file.parent / "raw_data"

            # Check that backups directory was created
            assert (test_file.parent / "backups").exists()

            # Check that raw_data directory was created
            assert (test_file.parent / "raw_data").exists()
        finally:
            config.get_config_file = original_get_config_file
            config.save_config = original_save_config


def test_setup_database_path_invalid():
    """Test setting database path to invalid location."""
    # Try to write to a location that doesn't exist and can't be created
    # On Unix, /dev/null/subdir is invalid
    if os.name != "nt":
        with pytest.raises(ValueError, match="Cannot create directory"):
            config.setup_database_path("/dev/null/invalid/path")


def test_reset_config():
    """Test resetting configuration to defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Override config functions for test
        original_get_config_file = config.get_config_file
        original_save_config = config.save_config
        test_config_file = Path(tmpdir) / "config.json"

        def mock_get_config_file():
            return test_config_file

        saved_config = None

        def mock_save_config(cfg):
            nonlocal saved_config
            saved_config = cfg
            original_save_config(cfg)

        config.get_config_file = mock_get_config_file
        config.save_config = mock_save_config

        try:
            # Set custom config first
            custom_cfg = config.Config(
                db_path=Path("/tmp/custom.db"),
                backups_path=Path("/tmp/backups"),
                raw_data_path=Path("/tmp/raw_data"),
            )
            config.save_config(custom_cfg)

            # Reset to defaults
            default_cfg = config.reset_config()

            # Should be default values
            assert default_cfg.db_path.name == "pokedex.db"
            assert default_cfg.backups_path.name == "backups"
            assert default_cfg.raw_data_path.name == "raw_data"

            # Should have been saved
            assert saved_config is not None
            assert saved_config.db_path == default_cfg.db_path
        finally:
            config.get_config_file = original_get_config_file
            config.save_config = original_save_config
