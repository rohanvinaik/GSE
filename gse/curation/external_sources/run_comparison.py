#!/usr/bin/env python3
"""
Run External Sources Comparison

Compares LLM-generated primitives against external sources for all words
in the lexicon database. Stores disagreements for review.

Usage:
    python -m gse.curation.external_sources.run_comparison
    python -m gse.curation.external_sources.run_comparison --phase 1
    python -m gse.curation.external_sources.run_comparison --report-only
"""

import argparse
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional

from gse.curation.external_sources.comparator import (
    ComparisonResult,
    ExternalSourcesComparator,
)
from gse.curation.lexicon_db import LexiconDatabase

logger = logging.getLogger(__name__)


def run_comparison(
    db_path: str = "data/lexicon.db",
    phase: Optional[int] = None,
    limit: Optional[int] = None,
    download_sources: bool = False,
) -> Dict[str, any]:
    """
    Run comparison between LLM decompositions and external sources.

    Args:
        db_path: Path to lexicon database
        phase: Only compare words from this phase (None = all)
        limit: Maximum words to compare
        download_sources: Whether to download missing external sources

    Returns:
        Statistics about the comparison
    """
    logger.info("Starting external sources comparison...")

    # Initialize components
    db = LexiconDatabase(db_path)
    comparator = ExternalSourcesComparator()

    # Download sources if requested
    if download_sources:
        logger.info("Downloading external sources...")
        from gse.curation.external_sources.integrator import download_all_sources
        download_all_sources()

    # Load external sources
    source_stats = comparator.load_all_sources()
    logger.info(f"Loaded sources: {list(source_stats.keys())}")

    # Get validated words from database
    if phase is not None:
        entries = db.get_validated_entries(phase=phase)
    else:
        entries = db.get_validated_entries()

    if limit:
        entries = entries[:limit]

    logger.info(f"Comparing {len(entries)} words against external sources...")

    # Run comparison for each word
    results: Dict[str, ComparisonResult] = {}
    disagreements_to_store = []
    coverage_to_store = []

    for i, entry in enumerate(entries):
        if (i + 1) % 500 == 0:
            logger.info(f"Progress: {i + 1}/{len(entries)}")

        # Get LLM decomposition (already stored)
        llm_primitives = entry.decomposition

        # Compare against external sources
        comparison = comparator.compare(entry.lemma, llm_primitives)
        results[entry.lemma] = comparison

        # Collect disagreements for batch storage
        for d in comparison.disagreements:
            disagreements_to_store.append((
                entry.id,
                d.primitive,
                d.llm_value,
                d.external_value,
                d.external_source,
                d.severity,
            ))

        # Collect coverage stats
        for source_name, ext_prims in comparison.external_primitives.items():
            matched = len(ext_prims)
            agreed = sum(1 for p in ext_prims if llm_primitives.get(p, 0) == ext_prims[p])
            coverage_to_store.append((
                entry.id,
                source_name,
                matched,
                agreed,
            ))

    # Store results in database
    if disagreements_to_store:
        logger.info(f"Storing {len(disagreements_to_store)} disagreements...")
        db.store_disagreements_batch(disagreements_to_store)

    for lexeme_id, source_name, matched, agreed in coverage_to_store:
        db.store_source_coverage(lexeme_id, source_name, matched, agreed)

    # Calculate statistics
    stats = calculate_stats(results)
    stats["source_stats"] = source_stats

    # Log summary
    logger.info("=" * 60)
    logger.info("COMPARISON COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Words compared: {stats['total_words']}")
    logger.info(f"Words with external data: {stats['words_with_external']}")
    logger.info(f"Total disagreements: {stats['total_disagreements']}")
    logger.info(f"Major disagreements: {stats['major_disagreements']}")
    logger.info(f"Words needing review: {stats['words_needing_review']}")
    logger.info(f"Average agreement rate: {stats['avg_agreement_rate']:.1%}")

    db.close()
    return stats


def calculate_stats(results: Dict[str, ComparisonResult]) -> Dict[str, any]:
    """Calculate comparison statistics."""
    stats = {
        "total_words": len(results),
        "words_with_external": 0,
        "total_disagreements": 0,
        "major_disagreements": 0,
        "words_needing_review": 0,
        "avg_agreement_rate": 0.0,
        "by_severity": defaultdict(int),
        "by_source": defaultdict(int),
        "by_primitive": defaultdict(int),
    }

    agreement_rates = []

    for word, result in results.items():
        if result.external_primitives:
            stats["words_with_external"] += 1
            agreement_rates.append(result.agreement_rate)

        if result.needs_review:
            stats["words_needing_review"] += 1

        for d in result.disagreements:
            stats["total_disagreements"] += 1
            stats["by_severity"][d.severity] += 1
            stats["by_source"][d.external_source] += 1
            stats["by_primitive"][d.primitive] += 1

            if d.severity in ("major", "sign_flip"):
                stats["major_disagreements"] += 1

    if agreement_rates:
        stats["avg_agreement_rate"] = sum(agreement_rates) / len(agreement_rates)

    # Convert defaultdicts to regular dicts
    stats["by_severity"] = dict(stats["by_severity"])
    stats["by_source"] = dict(stats["by_source"])
    stats["by_primitive"] = dict(stats["by_primitive"])

    return stats


def generate_report(
    db_path: str = "data/lexicon.db",
    output_path: Optional[str] = None,
) -> str:
    """Generate a detailed disagreement report."""
    db = LexiconDatabase(db_path)

    # Get disagreement stats
    stats = db.get_disagreement_stats()

    # Get some example disagreements
    major_disagreements = db.get_disagreements(severity="sign_flip", unresolved_only=True)
    minor_disagreements = db.get_disagreements(severity="minor", unresolved_only=True)

    report_lines = [
        "# External Sources Disagreement Report",
        "",
        "## Summary",
        f"- Total disagreements: {stats.get('total', 0)}",
        f"- Unresolved: {stats.get('unresolved', 0)}",
        "",
        "### By Severity",
    ]

    for severity, count in stats.get("by_severity", {}).items():
        report_lines.append(f"- {severity}: {count}")

    report_lines.extend([
        "",
        "### By Source",
    ])

    for source, count in stats.get("by_source", {}).items():
        report_lines.append(f"- {source}: {count}")

    # Top sign-flip disagreements (most concerning)
    if major_disagreements:
        report_lines.extend([
            "",
            "## Sign-Flip Disagreements (Top 20)",
            "These are cases where LLM and external sources have opposite signs:",
            "",
        ])
        for d in major_disagreements[:20]:
            # Get the word
            entry = db.get_lexeme_by_id(d["lexeme_id"])
            word = entry.lemma if entry else "unknown"
            report_lines.append(
                f"- **{word}**.{d['primitive']}: LLM={d['llm_value']} vs {d['external_source']}={d['external_value']}"
            )

    db.close()

    report = "\n".join(report_lines)

    if output_path:
        Path(output_path).write_text(report)
        logger.info(f"Report saved to {output_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Run external sources comparison")
    parser.add_argument("--db", default="data/lexicon.db", help="Lexicon database path")
    parser.add_argument("--phase", type=int, help="Only compare words from this phase")
    parser.add_argument("--limit", type=int, help="Maximum words to compare")
    parser.add_argument("--download", action="store_true", help="Download missing sources")
    parser.add_argument("--report-only", action="store_true", help="Only generate report")
    parser.add_argument("--report-output", help="Output path for report")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    if args.report_only:
        report = generate_report(args.db, args.report_output)
        print(report)
    else:
        stats = run_comparison(
            db_path=args.db,
            phase=args.phase,
            limit=args.limit,
            download_sources=args.download,
        )

        # Print detailed stats
        print("\n" + "=" * 60)
        print("DETAILED STATISTICS")
        print("=" * 60)

        print("\nDisagreements by Severity:")
        for severity, count in stats.get("by_severity", {}).items():
            print(f"  {severity}: {count}")

        print("\nDisagreements by Source:")
        for source, count in sorted(stats.get("by_source", {}).items(), key=lambda x: -x[1])[:10]:
            print(f"  {source}: {count}")

        print("\nMost Contested Primitives (top 10):")
        for prim, count in sorted(stats.get("by_primitive", {}).items(), key=lambda x: -x[1])[:10]:
            print(f"  {prim}: {count}")


if __name__ == "__main__":
    main()
