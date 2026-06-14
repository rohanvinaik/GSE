#!/usr/bin/env python3
"""
Tag lexemes with POS using spaCy.

This assigns accurate POS tags to lexemes that currently have 'unknown' POS,
enabling proper sentence-scale primitive assignment.
"""

import sqlite3
from pathlib import Path

import spacy

DB_PATH = Path("data/lexicon.db")
BATCH_SIZE = 500


def main():
    print("=== Tag Lexemes with POS ===\n")

    # Load spaCy
    print("Loading spaCy model...")
    nlp = spacy.load("en_core_web_sm")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get lexemes with unknown POS
    cursor.execute("""
        SELECT id, lemma FROM lexemes
        WHERE pos = 'unknown' OR pos IS NULL
    """)
    lexemes = cursor.fetchall()
    print(f"Lexemes to tag: {len(lexemes)}")

    if not lexemes:
        print("No lexemes need tagging.")
        return

    # Process in batches
    updated = 0
    pos_counts = {}

    for i in range(0, len(lexemes), BATCH_SIZE):
        batch = lexemes[i:i+BATCH_SIZE]

        for lexeme_id, lemma in batch:
            # Parse the lemma to get POS
            doc = nlp(lemma)
            if doc and len(doc) > 0:
                # Use the POS of the first token (for multi-word, use first)
                pos = doc[0].pos_

                cursor.execute(
                    "UPDATE lexemes SET pos = ? WHERE id = ?",
                    (pos, lexeme_id)
                )
                updated += 1
                pos_counts[pos] = pos_counts.get(pos, 0) + 1

        conn.commit()
        print(f"  Processed {min(i+BATCH_SIZE, len(lexemes))}/{len(lexemes)}", end="\r")

    conn.commit()
    print(f"\n\nUpdated {updated} lexemes")

    print("\nPOS distribution:")
    for pos, count in sorted(pos_counts.items(), key=lambda x: -x[1]):
        print(f"  {pos}: {count}")

    conn.close()
    print("\n✓ POS tagging complete")


if __name__ == "__main__":
    main()
