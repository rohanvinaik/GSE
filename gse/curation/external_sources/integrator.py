"""
External Sources Integrator

Combines multiple lexical resources to:
1. Find new words not in the lexicon
2. Pre-fill primitives from external sources
3. Use LLM only for remaining primitives

This reduces LLM calls and improves quality through cross-validation.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from gse.curation.lexicon_db import LexiconDatabase
from gse.curation.schema import ALL_PRIMITIVES

logger = logging.getLogger(__name__)


@dataclass
class ExternalWordData:
    """Aggregated data from external sources for a word."""
    word: str
    pos: Optional[str] = None
    sources: List[str] = field(default_factory=list)
    primitives: Dict[str, int] = field(default_factory=dict)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, any] = field(default_factory=dict)
    # Populated by ``aggregate_primitives_weighted`` only. Each entry records
    # a bipolar pair where both poles voted active and the weaker was
    # suppressed by mutual exclusion. Plain ``aggregate_primitives`` leaves
    # this empty for backwards compatibility.
    suppressions: List[Dict[str, Any]] = field(default_factory=list)


class ExternalSourcesIntegrator:
    """
    Integrates multiple external lexical resources.

    Provides:
    - Unified word list from all sources
    - Pre-filled primitives where available
    - Confidence based on source agreement
    - De-duplication against existing lexicon
    """

    def __init__(self, lexicon_db_path: Optional[str] = None):
        self.lexicon_db = LexiconDatabase(lexicon_db_path) if lexicon_db_path else None
        self.parsers = {}
        self.word_data: Dict[str, ExternalWordData] = {}
        self._loaded = False

    def load_all_sources(self) -> Dict[str, int]:
        """
        Load all available external sources.

        Returns:
            Dict mapping source name to word count
        """
        stats = {}

        # SentiWordNet
        try:
            from gse.curation.external_sources.sentiwordnet import SentiWordNetParser
            parser = SentiWordNetParser()
            if parser.load():
                self.parsers['sentiwordnet'] = parser
                stats['sentiwordnet'] = len(parser.entries)
                logger.info(f"Loaded SentiWordNet: {stats['sentiwordnet']} words")
        except Exception as e:
            logger.warning(f"Failed to load SentiWordNet: {e}")

        # NRC Emotion
        try:
            from gse.curation.external_sources.nrc_emotion import NRCEmotionParser
            parser = NRCEmotionParser()
            if parser.load():
                self.parsers['nrc_emotion'] = parser
                stats['nrc_emotion'] = len(parser.entries)
                logger.info(f"Loaded NRC Emotion: {stats['nrc_emotion']} words")
        except Exception as e:
            logger.warning(f"Failed to load NRC Emotion: {e}")

        # NRC VAD
        try:
            from gse.curation.external_sources.nrc_vad import NRCVADParser
            parser = NRCVADParser()
            if parser.load():
                self.parsers['nrc_vad'] = parser
                stats['nrc_vad'] = len(parser.entries)
                logger.info(f"Loaded NRC VAD: {stats['nrc_vad']} words")
        except Exception as e:
            logger.warning(f"Failed to load NRC VAD: {e}")

        # VerbNet
        try:
            from gse.curation.external_sources.verbnet import VerbNetParser
            parser = VerbNetParser()
            if parser.load():
                self.parsers['verbnet'] = parser
                stats['verbnet'] = len(parser.entries)
                logger.info(f"Loaded VerbNet: {stats['verbnet']} words")
        except Exception as e:
            logger.warning(f"Failed to load VerbNet: {e}")

        # Concreteness
        try:
            from gse.curation.external_sources.concreteness import ConcretenessParser
            parser = ConcretenessParser()
            if parser.load():
                self.parsers['concreteness'] = parser
                stats['concreteness'] = len(parser.entries)
                logger.info(f"Loaded Concreteness: {stats['concreteness']} words")
        except Exception as e:
            logger.warning(f"Failed to load Concreteness: {e}")

        # Lancaster Sensorimotor
        try:
            from gse.curation.external_sources.lancaster_sensorimotor import LancasterSensorimotorParser
            parser = LancasterSensorimotorParser()
            if parser.load():
                self.parsers['lancaster_sensorimotor'] = parser
                stats['lancaster_sensorimotor'] = len(parser.entries)
                logger.info(f"Loaded Lancaster Sensorimotor: {stats['lancaster_sensorimotor']} words")
        except Exception as e:
            logger.warning(f"Failed to load Lancaster Sensorimotor: {e}")

        # WordNet hierarchy (IS-A taxonomy → category / SUBSTANTIVES). The
        # category source: grounds `animal→ALIVE`, `person→SOMEONE`, the molecules
        # the dictionary genus chains can't reach. Scoped in source_scope.
        try:
            from gse.curation.external_sources.wordnet_hierarchy import (
                WordNetHierarchyParser,
            )
            parser = WordNetHierarchyParser()
            if parser.load():
                self.parsers['wordnet_hierarchy'] = parser
                stats['wordnet_hierarchy'] = len(parser.get_all_words())
                logger.info(f"Loaded WordNet hierarchy: {stats['wordnet_hierarchy']} words")
        except Exception as e:
            logger.warning(f"Failed to load WordNet hierarchy: {e}")

        # FrameNet (frame semantics → event structure + participant roles). One of
        # the three designed verb-structure sources (CONSTRUCTION_PLAN §4 lists 18
        # parsers); parser existed but was never registered. Scoped in source_scope.
        try:
            from gse.curation.external_sources.framenet import FrameNetParser
            parser = FrameNetParser()
            if parser.load():
                self.parsers['framenet'] = parser
                stats['framenet'] = len(parser.entries)
                logger.info(f"Loaded FrameNet: {stats['framenet']} words")
        except Exception as e:
            logger.warning(f"Failed to load FrameNet: {e}")

        # PropBank (verb rolesets → predicate-argument structure). Same competence
        # family as VerbNet; completes the designed verb-source trio.
        try:
            from gse.curation.external_sources.propbank import PropBankParser
            parser = PropBankParser()
            if parser.load():
                self.parsers['propbank'] = parser
                stats['propbank'] = len(parser.entries)
                logger.info(f"Loaded PropBank: {stats['propbank']} verbs")
        except Exception as e:
            logger.warning(f"Failed to load PropBank: {e}")

        # ConceptNet (commonsense relations → taxonomy/mereology/location/capability).
        # Reads the prebuilt data/external/conceptnet-en.sqlite index. Scoped tightly —
        # crowd-sourced, so it votes only where its relations are structural.
        try:
            from gse.curation.external_sources.conceptnet import ConceptNetParser
            parser = ConceptNetParser()
            if parser.load():
                self.parsers['conceptnet'] = parser
                stats['conceptnet'] = len(parser.get_all_words())
                logger.info(f"Loaded ConceptNet: {stats['conceptnet']} words")
        except Exception as e:
            logger.warning(f"Failed to load ConceptNet: {e}")

        # USAS (UCREL semantic fields → coarse categorical/topical typing) — the
        # topical complement to wordnet_hierarchy's IS-A category signal.
        try:
            from gse.curation.external_sources.usas import USASParser
            parser = USASParser()
            if parser.load():
                self.parsers['usas'] = parser
                stats['usas'] = len(parser.entries)
                logger.info(f"Loaded USAS: {stats['usas']} words")
        except Exception as e:
            logger.warning(f"Failed to load USAS: {e}")

        # (wiktionary_v2 — the degenerate ~1.3M bag-of-words spine — was retired and
        # purged 2026-06-20; the clean build scopes each remaining source to its
        # domain. See docs/MORPHOLOGY_RESEARCH_BRIEF.md / lexicon-clean-build memory.)

        self._loaded = True
        return stats

    def get_primary_lexeme_words(self) -> Set[str]:
        """The word list that drives lexeme creation — the union of all loaded scoped
        sources. (The degenerate ``wiktionary_v2`` spine was retired; the clean build
        scopes each source to its domain.)
        """
        if not self._loaded:
            self.load_all_sources()
        return self.get_all_words()

    def get_all_words(self) -> Set[str]:
        """Get union of all words from all sources."""
        if not self._loaded:
            self.load_all_sources()

        all_words = set()
        for parser in self.parsers.values():
            all_words.update(parser.get_all_words())

        return all_words

    def get_existing_words(self) -> Set[str]:
        """Get words already in the lexicon database."""
        if self.lexicon_db is None:
            return set()

        # Query all lemmas from database
        cursor = self.lexicon_db.conn.execute("SELECT DISTINCT lemma FROM lexemes")
        return {row[0].lower() for row in cursor.fetchall()}

    def get_new_words(self) -> Set[str]:
        """Get words from external sources not in lexicon."""
        all_external = self.get_all_words()
        existing = self.get_existing_words()
        return all_external - existing

    def aggregate_primitives_weighted(
        self,
        word: str,
        source_confidence: Optional[Dict[str, float]] = None,
        default_confidence: float = 1.0,
    ) -> ExternalWordData:
        """Confidence-weighted aggregation + bipolar mutual-exclusion.

        Alternative to :meth:`aggregate_primitives`. Uses the
        confidence-weighted voting formula from
        :mod:`gse.curation.external_sources.weighted_voting` (ported from
        the old ``rebuild_lexicon_from_sources`` script), then enforces
        NSM bipolar mutual exclusion via
        :mod:`gse.curation.external_sources.bipolar_exclusion`.

        Args:
            word: lemma to look up.
            source_confidence: optional per-source confidence priors. Any
                source not listed uses ``default_confidence``. This is the
                calibration knob — codify "ConceptNet is noisier than NRC"
                here when ready.
            default_confidence: fallback for sources without a prior.

        Returns:
            ExternalWordData with the cleaned decomposition,
            per-primitive confidences, contributing sources, and any
            bipolar-pair suppressions recorded for the provenance trail.
        """
        from gse.curation.external_sources.bipolar_exclusion import (
            enforce_bipolar_exclusion,
        )
        from gse.curation.external_sources.source_scope import filter_votes_by_scope
        from gse.curation.external_sources.tier_0_dispatch import (
            canonical_decomposition,
        )
        from gse.curation.external_sources.weighted_voting import aggregate_weighted

        # Tier 0 short-circuit: if the word is the English label of an NSM
        # primitive (good, bad, big, small, someone, think, ...), its
        # decomposition is definitional — {LABEL: +1}. Aggregation is skipped
        # because no external source can override what the primitive *is*.
        tier_0 = canonical_decomposition(word)
        if tier_0 is not None:
            return ExternalWordData(
                word=word,
                sources=["tier_0_definitional"],
                primitives=tier_0,
                confidence_scores={k: 1.0 for k in tier_0},
            )

        if not self._loaded:
            self.load_all_sources()

        priors = source_confidence or {}

        # Collect per-source votes as (value, confidence) tuples. Parsers that
        # expose per-vote confidence (e.g., WiktionaryPrimitivesV2Loader, which
        # stores per-(word, primitive) confidences in its DB) supply genuine
        # values via to_primitives_with_confidence. Other parsers fall back
        # to a single source-level prior applied uniformly.
        source_votes: Dict[str, Dict[str, tuple]] = {}
        for source_name, parser in self.parsers.items():
            # Legacy parsers (SentiWordNetParser, NRCEmotionParser, etc.) do
            # not inherit from BaseExternalParser, so they only have
            # to_primitives. New parsers (WiktionaryPrimitivesV2Loader) expose
            # genuine per-vote confidence via to_primitives_with_confidence.
            confidence_aware = getattr(parser, "to_primitives_with_confidence", None)
            if callable(confidence_aware):
                prims_with_conf = confidence_aware(word)
            else:
                prims_with_conf = {
                    p: (v, 1.0) for p, v in parser.to_primitives(word).items()
                }

            if not prims_with_conf:
                continue
            source_prior = priors.get(source_name, default_confidence)
            # If a per-vote confidence is < 1.0, treat it as authoritative
            # (the parser had real evidence). Otherwise apply the source
            # prior so legacy parsers honor source_confidence overrides.
            adjusted: Dict[str, tuple] = {}
            for prim, (val, conf) in prims_with_conf.items():
                effective = conf if conf < 1.0 else source_prior
                adjusted[prim] = (val, effective)
            # Per-source primitive scope: drop votes for primitives outside
            # this source's semantic domain (e.g., NRC VAD voting on MUST).
            # See SOURCE_PRIMITIVE_SCOPE for the empirical map.
            adjusted = filter_votes_by_scope(source_name, adjusted)
            if not adjusted:
                continue
            source_votes[source_name] = adjusted

        if not source_votes:
            return ExternalWordData(word=word)

        # Step 1: confidence-weighted voting per primitive.
        aggregation = aggregate_weighted(word, source_votes)

        # Step 2: bipolar mutual exclusion across the 14 NSM pairs.
        post_vote_primitives = {
            p: v.value for p, v in aggregation.primitives.items() if v.value != 0
        }
        post_vote_confidences = {
            p: v.confidence for p, v in aggregation.primitives.items() if v.value != 0
        }
        exclusion = enforce_bipolar_exclusion(post_vote_primitives, post_vote_confidences)

        # Step 3: stitch results back into ExternalWordData. Sources are
        # the union of every source that contributed to a surviving
        # primitive after exclusion.
        surviving_sources: Set[str] = set()
        for prim in exclusion.primitives:
            vote = aggregation.primitives.get(prim)
            if vote is not None:
                surviving_sources.update(vote.contributing_sources)

        return ExternalWordData(
            word=word,
            sources=sorted(surviving_sources),
            primitives=exclusion.primitives,
            confidence_scores=exclusion.confidences,
            suppressions=[
                {
                    "kept": s.kept,
                    "dropped": s.dropped,
                    "kept_confidence": s.kept_confidence,
                    "dropped_confidence": s.dropped_confidence,
                    "bipolar_pair": list(s.bipolar_pair),
                }
                for s in exclusion.suppressions
            ],
        )

    def aggregate_primitives(self, word: str) -> ExternalWordData:
        """
        Aggregate primitive mappings from all sources for a word.

        Uses voting: if multiple sources agree on a primitive, increase confidence.
        """
        if not self._loaded:
            self.load_all_sources()

        data = ExternalWordData(word=word)
        primitive_votes: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))

        # Collect from each source
        for source_name, parser in self.parsers.items():
            primitives = parser.to_primitives(word)
            if primitives:
                data.sources.append(source_name)
                for prim, value in primitives.items():
                    primitive_votes[prim][value] += 1

        # Resolve votes
        for prim, votes in primitive_votes.items():
            if votes:
                # Choose value with most votes
                best_value = max(votes.keys(), key=lambda v: votes[v])
                vote_count = votes[best_value]
                total_sources = len(data.sources)

                data.primitives[prim] = best_value
                data.confidence_scores[prim] = vote_count / max(total_sources, 1)

        return data

    def get_prefilled_entries(
        self,
        min_sources: int = 1,
        min_confidence: float = 0.5,
    ) -> List[ExternalWordData]:
        """
        Get words with pre-filled primitives.

        Args:
            min_sources: Minimum number of sources that must have the word
            min_confidence: Minimum confidence for primitives

        Returns:
            List of ExternalWordData with pre-filled primitives
        """
        new_words = self.get_new_words()
        logger.info(f"Found {len(new_words)} new words from external sources")

        results = []
        for word in new_words:
            data = self.aggregate_primitives(word)
            if len(data.sources) >= min_sources:
                # Filter low-confidence primitives
                data.primitives = {
                    p: v for p, v in data.primitives.items()
                    if data.confidence_scores.get(p, 0) >= min_confidence
                }
                if data.primitives:
                    results.append(data)

        logger.info(f"Returning {len(results)} words with pre-filled primitives")
        return results

    def export_for_llm_processing(
        self,
        output_path: str,
        limit: Optional[int] = None,
    ) -> int:
        """
        Export new words with partial primitives for LLM processing.

        Creates a JSON file with:
        - word
        - known_primitives (from external sources)
        - sources
        - needed_primitives (to be filled by LLM)

        Returns:
            Number of words exported
        """
        import json

        entries = self.get_prefilled_entries()
        if limit:
            entries = entries[:limit]

        export_data = []
        for entry in entries:
            # Calculate which primitives still need LLM
            known = set(entry.primitives.keys())
            needed = [p for p in ALL_PRIMITIVES if p not in known]

            export_data.append({
                'word': entry.word,
                'known_primitives': entry.primitives,
                'sources': entry.sources,
                'confidence': entry.confidence_scores,
                'needed_primitives': needed,
            })

        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported {len(export_data)} words to {output_path}")
        return len(export_data)

    def get_statistics(self) -> Dict[str, any]:
        """Get statistics about external sources."""
        if not self._loaded:
            self.load_all_sources()

        stats = {
            'sources_loaded': list(self.parsers.keys()),
            'words_per_source': {name: len(p.get_all_words()) for name, p in self.parsers.items()},
            'total_unique_words': len(self.get_all_words()),
            'existing_in_lexicon': len(self.get_existing_words()),
            'new_words': len(self.get_new_words()),
        }

        return stats

    def close(self):
        """Clean up resources."""
        if self.lexicon_db:
            self.lexicon_db.close()


def download_all_sources():
    """Download all external sources."""
    import nltk

    print("Downloading NLTK resources...")
    nltk.download('sentiwordnet', quiet=False)
    nltk.download('wordnet', quiet=False)
    nltk.download('omw-1.4', quiet=False)
    nltk.download('verbnet', quiet=False)
    nltk.download('verbnet3', quiet=False)

    print("\nDownloading NRC resources...")
    from gse.curation.external_sources.concreteness import ConcretenessParser
    from gse.curation.external_sources.nrc_emotion import NRCEmotionParser
    from gse.curation.external_sources.nrc_vad import NRCVADParser

    NRCEmotionParser().download()
    NRCVADParser().download()
    ConcretenessParser().download()

    print("\nAll sources downloaded!")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1 and sys.argv[1] == 'download':
        download_all_sources()
    else:
        integrator = ExternalSourcesIntegrator('data/lexicon.db')
        stats = integrator.load_all_sources()
        print("\nSource Statistics:")
        for name, count in stats.items():
            print(f"  {name}: {count} words")

        full_stats = integrator.get_statistics()
        print(f"\nTotal unique words: {full_stats['total_unique_words']}")
        print(f"Already in lexicon: {full_stats['existing_in_lexicon']}")
        print(f"New words to add: {full_stats['new_words']}")

        # Sample of pre-filled entries
        print("\nSample pre-filled entries:")
        entries = integrator.get_prefilled_entries(min_sources=2)[:10]
        for e in entries:
            print(f"  {e.word}: {e.primitives} (sources: {e.sources})")

        integrator.close()
