"""
Paragraph-level semantic encoding.

Captures inter-sentence relationships and rhetorical structure.
Enhanced with gestalt detection and intensity trajectory tracking.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum
import torch
import re
import hashlib

from .sentence_encoder import (
    SentenceEncoder, SentenceEncoding, 
    EmotionalRegister, RhetoricalFunction
)


class CoherenceRelation(Enum):
    """Rhetorical relations between sentences."""
    ELABORATION = "elaboration"
    CONTRAST = "contrast"
    CAUSE = "cause"
    RESULT = "result"
    TEMPORAL = "temporal"
    CONDITION = "condition"
    CONCESSION = "concession"
    CONTINUATION = "continuation"
    EXAMPLE = "example"
    RESTATEMENT = "restatement"
    ESCALATION = "escalation"      # NEW: Intensity building
    DE_ESCALATION = "de_escalation"  # NEW: Intensity reduction
    ANALOGY = "analogy"            # NEW: Semantic shortcut
    META_SHIFT = "meta_shift"      # NEW: Shift to meta-level
    UNKNOWN = "unknown"


class GestaltType(Enum):
    """Types of meaning crystallization points."""
    THESIS = "thesis"              # Core claim
    PIVOT = "pivot"                # Direction change
    SYNTHESIS = "synthesis"        # Multiple threads combined
    RESOLUTION = "resolution"      # Tension resolved
    HOOK = "hook"                  # Grabs attention
    COMPRESSION = "compression"    # Analogy/metaphor point


@dataclass
class IntensityTrajectory:
    """Track how emotional intensity evolves across paragraph."""
    values: List[float]            # Per-sentence intensity
    peak_index: int                # Where intensity peaks
    trajectory_type: str           # "building", "declining", "stable", "oscillating"
    
    @classmethod
    def from_sentences(cls, encodings: List[SentenceEncoding]) -> "IntensityTrajectory":
        values = [enc.structure.intensity_score for enc in encodings]
        if not values:
            return cls([], 0, "stable")
        
        peak_index = values.index(max(values))
        
        # Determine trajectory type
        if len(values) < 2:
            traj_type = "stable"
        else:
            diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
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
class ParagraphStructure:
    """Parsed paragraph structure."""
    raw_text: str
    sentences: List[str]
    sentence_encodings: List[SentenceEncoding]
    relations: List[Tuple[int, int, CoherenceRelation]]
    topic_chain: List[str]
    main_claim_idx: int
    
    # Enhanced features
    gestalt_points: List[GestaltPoint] = field(default_factory=list)
    intensity_trajectory: Optional[IntensityTrajectory] = None
    analogy_indices: List[int] = field(default_factory=list)
    meta_indices: List[int] = field(default_factory=list)


@dataclass
class ParagraphEncoding:
    """Result of paragraph encoding."""
    vector: torch.Tensor
    structure: ParagraphStructure
    sentence_vectors: List[torch.Tensor]


class RelationCodebook:
    """Codebook of relation vectors."""
    
    def __init__(self, dim: int = 8192, seed: int = 42):
        self.dim = dim
        self.seed = seed
        self.vectors: Dict[CoherenceRelation, torch.Tensor] = {}
        self._generate_vectors()
    
    def _generate_vectors(self):
        for relation in CoherenceRelation:
            seed = int(hashlib.md5(f"{self.seed}_REL_{relation.value}".encode()).hexdigest()[:8], 16)
            torch.manual_seed(seed)
            vec = torch.zeros(self.dim)
            rand = torch.rand(self.dim)
            vec[rand < 0.33] = 1.0
            vec[rand > 0.67] = -1.0
            self.vectors[relation] = vec
    
    def get(self, relation: CoherenceRelation) -> torch.Tensor:
        return self.vectors[relation]


class GestaltCodebook:
    """Codebook for gestalt type vectors."""
    
    def __init__(self, dim: int = 8192, seed: int = 42):
        self.dim = dim
        self.seed = seed
        self.vectors: Dict[GestaltType, torch.Tensor] = {}
        self._generate_vectors()
    
    def _generate_vectors(self):
        for gtype in GestaltType:
            seed = int(hashlib.md5(f"{self.seed}_GESTALT_{gtype.value}".encode()).hexdigest()[:8], 16)
            torch.manual_seed(seed)
            vec = torch.zeros(self.dim)
            rand = torch.rand(self.dim)
            vec[rand < 0.33] = 1.0
            vec[rand > 0.67] = -1.0
            self.vectors[gtype] = vec
    
    def get(self, gtype: GestaltType) -> torch.Tensor:
        return self.vectors[gtype]


class ParagraphEncoder:
    """
    Encode paragraphs preserving rhetorical structure.
    Enhanced with gestalt detection and intensity tracking.
    """
    
    RELATION_MARKERS = {
        CoherenceRelation.CONTRAST: [
            "but", "however", "although", "though", "yet", "nevertheless",
            "on the other hand", "in contrast", "conversely", "whereas"
        ],
        CoherenceRelation.CAUSE: [
            "because", "since", "as", "due to", "owing to", "caused by"
        ],
        CoherenceRelation.RESULT: [
            "therefore", "thus", "hence", "consequently", "as a result",
            "so", "accordingly", "for this reason"
        ],
        CoherenceRelation.TEMPORAL: [
            "then", "next", "after", "before", "when", "while",
            "subsequently", "previously", "finally", "first"
        ],
        CoherenceRelation.CONDITION: [
            "if", "unless", "provided", "assuming", "given that"
        ],
        CoherenceRelation.CONCESSION: [
            "despite", "although", "even though", "regardless"
        ],
        CoherenceRelation.EXAMPLE: [
            "for example", "for instance", "such as", "like", "e.g."
        ],
        CoherenceRelation.ELABORATION: [
            "specifically", "in particular", "namely", "that is",
            "in other words", "indeed", "in fact"
        ],
        CoherenceRelation.RESTATEMENT: [
            "in other words", "that is to say", "to put it another way"
        ],
        CoherenceRelation.ANALOGY: [
            "it's like", "similar to", "just as", "reminds me of",
            "think of it as", "imagine", "picture"
        ],
        CoherenceRelation.META_SHIFT: [
            "what i mean is", "here's the thing", "notice how",
            "the point is", "what's interesting"
        ],
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
            r"^\w+\?$",  # Single word question
        ],
        GestaltType.COMPRESSION: [
            r"it's (like|as if|similar to)",
            r"think of it as",
            r"in other words",
        ],
    }
    
    def __init__(
        self,
        sentence_encoder: SentenceEncoder,
        relation_codebook: Optional[RelationCodebook] = None,
        gestalt_codebook: Optional[GestaltCodebook] = None,
        dim: int = 8192
    ):
        self.sent_encoder = sentence_encoder
        self.relations = relation_codebook or RelationCodebook(dim=dim)
        self.gestalts = gestalt_codebook or GestaltCodebook(dim=dim)
        self.dim = dim
    
    def encode(self, paragraph: str) -> ParagraphEncoding:
        """Encode a paragraph into HDC space."""
        sentences = self._segment(paragraph)
        
        if not sentences:
            return ParagraphEncoding(
                vector=torch.zeros(self.dim),
                structure=ParagraphStructure(
                    raw_text=paragraph,
                    sentences=[],
                    sentence_encodings=[],
                    relations=[],
                    topic_chain=[],
                    main_claim_idx=0
                ),
                sentence_vectors=[]
            )
        
        # Encode each sentence
        sentence_encodings = []
        sentence_vectors = []
        for sent in sentences:
            enc = self.sent_encoder.encode(sent)
            sentence_encodings.append(enc)
            sentence_vectors.append(enc.vector)
        
        # Detect coherence relations
        relations = self._detect_relations(sentences, sentence_encodings)
        
        # Extract topic chain
        topic_chain = self._extract_topic_chain(sentence_encodings)
        
        # Identify main claim
        main_idx = self._identify_main_claim(sentences, relations, sentence_encodings)
        
        # Detect gestalt points (NEW)
        gestalt_points = self._detect_gestalt_points(sentences, sentence_encodings)
        
        # Compute intensity trajectory (NEW)
        intensity_trajectory = IntensityTrajectory.from_sentences(sentence_encodings)
        
        # Find analogy and meta indices (NEW)
        analogy_indices = [i for i, enc in enumerate(sentence_encodings) if enc.structure.has_analogy]
        meta_indices = [i for i, enc in enumerate(sentence_encodings) if enc.structure.has_meta_commentary]
        
        # Build paragraph vector
        para_vec = self._build_paragraph_vector(
            sentence_vectors, relations, main_idx,
            gestalt_points, intensity_trajectory, analogy_indices
        )
        
        structure = ParagraphStructure(
            raw_text=paragraph,
            sentences=sentences,
            sentence_encodings=sentence_encodings,
            relations=relations,
            topic_chain=topic_chain,
            main_claim_idx=main_idx,
            gestalt_points=gestalt_points,
            intensity_trajectory=intensity_trajectory,
            analogy_indices=analogy_indices,
            meta_indices=meta_indices
        )
        
        return ParagraphEncoding(
            vector=para_vec,
            structure=structure,
            sentence_vectors=sentence_vectors
        )
    
    def _segment(self, paragraph: str) -> List[str]:
        """Split paragraph into sentences."""
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', paragraph)
        return [s.strip() for s in sentences if s.strip()]
    
    def _detect_relations(
        self,
        sentences: List[str],
        encodings: List[SentenceEncoding]
    ) -> List[Tuple[int, int, CoherenceRelation]]:
        """Detect coherence relations between adjacent sentences."""
        relations = []
        
        for i in range(len(sentences) - 1):
            j = i + 1
            
            # Check for intensity-based relations first (NEW)
            int_i = encodings[i].structure.intensity_score
            int_j = encodings[j].structure.intensity_score
            
            if int_j - int_i > 0.2:
                relations.append((i, j, CoherenceRelation.ESCALATION))
                continue
            elif int_i - int_j > 0.2:
                relations.append((i, j, CoherenceRelation.DE_ESCALATION))
                continue
            
            # Check for marker-based relations
            relation = self._detect_relation_pair(sentences[i], sentences[j])
            relations.append((i, j, relation))
        
        return relations
    
    def _detect_relation_pair(self, sent1: str, sent2: str) -> CoherenceRelation:
        """Detect relation between two sentences using discourse markers."""
        sent2_lower = sent2.lower()
        
        for relation, markers in self.RELATION_MARKERS.items():
            for marker in markers:
                if sent2_lower.startswith(marker) or f" {marker}" in sent2_lower[:50]:
                    return relation
        
        return CoherenceRelation.CONTINUATION
    
    def _extract_topic_chain(self, encodings: List[SentenceEncoding]) -> List[str]:
        """Extract entities that persist across sentences."""
        entity_counts: Dict[str, int] = {}
        
        for enc in encodings:
            for entity_text, entity_label in enc.structure.named_entities:
                key = entity_text.lower()
                entity_counts[key] = entity_counts.get(key, 0) + 1
        
        return [entity for entity, count in entity_counts.items() if count >= 2]
    
    def _identify_main_claim(
        self,
        sentences: List[str],
        relations: List[Tuple[int, int, CoherenceRelation]],
        encodings: List[SentenceEncoding]
    ) -> int:
        """Identify which sentence is the main claim."""
        if not sentences:
            return 0
        
        # Priority 1: Look for thesis gestalt markers
        for i, enc in enumerate(encodings):
            if enc.structure.rhetorical_function == RhetoricalFunction.CLAIM:
                sent_lower = sentences[i].lower()
                for pattern in self.GESTALT_TRIGGERS[GestaltType.THESIS]:
                    if re.search(pattern, sent_lower):
                        return i
        
        # Priority 2: Sentence with most elaborations
        elaboration_counts = {}
        for i, j, rel in relations:
            if rel == CoherenceRelation.ELABORATION:
                elaboration_counts[i] = elaboration_counts.get(i, 0) + 1
        
        if elaboration_counts:
            return max(elaboration_counts.keys(), key=lambda k: elaboration_counts[k])
        
        # Priority 3: Highest intensity sentence that's not an example
        max_intensity = 0
        max_idx = 0
        for i, enc in enumerate(encodings):
            if enc.structure.rhetorical_function != RhetoricalFunction.EXAMPLE:
                if enc.structure.intensity_score > max_intensity:
                    max_intensity = enc.structure.intensity_score
                    max_idx = i
        
        return max_idx
    
    def _detect_gestalt_points(
        self,
        sentences: List[str],
        encodings: List[SentenceEncoding]
    ) -> List[GestaltPoint]:
        """Detect points where meaning crystallizes."""
        gestalt_points = []
        
        for i, (sent, enc) in enumerate(zip(sentences, encodings)):
            sent_lower = sent.lower()
            
            for gtype, patterns in self.GESTALT_TRIGGERS.items():
                for pattern in patterns:
                    if re.search(pattern, sent_lower):
                        # Weight based on position and intensity
                        weight = 0.5
                        if i == 0:  # First sentence thesis
                            weight = 0.8
                        if gtype == GestaltType.COMPRESSION:  # Analogies are important
                            weight = 0.9
                        weight *= enc.structure.intensity_score
                        
                        gestalt_points.append(GestaltPoint(i, gtype, weight))
                        break
        
        return gestalt_points
    
    def _build_paragraph_vector(
        self,
        sent_vecs: List[torch.Tensor],
        relations: List[Tuple[int, int, CoherenceRelation]],
        main_idx: int,
        gestalt_points: List[GestaltPoint],
        intensity_trajectory: IntensityTrajectory,
        analogy_indices: List[int]
    ) -> torch.Tensor:
        """Build paragraph vector encoding structure."""
        if not sent_vecs:
            return torch.zeros(self.dim)
        
        components = []
        
        # Add main claim with higher weight
        components.append(sent_vecs[main_idx] * 2.0)
        
        # Add gestalt points with their weights (NEW)
        for gp in gestalt_points:
            gestalt_vec = self.gestalts.get(gp.gestalt_type)
            bound = self._bind(sent_vecs[gp.sentence_idx], gestalt_vec)
            components.append(bound * (1 + gp.weight))
        
        # Add analogies with extra weight (NEW)
        for idx in analogy_indices:
            components.append(sent_vecs[idx] * 1.5)
        
        # Add relation-bound pairs
        for i, j, rel in relations:
            rel_vec = self.relations.get(rel)
            bound = self._bind(self._bind(sent_vecs[i], rel_vec), sent_vecs[j])
            components.append(bound)
        
        # Add intensity peak with emphasis (NEW)
        if intensity_trajectory.values:
            peak_idx = intensity_trajectory.peak_index
            components.append(sent_vecs[peak_idx] * 1.3)
        
        # Add individual sentences with lower weight
        for vec in sent_vecs:
            components.append(vec * 0.5)
        
        return self._bundle(components)
    
    def _bind(self, a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        """Bind two vectors."""
        return a * b
    
    def _bundle(self, vecs: List[torch.Tensor]) -> torch.Tensor:
        """Bundle vectors with thresholding."""
        if not vecs:
            return torch.zeros(self.dim)
        
        summed = torch.stack(vecs).sum(dim=0)
        result = torch.zeros_like(summed)
        threshold = len(vecs) * 0.3
        result[summed > threshold] = 1.0
        result[summed < -threshold] = -1.0
        
        return result
    
    def similarity(self, enc1: ParagraphEncoding, enc2: ParagraphEncoding) -> float:
        """Compute cosine similarity between paragraph encodings."""
        return torch.nn.functional.cosine_similarity(
            enc1.vector.unsqueeze(0),
            enc2.vector.unsqueeze(0)
        ).item()
