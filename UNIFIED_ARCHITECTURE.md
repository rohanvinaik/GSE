# GSE Unified Architecture: Constraint Cascade with Compound Pattern Learning

## Core Philosophy

This document specifies the unified GSE architecture based on:

1. **Constraint Cascade**: Progressive elimination of interpretations from text → paragraph → sentence → word → HDC
2. **Scale-Specific Primitives**: Each scale has its OWN primitive set (not just semantic primitives)
3. **Compound Pattern Learning**: K-line networks learn PRIMITIVE activation patterns, not word co-occurrences
4. **Graph Traversal + Vector Similarity**: Complementary mechanisms for different problems
5. **Merkle Caching**: Efficient reuse of resolved interpretations

---

## The Constraint Cascade

```
Raw text (infinite interpretations)
    ↓
┌─────────────────────────────────────────────────────────────────┐
│ TEXT-SCALE CONSTRAINTS                                          │
│ Primitives: genre, register, domain, formality                  │
│ Effect: 90% of interpretations eliminated                       │
│ Output: Text-level context frame                                │
└───────────────────────────────┬─────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ PARAGRAPH-SCALE CONSTRAINTS                                     │
│ Primitives: topic, shift, continuation, elaboration, contrast   │
│ Effect: 80% of remaining eliminated                             │
│ Output: Discourse structure + paragraph vectors                 │
└───────────────────────────────┬─────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ SENTENCE-SCALE CONSTRAINTS (GRAMMATICAL primitives)             │
│ Primitives: subject, predicate, object, modifier, complement    │
│ Effect: 90% of remaining eliminated                             │
│ Output: Grammatical frame + role assignments                    │
└───────────────────────────────┬─────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ WORD-SCALE DECOMPOSITION (SEMANTIC primitives)                  │
│ Primitives: 62 NSM primitives (GOOD, FEEL, SOMEONE, etc.)       │
│ Effect: Few possibilities remain                                │
│ Output: Word vectors with polarity                              │
└───────────────────────────────┬─────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ HDC COMPUTATION                                                 │
│ Operations: bind, bundle, permute                               │
│ Effect: Exact answer via vector similarity                      │
│ Output: Final semantic vector                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Key Insight**: Most interpretation work is CONSTRAINT PROPAGATION, not computation. The only compute-heavy part is the final HDC vector math.

---

## Scale-Specific Primitive Sets

### Text-Scale Primitives (~12)

```python
TEXT_PRIMITIVES = [
    # Genre
    "NARRATIVE", "EXPOSITORY", "ARGUMENTATIVE", "DESCRIPTIVE",
    # Register
    "FORMAL", "INFORMAL", "TECHNICAL", "CONVERSATIONAL",
    # Domain signals
    "ACADEMIC", "COMMERCIAL", "PERSONAL", "INSTITUTIONAL"
]
```

Purpose: Sets the "mind frame" for downstream processing. A technical document expects different sentence structures than casual conversation.

### Paragraph-Scale Primitives (~15)

```python
PARAGRAPH_PRIMITIVES = [
    # Discourse relations (RST-inspired)
    "TOPIC_INTRO", "CONTINUATION", "ELABORATION", "CONTRAST",
    "CAUSE", "EFFECT", "EXAMPLE", "SUMMARY",
    # Flow markers
    "SHIFT", "RETURN", "PARALLEL", "SEQUENCE",
    # Intentional
    "CLAIM", "EVIDENCE", "CONCESSION"
]
```

Purpose: Captures how paragraphs relate to each other and internal structure.

### Sentence-Scale Primitives (~20, GRAMMATICAL)

```python
SENTENCE_PRIMITIVES = [
    # Core grammatical functions
    "SUBJECT", "PREDICATE", "OBJECT", "COMPLEMENT",
    # Modifiers
    "ADJUNCT", "ATTRIBUTE", "ADVERBIAL",
    # Clause types
    "MAIN", "SUBORDINATE", "RELATIVE", "CONDITIONAL",
    # Mood/modality
    "DECLARATIVE", "INTERROGATIVE", "IMPERATIVE",
    "CERTAIN", "POSSIBLE", "NECESSARY",
    # Polarity
    "AFFIRMATIVE", "NEGATIVE"
]
```

Purpose: Constrains word sense disambiguation. "I went to the bank" → BANK must be NOUN filling OBJECT role. Eliminates verb reading.

### Word-Scale Primitives (62, SEMANTIC)

```python
WORD_PRIMITIVES = [
    # Substantives
    "I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY",
    # Relational
    "KIND", "PART",
    # Determiners
    "THIS", "SAME", "OTHER",
    # Quantifiers
    "ONE", "TWO", "SOME", "ALL", "MUCH", "LITTLE",
    # Evaluators
    "GOOD", "BAD",
    # Descriptors
    "BIG", "SMALL",
    # Mental predicates
    "THINK", "KNOW", "WANT", "FEEL", "SEE", "HEAR",
    # Speech
    "SAY", "WORDS", "TRUE",
    # Actions
    "DO", "HAPPEN", "MOVE",
    # Existence
    "BE", "HAVE", "EXIST", "LIVE", "DIE",
    # Time
    "WHEN", "NOW", "BEFORE", "AFTER", "LONG_TIME", "SHORT_TIME", "MOMENT",
    # Space
    "WHERE", "HERE", "ABOVE", "BELOW", "FAR", "NEAR", "INSIDE", "SIDE", "TOUCH",
    # Logical
    "NOT", "MAYBE", "CAN", "BECAUSE", "IF",
    # Intensifiers
    "VERY", "MORE",
    # Similarity
    "LIKE"
]
```

---

## Compound Pattern Learning Network

### What It Is NOT

- NOT learning word co-occurrences ("happy" often appears with "birthday")
- NOT gradient descent on massive data
- NOT Hopfield networks or modern neural architectures
- NOT training on specific right/wrong examples

### What It IS

A minimal pattern-matching network that learns COMPOUND PRIMITIVE ACTIVATIONS:

```
If primitives {3, 7, 42} are active
→ Increased proclivity for pattern {4, 19, 62}
```

This is **mechanistic learning**: extracting RULES about how primitives interact, not memorizing specific examples.

### Architecture: Scale-Local Pattern Networks

Each scale has its own tiny pattern network:

```
┌────────────────────────────────────────────────────────┐
│ TEXT-SCALE PATTERN NETWORK                             │
│ Nodes: 12 text primitives                              │
│ Learns: "FORMAL + TECHNICAL → high proclivity ACADEMIC"│
│ Connection matrix: 12 × 12 = 144 weights               │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ PARAGRAPH-SCALE PATTERN NETWORK                        │
│ Nodes: 15 paragraph primitives                         │
│ Learns: "CLAIM + EXAMPLE → proclivity EVIDENCE next"   │
│ Connection matrix: 15 × 15 = 225 weights               │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ SENTENCE-SCALE PATTERN NETWORK                         │
│ Nodes: 20 grammatical primitives                       │
│ Learns: "SUBJECT(animate) + PREDICATE(mental)"         │
│         "→ high coherence for OBJECT(propositional)"   │
│ Connection matrix: 20 × 20 = 400 weights               │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ WORD-SCALE PATTERN NETWORK                             │
│ Nodes: 62 semantic primitives                          │
│ Learns: "FEEL + GOOD + MUCH → pattern for 'ecstatic'"  │
│ Connection matrix: 62 × 62 = 3844 weights              │
└────────────────────────────────────────────────────────┘
```

**Total parameters**: ~4,600 weights across all scales. Compare to billions in LLMs.

### K-Line Storage: Pattern Memory

K-lines store successful COMPOUND activations:

```python
@dataclass
class CompoundKLine:
    """Records a compound primitive activation pattern."""
    id: str
    trigger_pattern: FrozenSet[int]    # Which primitive INDICES activated
    result_pattern: FrozenSet[int]     # What other primitives were co-activated
    confidence: float                   # How reliable this pattern is
    frequency: int                      # How often observed

    # Example:
    # trigger = {3, 7, 42}  (FEEL, GOOD, VERY)
    # result = {4, 19, 62}  (WANT, HAPPY-state, intensity)
```

This is NOT memorizing words - it's encoding the STRUCTURAL relationships between primitives.

### Learning Process

1. **Observe**: Process text through cascade, record which primitives activate together
2. **Extract**: Identify compound patterns (3+ primitives co-occurring)
3. **Strengthen**: When a pattern successfully predicts disambiguation, increase weight
4. **Prune**: Patterns that don't help get weakened and eventually pruned

Training data: The 18k high-quality lexicon entries we just filtered.

---

## Graph Traversal with Layer Slicing

### The Bellman-Ford Improvement Insight

From the paper you referenced: Instead of traversing the entire graph, slice it into layers and find key nodes.

For GSE, this maps perfectly to the constraint cascade:

```
Layer 0: Text primitives (12 nodes)
Layer 1: Paragraph primitives (15 nodes)
Layer 2: Sentence primitives (20 nodes)
Layer 3: Word primitives (62 nodes)
         ↓
Layer 4: Lexicon (18k nodes - but we only reach FEW via constraints)
```

### Key Nodes = Activated Primitives

At each layer, only a FEW primitives are active. These become the "key nodes" for the next layer:

```
Text layer: FORMAL, ACADEMIC activated (2/12)
    ↓ Only traverse paths FROM these 2 nodes
Paragraph layer: CLAIM, EVIDENCE activated (2/15)
    ↓ Only traverse paths FROM these 2 nodes
Sentence layer: SUBJECT(animate), PREDICATE(mental), OBJECT(propositional) (3/20)
    ↓ Only traverse paths FROM these 3 nodes
Word layer: SOMEONE, THINK, SOMETHING, TRUE (4/62)
    ↓ Only lookup words matching this pattern
Lexicon: "believe", "know", "understand" (3/18000)
```

**Complexity**: O(k × L) where k = average active primitives per layer (~3-5), L = layers (4).

Compare to naive O(N) where N = 18000 lexicon entries.

### Implementation: Hierarchical Merkle DAG

```
                    [ROOT HASH]
                   /           \
          [Text hash]     [Text hash...]
              |
      [Paragraph hash]
              |
      [Sentence hash]
         /    |    \
    [Word1] [Word2] [Word3]
```

Each node stores:
- Hash of its children
- Activated primitive indices
- Confidence score
- Pointer to resolved interpretation

**Caching**: Once a prompt is resolved, the Merkle tree is cached. Future prompts with matching prefix can reuse computed subtrees.

---

## Ternary Encoding: The Informational Zero

The {-1, 0, +1} encoding is crucial:

| Value | Meaning |
|-------|---------|
| +1 | Confidently PRESENT / POSITIVE |
| -1 | Confidently OPPOSITE / NEGATIVE |
| 0  | Not applicable / Orthogonal |

### Examples

**"happy" vs "sad"** in the EVALUATOR bank:
- "happy": GOOD = +1
- "sad": GOOD = -1 (same primitive, opposite polarity)
- Similarity: NEGATIVE (they're antonyms, not unrelated)

**"happy" vs "triangle"** in the EVALUATOR bank:
- "happy": GOOD = +1
- "triangle": GOOD = 0 (shapes don't have evaluation)
- Similarity: Near ZERO (orthogonal concepts)

**Cross-bank signals**:
- EVALUATOR and INTENSIFIER are partially orthogonal
- MENTAL and INTENSIFIER are nearly orthogonal
- A non-zero weight connecting orthogonal banks is a NOTABLE SIGNAL

---

## Integration with Existing Code

### What to Keep

1. **`gse/vectors.py`** (Hadamard-OTP architecture) - Core is solid
2. **`gse/primitives.py`** - Extend with scale-specific primitives
3. **`gse/lexicon_generator.py`** - Word-scale encoding works
4. **`gse/patterns/klines.py`** - Refactor to use primitive indices, not words

### What to Refactor

1. **`gse/patterns/pattern_network.py`** → Compound pattern network
2. **`gse/scales/`** → Implement scale-specific primitives and constraints
3. **`gse/orchestration/coordinator.py`** → Implement constraint cascade
4. **`gse/pipeline.py`** → Unified entry point

### What to Remove/Replace

1. **`gse/encoders/`** (torch-based) → Merge into scales with SparseVector
2. **`gse/patterns/cooccurrence.py`** (word co-occurrence) → Replace with primitive patterns

---

## Implementation Plan

### Phase 1: Scale-Specific Primitives

```python
# gse/primitives.py - extend

class Scale(Enum):
    TEXT = "text"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    WORD = "word"

PRIMITIVES_BY_SCALE = {
    Scale.TEXT: TEXT_PRIMITIVES,       # 12
    Scale.PARAGRAPH: PARAGRAPH_PRIMITIVES,  # 15
    Scale.SENTENCE: SENTENCE_PRIMITIVES,    # 20
    Scale.WORD: WORD_PRIMITIVES,            # 62
}
```

### Phase 2: Compound Pattern Network

```python
# gse/patterns/compound_network.py

class CompoundPatternNetwork:
    """
    Learns compound primitive activation patterns.
    NOT word co-occurrences.
    """

    def __init__(self, primitives: List[str], scale: Scale):
        self.primitives = primitives
        self.n = len(primitives)
        self.scale = scale

        # Pairwise connection weights (primitive-to-primitive)
        # NOT word-to-word
        self.weights = np.zeros((self.n, self.n), dtype=np.float32)

        # K-line storage for compound patterns
        self.klines: Dict[FrozenSet[int], CompoundKLine] = {}

    def observe_activation(self, active_indices: Set[int]):
        """
        Record which primitives activated together.
        Update connection weights based on co-activation.
        """
        for i in active_indices:
            for j in active_indices:
                if i != j:
                    self.weights[i, j] += 0.1  # Hebbian-like update

        # Store as K-line if compound (3+ primitives)
        if len(active_indices) >= 3:
            self._store_kline(active_indices)

    def predict_completion(self, active: Set[int]) -> List[Tuple[int, float]]:
        """
        Given active primitives, predict which others should activate.
        Uses COMPOUND patterns, not just pairwise.
        """
        # Check K-line matches first (compound patterns)
        kline_preds = self._kline_predict(active)

        # Fall back to pairwise weights
        pairwise_preds = self._pairwise_predict(active)

        # Combine with K-line taking precedence
        return self._combine_predictions(kline_preds, pairwise_preds)
```

### Phase 3: Constraint Cascade

```python
# gse/cascade.py

class ConstraintCascade:
    """
    Implements the constraint cascade from text to word scale.
    Each layer eliminates interpretations before passing down.
    """

    def __init__(self, lexicon, basis):
        self.text_net = CompoundPatternNetwork(TEXT_PRIMITIVES, Scale.TEXT)
        self.para_net = CompoundPatternNetwork(PARAGRAPH_PRIMITIVES, Scale.PARAGRAPH)
        self.sent_net = CompoundPatternNetwork(SENTENCE_PRIMITIVES, Scale.SENTENCE)
        self.word_net = CompoundPatternNetwork(WORD_PRIMITIVES, Scale.WORD)

        self.lexicon = lexicon
        self.basis = basis

        # Merkle cache for resolved interpretations
        self.cache = MerkleCache()

    def process(self, text: str) -> CascadeResult:
        """Process text through full constraint cascade."""

        # Check cache first
        cache_hit = self.cache.lookup(text)
        if cache_hit:
            return cache_hit

        # Layer 1: Text-scale constraints
        text_frame = self._text_constraints(text)
        # 90% of interpretations eliminated

        # Layer 2: Paragraph-scale constraints
        paragraphs = self._segment_paragraphs(text)
        para_frames = [self._para_constraints(p, text_frame) for p in paragraphs]
        # 80% of remaining eliminated

        # Layer 3: Sentence-scale constraints
        sentences = self._segment_sentences(paragraphs)
        sent_frames = [self._sent_constraints(s, para_frames) for s in sentences]
        # 90% of remaining eliminated

        # Layer 4: Word-scale decomposition
        word_vectors = []
        for sent, frame in zip(sentences, sent_frames):
            words = self._tokenize(sent)
            for word, grammatical_role in words:
                # Frame constrains word sense
                vector = self._decompose_word(word, grammatical_role, frame)
                word_vectors.append(vector)

        # Layer 5: HDC composition
        final_vector = self._compose_hdc(word_vectors, sent_frames)

        # Cache result
        result = CascadeResult(
            text=text,
            vector=final_vector,
            merkle_root=self._compute_merkle(text_frame, para_frames, sent_frames),
            confidence=self._compute_confidence()
        )
        self.cache.store(text, result)

        return result
```

### Phase 4: Merkle Caching

```python
# gse/cache/merkle.py - extend

class MerkleCache:
    """
    Content-addressable cache using Merkle tree structure.
    Enables efficient reuse of resolved interpretations.
    """

    def __init__(self, max_size: int = 10000):
        self.trees: Dict[str, MerkleNode] = {}
        self.max_size = max_size

    def lookup(self, text: str) -> Optional[CascadeResult]:
        """Check if text or prefix has cached interpretation."""
        # Compute hash of text
        text_hash = self._hash(text)

        if text_hash in self.trees:
            return self.trees[text_hash].result

        # Check for prefix matches (partial cache hit)
        for prefix_len in range(len(text) - 1, 0, -1):
            prefix = text[:prefix_len]
            prefix_hash = self._hash(prefix)
            if prefix_hash in self.trees:
                # Found prefix! Return partial result + remaining work
                return self._extend_from_prefix(prefix_hash, text[prefix_len:])

        return None

    def store(self, text: str, result: CascadeResult):
        """Store resolved interpretation with Merkle verification."""
        node = MerkleNode(
            hash=self._hash(text),
            result=result,
            children={}  # Populated with scale-level hashes
        )
        self.trees[node.hash] = node

        # Evict if over capacity
        if len(self.trees) > self.max_size:
            self._evict_lru()
```

---

## Training the Pattern Networks

The networks are trained on the 18k high-quality lexicon entries:

```python
def train_pattern_networks(lexicon_path: str, cascade: ConstraintCascade):
    """
    Train all scale-level pattern networks from lexicon.

    This is LEARNING (extracting mechanistic rules), not TRAINING
    (grading specific examples).
    """
    lexicon = load_lexicon(lexicon_path)

    for entry in lexicon:
        # Get decomposition
        decomp = entry.decomposition  # [(GOOD, agent), (FEEL, action), ...]

        # Convert to primitive indices
        active_indices = {
            cascade.word_net.primitives.index(prim)
            for prim, role in decomp
            if prim in cascade.word_net.primitives
        }

        # Observe activation pattern
        cascade.word_net.observe_activation(active_indices)

    # Prune weak patterns
    cascade.word_net.prune(min_frequency=3, min_strength=0.3)

    print(f"Learned {len(cascade.word_net.klines)} compound patterns")
    print(f"Connection matrix: {cascade.word_net.n}×{cascade.word_net.n} = {cascade.word_net.n**2} weights")
```

---

## Error Handling and Edge Cases

### Genuine Ambiguity

Some text is genuinely ambiguous. The system should:
1. Return multiple interpretations with confidence scores
2. Flag ambiguity for human review
3. NOT pretend to have a definitive answer

```python
class AmbiguousResult:
    """When the cascade can't resolve to a single interpretation."""
    text: str
    interpretations: List[Tuple[SparseVector, float]]  # (vector, confidence)
    ambiguity_type: str  # "lexical", "syntactic", "pragmatic"
```

### Metaphor/Irony/Novel Speech

These are OUT OF SCOPE for deterministic semantic encoding:
- Metaphor requires world knowledge
- Irony requires pragmatic context
- Novel slang requires external lookup

The system should:
1. Detect likely metaphor/irony via sentiment-structure discordance
2. Return "uncertain" interpretation
3. Optionally call external LLM for help

```python
if self._detect_discordance(sentiment, structure):
    return UncertainResult(
        text=text,
        best_guess=literal_interpretation,
        confidence=0.3,
        flag="possible_figurative"
    )
```

---

## Summary

| Aspect | Old Approach | New Unified Approach |
|--------|--------------|---------------------|
| Architecture | Two parallel systems | Single constraint cascade |
| Primitives | 62 word-scale only | 109 across 4 scales |
| Pattern learning | Word co-occurrence | Compound primitive activation |
| Network size | N/A | ~4,600 total weights |
| Graph traversal | Not used | Layer-sliced Bellman-Ford style |
| Caching | Per-sentence | Merkle tree (prefix reuse) |
| Ambiguity | Ignored | Explicit uncertainty |

The key insight: **Most of the work is constraint propagation, not computation.** The HDC vector math is the final step after 99% of interpretations have been eliminated.

---

## Next Steps

1. Extend `primitives.py` with scale-specific primitives
2. Implement `CompoundPatternNetwork`
3. Implement `ConstraintCascade`
4. Extend `MerkleCache` for prefix matching
5. Train networks on clean 18k lexicon
6. Wire everything into unified `pipeline.py`
