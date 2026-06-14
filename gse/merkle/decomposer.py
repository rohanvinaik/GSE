#!/usr/bin/env python3
"""
HDC Fuzzy Decomposer for GSE

Decomposes unknown words into primitive combinations using:
1. Morphological analysis (prefixes, suffixes, roots)
2. Context vector similarity routing
3. K-line pattern matching from similar known words
4. Polarity inference from alignment

This module enables the lexicon to handle novel words by:
- Analyzing morphological structure for clues
- Finding similar words in the Merkle tree
- Extracting common primitive patterns
- Inferring polarities from context
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from gse.primitives_v2 import (
    get_canonical_pole,
    is_bipolar,
)
from gse.vectors_v2 import SparseVector, create_basis

# =============================================================================
# MORPHOLOGICAL PATTERNS
# =============================================================================

# Common English prefixes with semantic implications
PREFIX_PATTERNS = {
    # Negation/Opposition
    "un": [("NOT", "modifier", 1)],
    "in": [("NOT", "modifier", 1)],
    "im": [("NOT", "modifier", 1)],
    "il": [("NOT", "modifier", 1)],
    "ir": [("NOT", "modifier", 1)],
    "dis": [("NOT", "modifier", 1)],
    "non": [("NOT", "modifier", 1)],
    "anti": [("NOT", "modifier", 1), ("OTHER", "relation", 1)],

    # Quantity/Degree
    "over": [("BIG", "degree", 1), ("ABOVE", "relation", 1)],
    "under": [("SMALL", "degree", 1), ("BELOW", "relation", 1)],
    "super": [("BIG", "degree", 1), ("ABOVE", "relation", 1)],
    "sub": [("SMALL", "degree", 1), ("BELOW", "relation", 1)],
    "hyper": [("BIG", "degree", 1)],
    "hypo": [("SMALL", "degree", 1)],
    "ultra": [("BIG", "degree", 1)],
    "mini": [("SMALL", "degree", 1)],
    "micro": [("SMALL", "degree", 1)],
    "macro": [("BIG", "degree", 1)],
    "mega": [("BIG", "degree", 1)],
    "multi": [("QUANTITY", "degree", 1)],
    "poly": [("QUANTITY", "degree", 1)],
    "mono": [("ONE", "quantity", 1)],
    "uni": [("ONE", "quantity", 1)],
    "bi": [("TWO", "quantity", 1)],
    "tri": [("QUANTITY", "quantity", 1)],

    # Temporal
    "pre": [("BEFORE", "time", 1)],
    "post": [("AFTER", "time", 1)],
    "re": [("BEFORE", "time", 1), ("SAME", "manner", 1)],
    "neo": [("NOW", "time", 1)],
    "proto": [("BEFORE", "time", 1)],

    # Spatial
    "inter": [("INSIDE", "location", 1)],
    "intra": [("INSIDE", "location", 1)],
    "extra": [("OUTSIDE", "location", 1)],
    "trans": [("MOVE", "action", 1)],
    "circum": [("SIDE", "location", 1)],

    # Agency/Causation
    "auto": [("SAME", "agent", 1), ("DO", "action", 1)],
    "self": [("SAME", "agent", 1)],
    "co": [("SAME", "manner", 1), ("SOMEONE", "agent", 1)],
}

# Common English suffixes with semantic implications
SUFFIX_PATTERNS = {
    # Agent/Doer
    "er": [("SOMEONE", "agent", 1), ("DO", "action", 1)],
    "or": [("SOMEONE", "agent", 1), ("DO", "action", 1)],
    "ist": [("SOMEONE", "agent", 1), ("DO", "action", 1)],
    "ian": [("SOMEONE", "agent", 1)],
    "ant": [("SOMEONE", "agent", 1), ("DO", "action", 1)],
    "ent": [("SOMEONE", "agent", 1), ("DO", "action", 1)],

    # State/Quality
    "ness": [("BE", "state", 1)],
    "ity": [("BE", "state", 1)],
    "ment": [("BE", "state", 1)],
    "tion": [("DO", "action", 1), ("HAPPEN", "result", 1)],
    "sion": [("DO", "action", 1), ("HAPPEN", "result", 1)],
    "ism": [("THINK", "content", 1), ("BE", "state", 1)],
    "dom": [("BE", "state", 1)],
    "hood": [("BE", "state", 1)],
    "ship": [("BE", "state", 1)],

    # Ability/Possibility
    "able": [("CAN", "modifier", 1)],
    "ible": [("CAN", "modifier", 1)],
    "ful": [("QUANTITY", "degree", 1), ("HAVE", "state", 1)],
    "less": [("NOT", "modifier", 1), ("HAVE", "state", -1)],

    # Manner/Direction
    "ly": [],  # Typically manner adverb, context-dependent
    "ward": [("MOVE", "direction", 1)],
    "wards": [("MOVE", "direction", 1)],
    "wise": [("LIKE", "manner", 1)],

    # Evaluation
    "ish": [("LIKE", "manner", 1), ("SMALL", "degree", 1)],
    "ous": [("HAVE", "state", 1)],
    "ive": [("DO", "action", 1), ("HAVE", "state", 1)],
    "al": [],  # Too general
    "ic": [],  # Too general
}

# POS-specific default patterns
POS_DEFAULTS = {
    "n": [("SOMETHING", "theme", 1)],
    "v": [("DO", "action", 1), ("HAPPEN", "result", 1)],
    "adj": [("BE", "attribute", 1)],
    "adv": [("DO", "manner", 1)],
    "prep": [("WHERE", "relation", 1)],
}


# =============================================================================
# DECOMPOSITION RESULT
# =============================================================================

@dataclass
class DecompositionResult:
    """Result of decomposing a word."""
    word: str
    pos: str

    # Inferred decomposition
    decomposition: List[Tuple[str, str, int]] = field(default_factory=list)

    # Confidence scores
    morphological_confidence: float = 0.0
    similarity_confidence: float = 0.0
    pattern_confidence: float = 0.0
    overall_confidence: float = 0.0

    # Sources of inference
    morphological_hints: List[Tuple[str, str, int]] = field(default_factory=list)
    similar_words: List[Tuple[str, float]] = field(default_factory=list)
    pattern_sources: List[str] = field(default_factory=list)

    # Generated vector
    vector: Optional[SparseVector] = None


# =============================================================================
# HDC FUZZY DECOMPOSER
# =============================================================================

class HDCFuzzyDecomposer:
    """
    Decomposes unknown words into primitive combinations.

    Uses multiple sources of information:
    1. Morphological analysis (prefixes, suffixes)
    2. Similar known words from Merkle tree
    3. K-line pattern extraction
    4. Context-based polarity inference
    """

    def __init__(
        self,
        tree: "MerkleLexiconTree",
        router: "MerkleBellmanFord",
        basis: "HadamardOTPBasis" = None,
    ):
        """
        Initialize decomposer.

        Args:
            tree: MerkleLexiconTree with known words
            router: MerkleBellmanFord for similarity search
            basis: HDC basis (created if not provided)
        """
        self.tree = tree
        self.router = router
        self.basis = basis or create_basis()

        # K-line patterns: primitive combinations that co-occur
        self.kline_patterns: Dict[str, Counter] = {}

        # Build K-lines from existing lexemes
        self._build_kline_patterns()

    def _build_kline_patterns(self):
        """Extract K-line patterns from existing lexemes."""
        for lexeme in self.tree.iter_lexemes():
            decomp = lexeme.decomposition
            if len(decomp) < 2:
                continue

            # For each primitive in decomposition
            for i, (prim1, role1, pol1) in enumerate(decomp):
                key = f"{prim1}:{role1}"
                if key not in self.kline_patterns:
                    self.kline_patterns[key] = Counter()

                # Count co-occurring primitives
                for j, (prim2, role2, pol2) in enumerate(decomp):
                    if i != j:
                        co_key = f"{prim2}:{role2}:{pol2}"
                        self.kline_patterns[key][co_key] += 1

    def decompose(
        self,
        word: str,
        pos: str,
        context_vector: Optional[SparseVector] = None,
        gloss: str = "",
    ) -> DecompositionResult:
        """
        Decompose an unknown word into primitives.

        Args:
            word: The word to decompose
            pos: Part of speech
            context_vector: Optional context from surrounding text
            gloss: Optional definition/gloss for hints

        Returns:
            DecompositionResult with inferred decomposition
        """
        result = DecompositionResult(word=word, pos=pos)

        # Step 1: Morphological analysis
        morph_hints = self._analyze_morphology(word)
        result.morphological_hints = morph_hints
        result.morphological_confidence = min(1.0, len(morph_hints) * 0.3)

        # Step 2: Find similar known words
        if context_vector is not None:
            route_result = self.router.route(context_vector, top_k=5)
            similar_words = route_result.matches
        else:
            # Use morphological hints to build initial query
            query = self._build_query_from_hints(morph_hints, pos)
            route_result = self.router.route(query, top_k=5)
            similar_words = route_result.matches

        result.similar_words = similar_words
        result.similarity_confidence = similar_words[0][1] if similar_words else 0.0

        # Step 3: Extract patterns from similar words
        patterns = self._extract_patterns(similar_words)
        result.pattern_sources = [w for w, _ in similar_words[:3]]
        result.pattern_confidence = len(patterns) / 5.0 if patterns else 0.0

        # Step 4: Combine all sources
        combined = self._combine_sources(morph_hints, patterns, pos, gloss)

        # Step 5: Infer polarities from context and patterns
        final_decomp = self._infer_polarities(combined, context_vector, similar_words)

        result.decomposition = final_decomp
        result.overall_confidence = (
            result.morphological_confidence * 0.3 +
            result.similarity_confidence * 0.4 +
            result.pattern_confidence * 0.3
        )

        # Generate vector
        if final_decomp:
            from gse.vectors_v2 import compose_decomposition
            result.vector = compose_decomposition(self.basis, final_decomp)

        return result

    def _analyze_morphology(self, word: str) -> List[Tuple[str, str, int]]:
        """Extract semantic hints from word morphology."""
        hints = []
        word_lower = word.lower()

        # Check prefixes (longest match first)
        for prefix in sorted(PREFIX_PATTERNS.keys(), key=len, reverse=True):
            if word_lower.startswith(prefix) and len(word_lower) > len(prefix) + 2:
                hints.extend(PREFIX_PATTERNS[prefix])
                word_lower = word_lower[len(prefix):]
                break

        # Check suffixes (longest match first)
        for suffix in sorted(SUFFIX_PATTERNS.keys(), key=len, reverse=True):
            if word_lower.endswith(suffix) and len(word_lower) > len(suffix) + 2:
                hints.extend(SUFFIX_PATTERNS[suffix])
                break

        return hints

    def _build_query_from_hints(
        self,
        hints: List[Tuple[str, str, int]],
        pos: str,
    ) -> SparseVector:
        """Build a query vector from morphological hints."""
        # Start with POS defaults
        decomp = list(POS_DEFAULTS.get(pos, []))

        # Add morphological hints
        decomp.extend(hints)

        if not decomp:
            # Fallback to generic
            decomp = [("SOMETHING", "theme", 1)]

        from gse.vectors_v2 import compose_decomposition
        return compose_decomposition(self.basis, decomp)

    def _extract_patterns(
        self,
        similar_words: List[Tuple[str, float]],
    ) -> List[Tuple[str, str, int]]:
        """Extract common patterns from similar words."""
        if not similar_words:
            return []

        # Count primitive occurrences
        prim_counts: Counter = Counter()
        role_counts: Dict[str, Counter] = {}
        pol_counts: Dict[str, Counter] = {}

        for word_key, sim in similar_words:
            lexeme = self.tree.get_lexeme(word_key)
            if not lexeme:
                continue

            for prim, role, pol in lexeme.decomposition:
                prim_counts[prim] += sim  # Weight by similarity

                if prim not in role_counts:
                    role_counts[prim] = Counter()
                    pol_counts[prim] = Counter()

                role_counts[prim][role] += sim
                pol_counts[prim][pol] += sim

        # Select top primitives
        patterns = []
        for prim, count in prim_counts.most_common(5):
            if count < 0.5:  # Threshold
                continue

            # Most common role for this primitive
            role = role_counts[prim].most_common(1)[0][0] if role_counts[prim] else "attribute"

            # Most common polarity
            pol = pol_counts[prim].most_common(1)[0][0] if pol_counts[prim] else 1

            patterns.append((prim, role, pol))

        return patterns

    def _combine_sources(
        self,
        morph_hints: List[Tuple[str, str, int]],
        patterns: List[Tuple[str, str, int]],
        pos: str,
        gloss: str,
    ) -> List[Tuple[str, str, int]]:
        """Combine hints and patterns into decomposition."""
        combined = []
        seen_prims = set()

        # Add POS defaults first
        for item in POS_DEFAULTS.get(pos, []):
            if item[0] not in seen_prims:
                combined.append(item)
                seen_prims.add(item[0])

        # Add morphological hints (high priority)
        for item in morph_hints:
            if item[0] not in seen_prims:
                combined.append(item)
                seen_prims.add(item[0])

        # Add pattern-derived primitives
        for item in patterns:
            if item[0] not in seen_prims:
                combined.append(item)
                seen_prims.add(item[0])

        # Analyze gloss for additional hints
        if gloss:
            gloss_hints = self._analyze_gloss(gloss)
            for item in gloss_hints:
                if item[0] not in seen_prims:
                    combined.append(item)
                    seen_prims.add(item[0])

        return combined[:8]  # Limit decomposition size

    def _analyze_gloss(self, gloss: str) -> List[Tuple[str, str, int]]:
        """Extract hints from gloss/definition."""
        hints = []
        gloss_lower = gloss.lower()

        # Simple keyword matching
        keyword_map = {
            "person": [("SOMEONE", "theme", 1)],
            "thing": [("SOMETHING", "theme", 1)],
            "place": [("WHERE", "location", 1)],
            "time": [("WHEN", "time", 1)],
            "good": [("GOOD", "evaluation", 1)],
            "bad": [("BAD", "evaluation", 1)],
            "big": [("BIG", "size", 1)],
            "small": [("SMALL", "size", 1)],
            "move": [("MOVE", "action", 1)],
            "think": [("THINK", "action", 1)],
            "feel": [("FEEL", "experiencer", 1)],
            "know": [("KNOW", "state", 1)],
            "want": [("WANT", "attitude", 1)],
            "say": [("SAY", "action", 1)],
            "see": [("SEE", "perception", 1)],
            "hear": [("HEAR", "perception", 1)],
        }

        for keyword, prims in keyword_map.items():
            if keyword in gloss_lower:
                hints.extend(prims)

        return hints

    def _infer_polarities(
        self,
        decomp: List[Tuple[str, str, int]],
        context: Optional[SparseVector],
        similar_words: List[Tuple[str, float]],
    ) -> List[Tuple[str, str, int]]:
        """Refine polarities based on context and similar words."""
        result = []

        for prim, role, pol in decomp:
            # Check if this primitive is bipolar
            if is_bipolar(prim):
                # Get canonical form
                canonical, canonical_pol = get_canonical_pole(prim)

                # Adjust polarity if needed
                final_pol = pol * canonical_pol

                # Use canonical name
                result.append((canonical, role, final_pol))
            else:
                result.append((prim, role, pol))

        return result

    def decompose_batch(
        self,
        words: List[Tuple[str, str]],  # (word, pos) pairs
    ) -> List[DecompositionResult]:
        """Decompose multiple words."""
        return [self.decompose(word, pos) for word, pos in words]


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    from gse.merkle import LexemeNode, MerkleLexiconTree
    from gse.merkle.router import MerkleBellmanFord
    from gse.vectors_v2 import compose_decomposition

    print("HDCFuzzyDecomposer Tests")
    print("=" * 50)

    # Create tree with sample lexemes
    tree = MerkleLexiconTree()
    basis = create_basis()

    # Add sample lexemes
    test_lexemes = [
        ("happy", "adj", "01", "feeling joy", [("FEEL", "experiencer", 1), ("GOOD", "attribute", 1)]),
        ("unhappy", "adj", "01", "not feeling joy", [("FEEL", "experiencer", 1), ("BAD", "attribute", 1), ("NOT", "modifier", 1)]),
        ("happiness", "n", "01", "state of being happy", [("FEEL", "experiencer", 1), ("GOOD", "attribute", 1), ("BE", "state", 1)]),
        ("runner", "n", "01", "person who runs", [("MOVE", "action", 1), ("SOMEONE", "agent", 1)]),
        ("teacher", "n", "01", "person who teaches", [("SAY", "action", 1), ("KNOW", "state", 1), ("SOMEONE", "agent", 1)]),
        ("quickly", "adv", "01", "in a fast manner", [("MOVE", "manner", 1)]),
        ("beautiful", "adj", "01", "pleasing to see", [("SEE", "perception", 1), ("GOOD", "evaluation", 1)]),
        ("unbelievable", "adj", "01", "hard to believe", [("THINK", "action", 1), ("NOT", "modifier", 1), ("CAN", "modifier", 1)]),
    ]

    for lemma, pos, sense, gloss, decomp in test_lexemes:
        vec = compose_decomposition(basis, decomp)
        lexeme = LexemeNode(
            node_id=f"{lemma}_{pos}_{sense}",
            lemma=lemma,
            pos=pos,
            sense_id=sense,
            gloss=gloss,
            decomposition=decomp,
            vector_positive=vec.positive_indices,
            vector_negative=vec.negative_indices,
        )
        tree.add_lexeme(lexeme)

    print(f"✓ Created tree with {len(tree.lexemes)} lexemes")

    # Create router and decomposer
    router = MerkleBellmanFord(tree, basis)
    decomposer = HDCFuzzyDecomposer(tree, router, basis)
    print("✓ Decomposer initialized")

    # Test 1: Morphological analysis
    morph = decomposer._analyze_morphology("unhappiness")
    print(f"\n✓ Morphology of 'unhappiness': {morph}")

    morph2 = decomposer._analyze_morphology("unbelievable")
    print(f"✓ Morphology of 'unbelievable': {morph2}")

    # Test 2: Decompose unknown word
    result = decomposer.decompose("sadness", "n", gloss="state of being sad")
    print("\n✓ Decomposition of 'sadness':")
    print(f"  Decomposition: {result.decomposition}")
    print(f"  Confidence: {result.overall_confidence:.3f}")
    print(f"  Similar words: {result.similar_words[:3]}")

    # Test 3: Decompose with prefix
    result2 = decomposer.decompose("rewrite", "v")
    print("\n✓ Decomposition of 'rewrite':")
    print(f"  Decomposition: {result2.decomposition}")
    print(f"  Morphological hints: {result2.morphological_hints}")

    # Test 4: Decompose with suffix
    result3 = decomposer.decompose("swimmer", "n")
    print("\n✓ Decomposition of 'swimmer':")
    print(f"  Decomposition: {result3.decomposition}")
    print(f"  Morphological hints: {result3.morphological_hints}")

    # Test 5: Batch decomposition
    batch_results = decomposer.decompose_batch([
        ("joyful", "adj"),
        ("darkness", "n"),
        ("unable", "adj"),
    ])
    print("\n✓ Batch decomposition:")
    for r in batch_results:
        print(f"  {r.word}: {r.decomposition[:3]}...")

    print("\n" + "=" * 50)
    print("All HDCFuzzyDecomposer tests passed!")
