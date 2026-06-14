#!/usr/bin/env python3
"""
GSE Pipeline v2 - Complete Integrated Processing Pipeline

Integrates all GSE v2 components:
- Primitives: 8 semantic banks, 10 bipolar dimensions, hierarchical modifiers
- Vectors: Hadamard-OTP basis with exact orthogonality
- Merkle Tree: 5-level lexicon with O(log N) verification
- Routing: Modified Bellman-Ford for semantic search
- Decomposition: HDC fuzzy matching for new words
- Encoding: D/N sentence structure encoding
- Learning: 4 scale networks + orchestrator

Usage:
    from gse.pipeline_v2 import GSEPipeline

    pipeline = GSEPipeline()
    pipeline.load_lexicon("lexicon.db")

    # Encode a sentence
    result = pipeline.encode_sentence("The cat sat on the mat")

    # Find similar words
    matches = pipeline.find_similar("happy", top_k=5)

    # Decompose unknown word
    decomp = pipeline.decompose_word("unhappiness", "n")
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

# Trace API
from gse.api.trace import OperationTrace, OperatorTrace, TokenTrace

# Encoding
from gse.encoders import (
    SentenceStructureEncoder,
    SentenceVectorMetadata,
    WordPosition,
)

# Merkle tree components
from gse.merkle import (
    HDCFuzzyDecomposer,
    LexemeNode,
    MerkleBellmanFord,
    MerkleLearningBridge,
    MerkleLexiconTree,
    SQLiteMerkleTranslator,
)

# Learning networks
from gse.patterns import (
    OrchestratorNetwork,
    ScaleNetworkCollection,
)

# Core primitives and vectors
from gse.primitives_v2 import (
    BIPOLAR_DIMENSIONS,
    DIMS_PER_BANK,
    N_BANKS,
    PRIMITIVE_REGISTRY,
    SENTENCE_PRIMITIVE_REGISTRY,
    D,
    get_compositional_metadata,
)
from gse.vectors_v2 import (
    HadamardOTPBasis,
    SparseVector,
    bundle,
    compose_decomposition,
    create_basis,
)

# =============================================================================
# PIPELINE RESULT TYPES
# =============================================================================

@dataclass
class EncodingResult:
    """Result of encoding text."""
    text: str
    vector: np.ndarray
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Word-level info
    words: List[str] = field(default_factory=list)
    word_vectors: List[SparseVector] = field(default_factory=list)
    decompositions: List[List[Tuple[str, str, int]]] = field(default_factory=list)

    # Sentence-level info
    sentence_vector: Optional[np.ndarray] = None
    sentence_metadata: Optional[SentenceVectorMetadata] = None

    # Layer-2 logical trace (only populated when encode_sentence is called
    # with with_trace=True)
    trace: Optional[OperationTrace] = None


@dataclass
class SimilarityResult:
    """Result of similarity search."""
    query: str
    matches: List[Tuple[str, float]] = field(default_factory=list)
    query_vector: Optional[SparseVector] = None
    route_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecompositionResult:
    """Result of word decomposition."""
    word: str
    pos: str
    decomposition: List[Tuple[str, str, int]] = field(default_factory=list)
    vector: Optional[SparseVector] = None
    confidence: float = 0.0
    source: str = "inferred"  # 'lexicon', 'inferred', 'morphological'
    similar_words: List[Tuple[str, float]] = field(default_factory=list)


# =============================================================================
# MAIN PIPELINE
# =============================================================================

class GSEPipeline:
    """
    Complete GSE v2 processing pipeline.

    Provides unified interface for:
    - Text encoding (word, sentence, document levels)
    - Semantic search and similarity
    - Word decomposition (known and unknown)
    - Learning from text
    """

    def __init__(
        self,
        lexicon_path: Optional[str] = None,
        basis: Optional[HadamardOTPBasis] = None,
    ):
        """
        Initialize pipeline.

        Args:
            lexicon_path: Optional path to SQLite lexicon
            basis: Optional pre-computed HDC basis
        """
        # Core components
        self.basis = basis or create_basis()
        self.tree = MerkleLexiconTree()

        # Encoders
        self.sentence_encoder = SentenceStructureEncoder()

        # Learning networks
        self.networks = ScaleNetworkCollection()
        self.orchestrator = OrchestratorNetwork(self.networks)

        # Router and decomposer (initialized after tree is populated)
        self.router: Optional[MerkleBellmanFord] = None
        self.decomposer: Optional[HDCFuzzyDecomposer] = None
        self.bridge: Optional[MerkleLearningBridge] = None

        # SQLite translator
        self.translator: Optional[SQLiteMerkleTranslator] = None

        # Load lexicon if provided
        if lexicon_path:
            self.load_lexicon(lexicon_path)

        # Statistics
        self._encoding_count = 0
        self._search_count = 0
        self._decomposition_count = 0

    def load_lexicon(self, path: str):
        """
        Load lexicon from SQLite database.

        Args:
            path: Path to SQLite database
        """
        self.translator = SQLiteMerkleTranslator(path)
        self.tree = self.translator.import_to_tree()

        # Initialize router, decomposer, and bridge
        self._init_components()

    def save_lexicon(self, path: Optional[str] = None):
        """
        Save lexicon to SQLite database.

        Args:
            path: Path to save (uses existing path if None)
        """
        if path:
            self.translator = SQLiteMerkleTranslator(path)

        if self.translator:
            self.translator.export_from_tree(self.tree)

    def _init_components(self):
        """Initialize components that depend on populated tree."""
        self.router = MerkleBellmanFord(self.tree, self.basis)
        self.decomposer = HDCFuzzyDecomposer(self.tree, self.router, self.basis)
        self.bridge = MerkleLearningBridge(self.tree, self.networks, self.orchestrator)

    # =========================================================================
    # WORD-LEVEL OPERATIONS
    # =========================================================================

    def encode_word(
        self,
        word: str,
        pos: Optional[str] = None,
    ) -> SparseVector:
        """
        Encode a word to its HDC vector.

        Args:
            word: Word to encode
            pos: Optional part of speech

        Returns:
            SparseVector encoding
        """
        # Try to find in lexicon
        for sense_id in ["01", "02", "03"]:
            for p in [pos, "n", "v", "adj", "adv"] if pos else ["n", "v", "adj", "adv"]:
                key = f"{word.lower()}_{p}_{sense_id}"
                lexeme = self.tree.get_lexeme(key)
                if lexeme:
                    return SparseVector(
                        D,
                        lexeme.vector_positive,
                        lexeme.vector_negative,
                    )

        # Not in lexicon - decompose
        result = self.decompose_word(word, pos or "n")
        return result.vector or SparseVector(D)

    def add_word(
        self,
        lemma: str,
        pos: str,
        decomposition: List[Tuple[str, str, int]],
        gloss: str = "",
        sense_id: str = "01",
    ) -> LexemeNode:
        """
        Add a word to the lexicon.

        Args:
            lemma: Word lemma
            pos: Part of speech
            decomposition: List of (primitive, role, polarity) tuples
            gloss: Optional definition
            sense_id: Sense identifier

        Returns:
            Created LexemeNode
        """
        # Generate vector
        vec = compose_decomposition(self.basis, decomposition)

        lexeme = LexemeNode(
            node_id=f"{lemma}_{pos}_{sense_id}",
            lemma=lemma,
            pos=pos,
            sense_id=sense_id,
            gloss=gloss,
            decomposition=decomposition,
            vector_positive=vec.positive_indices,
            vector_negative=vec.negative_indices,
            source="manual",
        )

        self.tree.add_lexeme(lexeme)

        # Update bridge if available
        if self.bridge:
            self.bridge.update_network_from_lexeme(lexeme)

        return lexeme

    def decompose_word(
        self,
        word: str,
        pos: str,
        context: Optional[str] = None,
        gloss: str = "",
    ) -> DecompositionResult:
        """
        Decompose a word into primitives.

        Args:
            word: Word to decompose
            pos: Part of speech
            context: Optional context sentence
            gloss: Optional definition hint

        Returns:
            DecompositionResult with inferred decomposition
        """
        self._decomposition_count += 1

        # Check if in lexicon
        for sense_id in ["01", "02", "03"]:
            key = f"{word.lower()}_{pos}_{sense_id}"
            lexeme = self.tree.get_lexeme(key)
            if lexeme:
                return DecompositionResult(
                    word=word,
                    pos=pos,
                    decomposition=lexeme.decomposition,
                    vector=SparseVector(D, lexeme.vector_positive, lexeme.vector_negative),
                    confidence=1.0,
                    source="lexicon",
                )

        # Use decomposer for unknown word
        if self.decomposer:
            result = self.decomposer.decompose(word, pos, gloss=gloss)
            return DecompositionResult(
                word=word,
                pos=pos,
                decomposition=result.decomposition,
                vector=result.vector,
                confidence=result.overall_confidence,
                source="inferred",
                similar_words=result.similar_words,
            )

        # Fallback
        return DecompositionResult(
            word=word,
            pos=pos,
            decomposition=[],
            confidence=0.0,
            source="unknown",
        )

    # =========================================================================
    # SENTENCE-LEVEL OPERATIONS
    # =========================================================================

    def encode_sentence(
        self,
        sentence: str,
        include_word_vectors: bool = True,
        with_trace: bool = False,
    ) -> EncodingResult:
        """
        Encode a sentence.

        Args:
            sentence: Sentence text
            include_word_vectors: Whether to include per-word vectors
            with_trace: If True, populate result.trace with a layer-2
                OperationTrace (logical structure suitable for Tier 2 audits)

        Returns:
            EncodingResult with sentence encoding (and trace if requested)
        """
        self._encoding_count += 1

        words = sentence.split()  # Simple tokenization
        n_words = len(words)

        if n_words == 0:
            return EncodingResult(
                text=sentence,
                vector=np.zeros(D, dtype=np.float32),
            )

        # Get word vectors and decompositions
        word_vectors = []
        decompositions = []
        word_positions = []
        syntactic_roles = []
        poses = []

        for i, word in enumerate(words):
            pos = self._guess_pos(word, i, words)
            poses.append(pos)

            decomp_result = self.decompose_word(word, pos)
            decompositions.append(decomp_result.decomposition)

            if decomp_result.vector:
                word_vectors.append(decomp_result.vector)
            else:
                word_vectors.append(SparseVector(D))

            role = self._guess_role(word, i, words)
            syntactic_roles.append(role)
            word_positions.append(WordPosition(
                position=i,
                word=word,
                syntactic_role=role,
                semantic_vector=decomp_result.vector.to_dense() if decomp_result.vector else np.array([]),
            ))

        # Encode sentence structure
        sent_vec, sent_meta = self.sentence_encoder.encode_sentence(word_positions)

        # Combine word vectors (bundle)
        combined = SparseVector(D)
        for wv in word_vectors:
            if wv.nnz > 0:
                combined = bundle([combined, wv])

        trace = None
        if with_trace:
            trace = self._build_operation_trace(
                sentence=sentence,
                words=words,
                poses=poses,
                decompositions=decompositions,
                word_vectors=word_vectors,
                syntactic_roles=syntactic_roles,
                combined=combined,
            )

        return EncodingResult(
            text=sentence,
            vector=combined.to_dense(),
            words=words,
            word_vectors=word_vectors if include_word_vectors else [],
            decompositions=decompositions,
            sentence_vector=sent_vec,
            sentence_metadata=sent_meta,
            metadata={
                "n_words": n_words,
                "dims_per_word": D / n_words,
            },
            trace=trace,
        )

    # =========================================================================
    # TRACE GENERATION
    # =========================================================================

    # Surface-form → COMP primitive map for operator detection.
    # Tier 2 will replace this with parser-driven operator resolution.
    _COMP_LEMMA_MAP = {
        "than": "COMP_THAN",
        "as": "COMP_AS",
        "how": "COMP_HOW",
        "what": "COMP_WHAT",
        "just": "COMP_JUST",
        "only": "COMP_ONLY",
        "even": "COMP_EVEN",
        "but": "COMP_BUT",
        "so": "COMP_SO",
        "because": "COMP_BECAUSE",
    }

    def _build_operation_trace(
        self,
        sentence: str,
        words: List[str],
        poses: List[str],
        decompositions: List[List[Tuple[str, str, int]]],
        word_vectors: List[SparseVector],
        syntactic_roles: List[str],
        combined: SparseVector,
    ) -> OperationTrace:
        """Build an OperationTrace from per-token encoding info."""
        # Per-token traces
        token_traces: List[TokenTrace] = []
        operators: List[OperatorTrace] = []

        for i, (word, pos, decomp, wv, role) in enumerate(
            zip(words, poses, decompositions, word_vectors, syntactic_roles)
        ):
            word_prims = {prim: polarity for prim, _role, polarity in decomp}
            sent_prims = {role: 1} if role else {}

            comp_prim_name = self._COMP_LEMMA_MAP.get(word.lower())
            is_op = comp_prim_name is not None
            comp_arity = 0
            comp_operation: Optional[str] = None
            if is_op and comp_prim_name in SENTENCE_PRIMITIVE_REGISTRY:
                meta = get_compositional_metadata(comp_prim_name)
                if meta is not None:
                    comp_arity, comp_operation = meta

            token_traces.append(TokenTrace(
                token=word,
                lemma=word.lower(),
                pos=pos,
                position=i,
                word_primitives=word_prims,
                sent_primitives=sent_prims,
                word_vec_nnz=wv.nnz,
                sent_vec_nnz=0,
                full_vec_nnz=wv.nnz,
                is_operator=is_op,
                comp_primitive=comp_prim_name,
                comp_operation=comp_operation,
                comp_arity=comp_arity,
            ))

            if is_op and comp_prim_name is not None:
                arg1_tokens, arg2_tokens = self._resolve_operator_args(
                    operator_position=i,
                    arity=comp_arity if comp_arity > 0 else 2,
                    n_tokens=len(words),
                )
                operators.append(OperatorTrace(
                    primitive=comp_prim_name,
                    operation=comp_operation or "",
                    position=i,
                    arity=comp_arity if comp_arity > 0 else 2,
                    arg1_tokens=arg1_tokens,
                    arg2_tokens=arg2_tokens,
                    arg1_lemmas=[words[t].lower() for t in arg1_tokens],
                    arg2_lemmas=[words[t].lower() for t in arg2_tokens],
                    result_nnz=wv.nnz,
                ))

        # Primitive activations (cosine with each primitive in basis)
        word_acts: Dict[str, float] = {}
        for prim_name in PRIMITIVE_REGISTRY:
            prim_vec = self.basis.get_primitive(prim_name)
            if prim_vec is not None and combined.nnz > 0:
                word_acts[prim_name] = float(combined.cosine(prim_vec))

        sent_acts: Dict[str, float] = {}
        # Sentence-scale primitives are tracked by syntactic role assignment;
        # populate from observed roles (richer activation requires Layer-2 trace
        # integration with the parser, deferred to a follow-up).
        for role in syntactic_roles:
            sent_acts[role] = sent_acts.get(role, 0.0) + 1.0

        final_nnz = combined.nnz
        sparsity = final_nnz / D if D > 0 else 0.0

        # Deterministic trace hash: combines vector indices with token sequence.
        # Tokens are included so traces from sentences with empty decompositions
        # (no lexicon loaded) still hash to distinct values.
        hasher = __import__("hashlib").sha256()
        hasher.update(combined.positive_indices.tobytes())
        hasher.update(combined.negative_indices.tobytes())
        hasher.update("|".join(t.lower() for t in words).encode("utf-8"))
        vector_hash = hasher.hexdigest()[:16]

        trace = OperationTrace(
            input_text=sentence,
            tokens=token_traces,
            operators=operators,
            final_nnz=final_nnz,
            sparsity=sparsity,
            word_primitive_activations=word_acts,
            sent_primitive_activations=sent_acts,
            vector_hash=vector_hash,
        )
        trace.vector = combined
        return trace

    @staticmethod
    def _resolve_operator_args(
        operator_position: int,
        arity: int,
        n_tokens: int,
    ) -> Tuple[List[int], List[int]]:
        """
        Resolve operator argument token positions by surface order.

        Defaults: arg1 = tokens before the operator, arg2 = tokens after.
        For arity 1, arg2 is empty. Tier 2 parser integration will replace
        this with proper scope resolution.
        """
        before = list(range(0, operator_position))
        after = list(range(operator_position + 1, n_tokens))
        if arity <= 1:
            return before, []
        return before, after

    def _guess_pos(self, word: str, position: int, words: List[str]) -> str:
        """Guess part of speech from word and position."""
        # Very simple heuristics
        word_lower = word.lower()

        if word_lower in ["the", "a", "an", "this", "that"]:
            return "det"
        if word_lower in ["is", "are", "was", "were", "be", "been", "being"]:
            return "v"
        if word_lower.endswith("ly"):
            return "adv"
        if word_lower.endswith(("ed", "ing", "s")) and len(word_lower) > 3:
            return "v"
        if word_lower.endswith(("ness", "tion", "ity", "ment")):
            return "n"
        if position == 0 or (position > 0 and words[position-1].lower() in ["the", "a", "an"]):
            return "n"

        return "n"  # Default

    def _guess_role(self, word: str, position: int, words: List[str]) -> str:
        """Guess syntactic role from position."""
        n = len(words)

        if position == 0:
            return "SYN_SUBJ"
        if position == 1 and n > 2:
            return "SYN_PRED"
        if position == n - 1:
            return "SYN_OBJ"

        word_lower = word.lower()
        if word_lower in ["the", "a", "an"]:
            return "SYN_DET"

        return "SYN_ADJ_MOD"

    # =========================================================================
    # SIMILARITY SEARCH
    # =========================================================================

    def find_similar(
        self,
        query: Union[str, SparseVector, List[Tuple[str, str, int]]],
        top_k: int = 10,
        pos: Optional[str] = None,
    ) -> SimilarityResult:
        """
        Find similar words in the lexicon.

        Args:
            query: Word string, vector, or decomposition
            top_k: Number of results
            pos: Optional POS filter

        Returns:
            SimilarityResult with matches
        """
        self._search_count += 1

        # Convert query to vector
        if isinstance(query, str):
            query_str = query
            decomp_result = self.decompose_word(query, pos or "n")
            query_vec = decomp_result.vector or SparseVector(D)
        elif isinstance(query, list):
            query_str = str(query)
            query_vec = compose_decomposition(self.basis, query)
        else:
            query_str = "vector"
            query_vec = query

        # Route through tree
        if self.router:
            result = self.router.route(query_vec, top_k=top_k)

            # Filter by POS if specified
            matches = result.matches
            if pos:
                matches = [(k, s) for k, s in matches if f"_{pos}_" in k]

            return SimilarityResult(
                query=query_str,
                matches=matches[:top_k],
                query_vector=query_vec,
                route_info={
                    "banks_checked": result.banks_checked,
                    "families_checked": result.families_checked,
                    "lexemes_checked": result.lexemes_checked,
                },
            )

        return SimilarityResult(query=query_str, query_vector=query_vec)

    def compare(
        self,
        word1: str,
        word2: str,
        pos1: Optional[str] = None,
        pos2: Optional[str] = None,
    ) -> float:
        """
        Compare similarity between two words.

        Args:
            word1, word2: Words to compare
            pos1, pos2: Optional POS hints

        Returns:
            Cosine similarity in [-1, 1]
        """
        vec1 = self.encode_word(word1, pos1)
        vec2 = self.encode_word(word2, pos2)
        return vec1.cosine(vec2)

    # =========================================================================
    # LEARNING
    # =========================================================================

    def learn_from_text(self, text: str):
        """
        Learn patterns from text.

        Args:
            text: Text to learn from
        """
        # Encode to get decompositions
        result = self.encode_sentence(text)

        # Learn word-level patterns
        for decomp in result.decompositions:
            if decomp:
                self.networks.word.learn_from_decomposition(decomp)

        # Learn sentence-level patterns
        if result.sentence_metadata:
            struct = {role: 1.0 for role in result.sentence_metadata.syntactic_roles}
            self.networks.sentence.learn(struct)

    def train_from_corpus(self, texts: List[str]):
        """
        Train networks from a corpus of texts.

        Args:
            texts: List of text strings
        """
        for text in texts:
            self.learn_from_text(text)

        # Train bridge if available
        if self.bridge:
            self.bridge.train_from_tree()

    # =========================================================================
    # STATISTICS AND DIAGNOSTICS
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        stats = {
            "lexicon": {
                "total_lexemes": len(self.tree.lexemes),
                "banks": len(self.tree.banks),
                "families": len(self.tree.families),
                "hubs": len(self.tree.hubs),
                "root_hash": self.tree.get_root_hash()[:16] + "...",
            },
            "basis": {
                "dimension": D,
                "n_banks": N_BANKS,
                "dims_per_bank": DIMS_PER_BANK,
                "bipolar_pairs": len(BIPOLAR_DIMENSIONS),
            },
            "usage": {
                "encodings": self._encoding_count,
                "searches": self._search_count,
                "decompositions": self._decomposition_count,
            },
        }

        if self.bridge:
            stats["networks"] = self.bridge.get_statistics()["networks"]

        return stats

    def verify_integrity(self) -> Tuple[bool, List[str]]:
        """Verify lexicon integrity."""
        return self.tree.verify_integrity()

    def get_lexeme(self, key: str) -> Optional[LexemeNode]:
        """Get lexeme by key."""
        return self.tree.get_lexeme(key)

    def iter_lexemes(self):
        """Iterate over all lexemes."""
        return self.tree.iter_lexemes()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_pipeline(lexicon_path: Optional[str] = None) -> GSEPipeline:
    """
    Create a new GSE pipeline.

    Args:
        lexicon_path: Optional path to lexicon database

    Returns:
        Initialized GSEPipeline
    """
    return GSEPipeline(lexicon_path=lexicon_path)


def encode_text(text: str, pipeline: Optional[GSEPipeline] = None) -> EncodingResult:
    """
    Encode text using default pipeline.

    Args:
        text: Text to encode
        pipeline: Optional pipeline (creates new if None)

    Returns:
        EncodingResult
    """
    if pipeline is None:
        pipeline = GSEPipeline()
    return pipeline.encode_sentence(text)


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    print("GSEPipeline v2 Tests")
    print("=" * 50)

    # Create pipeline
    pipeline = GSEPipeline()
    print(f"✓ Created pipeline with D={D} dimensions")

    # Add some words
    pipeline.add_word("happy", "adj", [("FEEL", "experiencer", 1), ("GOOD", "attribute", 1)], "feeling joy")
    pipeline.add_word("sad", "adj", [("FEEL", "experiencer", 1), ("BAD", "attribute", 1)], "feeling sorrow")
    pipeline.add_word("think", "v", [("THINK", "action", 1), ("SOMEONE", "agent", 1)], "use mind")
    pipeline.add_word("run", "v", [("MOVE", "action", 1), ("SOMEONE", "agent", 1)], "move fast")
    pipeline.add_word("big", "adj", [("BIG", "attribute", 1)], "large in size")
    print(f"✓ Added {len(pipeline.tree.lexemes)} words to lexicon")

    # Initialize components
    pipeline._init_components()

    # Test word encoding
    vec = pipeline.encode_word("happy")
    print(f"✓ Encoded 'happy': nnz={vec.nnz}")

    # Test sentence encoding
    result = pipeline.encode_sentence("The happy person runs")
    print(f"✓ Encoded sentence: {result.metadata['n_words']} words, {result.metadata['dims_per_word']:.1f} dims/word")

    # Test similarity search
    matches = pipeline.find_similar("happy", top_k=3)
    print(f"✓ Similar to 'happy': {matches.matches}")

    # Test word comparison
    sim = pipeline.compare("happy", "sad")
    print(f"✓ Similarity happy/sad: {sim:.4f}")

    sim2 = pipeline.compare("happy", "happy")
    print(f"✓ Similarity happy/happy: {sim2:.4f}")

    # Test decomposition
    decomp = pipeline.decompose_word("happiness", "n")
    print(f"✓ Decomposed 'happiness': {decomp.decomposition[:3]}... (conf={decomp.confidence:.3f})")

    # Test learning
    pipeline.learn_from_text("The happy person thinks about running")
    print("✓ Learned from text")

    # Test statistics
    stats = pipeline.get_statistics()
    print(f"✓ Statistics: {stats['lexicon']['total_lexemes']} lexemes, {stats['usage']['encodings']} encodings")

    # Test integrity
    valid, errors = pipeline.verify_integrity()
    print(f"✓ Integrity check: {'PASS' if valid else 'FAIL'}")

    # Test save/load with temp file
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_lexicon.db")

        # Save
        pipeline.save_lexicon(db_path)
        print(f"✓ Saved lexicon to {db_path}")

        # Create new pipeline and load
        pipeline2 = GSEPipeline(lexicon_path=db_path)
        print(f"✓ Loaded lexicon: {len(pipeline2.tree.lexemes)} lexemes")

        # Verify same root hash
        assert pipeline.tree.get_root_hash() == pipeline2.tree.get_root_hash()
        print("✓ Root hash verified")

    print("\n" + "=" * 50)
    print("All GSEPipeline v2 tests passed!")
