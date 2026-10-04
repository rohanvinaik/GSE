"""
Constraint Cascade Pipeline

Implements the core GSE processing flow:

    Raw text (infinite interpretations)
        ↓ Text-scale constraints → 90% eliminated
        ↓ Paragraph-scale constraints → 80% of remaining eliminated
        ↓ Sentence-scale constraints → 90% of remaining eliminated
        ↓ Word-scale decomposition → few possibilities
        ↓ HDC computation → exact answer

Key insight: Most work is CONSTRAINT PROPAGATION, not computation.
The only compute-heavy part is the final HDC vector math.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple, Any
from pathlib import Path
import hashlib
import json
import time
import re

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

from gse.primitives import (
    Scale, PRIMITIVES_BY_SCALE,
    TEXT_PRIMITIVES, PARAGRAPH_PRIMITIVES, SENTENCE_PRIMITIVES, WORD_PRIMITIVES,
    HUB_PRIMITIVES, ORCHESTRATOR_NODES, PRIMITIVE_TO_BANK
)
from gse.vectors import SparseVector, PrimitiveBasis, bundle
from gse.patterns.compound_network import WordScaleNetwork, OrchestratorNetwork


@dataclass
class ScaleFrame:
    """
    Activation frame for a single scale.
    Records which primitives are active and with what confidence.
    """
    scale: Scale
    active: Dict[str, float]  # primitive → activation level
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def active_set(self) -> Set[str]:
        """Get set of active primitives (above threshold)."""
        return {p for p, v in self.active.items() if v > 0.1}


@dataclass
class CascadeResult:
    """Result of processing through the full constraint cascade."""
    text: str
    vector: SparseVector
    frames: Dict[Scale, ScaleFrame]
    confidence: float
    merkle_root: str
    processing_time: float
    ambiguities: List[str] = field(default_factory=list)


class MerkleCache:
    """
    Content-addressable cache using Merkle hashing.

    Once a prompt is resolved, the Merkle tree provides:
    1. Verification of encoding integrity
    2. Efficient prefix reuse for similar prompts
    """

    def __init__(self, max_size: int = 10000):
        self.cache: Dict[str, CascadeResult] = {}
        self.prefix_index: Dict[str, List[str]] = {}  # prefix_hash → full_hashes
        self.max_size = max_size
        self.access_times: Dict[str, float] = {}

    def _hash(self, text: str) -> str:
        """Compute content hash."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

    def lookup(self, text: str) -> Optional[CascadeResult]:
        """Check if text has cached result."""
        text_hash = self._hash(text)

        if text_hash in self.cache:
            self.access_times[text_hash] = time.time()
            return self.cache[text_hash]

        return None

    def lookup_prefix(self, text: str, min_prefix_len: int = 20) -> Optional[Tuple[CascadeResult, str]]:
        """
        Find cached result for a prefix of the text.
        Returns (cached_result, remaining_text) if found.
        """
        for prefix_len in range(len(text) - 1, min_prefix_len - 1, -10):
            prefix = text[:prefix_len]
            prefix_hash = self._hash(prefix)

            if prefix_hash in self.cache:
                return (self.cache[prefix_hash], text[prefix_len:])

        return None

    def store(self, text: str, result: CascadeResult) -> None:
        """Store result with Merkle verification."""
        text_hash = self._hash(text)
        self.cache[text_hash] = result
        self.access_times[text_hash] = time.time()

        # Index prefixes for prefix matching
        for prefix_len in [20, 50, 100, 200]:
            if prefix_len < len(text):
                prefix_hash = self._hash(text[:prefix_len])
                if prefix_hash not in self.prefix_index:
                    self.prefix_index[prefix_hash] = []
                self.prefix_index[prefix_hash].append(text_hash)

        # Evict if over capacity
        if len(self.cache) > self.max_size:
            self._evict_lru()

    def _evict_lru(self) -> None:
        """Evict least recently used entries."""
        if not self.access_times:
            return

        # Find oldest entries
        sorted_hashes = sorted(self.access_times.items(), key=lambda x: x[1])
        to_evict = [h for h, _ in sorted_hashes[:len(self.cache) // 4]]

        for h in to_evict:
            if h in self.cache:
                del self.cache[h]
            if h in self.access_times:
                del self.access_times[h]


class ConstraintCascade:
    """
    Main processing pipeline implementing the constraint cascade.

    Progressively narrows interpretation space:
    - Text scale: genre, register, domain → sets mind frame
    - Paragraph scale: discourse relations → narrows topic space
    - Sentence scale: grammatical structure → constrains word senses
    - Word scale: semantic decomposition → final encoding
    """

    def __init__(
        self,
        lexicon_path: Optional[str] = None,
        basis_path: Optional[str] = None,
        use_cache: bool = True
    ):
        """
        Initialize cascade with optional lexicon and basis.

        Args:
            lexicon_path: Path to lexicon.db
            basis_path: Path to basis.msgpack
            use_cache: Whether to use Merkle caching
        """
        self.lexicon_path = lexicon_path
        self.basis_path = basis_path

        # Load basis if provided
        self.basis = None
        if basis_path and Path(basis_path).exists():
            self.basis = PrimitiveBasis.load(basis_path)

        # Load lexicon if provided
        self.lexicon = None
        if lexicon_path and Path(lexicon_path).exists():
            from gse.lexicon_generator import Lexicon
            self.lexicon = Lexicon(lexicon_path, self.basis)

        # Initialize learning networks
        self.word_network = WordScaleNetwork()
        self.orchestrator = OrchestratorNetwork()

        # Merkle cache
        self.cache = MerkleCache() if use_cache else None

        # spaCy for sentence-level parsing
        self.nlp = None
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                print("Warning: spaCy model not found. Run: python -m spacy download en_core_web_sm")

    def train(
        self,
        lexicon_path: Optional[str] = None,
        corpus_dir: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Train the learning networks.

        - Word network: trained on lexicon decompositions
        - Orchestrator: trained on text corpus

        Args:
            lexicon_path: Path to lexicon.db for word-scale training
            corpus_dir: Path to directory with .txt files for orchestrator training

        Returns:
            Dict with training statistics
        """
        stats = {}

        # Train word-scale network
        if lexicon_path:
            count = self.word_network.learn_from_lexicon(lexicon_path)
            stats['word_observations'] = count
            stats['word_patterns'] = len(self.word_network.patterns)

        # Train orchestrator
        if corpus_dir:
            count = self.orchestrator.learn_from_text_corpus(corpus_dir)
            stats['orchestrator_observations'] = count
            stats['orchestrator_patterns'] = len(self.orchestrator.patterns)

        return stats

    def process(self, text: str) -> CascadeResult:
        """
        Process text through the full constraint cascade.

        This is the main entry point for encoding text to HDC vectors.
        """
        start_time = time.time()

        # Check cache first
        if self.cache:
            cached = self.cache.lookup(text)
            if cached:
                return cached

        frames = {}

        # Layer 1: Text-scale constraints
        text_frame = self._text_constraints(text)
        frames[Scale.TEXT] = text_frame

        # Layer 2: Paragraph-scale constraints
        paragraphs = self._segment_paragraphs(text)
        para_frame = self._paragraph_constraints(paragraphs, text_frame)
        frames[Scale.PARAGRAPH] = para_frame

        # Layer 3: Sentence-scale constraints
        sentences = self._segment_sentences(text)
        sent_frame = self._sentence_constraints(sentences, para_frame)
        frames[Scale.SENTENCE] = sent_frame

        # Layer 4: Word-scale decomposition
        word_vectors = self._word_decomposition(sentences, sent_frame)

        # Layer 5: HDC composition
        final_vector = self._compose_hdc(word_vectors)

        # Compute confidence
        confidence = self._compute_confidence(frames)

        # Compute Merkle root
        merkle_root = self._compute_merkle(text, frames)

        # Detect ambiguities
        ambiguities = self._detect_ambiguities(frames)

        result = CascadeResult(
            text=text,
            vector=final_vector,
            frames=frames,
            confidence=confidence,
            merkle_root=merkle_root,
            processing_time=time.time() - start_time,
            ambiguities=ambiguities
        )

        # Cache result
        if self.cache:
            self.cache.store(text, result)

        return result

    def _text_constraints(self, text: str) -> ScaleFrame:
        """
        Apply text-scale constraints.

        Detects: genre, register, domain
        This sets the "mind frame" for all downstream processing.
        """
        active = {}
        text_lower = text.lower()
        word_count = len(text.split())

        # Genre detection (simple heuristics)
        # Narrative markers
        narrative_markers = ["once upon", "he said", "she said", "then", "suddenly",
                           "afterwards", "eventually", "story", "tale"]
        narrative_score = sum(1 for m in narrative_markers if m in text_lower)
        if narrative_score > 2 or "once upon" in text_lower:
            active["NARRATIVE"] = min(1.0, narrative_score * 0.2)

        # Argumentative markers
        argument_markers = ["therefore", "because", "thus", "hence", "consequently",
                          "argue", "claim", "evidence", "prove", "conclude"]
        argument_score = sum(1 for m in argument_markers if m in text_lower)
        if argument_score > 2:
            active["ARGUMENTATIVE"] = min(1.0, argument_score * 0.15)

        # Expository markers
        expository_markers = ["explain", "describe", "define", "means", "is defined as",
                            "for example", "such as", "in other words"]
        expository_score = sum(1 for m in expository_markers if m in text_lower)
        if expository_score > 1:
            active["EXPOSITORY"] = min(1.0, expository_score * 0.2)

        # Descriptive markers
        descriptive_markers = ["beautiful", "looked like", "appeared", "seemed",
                              "was a", "were the", "landscape", "scenery"]
        descriptive_score = sum(1 for m in descriptive_markers if m in text_lower)
        if descriptive_score > 2:
            active["DESCRIPTIVE"] = min(1.0, descriptive_score * 0.2)

        # Register detection
        formal_markers = ["therefore", "consequently", "furthermore", "moreover",
                         "nevertheless", "notwithstanding", "hereby", "whereas"]
        informal_markers = ["kinda", "gonna", "wanna", "dunno", "yeah", "nope",
                           "lol", "omg", "btw", "imo"]

        formal_score = sum(1 for m in formal_markers if m in text_lower)
        informal_score = sum(1 for m in informal_markers if m in text_lower)

        if formal_score > informal_score:
            active["FORMAL"] = min(1.0, formal_score * 0.2)
        elif informal_score > formal_score:
            active["INFORMAL"] = min(1.0, informal_score * 0.2)
            active["CONVERSATIONAL"] = min(1.0, informal_score * 0.15)

        # Technical detection
        technical_markers = ["algorithm", "function", "variable", "parameter",
                           "coefficient", "equation", "theorem", "hypothesis"]
        technical_score = sum(1 for m in technical_markers if m in text_lower)
        if technical_score > 1:
            active["TECHNICAL"] = min(1.0, technical_score * 0.25)

        # Domain detection
        academic_markers = ["study", "research", "findings", "methodology",
                          "abstract", "conclusion", "references", "et al"]
        academic_score = sum(1 for m in academic_markers if m in text_lower)
        if academic_score > 2:
            active["ACADEMIC"] = min(1.0, academic_score * 0.15)

        # Default if nothing detected
        if not active:
            active["EXPOSITORY"] = 0.5  # Default assumption

        confidence = max(active.values()) if active else 0.5

        return ScaleFrame(
            scale=Scale.TEXT,
            active=active,
            confidence=confidence,
            metadata={'word_count': word_count}
        )

    def _segment_paragraphs(self, text: str) -> List[str]:
        """Segment text into paragraphs."""
        # Split on double newlines or significant whitespace
        paragraphs = re.split(r'\n\s*\n', text.strip())
        return [p.strip() for p in paragraphs if p.strip()]

    def _paragraph_constraints(
        self,
        paragraphs: List[str],
        text_frame: ScaleFrame
    ) -> ScaleFrame:
        """
        Apply paragraph-scale constraints.

        Detects discourse relations between paragraphs.
        """
        active = {}

        if len(paragraphs) <= 1:
            # Single paragraph - just continuation
            active["CONTINUATION"] = 0.8
            return ScaleFrame(scale=Scale.PARAGRAPH, active=active, confidence=0.7)

        # Analyze paragraph transitions
        for i, para in enumerate(paragraphs):
            para_lower = para.lower().strip()

            # Topic introduction
            if i == 0 or para_lower.startswith(("first", "to begin", "introduction")):
                active["TOPIC_INTRO"] = active.get("TOPIC_INTRO", 0) + 0.3

            # Contrast markers
            if para_lower.startswith(("however", "but", "on the other hand", "in contrast")):
                active["CONTRAST"] = active.get("CONTRAST", 0) + 0.4

            # Continuation markers
            if para_lower.startswith(("additionally", "furthermore", "moreover", "also")):
                active["CONTINUATION"] = active.get("CONTINUATION", 0) + 0.3

            # Example markers
            if para_lower.startswith(("for example", "for instance", "consider", "such as")):
                active["EXAMPLE"] = active.get("EXAMPLE", 0) + 0.4

            # Cause/effect
            if para_lower.startswith(("because", "therefore", "as a result", "consequently")):
                active["CAUSE"] = active.get("CAUSE", 0) + 0.3
                active["EFFECT"] = active.get("EFFECT", 0) + 0.3

            # Summary/conclusion
            if para_lower.startswith(("in conclusion", "to summarize", "in summary", "overall")):
                active["SUMMARY"] = active.get("SUMMARY", 0) + 0.5

            # Claim markers
            if any(m in para_lower for m in ["i argue", "we claim", "this shows", "it is clear"]):
                active["CLAIM"] = active.get("CLAIM", 0) + 0.3

        # Normalize
        if active:
            max_val = max(active.values())
            active = {k: min(1.0, v / max_val) for k, v in active.items()}

        confidence = max(active.values()) if active else 0.5

        return ScaleFrame(
            scale=Scale.PARAGRAPH,
            active=active,
            confidence=confidence,
            metadata={'n_paragraphs': len(paragraphs)}
        )

    def _segment_sentences(self, text: str) -> List[str]:
        """Segment text into sentences."""
        if self.nlp:
            doc = self.nlp(text)
            return [sent.text.strip() for sent in doc.sents]
        else:
            # Fallback: simple splitting
            sentences = re.split(r'[.!?]+', text)
            return [s.strip() for s in sentences if s.strip()]

    def _sentence_constraints(
        self,
        sentences: List[str],
        para_frame: ScaleFrame
    ) -> ScaleFrame:
        """
        Apply sentence-scale (grammatical) constraints.

        Uses spaCy for parsing, extracts grammatical primitives.
        """
        active = {}

        for sent in sentences:
            if not self.nlp:
                continue

            doc = self.nlp(sent)

            # Analyze sentence structure
            has_subject = False
            has_verb = False
            has_object = False

            for token in doc:
                if token.dep_ in ("nsubj", "nsubjpass"):
                    has_subject = True
                    active["SUBJECT"] = active.get("SUBJECT", 0) + 0.2
                if token.pos_ == "VERB":
                    has_verb = True
                    active["PREDICATE"] = active.get("PREDICATE", 0) + 0.2
                if token.dep_ in ("dobj", "pobj"):
                    has_object = True
                    active["OBJECT"] = active.get("OBJECT", 0) + 0.2

            # Clause type
            if sent.endswith("?"):
                active["INTERROGATIVE"] = active.get("INTERROGATIVE", 0) + 0.5
            elif sent.endswith("!"):
                active["IMPERATIVE"] = active.get("IMPERATIVE", 0) + 0.3
            else:
                active["DECLARATIVE"] = active.get("DECLARATIVE", 0) + 0.2

            # Modality detection
            modal_verbs = {"can", "could", "may", "might", "must", "shall", "should", "will", "would"}
            for token in doc:
                if token.text.lower() in modal_verbs:
                    if token.text.lower() in ("must", "shall"):
                        active["NECESSARY"] = active.get("NECESSARY", 0) + 0.3
                    elif token.text.lower() in ("may", "might", "could"):
                        active["POSSIBLE"] = active.get("POSSIBLE", 0) + 0.3

            # Negation
            for token in doc:
                if token.dep_ == "neg" or token.text.lower() in ("not", "never", "no"):
                    active["NEGATIVE_POL"] = active.get("NEGATIVE_POL", 0) + 0.3

            # Passive voice
            for token in doc:
                if token.dep_ == "nsubjpass":
                    active["PASSIVE_VOICE"] = active.get("PASSIVE_VOICE", 0) + 0.3

        # Normalize
        if active:
            max_val = max(max(active.values()), 1.0)
            active = {k: min(1.0, v / max_val) for k, v in active.items()}

        confidence = 0.8 if self.nlp else 0.4

        return ScaleFrame(
            scale=Scale.SENTENCE,
            active=active,
            confidence=confidence,
            metadata={'n_sentences': len(sentences)}
        )

    def _word_decomposition(
        self,
        sentences: List[str],
        sent_frame: ScaleFrame
    ) -> List[SparseVector]:
        """
        Apply word-scale semantic decomposition.

        Uses lexicon lookup with sentence-frame constraints.
        """
        vectors = []

        if not self.lexicon or not self.basis:
            # Return empty vectors if no lexicon
            return [SparseVector.zeros(8192) for _ in sentences]

        for sent in sentences:
            if self.nlp:
                doc = self.nlp(sent)
                tokens = [(token.lemma_, token.pos_) for token in doc]
            else:
                tokens = [(w.lower(), "NOUN") for w in sent.split()]

            sent_vector = SparseVector.zeros(self.basis.dimension)

            for lemma, pos in tokens:
                # Skip stopwords and punctuation
                if len(lemma) <= 2 or not lemma.isalpha():
                    continue

                # Look up in lexicon
                entry = self.lexicon.lookup(lemma, pos)

                if entry and entry.vector:
                    # Use word-scale network for coherence check if trained
                    if entry.decomposition and self.word_network.total_observations > 100:
                        prims = {d[0] for d in entry.decomposition if len(d) >= 1}
                        coherence = self.word_network.coherence_score(prims)
                        # Bundle if coherent (threshold 0.3)
                        if coherence > 0.3:
                            sent_vector = bundle([sent_vector, entry.vector])
                    else:
                        # No trained network or no decomposition - include the vector
                        sent_vector = bundle([sent_vector, entry.vector])

            vectors.append(sent_vector)

        return vectors

    def _compose_hdc(self, word_vectors: List[SparseVector]) -> SparseVector:
        """
        Final HDC composition of word vectors.

        This is the compute-heavy part - but we've already eliminated
        99% of interpretations through constraint propagation.
        """
        if not word_vectors:
            return SparseVector.zeros(8192)

        if len(word_vectors) == 1:
            return word_vectors[0]

        # Bundle all sentence vectors
        return bundle(word_vectors)

    def _compute_confidence(self, frames: Dict[Scale, ScaleFrame]) -> float:
        """Compute overall confidence from scale frames."""
        if not frames:
            return 0.5

        # Weighted average of frame confidences
        weights = {
            Scale.TEXT: 0.15,
            Scale.PARAGRAPH: 0.2,
            Scale.SENTENCE: 0.3,
            Scale.WORD: 0.35
        }

        total_weight = 0.0
        weighted_conf = 0.0

        for scale, frame in frames.items():
            w = weights.get(scale, 0.25)
            weighted_conf += w * frame.confidence
            total_weight += w

        return weighted_conf / total_weight if total_weight > 0 else 0.5

    def _compute_merkle(self, text: str, frames: Dict[Scale, ScaleFrame]) -> str:
        """Compute Merkle root from frames."""
        components = [text]

        for scale in [Scale.TEXT, Scale.PARAGRAPH, Scale.SENTENCE, Scale.WORD]:
            if scale in frames:
                frame = frames[scale]
                components.append(json.dumps(frame.active, sort_keys=True))

        combined = "|".join(components)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def _detect_ambiguities(self, frames: Dict[Scale, ScaleFrame]) -> List[str]:
        """Detect potential ambiguities in the interpretation."""
        ambiguities = []

        # Low confidence at any scale
        for scale, frame in frames.items():
            if frame.confidence < 0.4:
                ambiguities.append(f"Low confidence at {scale.value} scale")

        # Multiple competing activations
        for scale, frame in frames.items():
            high_activations = [k for k, v in frame.active.items() if v > 0.6]
            if len(high_activations) > 3:
                ambiguities.append(f"Multiple strong signals at {scale.value}: {high_activations}")

        return ambiguities

    def save_networks(self, dir_path: str) -> None:
        """Save trained networks."""
        path = Path(dir_path)
        path.mkdir(parents=True, exist_ok=True)

        self.word_network.save(str(path / "word_network.json"))
        self.orchestrator.save(str(path / "orchestrator_network.json"))

    def load_networks(self, dir_path: str) -> None:
        """Load trained networks."""
        path = Path(dir_path)

        word_path = path / "word_network.json"
        if word_path.exists():
            self.word_network = WordScaleNetwork.load(str(word_path))

        orch_path = path / "orchestrator_network.json"
        if orch_path.exists():
            self.orchestrator = OrchestratorNetwork.load(str(orch_path))


def create_cascade(
    lexicon_path: str = "data/lexicon.db",
    basis_path: str = "data/basis.msgpack",
    networks_dir: Optional[str] = None
) -> ConstraintCascade:
    """
    Factory function to create a fully configured cascade.

    Args:
        lexicon_path: Path to lexicon database
        basis_path: Path to basis vectors
        networks_dir: Optional path to pre-trained networks

    Returns:
        Configured ConstraintCascade instance
    """
    cascade = ConstraintCascade(
        lexicon_path=lexicon_path,
        basis_path=basis_path,
        use_cache=True
    )

    if networks_dir and Path(networks_dir).exists():
        cascade.load_networks(networks_dir)

    return cascade
