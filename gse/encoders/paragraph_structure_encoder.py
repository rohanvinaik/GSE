#!/usr/bin/env python3
"""
GSE Paragraph Structure Encoder

Captures inter-sentence relationships and rhetorical structure at paragraph level.
Uses the ParagraphBank primitives from primitives_v2.py.

Key features:
1. Coherence relation detection between sentences
2. Gestalt point identification (thesis, pivot, synthesis, etc.)
3. Intensity trajectory tracking
4. Topic chain extraction
5. Main claim identification

The paragraph encoder operates on SentenceEncodings and produces a unified
ParagraphEncoding that captures discourse structure.
"""

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

from gse.encoders.marker_detection import KeywordDetector, RegexPatternDetector
from gse.primitives_v2 import (
    PARAGRAPH_BANK_NAMES,
    D,
)

# =============================================================================
# COHERENCE RELATIONS
# =============================================================================


class CoherenceRelation(Enum):
    """Rhetorical relations between sentences in a paragraph."""

    # Rhetorical (Bank 0)
    TOPIC_INTRO = "topic_intro"
    CONTINUATION = "continuation"
    ELABORATION = "elaboration"
    CONTRAST = "contrast"
    # Causal (Bank 1)
    CAUSE = "cause"
    EFFECT = "effect"
    # Exemplification (Bank 2)
    EXAMPLE = "example"
    SUMMARY = "summary"
    # Flow (Bank 3)
    SHIFT = "shift"
    RETURN = "return"
    PARALLEL = "parallel"
    SEQUENCE = "sequence"
    # Intentional (Bank 4)
    CLAIM = "claim"
    EVIDENCE = "evidence"
    CONCESSION = "concession"
    # Extended relations
    ESCALATION = "escalation"
    DE_ESCALATION = "de_escalation"
    RESTATEMENT = "restatement"
    UNKNOWN = "unknown"


# Map relation names to paragraph primitives
RELATION_TO_PRIMITIVE = {
    CoherenceRelation.TOPIC_INTRO: "TOPIC_INTRO",
    CoherenceRelation.CONTINUATION: "CONTINUATION",
    CoherenceRelation.ELABORATION: "ELABORATION",
    CoherenceRelation.CONTRAST: "CONTRAST",
    CoherenceRelation.CAUSE: "CAUSE",
    CoherenceRelation.EFFECT: "EFFECT",
    CoherenceRelation.EXAMPLE: "EXAMPLE",
    CoherenceRelation.SUMMARY: "SUMMARY",
    CoherenceRelation.SHIFT: "SHIFT",
    CoherenceRelation.RETURN: "RETURN",
    CoherenceRelation.PARALLEL: "PARALLEL",
    CoherenceRelation.SEQUENCE: "SEQUENCE",
    CoherenceRelation.CLAIM: "CLAIM",
    CoherenceRelation.EVIDENCE: "EVIDENCE",
    CoherenceRelation.CONCESSION: "CONCESSION",
}


# =============================================================================
# GESTALT TYPES
# =============================================================================


class GestaltType(Enum):
    """Types of meaning crystallization points."""

    THESIS = "thesis"  # Core claim
    PIVOT = "pivot"  # Direction change
    SYNTHESIS = "synthesis"  # Multiple threads combined
    RESOLUTION = "resolution"  # Tension resolved
    HOOK = "hook"  # Grabs attention
    COMPRESSION = "compression"  # Analogy/metaphor point


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class IntensityTrajectory:
    """Track how intensity evolves across paragraph."""

    values: List[float]
    peak_index: int
    trajectory_type: str  # "building", "declining", "stable", "oscillating"

    @classmethod
    def from_values(cls, values: List[float]) -> "IntensityTrajectory":
        """Create trajectory from intensity values."""
        if not values:
            return cls([], 0, "stable")

        peak_index = values.index(max(values)) if values else 0

        if len(values) < 2:
            traj_type = "stable"
        else:
            diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
            avg_diff = sum(diffs) / len(diffs) if diffs else 0

            if avg_diff > 0.1:
                traj_type = "building"
            elif avg_diff < -0.1:
                traj_type = "declining"
            elif max(values) - min(values) > 0.4:
                traj_type = "oscillating"
            else:
                traj_type = "stable"

        return cls(values, peak_index, traj_type)


@dataclass
class GestaltPoint:
    """A point where meaning crystallizes."""

    sentence_idx: int
    gestalt_type: GestaltType
    weight: float  # 0.0-1.0 importance


@dataclass
class SentenceInfo:
    """Information about a sentence for paragraph encoding."""

    text: str
    vector: np.ndarray
    intensity_score: float = 0.5
    named_entities: List[Tuple[str, str]] = field(default_factory=list)
    is_question: bool = False
    has_analogy: bool = False
    has_meta_commentary: bool = False


@dataclass
class ParagraphStructure:
    """Parsed paragraph structure."""

    raw_text: str
    sentences: List[str]
    sentence_info: List[SentenceInfo]
    relations: List[Tuple[int, int, CoherenceRelation]]
    topic_chain: List[str]
    main_claim_idx: int
    gestalt_points: List[GestaltPoint] = field(default_factory=list)
    intensity_trajectory: Optional[IntensityTrajectory] = None
    analogy_indices: List[int] = field(default_factory=list)
    meta_indices: List[int] = field(default_factory=list)


@dataclass
class ParagraphEncoding:
    """Result of paragraph encoding."""

    vector: np.ndarray
    structure: ParagraphStructure
    sentence_vectors: List[np.ndarray]
    bank_activations: Dict[str, float]
    coherence_score: float


# =============================================================================
# CODEBOOKS
# =============================================================================


class RelationCodebook:
    """Codebook of relation vectors."""

    def __init__(self, dim: int = D, seed: int = 42):
        self.dim = dim
        self.seed = seed
        self.vectors: Dict[CoherenceRelation, np.ndarray] = {}
        self._generate_vectors()

    def _generate_vectors(self):
        for relation in CoherenceRelation:
            seed = int(hashlib.md5(f"{self.seed}_REL_{relation.value}".encode()).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            vec = np.zeros(self.dim, dtype=np.float32)
            rand = rng.random(self.dim)
            vec[rand < 0.33] = 1.0
            vec[rand > 0.67] = -1.0
            self.vectors[relation] = vec

    def get(self, relation: CoherenceRelation) -> np.ndarray:
        return self.vectors[relation]


class GestaltCodebook:
    """Codebook for gestalt type vectors."""

    def __init__(self, dim: int = D, seed: int = 42):
        self.dim = dim
        self.seed = seed
        self.vectors: Dict[GestaltType, np.ndarray] = {}
        self._generate_vectors()

    def _generate_vectors(self):
        for gtype in GestaltType:
            seed = int(hashlib.md5(f"{self.seed}_GESTALT_{gtype.value}".encode()).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            vec = np.zeros(self.dim, dtype=np.float32)
            rand = rng.random(self.dim)
            vec[rand < 0.33] = 1.0
            vec[rand > 0.67] = -1.0
            self.vectors[gtype] = vec

    def get(self, gtype: GestaltType) -> np.ndarray:
        return self.vectors[gtype]


# =============================================================================
# PARAGRAPH ENCODER
# =============================================================================


class ParagraphStructureEncoder:
    """
    Encode paragraphs preserving rhetorical structure.

    Features:
    - Coherence relation detection
    - Gestalt point identification
    - Intensity trajectory tracking
    - Topic chain extraction
    """

    # Discourse markers for relation detection
    RELATION_MARKERS = {
        CoherenceRelation.CONTRAST: [
            "but",
            "however",
            "although",
            "though",
            "yet",
            "nevertheless",
            "on the other hand",
            "in contrast",
            "conversely",
            "whereas",
        ],
        CoherenceRelation.CAUSE: ["because", "since", "as", "due to", "owing to", "caused by"],
        CoherenceRelation.EFFECT: [
            "therefore",
            "thus",
            "hence",
            "consequently",
            "as a result",
            "so",
            "accordingly",
            "for this reason",
        ],
        CoherenceRelation.SEQUENCE: [
            "then",
            "next",
            "after",
            "before",
            "when",
            "while",
            "subsequently",
            "previously",
            "finally",
            "first",
        ],
        CoherenceRelation.EXAMPLE: ["for example", "for instance", "such as", "like", "e.g."],
        CoherenceRelation.ELABORATION: [
            "specifically",
            "in particular",
            "namely",
            "that is",
            "in other words",
            "indeed",
            "in fact",
        ],
        CoherenceRelation.CONCESSION: ["despite", "although", "even though", "regardless"],
        CoherenceRelation.RESTATEMENT: ["in other words", "that is to say", "to put it another way"],
    }

    # Gestalt trigger patterns
    GESTALT_TRIGGERS = {
        GestaltType.THESIS: [
            r"^the (point|truth|reality|fact) is",
            r"^fundamentally",
            r"^essentially",
            r"^the core (insight|idea|concept)",
        ],
        GestaltType.PIVOT: [
            r"^but (here's|that's|this is)",
            r"^and yet",
            r"^the problem is",
        ],
        GestaltType.SYNTHESIS: [
            r"^(together|combined|taken together)",
            r"^(this|all this) (means|shows|demonstrates)",
            r"^the connection",
        ],
        GestaltType.HOOK: [
            r"^(consider|imagine|think about|picture)",
            r"^what if",
            r"^\w+\?$",
        ],
        GestaltType.COMPRESSION: [
            r"it's (like|as if|similar to)",
            r"think of it as",
            r"in other words",
        ],
    }

    def __init__(
        self,
        dim: int = D,
        relation_codebook: Optional[RelationCodebook] = None,
        gestalt_codebook: Optional[GestaltCodebook] = None,
        relation_detector: Optional[KeywordDetector] = None,
        gestalt_detector: Optional[RegexPatternDetector] = None,
    ):
        self.dim = dim
        self.relations = relation_codebook or RelationCodebook(dim=dim)
        self.gestalts = gestalt_codebook or GestaltCodebook(dim=dim)
        self.relation_detector = relation_detector or KeywordDetector(self.RELATION_MARKERS)
        self.gestalt_detector = gestalt_detector or RegexPatternDetector(self.GESTALT_TRIGGERS)

    def encode(
        self,
        paragraph: str,
        sentence_vectors: Optional[List[np.ndarray]] = None,
    ) -> ParagraphEncoding:
        """
        Encode a paragraph into HDC space.

        Args:
            paragraph: Raw paragraph text
            sentence_vectors: Pre-computed sentence vectors (optional)

        Returns:
            ParagraphEncoding with structure and vector
        """
        sentences = self._segment(paragraph)

        if not sentences:
            return ParagraphEncoding(
                vector=np.zeros(self.dim, dtype=np.float32),
                structure=ParagraphStructure(
                    raw_text=paragraph,
                    sentences=[],
                    sentence_info=[],
                    relations=[],
                    topic_chain=[],
                    main_claim_idx=0,
                ),
                sentence_vectors=[],
                bank_activations={name: 0.0 for name in PARAGRAPH_BANK_NAMES.values()},
                coherence_score=0.0,
            )

        # Create sentence info with vectors
        sentence_info = []
        sent_vecs = []
        for i, sent in enumerate(sentences):
            if sentence_vectors and i < len(sentence_vectors):
                vec = sentence_vectors[i]
            else:
                # Create hash-based fallback vector
                vec = self._hash_vector(sent)

            info = SentenceInfo(
                text=sent,
                vector=vec,
                intensity_score=self._compute_intensity(sent),
                is_question=sent.strip().endswith("?"),
                has_analogy=self._has_analogy(sent),
                has_meta_commentary=self._has_meta(sent),
            )
            sentence_info.append(info)
            sent_vecs.append(vec)

        # Detect coherence relations
        relations = self._detect_relations(sentences, sentence_info)

        # Extract topic chain
        topic_chain = self._extract_topic_chain(sentences)

        # Identify main claim
        main_idx = self._identify_main_claim(sentences, relations, sentence_info)

        # Detect gestalt points
        gestalt_points = self._detect_gestalt_points(sentences, sentence_info)

        # Compute intensity trajectory
        intensity_values = [info.intensity_score for info in sentence_info]
        intensity_trajectory = IntensityTrajectory.from_values(intensity_values)

        # Find analogy and meta indices
        analogy_indices = [i for i, info in enumerate(sentence_info) if info.has_analogy]
        meta_indices = [i for i, info in enumerate(sentence_info) if info.has_meta_commentary]

        # Build paragraph vector
        para_vec = self._build_paragraph_vector(
            sent_vecs, relations, main_idx, gestalt_points, intensity_trajectory, analogy_indices
        )

        # Compute bank activations
        bank_activations = self._compute_bank_activations(relations)

        # Compute coherence score
        coherence_score = self._compute_coherence(sent_vecs)

        structure = ParagraphStructure(
            raw_text=paragraph,
            sentences=sentences,
            sentence_info=sentence_info,
            relations=relations,
            topic_chain=topic_chain,
            main_claim_idx=main_idx,
            gestalt_points=gestalt_points,
            intensity_trajectory=intensity_trajectory,
            analogy_indices=analogy_indices,
            meta_indices=meta_indices,
        )

        return ParagraphEncoding(
            vector=para_vec,
            structure=structure,
            sentence_vectors=sent_vecs,
            bank_activations=bank_activations,
            coherence_score=coherence_score,
        )

    def _segment(self, paragraph: str) -> List[str]:
        """Split paragraph into sentences."""
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", paragraph)
        return [s.strip() for s in sentences if s.strip()]

    def _hash_vector(self, text: str) -> np.ndarray:
        """Create hash-based vector for text."""
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        vec = np.zeros(self.dim, dtype=np.float32)
        nnz = min(len(text.split()) * 50, 800)
        indices = rng.choice(self.dim, nnz, replace=False)
        for i, idx in enumerate(indices):
            vec[idx] = 1.0 if i % 2 == 0 else -1.0
        return vec

    def _compute_intensity(self, sentence: str) -> float:
        """Compute intensity score for a sentence."""
        intensity_markers = [
            "very",
            "extremely",
            "incredibly",
            "absolutely",
            "totally",
            "!",
            "?!",
            "really",
            "truly",
            "completely",
        ]
        lower = sentence.lower()
        score = 0.5
        for marker in intensity_markers:
            if marker in lower:
                score += 0.1
        score += sentence.count("!") * 0.15
        return min(1.0, score)

    def _has_analogy(self, sentence: str) -> bool:
        """Check if sentence contains analogy."""
        analogy_markers = ["like", "as if", "similar to", "reminds", "imagine"]
        lower = sentence.lower()
        return any(m in lower for m in analogy_markers)

    def _has_meta(self, sentence: str) -> bool:
        """Check if sentence has meta-commentary."""
        meta_markers = ["what i mean", "here's the thing", "the point is", "notice"]
        lower = sentence.lower()
        return any(m in lower for m in meta_markers)

    def _detect_relations(
        self,
        sentences: List[str],
        info_list: List[SentenceInfo],
    ) -> List[Tuple[int, int, CoherenceRelation]]:
        """Detect coherence relations between adjacent sentences."""
        relations = []

        for i in range(len(sentences) - 1):
            j = i + 1

            # Check intensity changes first
            int_i = info_list[i].intensity_score
            int_j = info_list[j].intensity_score

            if int_j - int_i > 0.2:
                relations.append((i, j, CoherenceRelation.ESCALATION))
                continue
            elif int_i - int_j > 0.2:
                relations.append((i, j, CoherenceRelation.DE_ESCALATION))
                continue

            # Check marker-based relations
            relation = self._detect_relation_pair(sentences[i], sentences[j])
            relations.append((i, j, relation))

        return relations

    def _detect_relation_pair(self, sent1: str, sent2: str) -> CoherenceRelation:
        """Detect relation between two sentences using markers."""
        sent2_lower = sent2.lower()

        for relation, markers in self.relation_detector.markers.items():
            for marker in markers:
                if sent2_lower.startswith(marker) or f" {marker}" in sent2_lower[:50]:
                    return relation

        return CoherenceRelation.CONTINUATION

    def _extract_topic_chain(self, sentences: List[str]) -> List[str]:
        """Extract words that persist across sentences."""
        word_counts: Dict[str, int] = {}

        for sent in sentences:
            words = set(re.findall(r"\b[A-Z][a-z]+\b", sent))
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1

        return [word for word, count in word_counts.items() if count >= 2]

    def _identify_main_claim(
        self,
        sentences: List[str],
        relations: List[Tuple[int, int, CoherenceRelation]],
        info_list: List[SentenceInfo],
    ) -> int:
        """Identify which sentence is the main claim."""
        if not sentences:
            return 0

        # Check for thesis gestalt markers
        thesis_patterns = self.gestalt_detector.patterns_for(GestaltType.THESIS)
        for i, sent in enumerate(sentences):
            sent_lower = sent.lower()
            for pattern in thesis_patterns:
                if pattern.search(sent_lower):
                    return i

        # Sentence with most elaborations
        elaboration_counts: Dict[int, int] = {}
        for i, j, rel in relations:
            if rel == CoherenceRelation.ELABORATION:
                elaboration_counts[i] = elaboration_counts.get(i, 0) + 1

        if elaboration_counts:
            return max(elaboration_counts.keys(), key=lambda k: elaboration_counts[k])

        # Highest intensity non-example sentence
        max_intensity = 0.0
        max_idx = 0
        example_indices = {j for i, j, r in relations if r == CoherenceRelation.EXAMPLE}

        for i, info in enumerate(info_list):
            if i not in example_indices and info.intensity_score > max_intensity:
                max_intensity = info.intensity_score
                max_idx = i

        return max_idx

    def _detect_gestalt_points(
        self,
        sentences: List[str],
        info_list: List[SentenceInfo],
    ) -> List[GestaltPoint]:
        """Detect points where meaning crystallizes."""
        gestalt_points = []

        for i, (sent, info) in enumerate(zip(sentences, info_list)):
            sent_lower = sent.lower()

            for gtype in self.GESTALT_TRIGGERS:
                for pattern in self.gestalt_detector.patterns_for(gtype):
                    if pattern.search(sent_lower):
                        weight = 0.5
                        if i == 0:
                            weight = 0.8
                        if gtype == GestaltType.COMPRESSION:
                            weight = 0.9
                        weight *= info.intensity_score

                        gestalt_points.append(GestaltPoint(i, gtype, weight))
                        break

        return gestalt_points

    def _build_paragraph_vector(
        self,
        sent_vecs: List[np.ndarray],
        relations: List[Tuple[int, int, CoherenceRelation]],
        main_idx: int,
        gestalt_points: List[GestaltPoint],
        intensity_trajectory: IntensityTrajectory,
        analogy_indices: List[int],
    ) -> np.ndarray:
        """Build paragraph vector encoding structure."""
        if not sent_vecs:
            return np.zeros(self.dim, dtype=np.float32)

        components = []

        # Main claim with higher weight
        components.append(sent_vecs[main_idx] * 2.0)

        # Gestalt points with weights
        for gp in gestalt_points:
            gestalt_vec = self.gestalts.get(gp.gestalt_type)
            bound = self._bind(sent_vecs[gp.sentence_idx], gestalt_vec)
            components.append(bound * (1 + gp.weight))

        # Analogies with extra weight
        for idx in analogy_indices:
            components.append(sent_vecs[idx] * 1.5)

        # Relation-bound pairs
        for i, j, rel in relations:
            rel_vec = self.relations.get(rel)
            bound = self._bind(self._bind(sent_vecs[i], rel_vec), sent_vecs[j])
            components.append(bound)

        # Intensity peak
        if intensity_trajectory.values:
            peak_idx = intensity_trajectory.peak_index
            if peak_idx < len(sent_vecs):
                components.append(sent_vecs[peak_idx] * 1.3)

        # Individual sentences with lower weight
        for vec in sent_vecs:
            components.append(vec * 0.5)

        return self._bundle(components)

    def _bind(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Bind two vectors (element-wise multiply)."""
        return a * b

    def _bundle(self, vecs: List[np.ndarray]) -> np.ndarray:
        """Bundle vectors with thresholding."""
        if not vecs:
            return np.zeros(self.dim, dtype=np.float32)

        summed = np.stack(vecs).sum(axis=0)
        result = np.zeros(self.dim, dtype=np.float32)
        threshold = len(vecs) * 0.3
        result[summed > threshold] = 1.0
        result[summed < -threshold] = -1.0

        return result

    def _compute_bank_activations(
        self,
        relations: List[Tuple[int, int, CoherenceRelation]],
    ) -> Dict[str, float]:
        """Compute activation per paragraph bank based on relations."""
        activations = {name: 0.0 for name in PARAGRAPH_BANK_NAMES.values()}

        bank_mapping = {
            CoherenceRelation.TOPIC_INTRO: "RHETORICAL",
            CoherenceRelation.CONTINUATION: "RHETORICAL",
            CoherenceRelation.ELABORATION: "RHETORICAL",
            CoherenceRelation.CONTRAST: "RHETORICAL",
            CoherenceRelation.CAUSE: "CAUSAL",
            CoherenceRelation.EFFECT: "CAUSAL",
            CoherenceRelation.EXAMPLE: "EXEMPLIFICATION",
            CoherenceRelation.SUMMARY: "EXEMPLIFICATION",
            CoherenceRelation.SHIFT: "FLOW",
            CoherenceRelation.RETURN: "FLOW",
            CoherenceRelation.PARALLEL: "FLOW",
            CoherenceRelation.SEQUENCE: "FLOW",
            CoherenceRelation.CLAIM: "INTENTIONAL",
            CoherenceRelation.EVIDENCE: "INTENTIONAL",
            CoherenceRelation.CONCESSION: "INTENTIONAL",
        }

        for i, j, rel in relations:
            bank = bank_mapping.get(rel)
            if bank:
                activations[bank] = activations.get(bank, 0.0) + 1.0

        # Normalize
        total = sum(activations.values()) + 1e-6
        for bank in activations:
            activations[bank] /= total

        return activations

    def _compute_coherence(self, sent_vecs: List[np.ndarray]) -> float:
        """Compute overall paragraph coherence."""
        if len(sent_vecs) < 2:
            return 1.0

        coherences = []
        for i in range(len(sent_vecs) - 1):
            v1, v2 = sent_vecs[i], sent_vecs[i + 1]
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 > 0 and norm2 > 0:
                cos = np.dot(v1, v2) / (norm1 * norm2)
                coherences.append(float(cos))

        return float(np.mean(coherences)) if coherences else 1.0

    def similarity(self, enc1: ParagraphEncoding, enc2: ParagraphEncoding) -> float:
        """Compute cosine similarity between paragraph encodings."""
        norm1 = np.linalg.norm(enc1.vector)
        norm2 = np.linalg.norm(enc2.vector)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(enc1.vector, enc2.vector) / (norm1 * norm2))


# Singleton encoder
_paragraph_encoder = None


def get_paragraph_encoder() -> ParagraphStructureEncoder:
    """Get or create the paragraph encoder singleton."""
    global _paragraph_encoder
    if _paragraph_encoder is None:
        _paragraph_encoder = ParagraphStructureEncoder()
    return _paragraph_encoder


def encode_paragraph(paragraph: str) -> ParagraphEncoding:
    """Convenience function to encode a paragraph."""
    return get_paragraph_encoder().encode(paragraph)
