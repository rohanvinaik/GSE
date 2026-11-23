"""
Discourse Coherence for GSE.

Tracks semantic coherence across multiple sentences:
1. Entity tracking (coreference)
2. Topic continuity
3. Rhetorical relations between sentences
4. Discourse segment boundaries
"""

from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
import numpy as np

from gse.vectors import SparseVector, bundle, D, DIMS_PER_BANK, SemanticBank
from gse.composer import CompositionResult


@dataclass
class Entity:
    """A tracked entity in discourse."""
    id: str                            # Unique identifier
    mentions: List[Tuple[int, int]]    # (sentence_idx, token_idx) pairs
    vector: SparseVector               # Accumulated semantic representation
    salience: float                    # How prominent/important
    attributes: Dict[str, SparseVector]  # Accumulated attributes


@dataclass
class DiscourseSegment:
    """A coherent segment of discourse."""
    start_sentence: int
    end_sentence: int
    topic_vector: SparseVector
    entities: List[str]                # Entity IDs in this segment


@dataclass
class RhetoricalRelation:
    """Relation between discourse units."""
    relation_type: str                 # elaboration, contrast, cause, etc.
    source_sentence: int
    target_sentence: int
    confidence: float


@dataclass
class DiscourseState:
    """Current state of discourse processing."""
    entities: Dict[str, Entity]
    segments: List[DiscourseSegment]
    relations: List[RhetoricalRelation]
    current_topic: Optional[SparseVector]
    sentence_vectors: List[SparseVector]
    coherence_scores: List[float]      # Per-sentence coherence with prior


# Rhetorical relation indicators
RELATION_INDICATORS = {
    "elaboration": {
        "markers": {"specifically", "in particular", "for example", "such as", "namely"},
        "expected_similarity": 0.6,    # High overlap with prior
    },
    "contrast": {
        "markers": {"but", "however", "although", "yet", "nevertheless", "on the other hand"},
        "expected_similarity": 0.2,    # Low overlap, different content
    },
    "cause": {
        "markers": {"because", "since", "therefore", "thus", "consequently", "so"},
        "expected_similarity": 0.4,
    },
    "temporal": {
        "markers": {"then", "after", "before", "when", "while", "meanwhile"},
        "expected_similarity": 0.5,
    },
    "addition": {
        "markers": {"and", "also", "moreover", "furthermore", "in addition"},
        "expected_similarity": 0.5,
    },
    "concession": {
        "markers": {"although", "even though", "despite", "in spite of"},
        "expected_similarity": 0.3,
    },
}


class DiscourseTracker:
    """
    Track discourse coherence across sentences.

    Maintains:
    - Entity mentions and coreference
    - Topic continuity
    - Rhetorical structure
    - Coherence scoring
    """

    def __init__(self, coherence_threshold: float = 0.3):
        self.coherence_threshold = coherence_threshold
        self.state = DiscourseState(
            entities={},
            segments=[],
            relations=[],
            current_topic=None,
            sentence_vectors=[],
            coherence_scores=[],
        )
        self.entity_counter = 0

    def reset(self):
        """Reset discourse state for new document."""
        self.state = DiscourseState(
            entities={},
            segments=[],
            relations=[],
            current_topic=None,
            sentence_vectors=[],
            coherence_scores=[],
        )
        self.entity_counter = 0

    def process_sentence(
        self,
        sentence_idx: int,
        composition: CompositionResult,
        tokens: List[str],
        noun_indices: List[int],
    ) -> Dict:
        """
        Process a sentence and update discourse state.

        Args:
            sentence_idx: Index of this sentence in document
            composition: GSE composition result
            tokens: List of token strings
            noun_indices: Indices of noun tokens (potential entities)

        Returns:
            Dict with coherence analysis results
        """
        sentence_vector = composition.sentence_vector
        self.state.sentence_vectors.append(sentence_vector)

        results = {
            "sentence_idx": sentence_idx,
            "new_entities": [],
            "continued_entities": [],
            "topic_shift": False,
            "rhetorical_relation": None,
            "coherence_score": 1.0,
        }

        # 1. Entity tracking
        for noun_idx in noun_indices:
            if noun_idx in composition.token_vectors:
                noun_vector = composition.token_vectors[noun_idx]
                noun_text = tokens[noun_idx] if noun_idx < len(tokens) else "unknown"

                # Check if this matches an existing entity
                entity_id = self._find_matching_entity(noun_vector, noun_text)

                if entity_id:
                    # Update existing entity
                    entity = self.state.entities[entity_id]
                    entity.mentions.append((sentence_idx, noun_idx))
                    # Update vector with new mention
                    entity.vector = bundle([entity.vector, noun_vector])
                    entity.salience = min(1.0, entity.salience + 0.1)
                    results["continued_entities"].append(entity_id)
                else:
                    # Create new entity
                    entity_id = self._create_entity(
                        sentence_idx, noun_idx, noun_vector, noun_text
                    )
                    results["new_entities"].append(entity_id)

        # 2. Topic tracking
        if self.state.current_topic is None:
            self.state.current_topic = sentence_vector
        else:
            topic_similarity = sentence_vector.cosine(self.state.current_topic)
            if topic_similarity < 0.2:
                results["topic_shift"] = True
                # Start new segment
                self._end_current_segment(sentence_idx - 1)
                self._start_new_segment(sentence_idx, sentence_vector)
            else:
                # Update topic (weighted average)
                self.state.current_topic = bundle([
                    self.state.current_topic,
                    sentence_vector
                ])

        # 3. Coherence with prior sentence
        if sentence_idx > 0:
            prior_vector = self.state.sentence_vectors[sentence_idx - 1]
            coherence = sentence_vector.cosine(prior_vector)
            results["coherence_score"] = max(0.0, coherence)
            self.state.coherence_scores.append(coherence)

            # Detect rhetorical relation
            relation = self._detect_rhetorical_relation(
                tokens, prior_vector, sentence_vector, coherence
            )
            if relation:
                self.state.relations.append(RhetoricalRelation(
                    relation_type=relation,
                    source_sentence=sentence_idx - 1,
                    target_sentence=sentence_idx,
                    confidence=0.8,
                ))
                results["rhetorical_relation"] = relation
        else:
            self.state.coherence_scores.append(1.0)

        # 4. Decay entity salience
        self._decay_salience()

        return results

    def _find_matching_entity(
        self,
        vector: SparseVector,
        text: str
    ) -> Optional[str]:
        """Find an existing entity that matches this mention."""
        best_match = None
        best_score = 0.5  # Minimum threshold for matching

        for entity_id, entity in self.state.entities.items():
            # Check vector similarity
            sim = vector.cosine(entity.vector)

            # Boost if salience is high (recently mentioned)
            adjusted_sim = sim * (0.5 + 0.5 * entity.salience)

            if adjusted_sim > best_score:
                best_score = adjusted_sim
                best_match = entity_id

        return best_match

    def _create_entity(
        self,
        sentence_idx: int,
        token_idx: int,
        vector: SparseVector,
        text: str
    ) -> str:
        """Create a new entity."""
        self.entity_counter += 1
        entity_id = f"entity_{self.entity_counter}"

        self.state.entities[entity_id] = Entity(
            id=entity_id,
            mentions=[(sentence_idx, token_idx)],
            vector=vector,
            salience=1.0,
            attributes={},
        )

        return entity_id

    def _decay_salience(self, decay_rate: float = 0.1):
        """Decay salience of all entities."""
        for entity in self.state.entities.values():
            entity.salience = max(0.0, entity.salience - decay_rate)

    def _detect_rhetorical_relation(
        self,
        tokens: List[str],
        prior_vector: SparseVector,
        current_vector: SparseVector,
        coherence: float
    ) -> Optional[str]:
        """Detect rhetorical relation based on markers and similarity."""
        tokens_lower = [t.lower() for t in tokens]

        for relation, info in RELATION_INDICATORS.items():
            markers = info["markers"]
            expected_sim = info["expected_similarity"]

            # Check for discourse markers
            if any(marker in tokens_lower for marker in markers):
                return relation

        # Infer from similarity if no explicit marker
        if coherence > 0.7:
            return "elaboration"
        elif coherence < 0.1:
            return "contrast"
        elif 0.3 <= coherence <= 0.5:
            return "addition"

        return None

    def _start_new_segment(self, sentence_idx: int, topic_vector: SparseVector):
        """Start a new discourse segment."""
        active_entities = [
            eid for eid, e in self.state.entities.items()
            if e.salience > 0.3
        ]
        self.state.segments.append(DiscourseSegment(
            start_sentence=sentence_idx,
            end_sentence=sentence_idx,  # Will be updated
            topic_vector=topic_vector,
            entities=active_entities,
        ))
        self.state.current_topic = topic_vector

    def _end_current_segment(self, sentence_idx: int):
        """End the current discourse segment."""
        if self.state.segments:
            self.state.segments[-1].end_sentence = sentence_idx

    def get_document_coherence(self) -> float:
        """Get overall document coherence score."""
        if not self.state.coherence_scores:
            return 1.0
        return float(np.mean(self.state.coherence_scores))

    def get_entity_chain_length(self, entity_id: str) -> int:
        """Get number of mentions for an entity."""
        if entity_id in self.state.entities:
            return len(self.state.entities[entity_id].mentions)
        return 0

    def get_main_entities(self, top_n: int = 5) -> List[Entity]:
        """Get the most salient entities."""
        entities = list(self.state.entities.values())
        entities.sort(key=lambda e: (len(e.mentions), e.salience), reverse=True)
        return entities[:top_n]

    def get_discourse_summary(self) -> Dict:
        """Get summary of discourse analysis."""
        return {
            "num_sentences": len(self.state.sentence_vectors),
            "num_entities": len(self.state.entities),
            "num_segments": len(self.state.segments),
            "num_relations": len(self.state.relations),
            "overall_coherence": self.get_document_coherence(),
            "main_entities": [
                {
                    "id": e.id,
                    "mentions": len(e.mentions),
                    "salience": e.salience,
                }
                for e in self.get_main_entities(3)
            ],
            "relation_types": self._count_relation_types(),
        }

    def _count_relation_types(self) -> Dict[str, int]:
        """Count occurrences of each relation type."""
        counts: Dict[str, int] = {}
        for rel in self.state.relations:
            counts[rel.relation_type] = counts.get(rel.relation_type, 0) + 1
        return counts


@dataclass
class CoherenceAnalysis:
    """Complete coherence analysis for a document."""
    document_coherence: float
    sentence_coherences: List[float]
    topic_shifts: List[int]           # Sentence indices where topic shifts
    entity_chains: Dict[str, List[int]]  # entity_id -> sentence indices
    rhetorical_structure: List[RhetoricalRelation]


def analyze_document_coherence(
    compositions: List[CompositionResult],
    all_tokens: List[List[str]],
    all_noun_indices: List[List[int]],
) -> CoherenceAnalysis:
    """
    Analyze coherence across a document.

    Args:
        compositions: List of CompositionResult for each sentence
        all_tokens: List of token lists for each sentence
        all_noun_indices: List of noun index lists for each sentence

    Returns:
        Complete coherence analysis
    """
    tracker = DiscourseTracker()
    topic_shifts = []

    for i, (comp, tokens, nouns) in enumerate(
        zip(compositions, all_tokens, all_noun_indices)
    ):
        result = tracker.process_sentence(i, comp, tokens, nouns)
        if result["topic_shift"]:
            topic_shifts.append(i)

    # Build entity chains
    entity_chains = {}
    for entity_id, entity in tracker.state.entities.items():
        entity_chains[entity_id] = [m[0] for m in entity.mentions]

    return CoherenceAnalysis(
        document_coherence=tracker.get_document_coherence(),
        sentence_coherences=tracker.state.coherence_scores,
        topic_shifts=topic_shifts,
        entity_chains=entity_chains,
        rhetorical_structure=tracker.state.relations,
    )


# Singleton tracker
_tracker = None


def get_discourse_tracker() -> DiscourseTracker:
    """Get or create the discourse tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = DiscourseTracker()
    return _tracker
