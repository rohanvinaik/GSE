#!/usr/bin/env python3
"""
Populate sentence-scale primitives in the lexicon database.

Uses NLP resources (spaCy, AMR) to assign:
1. COMP_* operators to function words (than, how, just, etc.)
2. Default SYN_* primitives based on POS tags
3. TAM features for verbs

This implements the formal semantics mappings from CCG/AMR to our HDC architecture.
"""

from pathlib import Path

from gse.nlp import (
    FUNCTION_WORD_OPERATORS,
    LexiconSentencePrimitivePopulator,
)

DB_PATH = Path("data/lexicon.db")


def main():
    print("=== Populate Sentence-Scale Primitives ===\n")

    # Check database
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    populator = LexiconSentencePrimitivePopulator(str(DB_PATH))

    # 1. Assign COMP_* operators to function words
    print("1. Assigning COMP_* operators to function words...")
    print(f"   Function words to map: {list(FUNCTION_WORD_OPERATORS.keys())}")

    counts = populator.populate_function_words()
    for op, count in sorted(counts.items()):
        print(f"   {op}: {count} lexemes")
    print(f"   Total: {sum(counts.values())} operator assignments\n")

    # 2. Assign default SYN_* primitives by POS
    print("2. Assigning default SYN_* primitives by POS...")
    syn_count = populator.populate_pos_defaults()
    print(f"   Assigned {syn_count} primitive values\n")

    # 3. Verify results
    print("3. Verification...")
    cursor = populator.cursor

    # Count sentence primitive values
    cursor.execute("SELECT COUNT(*) FROM sentence_primitive_values")
    total_spv = cursor.fetchone()[0]
    print(f"   sentence_primitive_values rows: {total_spv}")

    # Count by primitive type
    cursor.execute("""
        SELECT primitive, COUNT(*) as cnt
        FROM sentence_primitive_values
        GROUP BY primitive
        ORDER BY cnt DESC
        LIMIT 15
    """)
    print("   Top primitives by count:")
    for prim, cnt in cursor.fetchall():
        print(f"      {prim}: {cnt}")

    # Count compositional operators in lexemes
    cursor.execute("SELECT COUNT(*) FROM lexemes WHERE comp_primitive IS NOT NULL")
    comp_count = cursor.fetchone()[0]
    print(f"\n   Lexemes with comp_primitive: {comp_count}")

    cursor.execute("""
        SELECT comp_primitive, COUNT(*) as cnt
        FROM lexemes
        WHERE comp_primitive IS NOT NULL
        GROUP BY comp_primitive
    """)
    for prim, cnt in cursor.fetchall():
        print(f"      {prim}: {cnt}")

    # Show example function words
    print("\n4. Sample function word mappings:")
    cursor.execute("""
        SELECT lemma, pos, comp_primitive, comp_arity, comp_operation
        FROM lexemes
        WHERE comp_primitive IS NOT NULL
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]:10} ({row[1]:5}) → {row[2]:15} arity={row[3]} op={row[4]}")

    populator.close()
    print("\n✓ Population complete")


if __name__ == "__main__":
    main()
