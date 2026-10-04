#!/usr/bin/env python3
"""
Encode Modifier Hierarchies in GSE Lexicon Database

Applies modifier hierarchy encodings from gse/lexicon/modifier_hierarchy.py:
- Populates hierarchy_levels table with scale positions
- Covers INTENSITY, QUANTITY, CERTAINTY, FREQUENCY scales
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gse.lexicon.modifier_hierarchy import ALL_MODIFIER_SCALES


def encode_modifiers(db_path: Path, dry_run: bool = False) -> dict:
    """
    Apply modifier hierarchy encodings to the database.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {
        "found": 0,
        "not_found": [],
        "hierarchy_levels_set": 0,
        "by_scale": {scale: 0 for scale in ALL_MODIFIER_SCALES},
    }

    for scale, words in ALL_MODIFIER_SCALES.items():
        print(f"=== {scale} Scale ===")

        for word, encoding in words.items():
            # Skip multi-word phrases for now
            if " " in word:
                continue

            cursor.execute(
                """
                SELECT id, lemma FROM lexemes
                WHERE LOWER(lemma) = LOWER(?)
                LIMIT 1
            """,
                (word,),
            )

            row = cursor.fetchone()
            if not row:
                stats["not_found"].append(f"{scale}:{word}")
                continue

            lexeme_id, lemma = row
            stats["found"] += 1
            stats["by_scale"][scale] += 1

            direction = encoding["direction"]
            level = encoding["level"]

            if not dry_run:
                cursor.execute(
                    """
                    INSERT INTO hierarchy_levels (lexeme_id, scale, direction, level, source)
                    VALUES (?, ?, ?, ?, 'modifier_encoding')
                    ON CONFLICT(lexeme_id, scale)
                    DO UPDATE SET direction = ?, level = ?, source = 'modifier_encoding'
                """,
                    (lexeme_id, scale, direction, level, direction, level),
                )

            stats["hierarchy_levels_set"] += 1
            print(f"  {lemma}: {'+' if direction > 0 else '-'}{level}")

    if not dry_run:
        conn.commit()

    conn.close()
    return stats


def verify_modifier_encodings(db_path: Path) -> None:
    """Show current state of modifier encodings."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=== Modifier Hierarchy Verification ===\n")

    for scale in ["INTENSITY", "QUANTITY", "CERTAINTY", "FREQUENCY"]:
        cursor.execute(
            """
            SELECT l.lemma, h.direction, h.level
            FROM hierarchy_levels h
            JOIN lexemes l ON h.lexeme_id = l.id
            WHERE h.scale = ?
            ORDER BY h.direction, h.level
        """,
            (scale,),
        )

        rows = cursor.fetchall()
        print(f"{scale} ({len(rows)} words):")

        # Group by position
        for direction in [-1, 1]:
            dir_words = [r for r in rows if r[1] == direction]
            if dir_words:
                sign = "+" if direction > 0 else "-"
                for level in range(5, 0, -1) if direction < 0 else range(1, 6):
                    level_words = [r[0] for r in dir_words if r[2] == level]
                    if level_words:
                        print(f"  {sign}{level}: {', '.join(level_words[:5])}{'...' if len(level_words) > 5 else ''}")
        print()

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Encode modifier hierarchies in GSE lexicon")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--verify", action="store_true", help="Verify current encodings")
    args = parser.parse_args()

    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        exit(1)

    if args.verify:
        verify_modifier_encodings(db_path)
        exit(0)

    print("=== Encoding Modifier Hierarchies ===")
    print(f"Database: {db_path}")
    total = sum(len([w for w in words if " " not in w]) for words in ALL_MODIFIER_SCALES.values())
    print(f"Total single-word modifiers: {total}")
    print()

    stats = encode_modifiers(db_path, dry_run=args.dry_run)

    print()
    print("=== Summary ===")
    print(f"Found in database: {stats['found']}")
    print(f"Hierarchy levels set: {stats['hierarchy_levels_set']}")
    for scale, count in stats["by_scale"].items():
        print(f"  {scale}: {count}")
    print(f"Not found: {len(stats['not_found'])}")

    if args.dry_run:
        print("\n[DRY RUN] No changes applied")
