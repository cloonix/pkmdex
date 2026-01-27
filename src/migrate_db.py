#!/usr/bin/env python3
"""Database migration script for pkmdex - adds new columns."""

import sqlite3
import sys
from pathlib import Path

def migrate_database(db_path: Path) -> None:
    """Add new columns to existing database.
    
    Args:
        db_path: Path to database file
    """
    print(f'Checking database: {db_path}')
    
    if not db_path.exists():
        print('✗ Database not found')
        sys.exit(1)
    
    # New columns to add
    new_columns = [
        ('illustrator', 'TEXT'),
        ('evolve_from', 'TEXT'),
        ('description', 'TEXT'),
        ('attacks', 'TEXT'),
        ('abilities', 'TEXT'),
        ('weaknesses', 'TEXT'),
        ('resistances', 'TEXT'),
        ('retreat_cost', 'INTEGER'),
        ('effect', 'TEXT'),
        ('trainer_type', 'TEXT'),
        ('energy_type', 'TEXT'),
        ('regulation_mark', 'TEXT'),
        ('variants', 'TEXT'),
    ]
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get existing columns
    cursor.execute('PRAGMA table_info(cards)')
    existing_cols = [row[1] for row in cursor.fetchall()]
    
    # Add missing columns
    added_count = 0
    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            try:
                cursor.execute(f'ALTER TABLE cards ADD COLUMN {col_name} {col_type}')
                print(f'  ✓ Added column: {col_name}')
                added_count += 1
            except sqlite3.OperationalError as e:
                print(f'  ✗ Error adding {col_name}: {e}')
    
    conn.commit()
    conn.close()
    
    if added_count > 0:
        print(f'\n✓ Migration complete! Added {added_count} columns.')
        print('  Run "pkm sync" to fetch updated card data.')
    else:
        print('\n✓ Database already up to date!')

if __name__ == '__main__':
    # Import here to use the actual config
    try:
        from src.config import load_config
        config = load_config()
        migrate_database(Path(config.db_path))
    except ImportError:
        print('Error: Run this script from the pkmdex directory')
        print('Usage: python -m src.migrate_db')
        sys.exit(1)
