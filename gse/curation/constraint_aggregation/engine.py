"""
Constraint Aggregation Engine

Main engine for aggregating constraints from multiple NLP sources.

Strategy:
1. Collect evidence from each source
2. Detect conflicts between sources
3. Score confidence based on agreement and source reliability
4. Apply strict constraint logic:
   - Unanimous agreement + high confidence -> auto-apply
   - ANY disagreement -> flag for review
   - Missing data -> no constraint (let LLM decide)
"""

import logging
from typing import Dict, List

from gse.curation.constraint_aggregation.conflict_detector import (
    detect_conflicts,
    should_flag_for_review,
)
from gse.curation.constraint_aggregation.mapping_registry import (
    SOURCE_PRIMITIVE_COVERAGE,
    SOURCE_RELIABILITY,
    get_evidence_strength,
    get_primitive_constraint_type,
)
from gse.curation.constraint_aggregation.scoring import (
    calculate_constraint_confidence,
    calculate_overall_word_confidence,
    confidence_to_status,
)
from gse.curation.constraint_aggregation.types import (
    PrimitiveConstraint,
    SourceMapping,
    WordConstraintProfile,
)

logger = logging.getLogger(__name__)


class ConstraintAggregationEngine:
    """
    Main engine for aggregating constraints from multiple NLP sources.

    Usage:
        engine = ConstraintAggregationEngine()
        engine.load_sources()
        profile = engine.aggregate_constraints("run")
        auto_apply = profile.get_auto_apply_constraints()
    """

    def __init__(
        self,
        min_auto_apply_confidence: float = 0.8,
        include_large_sources: bool = True,
    ):
        """
        Initialize the engine.

        Args:
            min_auto_apply_confidence: Minimum confidence for auto-apply (default 0.8)
            include_large_sources: Whether to load Wiktionary/ConceptNet (default True)
        """
        self.min_auto_apply_confidence = min_auto_apply_confidence
        self.include_large_sources = include_large_sources
        self.parsers: Dict = {}
        self._loaded = False

    def load_sources(self) -> Dict[str, int]:
        """
        Load all external source parsers.

        Returns:
            Dict of source_name -> entry count (or 'sqlite' for large sources)
        """
        stats = {}

        # Load NLTK-based parsers (small, always load)
        nltk_parsers = [
            ("sentiwordnet", "SentiWordNetParser"),
            ("nrc_emotion", "NRCEmotionParser"),
            ("nrc_vad", "NRCVADParser"),
            ("verbnet", "VerbNetParser"),
            ("concreteness", "ConcretenessParser"),
            ("lancaster_sensorimotor", "LancasterSensorimotorParser"),
            ("framenet", "FrameNetParser"),
            ("propbank", "PropBankParser"),
            ("wordnet_hierarchy", "WordNetHierarchyParser"),
            ("usas", "USASParser"),
        ]

        for source_name, class_name in nltk_parsers:
            try:
                module = __import__(f"gse.curation.external_sources.{source_name}", fromlist=[class_name])
                parser_class = getattr(module, class_name)
                parser = parser_class()
                if parser.load():
                    self.parsers[source_name] = parser
                    count = len(parser.entries) if hasattr(parser, "entries") else 0
                    stats[source_name] = count
                    logger.info(f"Loaded {source_name}: {count} entries")
            except Exception as e:
                logger.debug(f"{source_name} not available: {e}")

        # Load large sources (SQLite-based)
        if self.include_large_sources:
            # Wiktionary
            try:
                from gse.curation.external_sources.wiktionary import WiktionaryParser

                parser = WiktionaryParser()
                if parser.load():
                    self.parsers["wiktionary"] = parser
                    stats["wiktionary"] = "sqlite"
                    logger.info("Loaded wiktionary (SQLite)")
            except Exception as e:
                logger.debug(f"Wiktionary not available: {e}")

            # ConceptNet
            try:
                from gse.curation.external_sources.conceptnet import ConceptNetParser

                parser = ConceptNetParser()
                if parser.load():
                    self.parsers["conceptnet"] = parser
                    stats["conceptnet"] = "sqlite"
                    logger.info("Loaded conceptnet (SQLite)")
            except Exception as e:
                logger.debug(f"ConceptNet not available: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self.parsers)} sources: {list(self.parsers.keys())}")
        return stats

    def collect_raw_source_data(self, word: str) -> Dict[str, str]:
        """
        Collect raw data from each source for LLM context.

        Returns human-readable summaries of what each source says about the word.
        This is used by the LLM as context for translation decisions.
        """
        raw_data = {}

        for source_name, parser in self.parsers.items():
            try:
                # Get primitives (the interpretation)
                primitives = parser.to_primitives(word)

                if primitives:
                    # Format as readable summary
                    active = [f"{k}={v}" for k, v in primitives.items() if v != 0]
                    if active:
                        raw_data[source_name] = ", ".join(active)

            except Exception as e:
                logger.debug(f"Error getting raw data from {source_name}: {e}")

        return raw_data

    def collect_evidence(self, word: str) -> Dict[str, List[SourceMapping]]:
        """
        Collect all evidence for a word from all sources.

        Args:
            word: The word to look up

        Returns:
            Dict of primitive -> list of SourceMapping
        """
        if not self._loaded:
            self.load_sources()

        evidence: Dict[str, List[SourceMapping]] = {}

        for source_name, parser in self.parsers.items():
            try:
                # Get raw primitives from parser
                primitives = parser.to_primitives(word)

                # Convert to SourceMapping objects with metadata
                for prim, value in primitives.items():
                    if value == 0:
                        continue

                    # Determine constraint type and strength
                    constraint_type = get_primitive_constraint_type(source_name, prim)
                    strength = get_evidence_strength(constraint_type)

                    mapping = SourceMapping(
                        source_name=source_name,
                        source_concept=f"{source_name}:{prim}",
                        target_primitive=prim,
                        target_value=value,
                        constraint_type=constraint_type,
                        evidence_strength=strength,
                    )

                    evidence.setdefault(prim, []).append(mapping)

            except Exception as e:
                logger.debug(f"Error collecting evidence from {source_name} for '{word}': {e}")

        return evidence

    def aggregate_constraints(self, word: str) -> WordConstraintProfile:
        """
        Aggregate constraints for a word from all sources.

        This is the main entry point for constraint aggregation.

        Args:
            word: The word to process

        Returns:
            Complete WordConstraintProfile with constraints, conflicts, and metadata
        """
        evidence = self.collect_evidence(word)
        raw_source_data = self.collect_raw_source_data(word)

        # Track sources
        sources_checked = list(self.parsers.keys())
        sources_with_data = list(set(mapping.source_name for mappings in evidence.values() for mapping in mappings))

        # Build constraints per primitive
        constraints: Dict[str, PrimitiveConstraint] = {}

        for prim, mappings in evidence.items():
            # Separate by value
            positive_mappings = [m for m in mappings if m.target_value > 0]
            negative_mappings = [m for m in mappings if m.target_value < 0]

            # Determine final value (majority)
            if len(positive_mappings) > len(negative_mappings):
                final_value = +1
                supporting = positive_mappings
                conflicting = negative_mappings
            elif len(negative_mappings) > len(positive_mappings):
                final_value = -1
                supporting = negative_mappings
                conflicting = positive_mappings
            else:
                # Tie - use evidence strength as tiebreaker
                pos_strength = sum(m.evidence_strength.value for m in positive_mappings)
                neg_strength = sum(m.evidence_strength.value for m in negative_mappings)
                if pos_strength >= neg_strength:
                    final_value = +1
                    supporting = positive_mappings
                    conflicting = negative_mappings
                else:
                    final_value = -1
                    supporting = negative_mappings
                    conflicting = positive_mappings

            # Calculate confidence
            confidence = calculate_constraint_confidence(supporting, conflicting, SOURCE_RELIABILITY)

            # Determine status
            has_conflict = len(conflicting) > 0
            status = confidence_to_status(
                confidence,
                has_conflict,
                min_auto_apply=self.min_auto_apply_confidence,
            )

            constraints[prim] = PrimitiveConstraint(
                primitive=prim,
                value=final_value,
                confidence=confidence,
                supporting_sources=[m.source_name for m in supporting],
                conflicting_sources=[m.source_name for m in conflicting],
                evidence_records=mappings,
                status=status,
            )

        # Detect conflicts
        conflicts = detect_conflicts(evidence)

        # Calculate overall confidence
        overall_confidence = calculate_overall_word_confidence(constraints, sources_with_data, len(self.parsers))

        # Determine review requirement
        review_required, review_reasons = should_flag_for_review(conflicts, overall_confidence)

        return WordConstraintProfile(
            word=word,
            pos=None,  # Could be enhanced to handle POS
            sources_checked=sources_checked,
            sources_with_data=sources_with_data,
            constraints=constraints,
            conflicts=conflicts,
            overall_confidence=overall_confidence,
            review_required=review_required,
            review_reasons=review_reasons,
            raw_source_data=raw_source_data,
        )

    def get_sources_for_primitive(self, primitive: str) -> List[str]:
        """Get all loaded sources that can inform a given primitive."""
        sources = []
        for source_name in self.parsers.keys():
            coverage = SOURCE_PRIMITIVE_COVERAGE.get(source_name, {})
            all_prims = set(coverage.get("definitive", [])) | set(coverage.get("inferential", []))
            if primitive in all_prims:
                sources.append(source_name)
        return sources

    def close(self):
        """Close all parser connections."""
        for parser in self.parsers.values():
            if hasattr(parser, "close"):
                parser.close()
        self.parsers.clear()
        self._loaded = False


# Convenience function for quick testing
def test_word(word: str, verbose: bool = True) -> WordConstraintProfile:
    """
    Quick test function to aggregate constraints for a word.

    Usage:
        from gse.curation.constraint_aggregation.engine import test_word
        profile = test_word("run")
    """
    engine = ConstraintAggregationEngine(include_large_sources=False)
    engine.load_sources()

    profile = engine.aggregate_constraints(word)

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"Word: {profile.word}")
        print(f"Sources with data: {profile.sources_with_data}")
        print(f"Overall confidence: {profile.overall_confidence}")
        print(f"Review required: {profile.review_required}")
        if profile.review_required:
            print(f"Review reasons: {profile.review_reasons}")
        print(f"\nConstraints ({len(profile.constraints)}):")
        for prim, c in sorted(profile.constraints.items()):
            status_icon = "✓" if c.status == "auto_apply" else "?" if c.status == "flag_review" else "×"
            print(f"  {status_icon} {prim}: {c.value:+d} (conf={c.confidence:.2f}, {c.status})")
            if c.conflicting_sources:
                print(f"      CONFLICT: {c.supporting_sources} vs {c.conflicting_sources}")
        if profile.conflicts:
            print(f"\nConflicts ({len(profile.conflicts)}):")
            for c in profile.conflicts:
                print(f"  - {c.primitive}: {c.conflict_type} ({c.severity})")
        print(f"{'=' * 60}\n")

    return profile


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)

    # Test with some words
    test_words = ["run", "think", "love", "dog", "happy", "give"]
    for word in test_words:
        test_word(word)
