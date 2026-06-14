#!/usr/bin/env python3
"""
GSE Lexicon Schema Migration

Migrates the existing lexicon.db to be compatible with:
1. GSEPipeline (pipeline_v2) - needs decompositions, vectors, content_hash
2. GSEEncoder (legacy api) - needs comp_primitive, comp_arity, comp_operation

This script:
1. Adds missing columns to lexemes table
2. Populates decompositions from primitive_values
3. Generates HDC vectors for each lexeme
4. Computes content hashes for verification
"""

import sqlite3
import hashlib
import json
import sys
from pathlib import Path
from typing import List, Tuple, Dict
import numpy as np

# Add GSE to path
GSE_PATH = Path(__file__).parent.parent
sys.path.insert(0, str(GSE_PATH))

from gse.vectors_v2 import create_basis, compose_decomposition, SparseVector
from gse.primitives_v2 import SEMANTIC_BANK_NAMES


def migrate_database(db_path: str, backup: bool = True):
    """
    Migrate the lexicon database to the new schema.

    Args:
        db_path: Path to lexicon.db
        backup: Whether to create a backup before migration
    """
    db_path = Path(db_path)

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return False

    # Create backup
    if backup:
        backup_path = db_path.with_suffix('.db.backup')
        import shutil
        shutil.copy(db_path, backup_path)
        print(f"Created backup at {backup_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("Starting migration...")

    # Step 1: Add missing columns to lexemes table
    print("\n1. Adding missing columns to lexemes table...")
    add_missing_columns(cursor)
    conn.commit()

    # Step 2: Populate decompositions from primitive_values
    print("\n2. Populating decompositions from primitive_values...")
    populate_decompositions(cursor)
    conn.commit()

    # Step 3: Generate vectors for each lexeme
    print("\n3. Generating HDC vectors...")
    generate_vectors(cursor)
    conn.commit()

    # Step 4: Compute content hashes
    print("\n4. Computing content hashes...")
    compute_content_hashes(cursor)
    conn.commit()

    # Step 5: Update metadata
    print("\n5. Updating metadata...")
    update_metadata(cursor)
    conn.commit()

    conn.close()
    print("\nMigration complete!")
    return True


def add_missing_columns(cursor: sqlite3.Cursor):
    """Add columns required by GSEPipeline and GSEEncoder."""

    # Check existing columns
    cursor.execute("PRAGMA table_info(lexemes)")
    existing_cols = {row['name'] for row in cursor.fetchall()}

    columns_to_add = [
        ("source", "TEXT DEFAULT 'llm'"),
        ("frequency", "REAL DEFAULT 1.0"),
        ("content_hash", "TEXT"),
        ("comp_primitive", "TEXT"),  # For compositional operators
        ("comp_arity", "INTEGER DEFAULT 0"),
        ("comp_operation", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ]

    for col_name, col_type in columns_to_add:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE lexemes ADD COLUMN {col_name} {col_type}")
                print(f"  Added column: {col_name}")
            except sqlite3.OperationalError as e:
                print(f"  Column {col_name} already exists or error: {e}")

    # Create indexes if missing
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lexemes_hash ON lexemes(content_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lexemes_source ON lexemes(source)")
    except Exception as e:
        print(f"  Index creation note: {e}")

    # Update source from component_type if available
    cursor.execute("""
        UPDATE lexemes
        SET source = COALESCE(component_type, 'llm')
        WHERE source IS NULL OR source = ''
    """)

    # Set frequency from frequency_rank (inverse relationship)
    cursor.execute("""
        UPDATE lexemes
        SET frequency = CASE
            WHEN frequency_rank IS NOT NULL AND frequency_rank > 0
            THEN 1.0 / (1.0 + LOG(frequency_rank))
            ELSE 0.5
        END
        WHERE frequency IS NULL
    """)

    print(f"  Updated source and frequency columns")


def populate_decompositions(cursor: sqlite3.Cursor):
    """Populate decompositions table from primitive_values."""

    # Check if decompositions already has data
    cursor.execute("SELECT COUNT(*) FROM decompositions")
    existing_count = cursor.fetchone()[0]

    if existing_count > 0:
        print(f"  Decompositions table already has {existing_count} entries, skipping...")
        return

    # Get primitive values and convert to decompositions
    cursor.execute("""
        SELECT lexeme_id, primitive, value, confidence, source
        FROM primitive_values
        WHERE value != 0
        ORDER BY lexeme_id, primitive
    """)

    rows = cursor.fetchall()
    print(f"  Processing {len(rows)} primitive values...")

    batch = []
    for row in rows:
        lexeme_id = row['lexeme_id']
        primitive = row['primitive']
        value = row['value']

        # Determine role based on primitive category
        role = get_role_for_primitive(primitive)
        polarity = 1 if value > 0 else -1
        position = len([b for b in batch if b[0] == lexeme_id])

        batch.append((lexeme_id, primitive, role, polarity, position))

        if len(batch) >= 10000:
            cursor.executemany("""
                INSERT OR IGNORE INTO decompositions
                (lexeme_id, primitive, role, polarity, position)
                VALUES (?, ?, ?, ?, ?)
            """, batch)
            batch = []

    if batch:
        cursor.executemany("""
            INSERT OR IGNORE INTO decompositions
            (lexeme_id, primitive, role, polarity, position)
            VALUES (?, ?, ?, ?, ?)
        """, batch)

    cursor.execute("SELECT COUNT(*) FROM decompositions")
    new_count = cursor.fetchone()[0]
    print(f"  Created {new_count} decomposition entries")


def get_role_for_primitive(primitive: str) -> str:
    """Map primitive to semantic role."""
    # Evaluators
    if primitive in ['GOOD', 'BAD']:
        return 'evaluation'
    # Mental
    if primitive in ['THINK', 'KNOW', 'WANT', 'FEEL', 'SEE', 'HEAR']:
        return 'mental_process'
    # Actions
    if primitive in ['DO', 'HAPPEN', 'MOVE', 'TOUCH']:
        return 'action'
    # Substantives
    if primitive in ['SOMEONE', 'SOMETHING', 'PEOPLE', 'BODY']:
        return 'entity'
    # Determiners
    if primitive in ['THIS', 'THE_SAME', 'OTHER']:
        return 'determiner'
    # Quantifiers
    if primitive in ['ONE', 'TWO', 'SOME', 'ALL', 'MUCH', 'MANY', 'LITTLE', 'FEW']:
        return 'quantifier'
    # Attributes
    if primitive in ['BIG', 'SMALL']:
        return 'size'
    if primitive in ['LONG', 'SHORT']:
        return 'duration'
    if primitive in ['FAST', 'SLOW']:
        return 'speed'
    # Logical
    if primitive in ['NOT', 'MAYBE', 'CAN', 'IF', 'BECAUSE']:
        return 'logical'
    # Spatial
    if primitive in ['WHERE', 'HERE', 'ABOVE', 'BELOW', 'FAR', 'NEAR', 'SIDE', 'INSIDE', 'PART']:
        return 'spatial'
    # Temporal
    if primitive in ['WHEN', 'NOW', 'BEFORE', 'AFTER', 'MOMENT']:
        return 'temporal'

    return 'attribute'


def generate_vectors(cursor: sqlite3.Cursor):
    """Generate HDC vectors for each lexeme."""

    # Check if vectors already has data
    cursor.execute("SELECT COUNT(*) FROM vectors")
    existing_count = cursor.fetchone()[0]

    if existing_count > 0:
        print(f"  Vectors table already has {existing_count} entries, skipping...")
        return

    # Create basis
    print("  Creating HDC basis...")
    basis = create_basis()

    # Get all lexemes with decompositions
    cursor.execute("""
        SELECT DISTINCT lexeme_id FROM decompositions
    """)
    lexeme_ids = [row[0] for row in cursor.fetchall()]
    print(f"  Generating vectors for {len(lexeme_ids)} lexemes...")

    batch = []
    processed = 0

    for lexeme_id in lexeme_ids:
        # Get decomposition for this lexeme
        cursor.execute("""
            SELECT primitive, role, polarity
            FROM decompositions
            WHERE lexeme_id = ?
            ORDER BY position
        """, (lexeme_id,))

        decomp = [(row['primitive'], row['role'], row['polarity'])
                  for row in cursor.fetchall()]

        if decomp:
            try:
                vec = compose_decomposition(basis, decomp)
                positive_blob = vec.positive_indices.astype(np.uint16).tobytes()
                negative_blob = vec.negative_indices.astype(np.uint16).tobytes()
                batch.append((lexeme_id, positive_blob, negative_blob))
            except Exception as e:
                # Some primitives may not be in the basis, skip
                pass

        processed += 1
        if len(batch) >= 5000:
            cursor.executemany("""
                INSERT OR IGNORE INTO vectors (lexeme_id, positive_indices, negative_indices)
                VALUES (?, ?, ?)
            """, batch)
            print(f"    Processed {processed}/{len(lexeme_ids)} lexemes...")
            batch = []

    if batch:
        cursor.executemany("""
            INSERT OR IGNORE INTO vectors (lexeme_id, positive_indices, negative_indices)
            VALUES (?, ?, ?)
        """, batch)

    cursor.execute("SELECT COUNT(*) FROM vectors")
    new_count = cursor.fetchone()[0]
    print(f"  Created {new_count} vector entries")


def compute_content_hashes(cursor: sqlite3.Cursor):
    """Compute content hashes for lexemes."""

    # Get lexemes without hashes
    cursor.execute("""
        SELECT l.id, l.lemma, l.pos, l.sense_id, l.gloss
        FROM lexemes l
        WHERE l.content_hash IS NULL
        LIMIT 100000
    """)

    rows = cursor.fetchall()
    if not rows:
        print("  All lexemes already have content hashes")
        return

    print(f"  Computing hashes for {len(rows)} lexemes...")

    batch = []
    for row in rows:
        # Create hash from content
        content = f"{row['lemma']}|{row['pos']}|{row['sense_id']}|{row['gloss'] or ''}"
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:32]
        batch.append((content_hash, row['id']))

        if len(batch) >= 10000:
            cursor.executemany("""
                UPDATE lexemes SET content_hash = ? WHERE id = ?
            """, batch)
            batch = []

    if batch:
        cursor.executemany("""
            UPDATE lexemes SET content_hash = ? WHERE id = ?
        """, batch)

    print(f"  Updated content hashes")


def update_metadata(cursor: sqlite3.Cursor):
    """Update metadata table."""

    # Get counts
    cursor.execute("SELECT COUNT(*) FROM lexemes")
    lexeme_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM decompositions")
    decomp_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM vectors")
    vector_count = cursor.fetchone()[0]

    # Update metadata
    metadata = [
        ('total_lexemes', str(lexeme_count)),
        ('total_decompositions', str(decomp_count)),
        ('total_vectors', str(vector_count)),
        ('schema_version', '2.0'),
        ('migration_date', 'CURRENT_TIMESTAMP'),
    ]

    for key, value in metadata:
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)
        """, (key, value))

    print(f"  Updated metadata: {lexeme_count} lexemes, {vector_count} vectors")


def verify_migration(db_path: str):
    """Verify the migration was successful."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\nVerification:")

    # Check columns
    cursor.execute("PRAGMA table_info(lexemes)")
    cols = {row[1] for row in cursor.fetchall()}
    required = {'source', 'frequency', 'content_hash', 'comp_primitive', 'comp_arity', 'comp_operation'}
    missing = required - cols
    if missing:
        print(f"  WARNING: Missing columns: {missing}")
    else:
        print("  OK: All required columns present")

    # Check data
    cursor.execute("SELECT COUNT(*) FROM lexemes WHERE content_hash IS NOT NULL")
    with_hash = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM decompositions")
    decomp_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM vectors")
    vector_count = cursor.fetchone()[0]

    print(f"  Lexemes with hash: {with_hash}")
    print(f"  Decomposition entries: {decomp_count}")
    print(f"  Vector entries: {vector_count}")

    # Test a sample query like GSEEncoder would
    cursor.execute("""
        SELECT id, lemma, pos, comp_primitive, comp_arity, comp_operation
        FROM lexemes WHERE lemma = 'happy' LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        print(f"  Sample query OK: {row}")
    else:
        print("  Sample query: No 'happy' entry found")

    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate GSE lexicon database schema")
    parser.add_argument("--db", default="/Users/rohanvinaik/gse/data/lexicon.db",
                        help="Path to lexicon database")
    parser.add_argument("--no-backup", action="store_true",
                        help="Skip creating backup")
    parser.add_argument("--verify-only", action="store_true",
                        help="Only verify, don't migrate")

    args = parser.parse_args()

    if args.verify_only:
        verify_migration(args.db)
    else:
        if migrate_database(args.db, backup=not args.no_backup):
            verify_migration(args.db)
