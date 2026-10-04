#!/usr/bin/env python3
"""
Encode Pronouns in GSE Lexicon Database

Applies pronoun encodings from gse/lexicon/pronouns.py to the database:
1. Sets SOMEONE=1 or SOMETHING=1 as the semantic primitive
2. Populates gram_feature_values table with grammatical features
3. Sets animacy on the lexemes table
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gse.lexicon.pronouns import PRONOUN_ENCODINGS


def encode_pronouns(db_path: Path, dry_run: bool = False) -> dict:
    """
    Apply pronoun encodings to the database.

    Returns dict with statistics.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {
        'found': 0,
        'not_found': [],
        'primitives_set': 0,
        'gram_features_set': 0,
        'animacy_set': 0,
    }

    for word, encoding in PRONOUN_ENCODINGS.items():
        # Find lexeme in database (try exact match first)
        cursor.execute("""
            SELECT id, lemma, pos FROM lexemes
            WHERE LOWER(lemma) = LOWER(?)
            LIMIT 1
        """, (word,))

        row = cursor.fetchone()

        if not row:
            # Try without spaces for compound pronouns
            cursor.execute("""
                SELECT id, lemma, pos FROM lexemes
                WHERE LOWER(REPLACE(lemma, ' ', '')) = LOWER(REPLACE(?, ' ', ''))
                LIMIT 1
            """, (word,))
            row = cursor.fetchone()

        if not row:
            stats['not_found'].append(word)
            continue

        lexeme_id, lemma, pos = row
        stats['found'] += 1

        # 1. Set semantic primitive (SOMEONE or SOMETHING)
        primitives = encoding.get('primitives', {})
        for prim, value in primitives.items():
            if not dry_run:
                cursor.execute("""
                    INSERT INTO primitive_values (lexeme_id, primitive, value, source)
                    VALUES (?, ?, ?, 'pronoun_encoding')
                    ON CONFLICT(lexeme_id, primitive)
                    DO UPDATE SET value = ?, source = 'pronoun_encoding'
                """, (lexeme_id, prim, value, value))
            stats['primitives_set'] += 1
            print(f"  {lemma}: {prim}={value}")

        # 2. Set grammatical features
        gram = encoding.get('gram', {})
        for feature, value in gram.items():
            if not dry_run:
                cursor.execute("""
                    INSERT INTO gram_feature_values (lexeme_id, feature, value, source)
                    VALUES (?, ?, ?, 'pronoun_encoding')
                    ON CONFLICT(lexeme_id, feature)
                    DO UPDATE SET value = ?, source = 'pronoun_encoding'
                """, (lexeme_id, feature, str(value), str(value)))
            stats['gram_features_set'] += 1

        # 3. Set animacy
        animacy = encoding.get('animacy')
        if animacy:
            if not dry_run:
                cursor.execute("""
                    UPDATE lexemes SET animacy = ? WHERE id = ?
                """, (animacy, lexeme_id))
            stats['animacy_set'] += 1

    if not dry_run:
        conn.commit()

    conn.close()
    return stats


def verify_pronoun_encodings(db_path: Path) -> None:
    """Show current state of pronoun encodings."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=== Pronoun Encoding Verification ===\n")

    # Check a sample of pronouns
    sample = ['i', 'you', 'he', 'she', 'it', 'they', 'who', 'what']

    for word in sample:
        cursor.execute("""
            SELECT l.id, l.lemma, l.animacy,
                   GROUP_CONCAT(pv.primitive || '=' || pv.value) as primitives
            FROM lexemes l
            LEFT JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.value != 0
            WHERE LOWER(l.lemma) = LOWER(?)
            GROUP BY l.id
        """, (word,))

        row = cursor.fetchone()
        if row:
            lexeme_id, lemma, animacy, primitives = row

            # Get gram features
            cursor.execute("""
                SELECT feature, value FROM gram_feature_values
                WHERE lexeme_id = ?
            """, (lexeme_id,))
            gram = {r[0]: r[1] for r in cursor.fetchall()}

            print(f"{lemma}:")
            print(f"  Primitives: {primitives or 'none'}")
            print(f"  Animacy: {animacy}")
            print(f"  Gram features: {gram or 'none'}")
            print()
        else:
            print(f"{word}: NOT FOUND\n")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Encode pronouns in GSE lexicon")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--verify", action="store_true", help="Verify current encodings")
    args = parser.parse_args()

    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        exit(1)

    if args.verify:
        verify_pronoun_encodings(db_path)
        exit(0)

    print("=== Encoding Pronouns ===")
    print(f"Database: {db_path}")
    print(f"Total pronouns to encode: {len(PRONOUN_ENCODINGS)}")
    print()

    stats = encode_pronouns(db_path, dry_run=args.dry_run)

    print()
    print("=== Summary ===")
    print(f"Found in database: {stats['found']}")
    print(f"Not found: {len(stats['not_found'])}")
    if stats['not_found']:
        print(f"  Missing: {', '.join(stats['not_found'][:10])}{'...' if len(stats['not_found']) > 10 else ''}")
    print(f"Primitives set: {stats['primitives_set']}")
    print(f"Gram features set: {stats['gram_features_set']}")
    print(f"Animacy set: {stats['animacy_set']}")

    if args.dry_run:
        print("\n[DRY RUN] No changes applied")
