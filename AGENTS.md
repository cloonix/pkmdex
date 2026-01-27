# Agent Instructions for Pokemon Card Manager

This document provides guidance for AI coding agents (Aider, Claude Code, Cursor, etc.) working on this project.

## Project Overview

A minimal CLI tool for managing German Pokemon TCG card collections. Built with Python 3.13, SQLite, and the TCGdex API.

**Key Principle**: Keep it simple. Use standard library where possible. Optimize for user typing speed.

## Quick Reference

### Commands to Know

```bash
# Install dependencies (recommended)
uv sync --all-extras

# Run the CLI
python -m src.cli <command>

# Run tests
python -m pytest tests/

# Type checking
python -m mypy src/

# Alternative: Install with pip
pip install -e ".[dev]"
```

### Development Workflow with bd (Beads)

This project uses `bd` - a dependency-aware issue tracker designed for AI-supervised workflows.

**Quick Start:**
```bash
bd quickstart              # Show full guide
bd list                    # List all issues
bd ready                   # Show issues ready to work on (no blocking dependencies)
bd create "Issue title"    # Create new issue
bd show <issue-id>         # Show issue details
bd update <issue-id> --status in_progress  # Update status
bd close <issue-id>        # Close completed issue
```

**Agent Workflow:**
1. **Start session:** `bd ready` to see what's unblocked
2. **Discover work:** Create issues when finding new tasks: `bd create "Fix bug in X"`
3. **Track dependencies:** `bd dep add <blocker> <blocked>` to chain work
4. **Update progress:** `bd update <id> --status in_progress` when starting
5. **Complete work:** `bd close <id>` when done

**Database location:** `.beads/beads.db` (auto-syncs to `.beads/beads.jsonl` for git)

**Key features:**
- Issues auto-prefixed based on directory name (e.g., `pokedex-a3f2`)
- Dependency blocking prevents duplicate work
- Git auto-sync keeps team in sync
- Agents can extend DB with custom tables

See `bd quickstart` for full documentation.

### File Structure

```
src/
├── cli.py      # Entry point, argparse, command routing
├── db.py       # SQLite operations, schema management
├── api.py      # TCGdex API wrapper
└── models.py   # Dataclasses for type safety
```

## Coding Standards

### Python Style

- **Python version**: 3.13+ only
- **Type hints**: Required for all functions
- **Docstrings**: Google style for public functions
- **Line length**: 100 characters max
- **Imports**: Group stdlib, third-party, local (separated by blank lines)
- **Async**: Use async/await for all API calls
- **Error handling**: Explicit try/except with helpful messages

### Example Function

```python
import asyncio
from typing import Optional

async def get_card_info(set_id: str, card_number: str) -> Optional[CardInfo]:
    """Fetch card information from API or cache.
    
    Args:
        set_id: TCGdex set identifier (e.g., "me01")
        card_number: Card number in set (e.g., "136")
    
    Returns:
        CardInfo object if found, None otherwise.
    
    Raises:
        APIError: If API request fails and no cache available.
    """
    # Check cache first
    cached = db.get_cached_card(f"{set_id}-{card_number}")
    if cached:
        return cached
    
    # Fetch from API
    try:
        card_data = await api.fetch_card(set_id, card_number)
        return CardInfo.from_api_response(card_data)
    except Exception as e:
        raise APIError(f"Failed to fetch card {set_id}-{card_number}: {e}")
```

## Architecture Guidelines

### Database Layer (db.py)

**Responsibilities:**
- Schema creation and migrations
- CRUD operations for cards, cache
- Query builders for common patterns
- Connection management

**Rules:**
- Always use context managers for connections
- Return dataclass instances, not raw dicts
- Use parameterized queries (never string interpolation)
- Index frequently queried columns
- Handle SQLite-specific quirks (datetime, JSON)

**Example:**
```python
def add_card_variant(tcgdex_id: str, variant: str, quantity: int = 1) -> OwnedCard:
    """Add or update a card variant in collection."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO cards (tcgdex_id, variant, quantity, set_id, card_number)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tcgdex_id, variant) 
            DO UPDATE SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            (tcgdex_id, variant, quantity, *parse_id(tcgdex_id), quantity)
        )
        return OwnedCard.from_row(cursor.fetchone())
```

### API Layer (api.py)

**Responsibilities:**
- TCGdex SDK initialization
- Card/set fetching with error handling
- Response transformation to our models
- Rate limiting (if needed)

**Rules:**
- Always use German language ("de")
- Async functions only
- Cache SDK instance (singleton)
- Transform API responses to our dataclasses immediately
- Provide helpful error messages

**Example:**
```python
class TCGdexAPI:
    """Wrapper around TCGdex SDK for German cards."""
    
    def __init__(self):
        self.sdk = TCGdex("de")
    
    async def get_card(self, set_id: str, card_number: str) -> dict:
        """Fetch card from API.
        
        Returns raw API response dict.
        Raises APIError if card not found.
        """
        try:
            return await self.sdk.fetch(f'sets/{set_id}/{card_number}')
        except Exception as e:
            raise APIError(
                f"Card not found: {set_id}:{card_number}\n"
                f"Try 'poke sets {set_id}' to see available cards."
            ) from e
```

### CLI Layer (cli.py)

**Responsibilities:**
- Argument parsing
- Input validation and normalization
- Command routing
- Output formatting
- Error display

**Rules:**
- Parse format: `set_id:card_number:variant[,variant]`
- Normalize set_id to lowercase
- Validate input before calling business logic
- Show helpful error messages (suggest fixes)
- Keep output concise and scannable

**Example:**
```python
def parse_card_input(card_str: str) -> tuple[str, str, list[str]]:
    """Parse user input like 'me01:136:normal,reverse'.
    
    Returns:
        (set_id, card_number, variants)
    
    Raises:
        ValueError: If format is invalid.
    """
    parts = card_str.split(':')
    if len(parts) != 3:
        raise ValueError(
            f"Invalid format: {card_str}\n"
            f"Expected: <set_id>:<card_number>:<variant>[,<variant>]\n"
            f"Example: me01:136:normal,reverse"
        )
    
    set_id, card_number, variant_str = parts
    variants = [v.strip() for v in variant_str.split(',')]
    
    return set_id.lower(), card_number, variants
```

### Models Layer (models.py)

**Responsibilities:**
- Type-safe dataclasses
- Conversion between API, DB, and internal formats
- Validation logic

**Rules:**
- Use `@dataclass` decorator
- Add `from_api_response()` and `from_db_row()` class methods
- Use Optional[] for nullable fields
- Add validation in `__post_init__` if needed

**Example:**
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class CardVariants:
    """Card variant availability from API."""
    normal: bool = False
    reverse: bool = False
    holo: bool = False
    firstEdition: bool = False
    
    @classmethod
    def from_api_response(cls, data: dict) -> 'CardVariants':
        """Parse variants from API response."""
        return cls(
            normal=data.get('normal', False),
            reverse=data.get('reverse', False),
            holo=data.get('holo', False),
            firstEdition=data.get('firstEdition', False)
        )
    
    def is_valid(self, variant: str) -> bool:
        """Check if variant is available for this card."""
        return getattr(self, variant, False)
    
    def available_list(self) -> list[str]:
        """Return list of available variant names."""
        return [v for v in ['normal', 'reverse', 'holo', 'firstEdition'] 
                if getattr(self, v)]
```

## Common Tasks

### Adding a New Command

1. **Add argument parsing in cli.py:**
```python
subparsers = parser.add_subparsers(dest='command')
my_parser = subparsers.add_parser('mycommand', help='Description')
my_parser.add_argument('arg1', help='Argument help')
```

2. **Create command handler:**
```python
async def handle_mycommand(args):
    """Handle mycommand logic."""
    # Validate input
    # Call business logic
    # Format output
    pass
```

3. **Route in main():**
```python
if args.command == 'mycommand':
    await handle_mycommand(args)
```

4. **Add tests:**
```python
def test_mycommand():
    # Test valid inputs
    # Test error cases
    # Test output format
    pass
```

### Adding a Database Table

1. **Update schema in db.py:**
```python
CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS my_table (
    id INTEGER PRIMARY KEY,
    field TEXT NOT NULL
);
CREATE INDEX idx_field ON my_table(field);
"""
```

2. **Add CRUD functions:**
```python
def get_thing(id: int) -> Optional[Thing]:
    """Fetch thing by ID."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM my_table WHERE id = ?", (id,))
        row = cursor.fetchone()
        return Thing.from_row(row) if row else None
```

3. **Create model in models.py:**
```python
@dataclass
class Thing:
    id: int
    field: str
    
    @classmethod
    def from_row(cls, row: tuple) -> 'Thing':
        return cls(id=row[0], field=row[1])
```

### Adding API Endpoint Support

1. **Add method to api.py:**
```python
async def get_new_data(self, param: str) -> dict:
    """Fetch new data type from API."""
    return await self.sdk.fetch(f'endpoint/{param}')
```

2. **Create response model:**
```python
@dataclass
class NewData:
    @classmethod
    def from_api_response(cls, data: dict) -> 'NewData':
        # Parse response
        pass
```

3. **Add caching if appropriate:**
```python
def cache_new_data(data: NewData) -> None:
    """Store in cache table."""
    # INSERT INTO cache ...
    pass
```

## Testing Guidelines

### Unit Tests

- Test each layer independently
- Mock external dependencies (API, filesystem)
- Test edge cases (empty inputs, invalid data)
- Test error handling

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_add_card_success():
    """Test adding a card successfully."""
    # Setup
    mock_api = AsyncMock(return_value={'name': 'Test', 'variants': {'normal': True}})
    
    # Execute
    with patch('api.TCGdexAPI.get_card', mock_api):
        result = await add_card('me01', '136', ['normal'])
    
    # Assert
    assert result.name == 'Test'
    assert result.variant == 'normal'
```

### Integration Tests

- Test full command flow
- Use temporary database
- Test real API responses (with VCR.py or similar)

```python
@pytest.fixture
def temp_db():
    """Create temporary test database."""
    db_path = ':memory:'
    init_database(db_path)
    yield db_path
    # Cleanup handled by :memory:

def test_add_and_list_flow(temp_db):
    """Test adding card and listing it."""
    # Add card
    run_command(['add', 'me01:136:normal'])
    
    # List cards
    output = run_command(['list'])
    assert 'me01' in output
    assert '136' in output
```

## Error Handling Strategy

### User-Facing Errors

Always provide:
1. What went wrong
2. Why it happened (if known)
3. How to fix it

**Bad:**
```
Error: Card not found
```

**Good:**
```
Error: Card not found: me01:136
Possible causes:
  - Card number doesn't exist in this set
  - Set ID is incorrect

Try 'pkm sets mega' to search for the right set ID.
```

### Error Types

```python
class PokedexError(Exception):
    """Base exception for all app errors."""
    pass

class InputError(PokedexError):
    """User input is invalid."""
    pass

class APIError(PokedexError):
    """API request failed."""
    pass

class DatabaseError(PokedexError):
    """Database operation failed."""
    pass
```

## Performance Optimization

### Database

- Use indexes on frequently queried columns (set_id, tcgdex_id)
- Batch inserts when possible
- Keep connections open for duration of command
- Use `RETURNING` to avoid extra SELECT

### API

- Cache everything possible
- Check cache before API call
- Use async for concurrent requests (future)
- Consider request coalescing for repeated calls

### CLI

- Lazy import heavy modules
- Minimize database queries (JOIN instead of N+1)
- Stream large outputs instead of building full string

## Debugging Tips

### Enable SQL Logging

```python
import sqlite3
sqlite3.enable_callback_tracebacks(True)
conn.set_trace_callback(print)
```

### Debug API Responses

```python
# In api.py
async def get_card(self, set_id: str, card_number: str):
    response = await self.sdk.fetch(f'sets/{set_id}/{card_number}')
    import json
    print(json.dumps(response, indent=2))  # Debug print
    return response
```

### Check Database State

```bash
sqlite3 pokedex.db
> .schema
> SELECT * FROM cards;
> .quit
```

## Common Pitfalls

### 1. Async/Await Confusion

**Wrong:**
```python
def main():
    result = api.get_card('me01', '136')  # Missing await!
```

**Right:**
```python
async def main():
    result = await api.get_card('me01', '136')

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
```

### 2. SQL Injection

**Wrong:**
```python
conn.execute(f"SELECT * FROM cards WHERE set_id = '{set_id}'")
```

**Right:**
```python
conn.execute("SELECT * FROM cards WHERE set_id = ?", (set_id,))
```

### 3. Forgetting to Handle None

**Wrong:**
```python
card = db.get_card(id)
print(card.name)  # Crashes if None!
```

**Right:**
```python
card = db.get_card(id)
if card is None:
    print("Card not found")
    return
print(card.name)
```

### 4. Not Normalizing Input

**Wrong:**
```python
set_id = user_input  # Could be "ME01" or "me01"
```

**Right:**
```python
set_id = user_input.strip().lower()
```

## Development Workflow

### Starting a New Feature

1. Read relevant section in DESIGN.md
2. Create test file first (TDD approach)
3. Implement minimal version
4. Test manually with real API
5. Handle edge cases
6. Update docs if needed

### Before Committing

- [ ] Run tests: `pytest`
- [ ] Check types: `mypy src/`
- [ ] Test manually with CLI
- [ ] Update docstrings if needed
- [ ] Check for debug prints/commented code

### When Stuck

1. Check DESIGN.md for architectural decisions
2. Look at similar existing code
3. Test with real API using curl/httpie
4. Check TCGdex documentation
5. Add debug logging

## Useful Commands

```bash
# Install in development mode
pip install -e .

# Run specific test
pytest tests/test_db.py::test_add_card -v

# Check types
mypy src/

# Format code (if we add black)
black src/ tests/

# Database inspection
sqlite3 pokedex.db "SELECT * FROM cards;"

# Test API manually
curl https://api.tcgdex.net/v2/de/sets/me01/136 | jq

# Check Python version
python --version  # Should be 3.13+

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
```

## Resources

- [TCGdex API Docs](https://tcgdex.dev)
- [Python 3.13 Docs](https://docs.python.org/3.13/)
- [SQLite Docs](https://www.sqlite.org/docs.html)
- [Type Hints PEP](https://peps.python.org/pep-0484/)

## Questions?

When uncertain about implementation details:

1. Check if DESIGN.md addresses it
2. Follow existing patterns in codebase
3. Prefer simplicity over cleverness
4. Ask for clarification if it affects UX

Remember: The goal is a **fast, simple, minimal** CLI tool. When in doubt, choose the simpler solution.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
