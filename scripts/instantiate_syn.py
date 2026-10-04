#!/usr/bin/env python3
"""
Instantiate SYN_* Dimensions for All Words

Creates informational zeros for sentence-level processing.
Each word gets SYN_* dimensions based on its POS (grammatical role):

- Nouns (NN, NNS, NNP, NNPS) -> SYN_SUBJ, SYN_OBJ, SYN_OBJ2, SYN_COMPL
- Verbs (VB, VBD, VBG, VBN, VBP, VBZ) -> SYN_PRED
- Adjectives (JJ, JJR, JJS) -> SYN_ADJ_MOD, SYN_COMPL
- Adverbs (RB, RBR, RBS) -> SYN_ADV_MOD
- Determiners (DT) -> SYN_DET
- Pronouns (PRP, PRP$, WP, WP$) -> SYN_SUBJ, SYN_OBJ
- Prepositions (IN) -> SYN_PP_MOD

This enables O(1) lookup during sentence parsing via pre-computed masks.
"""

import argparse
import sqlite3
from pathlib import Path

# POS to SYN_* dimension mapping
POS_SYN_MAPPING = {
    # Nouns - can be subject, object, complement
    "NN": ["SYN_SUBJ", "SYN_OBJ", "SYN_OBJ2", "SYN_COMPL"],
    "NNS": ["SYN_SUBJ", "SYN_OBJ", "SYN_OBJ2", "SYN_COMPL"],
    "NNP": ["SYN_SUBJ", "SYN_OBJ", "SYN_OBJ2", "SYN_COMPL"],
    "NNPS": ["SYN_SUBJ", "SYN_OBJ", "SYN_OBJ2", "SYN_COMPL"],
    "NOUN": ["SYN_SUBJ", "SYN_OBJ", "SYN_OBJ2", "SYN_COMPL"],
    "n": ["SYN_SUBJ", "SYN_OBJ", "SYN_OBJ2", "SYN_COMPL"],
    # Verbs - predicates
    "VB": ["SYN_PRED"],
    "VBD": ["SYN_PRED"],
    "VBG": ["SYN_PRED", "SYN_ADJ_MOD"],  # Gerunds can modify
    "VBN": ["SYN_PRED", "SYN_ADJ_MOD"],  # Past participles can modify
    "VBP": ["SYN_PRED"],
    "VBZ": ["SYN_PRED"],
    "VERB": ["SYN_PRED"],
    "v": ["SYN_PRED"],
    # Adjectives - modify nouns
    "JJ": ["SYN_ADJ_MOD", "SYN_COMPL"],
    "JJR": ["SYN_ADJ_MOD", "SYN_COMPL"],
    "JJS": ["SYN_ADJ_MOD", "SYN_COMPL"],
    "ADJ": ["SYN_ADJ_MOD", "SYN_COMPL"],
    "a": ["SYN_ADJ_MOD", "SYN_COMPL"],
    # Adverbs - modify verbs/adjectives/other adverbs
    "RB": ["SYN_ADV_MOD"],
    "RBR": ["SYN_ADV_MOD"],
    "RBS": ["SYN_ADV_MOD"],
    "ADV": ["SYN_ADV_MOD"],
    "r": ["SYN_ADV_MOD"],
    # Pronouns - same as nouns
    "PRP": ["SYN_SUBJ", "SYN_OBJ"],
    "PRP$": ["SYN_DET"],  # Possessive pronouns act as determiners
    "WP": ["SYN_SUBJ", "SYN_OBJ"],
    "WP$": ["SYN_DET"],
    "PRON": ["SYN_SUBJ", "SYN_OBJ"],
    # Determiners
    "DT": ["SYN_DET"],
    "PDT": ["SYN_DET"],
    "WDT": ["SYN_DET"],
    "DET": ["SYN_DET"],
    # Prepositions
    "IN": ["SYN_PP_MOD", "SYN_CLAUSE_MOD"],  # IN also includes subordinating conjunctions
    "TO": ["SYN_PP_MOD"],
    "PREP": ["SYN_PP_MOD"],
    "ADP": ["SYN_PP_MOD"],
    # Conjunctions
    "CC": ["SYN_CLAUSE_MOD"],
    "CONJ": ["SYN_CLAUSE_MOD"],
    "CCONJ": ["SYN_CLAUSE_MOD"],
    "SCONJ": ["SYN_CLAUSE_MOD"],
    # Interjections
    "UH": [],
    # Particles
    "RP": [],
    # Others - minimal dimensions
    "FW": [],
    "SYM": [],
    "LS": [],
}


def instantiate_syn_dimensions(db_path: Path, dry_run: bool = False) -> dict:
    """
    Create SYN_* dimension entries for all words based on component_type.

    Since POS is 'unknown' for all words, we use component_type and operator_type:
    - ATOMIC words: default to noun-like (SYN_SUBJ, SYN_OBJ, SYN_COMPL)
    - OPERATOR words: based on operator_type
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {
        "words_processed": 0,
        "dimensions_created": 0,
        "by_dimension": {},
        "by_type": {},
    }

    # Component/operator type to SYN_* mapping
    TYPE_SYN_MAPPING = {
        # ATOMIC words - treat as noun/verb/adj candidates
        ("ATOMIC", None): ["SYN_SUBJ", "SYN_OBJ", "SYN_COMPL", "SYN_PRED", "SYN_ADJ_MOD"],
        # OPERATOR types
        ("OPERATOR", "DETERMINER"): ["SYN_DET"],
        ("OPERATOR", "PREPOSITION"): ["SYN_PP_MOD"],
        ("OPERATOR", "TAM_AUXILIARY"): ["SYN_PRED"],  # Auxiliary verbs
        ("OPERATOR", "DEGREE"): ["SYN_DEGREE_MOD"],
        ("OPERATOR", "NEGATOR"): ["SYN_ADV_MOD"],
        ("OPERATOR", "CONJUNCTION"): ["SYN_CLAUSE_MOD"],
        ("OPERATOR", "COMPLEMENTIZER"): ["SYN_CLAUSE_MOD"],
    }

    # Get all words with their component_type and operator_type
    cursor.execute("""
        SELECT id, lemma, component_type, operator_type FROM lexemes
        ORDER BY frequency_rank
    """)

    words = cursor.fetchall()
    total = len(words)

    print(f"Processing {total} words...")

    for i, (lexeme_id, lemma, component_type, operator_type) in enumerate(words):
        if i % 2000 == 0:
            print(f"  Progress: {i}/{total} ({i * 100 // total}%)")

        # Get SYN_* dimensions based on type
        key = (component_type, operator_type)
        dimensions = TYPE_SYN_MAPPING.get(key, [])

        if not dimensions:
            # Try with None operator_type for ATOMIC
            key = (component_type, None)
            dimensions = TYPE_SYN_MAPPING.get(key, [])

        if not dimensions:
            continue

        stats["words_processed"] += 1
        type_key = f"{component_type}:{operator_type or 'content'}"
        stats["by_type"][type_key] = stats["by_type"].get(type_key, 0) + 1

        for dim in dimensions:
            if not dry_run:
                cursor.execute(
                    """
                    INSERT INTO syn_dimensions (lexeme_id, dimension, instantiated, source)
                    VALUES (?, ?, 0, 'type_mapping')
                    ON CONFLICT(lexeme_id, dimension) DO NOTHING
                """,
                    (lexeme_id, dim),
                )

            stats["dimensions_created"] += 1
            stats["by_dimension"][dim] = stats["by_dimension"].get(dim, 0) + 1

    if not dry_run:
        conn.commit()

    conn.close()
    return stats


def verify_syn_dimensions(db_path: Path) -> None:
    """Show current state of SYN_* dimension instantiation."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=== SYN_* Dimension Verification ===\n")

    # Count by dimension
    cursor.execute("""
        SELECT dimension, COUNT(*) as cnt
        FROM syn_dimensions
        GROUP BY dimension
        ORDER BY cnt DESC
    """)

    rows = cursor.fetchall()
    print("Dimension Distribution:")
    for dim, count in rows:
        print(f"  {dim}: {count} words")

    # Sample words per dimension
    print("\nSample Words by Dimension:")
    for dim, _ in rows[:5]:
        cursor.execute(
            """
            SELECT l.lemma FROM syn_dimensions s
            JOIN lexemes l ON s.lexeme_id = l.id
            WHERE s.dimension = ?
            ORDER BY l.frequency_rank
            LIMIT 5
        """,
            (dim,),
        )
        words = [r[0] for r in cursor.fetchall()]
        print(f"  {dim}: {', '.join(words)}")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Instantiate SYN_* dimensions")
    parser.add_argument("--db", default="data/lexicon.db", help="Database path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--verify", action="store_true", help="Verify current state")
    args = parser.parse_args()

    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        exit(1)

    if args.verify:
        verify_syn_dimensions(db_path)
        exit(0)

    print("=== Instantiating SYN_* Dimensions ===")
    print(f"Database: {db_path}")
    print()

    stats = instantiate_syn_dimensions(db_path, dry_run=args.dry_run)

    print()
    print("=== Summary ===")
    print(f"Words processed: {stats['words_processed']}")
    print(f"Dimensions created: {stats['dimensions_created']}")
    print()
    print("By dimension:")
    for dim, count in sorted(stats["by_dimension"].items(), key=lambda x: -x[1]):
        print(f"  {dim}: {count}")

    if "by_type" in stats and stats["by_type"]:
        print("\nBy component type:")
        for type_key, count in sorted(stats["by_type"].items(), key=lambda x: -x[1]):
            print(f"  {type_key}: {count}")

    if args.dry_run:
        print("\n[DRY RUN] No changes applied")
