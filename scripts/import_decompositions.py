#!/usr/bin/env python3
"""
Import word decompositions into the GSE lexicon from a JSON file.
This bypasses the need for an API key by accepting pre-generated decompositions.

Usage:
    python scripts/import_decompositions.py data/new_words.json
    python scripts/import_decompositions.py data/new_words.json --db data/lexicon.db
"""

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gse.lexicon_generator import LexiconGenerator
from gse.primitives import PRIMITIVES, ROLES
from gse.vectors import PrimitiveBasis


def validate_decomposition(word: str, decomposition: list) -> list:
    """Validate and return errors for a decomposition."""
    errors = []
    for item in decomposition:
        if isinstance(item, list) and len(item) == 2:
            prim, role = item
        elif isinstance(item, dict):
            prim = item.get("primitive")
            role = item.get("role")
        else:
            errors.append(f"  Invalid format: {item}")
            continue

        if prim not in PRIMITIVES:
            errors.append(f"  Unknown primitive: '{prim}'")
        if role not in ROLES:
            errors.append(f"  Unknown role: '{role}'")
    return errors


def normalize_decomposition(decomposition: list) -> list:
    """Convert decomposition to standard [(primitive, role), ...] format."""
    result = []
    for item in decomposition:
        if isinstance(item, list) and len(item) == 2:
            result.append(tuple(item))
        elif isinstance(item, dict):
            result.append((item["primitive"], item["role"]))
    return result


def import_decompositions(input_file: str, db_path: str, basis_path: str):
    """Import decompositions from JSON file into the lexicon database."""

    # Load basis
    if os.path.exists(basis_path):
        basis = PrimitiveBasis.load(basis_path)
        print(f"Loaded basis from {basis_path}")
    else:
        print(f"Basis not found at {basis_path}, generating new one...")
        basis = PrimitiveBasis.generate(PRIMITIVES, ROLES, dimension=10000, sparsity=0.1)
        basis.save(basis_path)
        print(f"Saved new basis to {basis_path}")

    # Create generator (no API key needed for encoding)
    generator = LexiconGenerator(basis)

    # Load input file
    with open(input_file, "r") as f:
        words = json.load(f)

    print(f"\nLoaded {len(words)} word entries from {input_file}")

    # Validate all entries first
    print("\nValidating entries...")
    valid_entries = []
    for entry in words:
        word = entry.get("word", "")
        pos = entry.get("pos", "")
        decomposition = entry.get("decomposition", [])

        if not word or not pos or not decomposition:
            print(f"⚠ Skipping incomplete entry: {entry}")
            continue

        errors = validate_decomposition(word, decomposition)
        if errors:
            print(f"✗ {word} ({pos}):")
            for e in errors:
                print(e)
        else:
            valid_entries.append(entry)
            print(f"✓ {word} ({pos})")

    print(f"\n{len(valid_entries)}/{len(words)} entries valid")

    if not valid_entries:
        print("No valid entries to import.")
        return

    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lexicon (
            id INTEGER PRIMARY KEY,
            lemma TEXT,
            pos TEXT,
            sense_id TEXT,
            gloss TEXT,
            decomposition TEXT,
            vector BLOB,
            frequency REAL,
            source TEXT,
            confidence REAL,
            UNIQUE(lemma, pos, sense_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lemma ON lexicon(lemma)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lemma_pos ON lexicon(lemma, pos)")

    # Import entries
    print(f"\nImporting to {db_path}...")
    imported = 0
    skipped = 0

    for entry in valid_entries:
        word = entry["word"]
        pos = entry["pos"]
        decomposition = normalize_decomposition(entry["decomposition"])
        definition = entry.get("definition", "")
        frequency = entry.get("frequency", 0.0)

        # Check if exists
        existing = conn.execute("SELECT 1 FROM lexicon WHERE lemma = ? AND pos = ?", (word.lower(), pos)).fetchone()

        if existing:
            print(f"  Skipped (exists): {word} ({pos})")
            skipped += 1
            continue

        # Encode and insert
        vector = generator.encode_decomposition(decomposition)

        conn.execute(
            """
            INSERT INTO lexicon
            (lemma, pos, sense_id, gloss, decomposition, vector, frequency, source, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                word.lower(),
                pos,
                f"{word.lower()}.{pos}.01",
                definition,
                json.dumps(decomposition),
                vector.serialize(),
                frequency,
                "manual",
                0.9,
            ),
        )
        imported += 1
        print(f"  Imported: {word} ({pos})")

    conn.commit()
    conn.close()

    print(f"\nDone! Imported {imported}, skipped {skipped} (already exist)")


def main():
    parser = argparse.ArgumentParser(description="Import word decompositions into GSE lexicon")
    parser.add_argument("input_file", help="JSON file with word decompositions")
    parser.add_argument("--db", default="data/lexicon.db", help="Path to lexicon database")
    parser.add_argument("--basis", default="data/basis.msgpack", help="Path to basis file")

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found: {args.input_file}")
        sys.exit(1)

    import_decompositions(args.input_file, args.db, args.basis)


if __name__ == "__main__":
    main()
