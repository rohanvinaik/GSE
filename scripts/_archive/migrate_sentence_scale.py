#!/usr/bin/env python3
"""
Migration: Add sentence-scale primitive support to lexicon database.

This adds:
1. sentence_primitives table (primitive definitions)
2. sentence_primitive_values table (lexeme -> primitive mappings)
3. Extended lexemes columns for compositional operators
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/lexicon.db")


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=== Sentence-Scale Database Migration ===\n")

    # 1. Create sentence_primitives table
    print("1. Creating sentence_primitives table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sentence_primitives (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            bank INTEGER NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            is_compositional BOOLEAN DEFAULT FALSE,
            comp_arity INTEGER DEFAULT 0,
            comp_operation TEXT
        )
    """)

    # 2. Insert sentence primitive definitions
    print("2. Populating sentence_primitives...")
    primitives = [
        # Bank 0: Core Structure
        ("SYN_SUBJ", 0, "CORE", "Subject syntactic role", False, 0, None),
        ("SYN_PRED", 0, "CORE", "Predicate syntactic role", False, 0, None),
        ("SYN_OBJ", 0, "CORE", "Object syntactic role", False, 0, None),
        ("SYN_COMPL", 0, "CORE", "Complement syntactic role", False, 0, None),

        # Bank 1: Modification
        ("SYN_ADJ_MOD", 1, "MODIFICATION", "Adjectival modifier", False, 0, None),
        ("SYN_ADV_MOD", 1, "MODIFICATION", "Adverbial modifier", False, 0, None),
        ("SYN_DET", 1, "MODIFICATION", "Determiner", False, 0, None),

        # Bank 2: TAM
        ("SYN_TENSE_PAST", 2, "TAM", "Past tense marker", False, 0, None),
        ("SYN_TENSE_PRES", 2, "TAM", "Present tense marker", False, 0, None),
        ("SYN_TENSE_FUT", 2, "TAM", "Future tense marker", False, 0, None),
        ("SYN_ASPECT_PERF", 2, "TAM", "Perfect aspect", False, 0, None),
        ("SYN_ASPECT_PROG", 2, "TAM", "Progressive aspect", False, 0, None),
        ("SYN_MOOD_INTER", 2, "TAM", "Interrogative mood", False, 0, None),
        ("SYN_MOOD_IMPER", 2, "TAM", "Imperative mood", False, 0, None),

        # Bank 3: Comparison (compositional)
        ("COMP_THAN", 3, "COMPARISON", "Set difference comparison", True, 2, "SET_DIFF"),
        ("COMP_AS", 3, "COMPARISON", "Equation comparison", True, 2, "BIND_EQ"),

        # Bank 4: Quantification (compositional)
        ("COMP_HOW", 4, "QUANTIFICATION", "Degree query", True, 1, "DEGREE_QUERY"),
        ("COMP_WHAT", 4, "QUANTIFICATION", "Type query", True, 1, "TYPE_QUERY"),

        # Bank 5: Constraint (compositional)
        ("COMP_JUST", 5, "CONSTRAINT", "Lower cardinality bound", True, 2, "CARD_LOWER"),
        ("COMP_ONLY", 5, "CONSTRAINT", "Set restriction", True, 1, "SET_RESTRICT"),
        ("COMP_EVEN", 5, "CONSTRAINT", "Scalar extreme marker", True, 1, "SCALAR_EXTREME"),

        # Bank 6: Discourse (compositional)
        ("COMP_BUT", 6, "DISCOURSE", "Adversative contrast", True, 2, "CONTRAST"),
        ("COMP_SO", 6, "DISCOURSE", "Consequence", True, 2, "CONSEQUENCE"),
        ("COMP_BECAUSE", 6, "DISCOURSE", "Causal source", True, 2, "CAUSAL_SOURCE"),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO sentence_primitives
        (name, bank, category, description, is_compositional, comp_arity, comp_operation)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, primitives)
    print(f"   Inserted {cursor.rowcount} primitives")

    # 3. Create sentence_primitive_values table
    print("3. Creating sentence_primitive_values table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sentence_primitive_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lexeme_id INTEGER NOT NULL,
            primitive TEXT NOT NULL,
            value INTEGER NOT NULL DEFAULT 0,
            confidence REAL DEFAULT 1.0,
            source TEXT DEFAULT 'inferred',
            FOREIGN KEY (lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE,
            UNIQUE(lexeme_id, primitive)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_spv_lexeme ON sentence_primitive_values(lexeme_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_spv_primitive ON sentence_primitive_values(primitive)")

    # 4. Add compositional operator columns to lexemes
    print("4. Extending lexemes table...")

    # Check existing columns
    cursor.execute("PRAGMA table_info(lexemes)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    new_columns = [
        ("sentence_vector", "BLOB"),
        ("comp_primitive", "TEXT"),
        ("comp_arity", "INTEGER DEFAULT 0"),
        ("comp_operation", "TEXT"),
        ("comp_sign_aware", "BOOLEAN DEFAULT TRUE"),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE lexemes ADD COLUMN {col_name} {col_type}")
            print(f"   Added column: {col_name}")
        else:
            print(f"   Column exists: {col_name}")

    # 5. Create index for compositional lookups
    print("5. Creating indexes...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lexemes_comp ON lexemes(comp_primitive)")

    conn.commit()

    # Verify
    print("\n=== Verification ===")
    cursor.execute("SELECT COUNT(*) FROM sentence_primitives")
    print(f"sentence_primitives count: {cursor.fetchone()[0]}")

    cursor.execute("SELECT bank, COUNT(*) FROM sentence_primitives GROUP BY bank ORDER BY bank")
    for row in cursor.fetchall():
        print(f"  Bank {row[0]}: {row[1]} primitives")

    cursor.execute("SELECT COUNT(*) FROM sentence_primitives WHERE is_compositional = 1")
    print(f"Compositional operators: {cursor.fetchone()[0]}")

    conn.close()
    print("\n✓ Migration complete")


if __name__ == "__main__":
    migrate()
