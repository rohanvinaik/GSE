> **Unverified planning document** — moved from the repository root on 2026-10-04. It predates GSE's
> current core and has not been checked against the code; where they disagree, the code and
> [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) are authoritative.

# GSE Implementation Instructions

## For Claude Code / Google Antigravity / LLM Coding Agents

---

## Your Mission

Build **Geometric Semantic Encoding (GSE)**: a symbolic NLP system that encodes natural language as high-dimensional sparse ternary vectors. This is a standalone semantic processing pipeline.

**Reference Specification**: `gse_implementation_spec.md` (attached)

---

## What You're Building

```
Input: "The dog runs in the park."
       ↓
Output: {
  vector: SparseVector[10000],  # Semantic representation
  confidence: 0.94,              # Parse certainty
  merkle_root: "a3f2...",       # Integrity hash
  sense_selections: {...},       # Which word senses used
  anomalies: []                  # Any issues detected
}
```

---

## Implementation Order

### Phase 1: Vector Foundation (Start Here)
**Files**: `gse/vectors.py`, `gse/primitives.py`, `tests/test_vectors.py`

Create:
1. `SparseVector` class with sparse ternary representation
2. `bind()` - element-wise multiplication (creates dissimilar vector)
3. `bundle()` - element-wise addition with normalization (creates similar vector)
4. `permute()` - circular index shift
5. `PrimitiveBasis` class for generating quasi-orthogonal basis vectors

**Key Properties**:
- Dimension: 10,000
- Sparsity: ~10% non-zero
- Values: {-1, 0, +1} only
- Basis vectors must be quasi-orthogonal (|cosine| < 0.1)

**Tests Must Pass**:
- `bind(v1, v2)` produces vector with low similarity to v1 and v2
- `bundle([v1, v2])` produces vector similar to both v1 and v2
- Random vectors have near-zero similarity
- Serialization roundtrip works

### Phase 2: Lexicon Generation
**Files**: `gse/lexicon_generator.py`, `gse/lexicon_validator.py`, `scripts/generate_lexicon.py`

Create:
1. LLM-based word decomposition pipeline (prompt included in spec)
2. Encoding from decomposition to vector
3. SQLite storage for lexicon entries
4. Validation against synonym/antonym pairs

**Key**: Use provided prompt template for LLM decomposition. Store: lemma, POS, sense_id, decomposition JSON, vector blob, frequency.

### Phase 3: Parser Integration
**Files**: `gse/parser.py`, `tests/test_parser.py`

Create:
1. SpaCy wrapper for tokenization, POS tagging, dependency parsing
2. Mapping from dependency relations to semantic roles
3. `ParsedSentence` class with bottom-up traversal order

**Use SpaCy**: `en_core_web_sm` model. Map deps like `nsubj`→`agent`, `dobj`→`patient`.

### Phase 4: Composition Engine
**Files**: `gse/composer.py`, `tests/test_composer.py`

Create:
1. Bottom-up composition following dependency tree
2. Role-filler binding (bind role vector with dependent's vector)
3. Bundling of composed elements
4. Merkle tree computation for verification

**Core Algorithm**:
```python
for token_idx in parsed.bottom_up_order():
    base_vec = lexicon.lookup(token.lemma, token.pos)
    for dependent in get_dependents(token_idx):
        role_vec = basis.roles[dependent.role]
        dep_vec = token_vectors[dependent.idx]
        bound = bind(role_vec, dep_vec)
        components.append(bound)
    token_vectors[token_idx] = bundle([base_vec] + components)
```

### Phase 5: Coherence Checking
**Files**: `gse/coherence.py`, `tests/test_coherence.py`

Create:
1. Coherence scorer (0-1 scale)
2. Anomaly detection (flag "colorless green ideas sleep furiously")
3. Threshold-based pass/fail

### Phase 6: Pipeline API
**Files**: `gse/pipeline.py`, `gse/cli.py`, `tests/test_integration.py`

Create:
1. `GSEPipeline` class wrapping all components
2. `process(text) -> GSEResult` main method
3. `similarity(text1, text2)` convenience method
4. CLI with `encode`, `similarity`, `check`, `batch` commands

---

## File Structure

```
gse/
├── __init__.py
├── vectors.py
├── primitives.py
├── parser.py
├── lexicon_generator.py
├── lexicon_validator.py
├── composer.py
├── coherence.py
├── pipeline.py
└── cli.py

scripts/
├── quickstart.py
├── generate_basis.py
├── generate_lexicon.py
└── validate_lexicon.py

tests/
├── test_vectors.py
├── test_parser.py
├── test_composer.py
├── test_coherence.py
└── test_integration.py

data/
├── basis.msgpack
└── lexicon.db
```

---

## Critical Requirements

1. **Deterministic**: Same input MUST produce same output every time
2. **Sparse**: Vectors must be sparse (~10% non-zero) for efficiency
3. **Ternary**: Only values {-1, 0, +1}
4. **Orthogonal basis**: Primitive vectors must have |cosine| < 0.1 pairwise
5. **Fast**: Single sentence < 20ms processing time

---

## Dependencies

```
numpy>=1.24.0
scipy>=1.10.0
spacy>=3.5.0
msgpack>=1.0.0
pytest>=7.0.0
```

Download SpaCy model: `python -m spacy download en_core_web_sm`

---

## Quick Validation

After each phase, run:
```bash
pytest tests/test_<phase>.py -v
```

For full integration:
```bash
pytest tests/ -v
```

---

## Constants (primitives.py)

```python
PRIMITIVES = [
    "I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY",
    "KIND", "PART", "THIS", "SAME", "OTHER",
    "ONE", "TWO", "SOME", "ALL", "MUCH", "LITTLE",
    "GOOD", "BAD", "BIG", "SMALL",
    "THINK", "KNOW", "WANT", "FEEL", "SEE", "HEAR",
    "SAY", "WORDS", "TRUE", "DO", "HAPPEN", "MOVE",
    "BE", "HAVE", "EXIST", "LIVE", "DIE",
    "WHEN", "NOW", "BEFORE", "AFTER", "LONG_TIME", "SHORT_TIME", "MOMENT",
    "WHERE", "HERE", "ABOVE", "BELOW", "FAR", "NEAR", "INSIDE", "SIDE", "TOUCH",
    "NOT", "MAYBE", "CAN", "BECAUSE", "IF", "VERY", "MORE", "LIKE"
]

ROLES = [
    "agent", "patient", "experiencer", "theme",
    "recipient", "beneficiary", "instrument", "source", "goal", "location",
    "attribute", "manner", "time", "cause", "result",
    "action", "state", "evaluation", "intention", "content"
]
```

---

## Success Criteria

| Phase | Key Test |
|-------|----------|
| 1 | `bind(v1, v2).cosine(v1) < 0.2` |
| 2 | Synonym similarity > 0.4 |
| 3 | Correct parse of "The dog runs." |
| 4 | Merkle root is deterministic |
| 5 | "Colorless green ideas..." flagged |
| 6 | End-to-end < 20ms per sentence |

---

## Reference

Full specification with code templates: `gse_implementation_spec.md`

Start with Phase 1. Run tests. Proceed to Phase 2. Repeat.

Good luck!
