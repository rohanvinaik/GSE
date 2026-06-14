#!/usr/bin/env python3
"""
Enhance Function Words in GSE Lexicon Database

Applies function word encodings from gse/lexicon/function_words.py:
1. Adds definiteness to determiners
2. Adds clause relations to conjunctions/complementizers
3. Adds spatial/temporal features to prepositions
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gse.lexicon.function_words import (
    CONJUNCTION_ENCODINGS,
    DETERMINER_ENCODINGS,
    PREPOSITION_ENCODINGS,
)


def enhance_function_words(db_path: Path, dry_run: bool = False) -> dict:
    """
    Apply function word enhancements to the database.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {
        'determiners_enhanced': 0,
        'conjunctions_enhanced': 0,
        'prepositions_enhanced': 0,
        'gram_features_set': 0,
        'not_found': [],
    }

    # 1. Enhance Determiners
    print("=== Enhancing Determiners ===")
    for word, encoding in DETERMINER_ENCODINGS.items():
        cursor.execute("""
            SELECT id, lemma FROM lexemes
            WHERE LOWER(lemma) = LOWER(?) AND operator_type = 'DETERMINER'
            LIMIT 1
        """, (word,))

        row = cursor.fetchone()
        if not row:
            # Try without operator_type restriction
            cursor.execute("""
                SELECT id, lemma FROM lexemes
                WHERE LOWER(lemma) = LOWER(?)
                LIMIT 1
            """, (word,))
            row = cursor.fetchone()

        if not row:
            stats['not_found'].append(f"det:{word}")
            continue

        lexeme_id, lemma = row
        stats['determiners_enhanced'] += 1

        for feature, value in encoding.items():
            if not dry_run:
                cursor.execute("""
                    INSERT INTO gram_feature_values (lexeme_id, feature, value, source)
                    VALUES (?, ?, ?, 'function_word_encoding')
                    ON CONFLICT(lexeme_id, feature)
                    DO UPDATE SET value = ?, source = 'function_word_encoding'
                """, (lexeme_id, feature, str(value), str(value)))
            stats['gram_features_set'] += 1

        print(f"  {lemma}: {list(encoding.keys())}")

    # 2. Enhance Conjunctions
    print("\n=== Enhancing Conjunctions ===")
    for word, encoding in CONJUNCTION_ENCODINGS.items():
        cursor.execute("""
            SELECT id, lemma FROM lexemes
            WHERE LOWER(lemma) = LOWER(?)
            LIMIT 1
        """, (word,))

        row = cursor.fetchone()
        if not row:
            stats['not_found'].append(f"conj:{word}")
            continue

        lexeme_id, lemma = row
        stats['conjunctions_enhanced'] += 1

        for feature, value in encoding.items():
            if not dry_run:
                cursor.execute("""
                    INSERT INTO gram_feature_values (lexeme_id, feature, value, source)
                    VALUES (?, ?, ?, 'function_word_encoding')
                    ON CONFLICT(lexeme_id, feature)
                    DO UPDATE SET value = ?, source = 'function_word_encoding'
                """, (lexeme_id, feature, str(value), str(value)))
            stats['gram_features_set'] += 1

        print(f"  {lemma}: {list(encoding.keys())}")

    # 3. Enhance Prepositions
    print("\n=== Enhancing Prepositions ===")
    for word, encoding in PREPOSITION_ENCODINGS.items():
        cursor.execute("""
            SELECT id, lemma FROM lexemes
            WHERE LOWER(lemma) = LOWER(?)
            LIMIT 1
        """, (word,))

        row = cursor.fetchone()
        if not row:
            stats['not_found'].append(f"prep:{word}")
            continue

        lexeme_id, lemma = row
        stats['prepositions_enhanced'] += 1

        for feature, value in encoding.items():
            if not dry_run:
                cursor.execute("""
                    INSERT INTO gram_feature_values (lexeme_id, feature, value, source)
                    VALUES (?, ?, ?, 'function_word_encoding')
                    ON CONFLICT(lexeme_id, feature)
                    DO UPDATE SET value = ?, source = 'function_word_encoding'
                """, (lexeme_id, feature, str(value), str(value)))
            stats['gram_features_set'] += 1

        print(f"  {lemma}: {list(encoding.keys())}")

    if not dry_run:
        conn.commit()

    conn.close()
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhance function words in GSE lexicon")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        exit(1)

    print("=== Enhancing Function Words ===")
    print(f"Database: {db_path}")
    print(f"Determiners: {len(DETERMINER_ENCODINGS)}")
    print(f"Conjunctions: {len(CONJUNCTION_ENCODINGS)}")
    print(f"Prepositions: {len(PREPOSITION_ENCODINGS)}")
    print()

    stats = enhance_function_words(db_path, dry_run=args.dry_run)

    print()
    print("=== Summary ===")
    print(f"Determiners enhanced: {stats['determiners_enhanced']}")
    print(f"Conjunctions enhanced: {stats['conjunctions_enhanced']}")
    print(f"Prepositions enhanced: {stats['prepositions_enhanced']}")
    print(f"Gram features set: {stats['gram_features_set']}")
    if stats['not_found']:
        print(f"Not found: {len(stats['not_found'])}")

    if args.dry_run:
        print("\n[DRY RUN] No changes applied")
