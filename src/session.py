"""Session context management for pkmdex CLI."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import config


class SessionContext:
    """Manages persistent session context for card adding."""

    def __init__(self):
        """Initialize session context."""
        self.language: Optional[str] = None
        self.set_id: Optional[str] = None
        self.last_updated: Optional[datetime] = None

    def is_valid(self) -> bool:
        """Check if context has required fields.

        Returns:
            True if both language and set_id are set
        """
        return self.language is not None and self.set_id is not None

    def update(self, language: str, set_id: str) -> None:
        """Update context with new language and set.

        Args:
            language: Language code (e.g., 'de', 'en')
            set_id: Set identifier (e.g., 'me01', 'swsh3')
        """
        self.language = language
        self.set_id = set_id
        self.last_updated = datetime.now()

    def clear(self) -> None:
        """Clear the session context."""
        self.language = None
        self.set_id = None
        self.last_updated = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation
        """
        return {
            "language": self.language,
            "set_id": self.set_id,
            "last_updated": self.last_updated.isoformat()
            if self.last_updated
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionContext":
        """Create SessionContext from dictionary.

        Args:
            data: Dictionary with context data

        Returns:
            SessionContext instance
        """
        context = cls()
        context.language = data.get("language")
        context.set_id = data.get("set_id")

        last_updated_str = data.get("last_updated")
        if last_updated_str:
            context.last_updated = datetime.fromisoformat(last_updated_str)

        return context

    def __str__(self) -> str:
        """String representation of context.

        Returns:
            Human-readable context string
        """
        if not self.is_valid():
            return "No context set"
        return f"{self.language}:{self.set_id}"


def get_session_file() -> Path:
    """Get path to session file.

    Returns:
        Path to session.json
    """
    cfg = config.load_config()
    session_dir = config.get_config_dir()
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / "session.json"


def load_context() -> SessionContext:
    """Load session context from file.

    Returns:
        SessionContext instance (may be empty)
    """
    session_file = get_session_file()

    if not session_file.exists():
        return SessionContext()

    try:
        with open(session_file, "r") as f:
            data = json.load(f)
        return SessionContext.from_dict(data)
    except (json.JSONDecodeError, IOError):
        # If file is corrupted, return empty context
        return SessionContext()


def save_context(context: SessionContext) -> None:
    """Save session context to file.

    Args:
        context: SessionContext to save
    """
    session_file = get_session_file()

    try:
        with open(session_file, "w") as f:
            json.dump(context.to_dict(), f, indent=2)
    except IOError:
        # Silently fail if we can't write (don't break the user's workflow)
        pass


def clear_context() -> None:
    """Clear and delete session file."""
    session_file = get_session_file()

    if session_file.exists():
        try:
            session_file.unlink()
        except IOError:
            pass
