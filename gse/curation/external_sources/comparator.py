"""
External Sources Comparator

Compares LLM-generated primitive decompositions against external sources.
Flags disagreements for review rather than pre-filling primitives.

Strategy:
1. LLM generates ALL primitives independently
2. External sources provide their mappings
3. Compare and flag disagreements (LLM vs External)
4. High disagreement = lower confidence, needs review
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DisagreementRecord:
    """Records a disagreement between LLM and external source."""

    primitive: str
    llm_value: int
    external_value: int
    external_source: str
    severity: str  # 'minor' (0 vs ±1), 'major' (±1 vs ∓1), 'sign_flip'

    def __repr__(self):
        return (
            f"{self.primitive}: LLM={self.llm_value} vs {self.external_source}={self.external_value} ({self.severity})"
        )


@dataclass
class ComparisonResult:
    """Result of comparing LLM decomposition with external sources."""

    word: str
    llm_primitives: Dict[str, int]
    external_primitives: Dict[str, Dict[str, int]]  # source -> {primitive: value}
    disagreements: List[DisagreementRecord] = field(default_factory=list)
    agreements: List[str] = field(default_factory=list)  # primitives that agree
    confidence_adjustment: float = 0.0  # -1.0 to +1.0
    needs_review: bool = False

    @property
    def agreement_rate(self) -> float:
        """Proportion of primitives that agree across sources."""
        total = len(self.agreements) + len(self.disagreements)
        return len(self.agreements) / max(total, 1)

    @property
    def major_disagreements(self) -> List[DisagreementRecord]:
        """Disagreements where LLM and external have opposite signs."""
        return [d for d in self.disagreements if d.severity in ("major", "sign_flip")]


class ExternalSourcesComparator:
    """
    Compares LLM decompositions against external lexical sources.

    Unlike the Integrator which pre-fills primitives, this class:
    1. Lets LLM generate ALL primitives independently
    2. Compares against external sources
    3. Flags disagreements and adjusts confidence
    """

    def __init__(self):
        self.parsers = {}
        self._loaded = False

    def load_all_sources(self) -> Dict[str, int]:
        """Load all available external sources."""
        stats = {}

        # SentiWordNet
        try:
            from gse.curation.external_sources.sentiwordnet import SentiWordNetParser

            parser = SentiWordNetParser()
            if parser.load():
                self.parsers["sentiwordnet"] = parser
                stats["sentiwordnet"] = len(parser.entries)
        except Exception as e:
            logger.debug(f"SentiWordNet not available: {e}")

        # NRC Emotion
        try:
            from gse.curation.external_sources.nrc_emotion import NRCEmotionParser

            parser = NRCEmotionParser()
            if parser.load():
                self.parsers["nrc_emotion"] = parser
                stats["nrc_emotion"] = len(parser.entries)
        except Exception as e:
            logger.debug(f"NRC Emotion not available: {e}")

        # NRC VAD
        try:
            from gse.curation.external_sources.nrc_vad import NRCVADParser

            parser = NRCVADParser()
            if parser.load():
                self.parsers["nrc_vad"] = parser
                stats["nrc_vad"] = len(parser.entries)
        except Exception as e:
            logger.debug(f"NRC VAD not available: {e}")

        # VerbNet
        try:
            from gse.curation.external_sources.verbnet import VerbNetParser

            parser = VerbNetParser()
            if parser.load():
                self.parsers["verbnet"] = parser
                stats["verbnet"] = len(parser.entries)
        except Exception as e:
            logger.debug(f"VerbNet not available: {e}")

        # Concreteness
        try:
            from gse.curation.external_sources.concreteness import ConcretenessParser

            parser = ConcretenessParser()
            if parser.load():
                self.parsers["concreteness"] = parser
                stats["concreteness"] = len(parser.entries)
        except Exception as e:
            logger.debug(f"Concreteness not available: {e}")

        # Lancaster Sensorimotor
        try:
            from gse.curation.external_sources.lancaster_sensorimotor import LancasterSensorimotorParser

            parser = LancasterSensorimotorParser()
            if parser.load():
                self.parsers["lancaster_sensorimotor"] = parser
                stats["lancaster_sensorimotor"] = len(parser.entries)
        except Exception as e:
            logger.debug(f"Lancaster Sensorimotor not available: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(stats)} external sources for comparison")
        return stats

    def get_external_primitives(self, word: str) -> Dict[str, Dict[str, int]]:
        """
        Get primitive mappings from all external sources for a word.

        Returns:
            Dict mapping source name to primitive dict
        """
        if not self._loaded:
            self.load_all_sources()

        result = {}
        word_lower = word.lower()

        for source_name, parser in self.parsers.items():
            primitives = parser.to_primitives(word_lower)
            if primitives:
                result[source_name] = primitives

        return result

    def compare(
        self,
        word: str,
        llm_primitives: Dict[str, int],
        review_threshold: float = 0.3,  # Flag for review if >30% disagree
    ) -> ComparisonResult:
        """
        Compare LLM decomposition against external sources.

        Args:
            word: The word being analyzed
            llm_primitives: Dict of primitive -> value from LLM
            review_threshold: If disagreement rate exceeds this, flag for review

        Returns:
            ComparisonResult with agreements, disagreements, and confidence
        """
        external = self.get_external_primitives(word)

        result = ComparisonResult(
            word=word,
            llm_primitives=llm_primitives,
            external_primitives=external,
        )

        if not external:
            # No external data - can't compare
            return result

        # Compare each external source against LLM
        checked_primitives = set()

        for source_name, ext_prims in external.items():
            for prim, ext_val in ext_prims.items():
                llm_val = llm_primitives.get(prim, 0)
                checked_primitives.add(prim)

                if llm_val == ext_val:
                    if prim not in result.agreements:
                        result.agreements.append(prim)
                else:
                    # Determine severity
                    if llm_val == 0 or ext_val == 0:
                        severity = "minor"  # One says neutral, other says something
                    elif (llm_val > 0 and ext_val < 0) or (llm_val < 0 and ext_val > 0):
                        severity = "sign_flip"  # Opposite signs - major disagreement
                    else:
                        severity = "major"

                    result.disagreements.append(
                        DisagreementRecord(
                            primitive=prim,
                            llm_value=llm_val,
                            external_value=ext_val,
                            external_source=source_name,
                            severity=severity,
                        )
                    )

        # Calculate confidence adjustment
        if checked_primitives:
            agreement_count = len(result.agreements)
            disagreement_count = len(result.disagreements)
            total = agreement_count + disagreement_count

            # Major/sign-flip disagreements hurt more
            major_count = len(result.major_disagreements)

            # Confidence adjustment: agreements boost, disagreements penalize
            # Range: -1.0 (all major disagree) to +1.0 (all agree)
            if total > 0:
                base_agreement = agreement_count / total
                major_penalty = (major_count / total) * 0.5  # Extra penalty for major
                result.confidence_adjustment = (base_agreement * 2 - 1) - major_penalty

            # Flag for review if too many disagreements
            disagreement_rate = disagreement_count / max(total, 1)
            result.needs_review = disagreement_rate > review_threshold or major_count > 0

        return result

    def compare_batch(
        self,
        word_primitives: Dict[str, Dict[str, int]],
    ) -> Dict[str, ComparisonResult]:
        """
        Compare multiple words against external sources.

        Args:
            word_primitives: Dict mapping word -> primitive dict

        Returns:
            Dict mapping word -> ComparisonResult
        """
        results = {}
        for word, primitives in word_primitives.items():
            results[word] = self.compare(word, primitives)
        return results

    def get_high_confidence_disagreements(
        self,
        results: Dict[str, ComparisonResult],
        min_sources: int = 2,
    ) -> List[Tuple[str, DisagreementRecord]]:
        """
        Get disagreements where multiple external sources agree against LLM.

        These are cases where the LLM is likely wrong.
        """
        high_conf_disagree = []

        for word, result in results.items():
            # Group disagreements by primitive
            prim_disagreements = defaultdict(list)
            for d in result.disagreements:
                prim_disagreements[d.primitive].append(d)

            # Check if multiple sources agree on a different value
            for prim, disagrees in prim_disagreements.items():
                if len(disagrees) >= min_sources:
                    # Multiple sources disagree with LLM on same primitive
                    # Check if they agree with each other
                    ext_values = [d.external_value for d in disagrees]
                    if len(set(ext_values)) == 1:
                        # All external sources agree, LLM differs
                        high_conf_disagree.append((word, disagrees[0]))

        return high_conf_disagree

    def generate_report(
        self,
        results: Dict[str, ComparisonResult],
    ) -> str:
        """Generate a human-readable comparison report."""
        lines = ["# External Sources Comparison Report\n"]

        total = len(results)
        needs_review = sum(1 for r in results.values() if r.needs_review)
        with_external = sum(1 for r in results.values() if r.external_primitives)

        lines.append("## Summary")
        lines.append(f"- Total words analyzed: {total}")
        lines.append(f"- Words with external data: {with_external}")
        lines.append(f"- Words needing review: {needs_review}")
        lines.append("")

        # High-confidence disagreements
        high_conf = self.get_high_confidence_disagreements(results)
        if high_conf:
            lines.append(f"## High-Confidence Disagreements ({len(high_conf)})")
            lines.append("Multiple external sources agree, LLM differs:")
            lines.append("")
            for word, d in high_conf[:20]:  # Top 20
                lines.append(f"- **{word}**: {d}")
            lines.append("")

        # Words needing review
        if needs_review > 0:
            lines.append(f"## Words Needing Review ({needs_review})")
            for word, result in sorted(results.items()):
                if result.needs_review:
                    major = result.major_disagreements
                    lines.append(f"- **{word}**: {len(major)} major disagreements")
                    for d in major[:3]:
                        lines.append(f"  - {d}")

        return "\n".join(lines)


def integrate_comparison_into_pipeline():
    """
    Example of how to integrate comparison into the build pipeline.

    This would be called after LLM generates primitives but before
    final validation/storage.
    """
    from gse.curation.llm.ollama_client import OllamaClient

    comparator = ExternalSourcesComparator()
    comparator.load_all_sources()

    # Example: After LLM decomposition
    llm = OllamaClient()
    word = "happy"

    # LLM generates ALL primitives
    llm_result = llm.decompose_word(word)

    # Compare against external sources
    comparison = comparator.compare(word, llm_result)

    print(f"Word: {word}")
    print(f"Agreement rate: {comparison.agreement_rate:.1%}")
    print(f"Needs review: {comparison.needs_review}")
    print(f"Confidence adjustment: {comparison.confidence_adjustment:+.2f}")

    if comparison.disagreements:
        print("Disagreements:")
        for d in comparison.disagreements:
            print(f"  - {d}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    integrate_comparison_into_pipeline()
