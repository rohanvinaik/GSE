#!/usr/bin/env python3
"""
Debug scripts for primitive decomposition quality.

Run checks on the lexicon database to find issues.
"""

import argparse
import sqlite3
from collections import defaultdict

BIPOLAR_PAIRS = [
    ("GOOD", "BAD"),
    ("BIG", "SMALL"),
    ("SAME", "OTHER"),
    ("ALIVE", "DEAD"),
    ("LONG_TIME", "SHORT_TIME"),
    ("BEFORE", "AFTER"),
    ("THEN", "NOW"),
    ("START", "END"),
    ("ABOVE", "BELOW"),
    ("FAR", "NEAR"),
    ("OUTSIDE", "INSIDE"),
    ("TOWARD", "AWAY"),
    ("WITH", "WITHOUT"),
    ("TRUE", "FALSE"),
]


def check_bipolar_violations(conn) -> list:
    """Find words where both poles of a bipolar pair are active."""
    violations = []

    for pole_a, pole_b in BIPOLAR_PAIRS:
        cursor = conn.execute("""
            SELECT l.lemma, pa.value as val_a, pb.value as val_b
            FROM lexemes l
            JOIN primitive_values pa ON l.id = pa.lexeme_id AND pa.primitive = ?
            JOIN primitive_values pb ON l.id = pb.lexeme_id AND pb.primitive = ?
            WHERE pa.value != 0 AND pb.value != 0
            ORDER BY l.frequency_rank
        """, (pole_a, pole_b))

        for lemma, val_a, val_b in cursor.fetchall():
            violations.append({
                "word": lemma,
                "pair": f"{pole_a}/{pole_b}",
                "values": f"{val_a}/{val_b}",
            })

    return violations


def check_primitive_distribution(conn) -> dict:
    """Get distribution of each primitive (how many words activate it)."""
    cursor = conn.execute("""
        SELECT primitive,
               SUM(CASE WHEN value = 1 THEN 1 ELSE 0 END) as positive,
               SUM(CASE WHEN value = -1 THEN 1 ELSE 0 END) as negative,
               SUM(CASE WHEN value = 0 THEN 1 ELSE 0 END) as zero
        FROM primitive_values
        GROUP BY primitive
        ORDER BY positive + negative DESC
    """)

    return {row[0]: {"pos": row[1], "neg": row[2], "zero": row[3]}
            for row in cursor.fetchall()}


def check_words_by_active_count(conn, min_active: int = 0, max_active: int = 100) -> list:
    """Find words with unusual number of active primitives."""
    cursor = conn.execute("""
        SELECT l.lemma, l.frequency_rank,
               SUM(CASE WHEN p.value != 0 THEN 1 ELSE 0 END) as active_count
        FROM lexemes l
        JOIN primitive_values p ON l.id = p.lexeme_id
        GROUP BY l.id
        HAVING active_count >= ? AND active_count <= ?
        ORDER BY active_count DESC, l.frequency_rank
        LIMIT 50
    """, (min_active, max_active))

    return [{"word": row[0], "rank": row[1], "active": row[2]}
            for row in cursor.fetchall()]


def show_word_decomposition(conn, word: str):
    """Show full decomposition for a word."""
    cursor = conn.execute("""
        SELECT p.primitive, p.value, p.confidence, p.source
        FROM lexemes l
        JOIN primitive_values p ON l.id = p.lexeme_id
        WHERE l.lemma = ?
        ORDER BY p.primitive
    """, (word,))

    active = []
    for prim, val, conf, source in cursor.fetchall():
        if val != 0:
            active.append({
                "primitive": prim,
                "value": val,
                "confidence": conf,
                "source": source,
            })

    return active


def check_source_agreement(conn, word: str) -> dict:
    """Check if different sources agree for a word."""
    cursor = conn.execute("""
        SELECT p.primitive, p.value, p.source
        FROM lexemes l
        JOIN primitive_values p ON l.id = p.lexeme_id
        WHERE l.lemma = ?
    """, (word,))

    by_primitive = defaultdict(list)
    for prim, val, source in cursor.fetchall():
        by_primitive[prim].append({"value": val, "source": source})

    return dict(by_primitive)


def main():
    parser = argparse.ArgumentParser(description="Debug primitive decompositions")
    parser.add_argument("--db", default="data/lexicon.db")
    parser.add_argument("--check", choices=["bipolar", "distribution", "active", "word", "all"],
                        default="all")
    parser.add_argument("--word", help="Specific word to inspect")
    parser.add_argument("--min-active", type=int, default=10, help="Min active for check")
    parser.add_argument("--max-active", type=int, default=100, help="Max active for check")

    args = parser.parse_args()

    conn = sqlite3.connect(args.db)

    if args.word:
        print(f"\n=== Decomposition: {args.word} ===")
        active = show_word_decomposition(conn, args.word)
        if active:
            for a in active:
                print(f"  {a['primitive']}: {a['value']} (conf={a['confidence']:.2f}, src={a['source']})")
        else:
            print("  No active primitives found")
        return

    if args.check in ["bipolar", "all"]:
        print("\n=== Bipolar Violations ===")
        violations = check_bipolar_violations(conn)
        if violations:
            for v in violations[:20]:
                print(f"  {v['word']}: {v['pair']} = {v['values']}")
            if len(violations) > 20:
                print(f"  ... and {len(violations) - 20} more")
            print(f"\nTotal violations: {len(violations)}")
        else:
            print("  No violations found!")

    if args.check in ["distribution", "all"]:
        print("\n=== Primitive Distribution (top 20) ===")
        dist = check_primitive_distribution(conn)
        sorted_prims = sorted(dist.items(), key=lambda x: x[1]["pos"] + x[1]["neg"], reverse=True)
        for prim, counts in sorted_prims[:20]:
            total_active = counts["pos"] + counts["neg"]
            print(f"  {prim}: +{counts['pos']} / -{counts['neg']} ({total_active} active)")

    if args.check in ["active", "all"]:
        print(f"\n=== Words with {args.min_active}+ active primitives ===")
        words = check_words_by_active_count(conn, args.min_active, args.max_active)
        for w in words[:20]:
            print(f"  {w['word']} (rank {w['rank']}): {w['active']} active")

    conn.close()


if __name__ == "__main__":
    main()
