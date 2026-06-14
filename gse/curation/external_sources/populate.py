"""
External-sources-first lexicon population.

Closes the SWKE pipeline loop: the integrator discovers words and votes on
primitive values across external sources, but only returns ExternalWordData.
This module is the Store step — it writes those entries into the lexicon
database (lexemes + primitive_values + decomposition_provenance) with full
source provenance.

Typical usage:
    stats = populate_lexicon_from_external("lexicon.db", min_sources=2)
    print(stats.lexemes_added, "new lexemes from external sources")
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from gse.curation.external_sources.integrator import (
    ExternalSourcesIntegrator,
    ExternalWordData,
)
from gse.curation.lexicon_db import LexiconDatabase

logger = logging.getLogger(__name__)


@dataclass
class PopulationStats:
    """Counts produced by a population run."""
    lexemes_added: int = 0
    lexemes_skipped_existing: int = 0
    primitives_set: int = 0
    provenance_rows: int = 0
    words_filtered_no_primitives: int = 0


def populate_from_entries(
    db: LexiconDatabase,
    entries: List[ExternalWordData],
    default_pos: str = "n",
) -> PopulationStats:
    """
    Write a batch of ExternalWordData entries into the lexicon database.

    Each entry that has at least one primitive becomes a lexeme row with its
    72-primitive decomposition and a provenance record naming the contributing
    sources. Entries whose lemma already exists in the database are skipped,
    making this idempotent under re-run.

    Args:
        db: open LexiconDatabase
        entries: voting results from the integrator
        default_pos: part-of-speech to record (external sources rarely supply one)

    Returns:
        PopulationStats with row counts for the write.
    """
    stats = PopulationStats()

    for entry in entries:
        lemma = entry.word.lower()

        if not entry.primitives:
            stats.words_filtered_no_primitives += 1
            continue

        if db.get_lexeme(lemma, default_pos) is not None:
            stats.lexemes_skipped_existing += 1
            continue

        confidences = entry.confidence_scores
        avg_conf = (
            sum(confidences.values()) / len(confidences) if confidences else 0.0
        )

        lexeme_id = db.add_lexeme(
            lemma=lemma,
            pos=default_pos,
            source="external_sources_voting",
            confidence=avg_conf,
        )
        stats.lexemes_added += 1

        db.set_decomposition(
            lexeme_id=lexeme_id,
            decomposition=entry.primitives,
            source="external_sources_voting",
            confidences=confidences,
        )
        stats.primitives_set += len(entry.primitives)

        sources_str = ",".join(sorted(set(entry.sources)))
        db.add_provenance(
            lexeme_id=lexeme_id,
            source_type="external",
            source_detail=sources_str,
            confidence_after=avg_conf,
        )
        stats.provenance_rows += 1

    return stats


def populate_lexicon_from_external(
    db_path: str,
    min_sources: int = 2,
    min_confidence: float = 0.5,
    default_pos: str = "n",
    limit: Optional[int] = None,
) -> PopulationStats:
    """
    Top-level orchestrator: load external sources, vote, write to lexicon.

    Args:
        db_path: path to lexicon SQLite database
        min_sources: minimum external sources that must agree on a word
        min_confidence: minimum per-primitive vote ratio to keep that primitive
        default_pos: POS recorded for inserted lexemes
        limit: cap on number of entries to write (None = all)

    Returns:
        PopulationStats summarizing the run.
    """
    integrator = ExternalSourcesIntegrator(db_path)
    try:
        integrator.load_all_sources()
        entries = integrator.get_prefilled_entries(
            min_sources=min_sources,
            min_confidence=min_confidence,
        )
        if limit is not None:
            entries = entries[:limit]

        assert integrator.lexicon_db is not None
        stats = populate_from_entries(
            integrator.lexicon_db,
            entries,
            default_pos=default_pos,
        )
    finally:
        integrator.close()

    logger.info(
        "Populated %d lexemes (%d primitive values, %d provenance rows); "
        "skipped %d existing, %d without primitives",
        stats.lexemes_added,
        stats.primitives_set,
        stats.provenance_rows,
        stats.lexemes_skipped_existing,
        stats.words_filtered_no_primitives,
    )
    return stats


def populate_with_voting_and_exclusion(
    db_path: str,
    words: Optional[List[str]] = None,
    source_confidence: Optional[dict] = None,
    default_confidence: float = 1.0,
    min_sources: int = 1,
    default_pos: str = "n",
    limit: Optional[int] = None,
) -> PopulationStats:
    """
    Rebuild-grade population: confidence-weighted voting + bipolar exclusion.

    Calls ``ExternalSourcesIntegrator.aggregate_primitives_weighted`` for each
    word, which runs the ported voting formula and then enforces NSM bipolar
    mutual exclusion. Each surviving primitive carries its confidence; each
    bipolar conflict is recorded in the lexeme's provenance trail.

    Args:
        db_path: path to lexicon SQLite database (writes here)
        words: explicit list of words to process. ``None`` means
            "every word that appears in any loaded external source"
            (via ``integrator.get_all_words()``).
        source_confidence: per-source prior confidence overrides
            (e.g., ``{"nrc_emotion": 0.9, "conceptnet": 0.6}``).
        default_confidence: confidence used for sources without a prior.
        min_sources: minimum sources that must contribute for the word
            to be written. Drops orphan-source entries.
        default_pos: POS recorded for inserted lexemes.
        limit: cap on the number of words to process.

    Returns:
        PopulationStats summarizing the run.
    """
    integrator = ExternalSourcesIntegrator(db_path)
    stats = PopulationStats()
    try:
        integrator.load_all_sources()
        if words is None:
            # Spine of the rebuild: Wiktionary v2's 1.3M deterministically-
            # decomposed words. Falls back to all-sources union if v2 isn't
            # loaded.
            words = sorted(integrator.get_primary_lexeme_words())
        if limit is not None:
            words = words[:limit]

        assert integrator.lexicon_db is not None
        db = integrator.lexicon_db

        for word in words:
            data = integrator.aggregate_primitives_weighted(
                word,
                source_confidence=source_confidence,
                default_confidence=default_confidence,
            )

            if not data.primitives:
                stats.words_filtered_no_primitives += 1
                continue
            if len(data.sources) < min_sources:
                stats.words_filtered_no_primitives += 1
                continue
            if db.get_lexeme(data.word, default_pos) is not None:
                stats.lexemes_skipped_existing += 1
                continue

            confidences = data.confidence_scores
            avg_conf = (
                sum(confidences.values()) / len(confidences) if confidences else 0.0
            )

            lexeme_id = db.add_lexeme(
                lemma=data.word,
                pos=default_pos,
                source="external_sources_weighted",
                confidence=avg_conf,
            )
            stats.lexemes_added += 1

            db.set_decomposition(
                lexeme_id=lexeme_id,
                decomposition=data.primitives,
                source="external_sources_weighted",
                confidences=confidences,
            )
            stats.primitives_set += len(data.primitives)

            source_detail = ",".join(sorted(set(data.sources)))
            if data.suppressions:
                suppressions_repr = ";".join(
                    f"{s['dropped']}->{s['kept']}@{s['kept_confidence']:.2f}"
                    for s in data.suppressions
                )
                source_detail = f"{source_detail}|suppressed:{suppressions_repr}"

            db.add_provenance(
                lexeme_id=lexeme_id,
                source_type="external_weighted",
                source_detail=source_detail,
                confidence_after=avg_conf,
            )
            stats.provenance_rows += 1
    finally:
        integrator.close()

    logger.info(
        "Weighted+exclusion populated %d lexemes (%d primitive values, %d provenance "
        "rows); skipped %d existing, %d without primitives",
        stats.lexemes_added,
        stats.primitives_set,
        stats.provenance_rows,
        stats.lexemes_skipped_existing,
        stats.words_filtered_no_primitives,
    )
    return stats


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Populate lexicon from external sources via majority voting",
    )
    parser.add_argument("--db", default="lexicon.db", help="Lexicon SQLite path")
    parser.add_argument("--min-sources", type=int, default=2, help="Min agreeing sources")
    parser.add_argument(
        "--min-confidence", type=float, default=0.5, help="Min per-primitive vote ratio"
    )
    parser.add_argument("--default-pos", default="n", help="Default part-of-speech")
    parser.add_argument("--limit", type=int, default=None, help="Cap on entries written")

    args = parser.parse_args()

    stats = populate_lexicon_from_external(
        db_path=args.db,
        min_sources=args.min_sources,
        min_confidence=args.min_confidence,
        default_pos=args.default_pos,
        limit=args.limit,
    )

    print("\n=== Population complete ===")
    print(f"  lexemes added:                 {stats.lexemes_added}")
    print(f"  primitive values written:      {stats.primitives_set}")
    print(f"  provenance rows:               {stats.provenance_rows}")
    print(f"  skipped (already in lexicon):  {stats.lexemes_skipped_existing}")
    print(f"  filtered (no primitives):      {stats.words_filtered_no_primitives}")
