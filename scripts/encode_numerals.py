#!/usr/bin/env python3
"""
Encode Numerals in GSE Lexicon Database

Applies numeral encodings from gse/lexicon/numerals.py to the database:
1. Sets SING/PLUR/ZERO primitives based on the mutual transparency system
2. Populates hierarchy_levels table for quantity scale positions
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gse.lexicon.numerals import NUMERAL_ENCODINGS, validate_mutual_transparency


def encode_numerals(db_path: Path, dry_run: bool = False) -> dict:
    """
    Apply numeral encodings to the database.

    Returns dict with statistics.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {
        "found": 0,
        "not_found": [],
        "primitives_set": 0,
        "hierarchy_levels_set": 0,
        "validation_errors": [],
    }

    for word, encoding in NUMERAL_ENCODINGS.items():
        # Validate mutual transparency before applying
        primitives = encoding.get("primitives", {})
        if not validate_mutual_transparency(primitives):
            stats["validation_errors"].append(f"{word}: violates SING/PLUR/ZERO rule")
            continue

        # Find lexeme in database
        cursor.execute(
            """
            SELECT id, lemma, pos FROM lexemes
            WHERE LOWER(lemma) = LOWER(?)
            LIMIT 1
        """,
            (word,),
        )

        row = cursor.fetchone()

        if not row:
            stats["not_found"].append(word)
            continue

        lexeme_id, lemma, pos = row
        stats["found"] += 1

        # 1. Set semantic primitives (SING, PLUR, ZERO, ONE, TWO)
        for prim, value in primitives.items():
            if not dry_run:
                cursor.execute(
                    """
                    INSERT INTO primitive_values (lexeme_id, primitive, value, source)
                    VALUES (?, ?, ?, 'numeral_encoding')
                    ON CONFLICT(lexeme_id, primitive)
                    DO UPDATE SET value = ?, source = 'numeral_encoding'
                """,
                    (lexeme_id, prim, value, value),
                )
            stats["primitives_set"] += 1

        # 2. Set hierarchy level if present
        hierarchy = encoding.get("hierarchy")
        if hierarchy:
            scale = hierarchy["scale"]
            direction = hierarchy["direction"]
            level = hierarchy["level"]

            if not dry_run:
                cursor.execute(
                    """
                    INSERT INTO hierarchy_levels (lexeme_id, scale, direction, level, source)
                    VALUES (?, ?, ?, ?, 'numeral_encoding')
                    ON CONFLICT(lexeme_id, scale)
                    DO UPDATE SET direction = ?, level = ?, source = 'numeral_encoding'
                """,
                    (lexeme_id, scale, direction, level, direction, level),
                )
            stats["hierarchy_levels_set"] += 1
            print(f"  {lemma}: {list(primitives.keys())} + {scale}({'+' if direction > 0 else '-'}{level})")
        else:
            print(f"  {lemma}: {list(primitives.keys())}")

    if not dry_run:
        conn.commit()

    conn.close()
    return stats


def verify_numeral_encodings(db_path: Path) -> None:
    """Show current state of numeral encodings."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=== Numeral Encoding Verification ===\n")

    # Check a sample of numerals
    sample = ["zero", "one", "two", "three", "ten", "many", "all", "none"]

    for word in sample:
        cursor.execute(
            """
            SELECT l.id, l.lemma,
                   GROUP_CONCAT(pv.primitive || '=' || pv.value) as primitives
            FROM lexemes l
            LEFT JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.value != 0
            WHERE LOWER(l.lemma) = LOWER(?)
            GROUP BY l.id
        """,
            (word,),
        )

        row = cursor.fetchone()
        if row:
            lexeme_id, lemma, primitives = row

            # Get hierarchy level
            cursor.execute(
                """
                SELECT scale, direction, level FROM hierarchy_levels
                WHERE lexeme_id = ?
            """,
                (lexeme_id,),
            )
            hier_row = cursor.fetchone()

            hier_str = ""
            if hier_row:
                scale, direction, level = hier_row
                hier_str = f" | {scale}({'+' if direction > 0 else '-'}{level})"

            print(f"{lemma}: {primitives or 'none'}{hier_str}")
        else:
            print(f"{word}: NOT FOUND")

    # Summary statistics
    print("\n=== SING/PLUR/ZERO Distribution ===")
    for prim in ["SING", "PLUR", "ZERO"]:
        cursor.execute(
            """
            SELECT COUNT(*) FROM primitive_values
            WHERE primitive = ? AND value = 1
        """,
            (prim,),
        )
        count = cursor.fetchone()[0]
        print(f"{prim}=1: {count} words")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Encode numerals in GSE lexicon")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--verify", action="store_true", help="Verify current encodings")
    args = parser.parse_args()

    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        exit(1)

    if args.verify:
        verify_numeral_encodings(db_path)
        exit(0)

    print("=== Encoding Numerals ===")
    print(f"Database: {db_path}")
    print(f"Total numerals to encode: {len(NUMERAL_ENCODINGS)}")
    print()

    stats = encode_numerals(db_path, dry_run=args.dry_run)

    print()
    print("=== Summary ===")
    print(f"Found in database: {stats['found']}")
    print(f"Not found: {len(stats['not_found'])}")
    if stats["not_found"]:
        print(f"  Missing: {', '.join(stats['not_found'][:15])}{'...' if len(stats['not_found']) > 15 else ''}")
    print(f"Primitives set: {stats['primitives_set']}")
    print(f"Hierarchy levels set: {stats['hierarchy_levels_set']}")
    if stats["validation_errors"]:
        print(f"Validation errors: {len(stats['validation_errors'])}")
        for err in stats["validation_errors"]:
            print(f"  {err}")

    if args.dry_run:
        print("\n[DRY RUN] No changes applied")
