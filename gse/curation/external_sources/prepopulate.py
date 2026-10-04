"""
Pre-populate Primitives from External Sources

Uses 6 external lexical resources to pre-fill primitive values
with confidence scores. Unknown primitives are left as NULL.
"""

import logging
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List

from gse.curation.external_sources.comparator import ExternalSourcesComparator
from gse.curation.schema import ALL_PRIMITIVES

logger = logging.getLogger(__name__)


@dataclass
class PrimitiveEvidence:
    """Evidence for a primitive value from external sources."""

    primitive: str
    value: int  # +1 or -1
    sources: List[str]
    confidence: float  # 0.0 to 1.0


def aggregate_external_evidence(
    word: str,
    comparator: ExternalSourcesComparator,
) -> Dict[str, PrimitiveEvidence]:
    """
    Aggregate primitive evidence from all external sources.

    Returns dict of primitive -> PrimitiveEvidence for primitives
    where we have confident data. Primitives without evidence are omitted.
    """
    evidence: Dict[str, Dict[int, List[str]]] = defaultdict(lambda: defaultdict(list))

    # Collect from each source
    for source_name, parser in comparator.parsers.items():
        primitives = parser.to_primitives(word)
        for prim, value in primitives.items():
            if value != 0:
                evidence[prim][value].append(source_name)

    # Aggregate into PrimitiveEvidence
    results = {}
    for prim, value_sources in evidence.items():
        if not value_sources:
            continue

        # Find majority value
        best_value = max(value_sources.keys(), key=lambda v: len(value_sources[v]))
        sources = value_sources[best_value]

        # Confidence based on:
        # - Number of agreeing sources
        # - Whether there's disagreement
        n_agree = len(sources)
        n_disagree = sum(len(s) for v, s in value_sources.items() if v != best_value)

        if n_disagree > 0:
            # Disagreement reduces confidence
            confidence = n_agree / (n_agree + n_disagree) * 0.8
        else:
            # Agreement boosts confidence
            confidence = min(0.5 + 0.15 * n_agree, 0.95)

        results[prim] = PrimitiveEvidence(
            primitive=prim,
            value=best_value,
            sources=sources,
            confidence=confidence,
        )

    return results


def prepopulate_from_external(
    db_path: str,
    min_confidence: float = 0.5,
    reset_existing: bool = False,
) -> Dict[str, int]:
    """
    Pre-populate primitive_values from external sources.

    Args:
        db_path: Path to lexicon database
        min_confidence: Minimum confidence to accept a value
        reset_existing: If True, clear existing primitive_values first

    Returns:
        Stats dict with counts
    """
    logger.info("Loading external sources...")
    comparator = ExternalSourcesComparator()
    source_stats = comparator.load_all_sources()
    logger.info(f"Loaded {len(source_stats)} sources")

    conn = sqlite3.connect(db_path)

    if reset_existing:
        logger.info("Clearing existing primitive_values...")
        conn.execute("DELETE FROM primitive_values")
        conn.commit()

    # Get all lexemes
    cursor = conn.execute("SELECT id, lemma FROM lexemes")
    lexemes = cursor.fetchall()
    logger.info(f"Processing {len(lexemes)} words...")

    stats = {
        "words_processed": 0,
        "words_with_evidence": 0,
        "primitives_filled": 0,
        "by_source": defaultdict(int),
    }

    batch_size = 500
    for i in range(0, len(lexemes), batch_size):
        batch = lexemes[i : i + batch_size]

        for lex_id, lemma in batch:
            evidence = aggregate_external_evidence(lemma.lower(), comparator)

            if evidence:
                stats["words_with_evidence"] += 1

                for prim, ev in evidence.items():
                    if ev.confidence >= min_confidence:
                        # Insert with source tracking
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO primitive_values
                            (lexeme_id, primitive, value, confidence, source)
                            VALUES (?, ?, ?, ?, ?)
                        """,
                            (lex_id, prim, ev.value, ev.confidence, ",".join(ev.sources)),
                        )

                        stats["primitives_filled"] += 1
                        for src in ev.sources:
                            stats["by_source"][src] += 1

            stats["words_processed"] += 1

        conn.commit()

        if (i + batch_size) % 2000 == 0:
            logger.info(f"Progress: {i + batch_size}/{len(lexemes)}")

    conn.close()
    stats["by_source"] = dict(stats["by_source"])

    logger.info(f"Pre-population complete: {stats}")
    return stats


def get_missing_primitives(
    db_path: str,
    lexeme_id: int,
) -> List[str]:
    """Get primitives that are NULL/missing for a lexeme."""
    conn = sqlite3.connect(db_path)

    cursor = conn.execute("SELECT primitive FROM primitive_values WHERE lexeme_id = ?", (lexeme_id,))
    filled = {row[0] for row in cursor.fetchall()}

    conn.close()

    return [p for p in ALL_PRIMITIVES if p not in filled]


def get_prefill_summary(db_path: str) -> Dict[str, any]:
    """Get summary of pre-filled vs missing primitives."""
    conn = sqlite3.connect(db_path)

    # Total lexemes
    cursor = conn.execute("SELECT COUNT(*) FROM lexemes")
    total_lexemes = cursor.fetchone()[0]

    # Primitives filled
    cursor = conn.execute("SELECT COUNT(*) FROM primitive_values WHERE value != 0")
    filled_nonzero = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(DISTINCT lexeme_id) FROM primitive_values")
    lexemes_with_data = cursor.fetchone()[0]

    # By primitive
    cursor = conn.execute("""
        SELECT primitive, COUNT(*)
        FROM primitive_values
        WHERE value != 0
        GROUP BY primitive
        ORDER BY COUNT(*) DESC
    """)
    by_primitive = dict(cursor.fetchall())

    # By source
    cursor = conn.execute("""
        SELECT source, COUNT(*)
        FROM primitive_values
        GROUP BY source
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    by_source = dict(cursor.fetchall())

    conn.close()

    return {
        "total_lexemes": total_lexemes,
        "lexemes_with_data": lexemes_with_data,
        "primitives_filled": filled_nonzero,
        "avg_per_word": filled_nonzero / max(lexemes_with_data, 1),
        "coverage": lexemes_with_data / max(total_lexemes, 1),
        "top_primitives": dict(list(by_primitive.items())[:10]),
        "by_source": by_source,
    }


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Pre-populate primitives from external sources")
    parser.add_argument("--db", default="data/lexicon.db", help="Lexicon database path")
    parser.add_argument("--min-confidence", type=float, default=0.5, help="Minimum confidence threshold")
    parser.add_argument("--reset", action="store_true", help="Reset existing primitive_values")
    parser.add_argument("--summary-only", action="store_true", help="Only show summary")

    args = parser.parse_args()

    if args.summary_only:
        summary = get_prefill_summary(args.db)
        print("\n=== Pre-fill Summary ===")
        for key, value in summary.items():
            print(f"{key}: {value}")
    else:
        stats = prepopulate_from_external(
            db_path=args.db,
            min_confidence=args.min_confidence,
            reset_existing=args.reset,
        )

        print("\n=== Pre-population Complete ===")
        for key, value in stats.items():
            print(f"{key}: {value}")
