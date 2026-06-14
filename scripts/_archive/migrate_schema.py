#!/usr/bin/env python3
"""
Schema Migration for Sentence-Scope Encoding

Adds new tables for:
1. gram_feature_values - Grammatical features (person, number, gender, case, etc.)
2. hierarchy_levels - Modifier hierarchy positions (INTENSITY, QUANTITY, etc.)
3. syn_dimensions - SYN_* dimension instantiation per word

Also ensures SING, PLUR, ZERO primitives exist for numeral encoding.
"""

import sqlite3
import argparse
from pathlib import Path
from datetime import datetime


def migrate_database(db_path: Path, dry_run: bool = False) -> dict:
    """
    Apply schema migration to add sentence-scope encoding tables.

    Returns dict with migration statistics.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {
        'tables_created': [],
        'primitives_added': [],
        'errors': []
    }

    # ================================================================
    # Table 1: gram_feature_values
    # Stores grammatical features separate from semantic primitives
    # ================================================================

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='gram_feature_values'
    """)

    if not cursor.fetchone():
        create_gram_features = """
        CREATE TABLE gram_feature_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lexeme_id INTEGER NOT NULL,
            feature TEXT NOT NULL,
            value TEXT NOT NULL,
            source TEXT DEFAULT 'migration',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE,
            UNIQUE(lexeme_id, feature)
        )
        """

        if not dry_run:
            cursor.execute(create_gram_features)
            cursor.execute("CREATE INDEX idx_gfv_lexeme ON gram_feature_values(lexeme_id)")
            cursor.execute("CREATE INDEX idx_gfv_feature ON gram_feature_values(feature)")
        stats['tables_created'].append('gram_feature_values')
        print("Created table: gram_feature_values")
    else:
        print("Table gram_feature_values already exists")

    # ================================================================
    # Table 2: hierarchy_levels
    # Stores modifier hierarchy positions for degree words
    # ================================================================

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='hierarchy_levels'
    """)

    if not cursor.fetchone():
        create_hierarchy = """
        CREATE TABLE hierarchy_levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lexeme_id INTEGER NOT NULL,
            scale TEXT NOT NULL,
            direction INTEGER NOT NULL,
            level INTEGER NOT NULL,
            source TEXT DEFAULT 'migration',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE,
            UNIQUE(lexeme_id, scale)
        )
        """

        if not dry_run:
            cursor.execute(create_hierarchy)
            cursor.execute("CREATE INDEX idx_hl_lexeme ON hierarchy_levels(lexeme_id)")
            cursor.execute("CREATE INDEX idx_hl_scale ON hierarchy_levels(scale)")
        stats['tables_created'].append('hierarchy_levels')
        print("Created table: hierarchy_levels")
    else:
        print("Table hierarchy_levels already exists")

    # ================================================================
    # Table 3: syn_dimensions
    # Stores SYN_* dimension instantiation (informational zeros)
    # ================================================================

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='syn_dimensions'
    """)

    if not cursor.fetchone():
        create_syn = """
        CREATE TABLE syn_dimensions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lexeme_id INTEGER NOT NULL,
            dimension TEXT NOT NULL,
            instantiated INTEGER DEFAULT 0,
            source TEXT DEFAULT 'migration',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE,
            UNIQUE(lexeme_id, dimension)
        )
        """

        if not dry_run:
            cursor.execute(create_syn)
            cursor.execute("CREATE INDEX idx_sd_lexeme ON syn_dimensions(lexeme_id)")
            cursor.execute("CREATE INDEX idx_sd_dimension ON syn_dimensions(dimension)")
        stats['tables_created'].append('syn_dimensions')
        print("Created table: syn_dimensions")
    else:
        print("Table syn_dimensions already exists")

    # ================================================================
    # Ensure SING, PLUR, ZERO primitives exist
    # These are needed for the numeral encoding system
    # ================================================================

    # Check existing primitives
    cursor.execute("SELECT DISTINCT primitive FROM primitive_values")
    existing_primitives = {row[0] for row in cursor.fetchall()}

    new_primitives = ['SING', 'PLUR', 'ZERO', 'HIER_PLUS', 'HIER_MINUS']

    for prim in new_primitives:
        if prim not in existing_primitives:
            stats['primitives_added'].append(prim)
            print(f"Primitive '{prim}' will be available for encoding")

    # ================================================================
    # Add animacy column to lexemes if not present
    # ================================================================

    cursor.execute("PRAGMA table_info(lexemes)")
    columns = {row[1] for row in cursor.fetchall()}

    if 'animacy' not in columns:
        if not dry_run:
            cursor.execute("ALTER TABLE lexemes ADD COLUMN animacy TEXT")
        print("Added column: lexemes.animacy")
    else:
        print("Column lexemes.animacy already exists")

    # ================================================================
    # Commit changes
    # ================================================================

    if not dry_run:
        conn.commit()
        print(f"\nMigration complete!")
    else:
        print(f"\n[DRY RUN] No changes applied")

    conn.close()
    return stats


def verify_migration(db_path: Path) -> bool:
    """Verify that all migration steps completed successfully."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    required_tables = ['gram_feature_values', 'hierarchy_levels', 'syn_dimensions']

    all_ok = True
    for table in required_tables:
        cursor.execute(f"""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='{table}'
        """)
        if not cursor.fetchone():
            print(f"MISSING: Table {table}")
            all_ok = False
        else:
            # Count rows
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"OK: Table {table} ({count} rows)")

    # Check animacy column
    cursor.execute("PRAGMA table_info(lexemes)")
    columns = {row[1] for row in cursor.fetchall()}
    if 'animacy' in columns:
        print("OK: Column lexemes.animacy exists")
    else:
        print("MISSING: Column lexemes.animacy")
        all_ok = False

    conn.close()
    return all_ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Schema migration for sentence-scope encoding")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--verify", action="store_true", help="Verify migration status")
    args = parser.parse_args()

    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        exit(1)

    if args.verify:
        print("=== Verifying Migration Status ===\n")
        success = verify_migration(db_path)
        exit(0 if success else 1)

    print("=== Schema Migration for Sentence-Scope Encoding ===")
    print(f"Database: {db_path}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    stats = migrate_database(db_path, dry_run=args.dry_run)

    print("\n=== Summary ===")
    print(f"Tables created: {stats['tables_created'] or 'none'}")
    print(f"New primitives: {stats['primitives_added'] or 'none'}")
