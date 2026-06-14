# GSE Final Integration: NL → Operations → Output

## System Status

**COMPLETE:**
- Word-scale HDC encoding (62 semantic primitives, 8 banks)
- Sentence-scale HDC encoding (24 primitives, 8 banks, orthogonal)
- Lexicon database (18,622 words with primitives)
- NLP integration (spaCy → primitive mappings)
- Compositional operators (COMP_THAN, COMP_HOW, COMP_JUST, etc.)
- bind/bundle/permute operations

**REMAINING:**
- Unified API wrapper
- JSON operation trace format
- Reconstruction/decoding
- Verification suite

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GSE ENCODER                              │
│  "The dog is cuter than the cat"                                │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  1. TOKENIZE (spaCy)                                    │   │
│  │     → tokens, lemmas, POS, dependencies                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  2. LEXICON LOOKUP                                      │   │
│  │     → word_primitives[], sent_primitives[]              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  3. VECTOR COMPOSITION                                  │   │
│  │     → bind(word_vec, sent_vec) for each token           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  4. OPERATOR RESOLUTION                                 │   │
│  │     → Apply COMP_* operations (SET_DIFF, DEGREE_QUERY)  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  5. BUNDLE + POSITION ENCODING                          │   │
│  │     → Final sentence vector (8192-dim)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│                    JSON OPERATION TRACE                         │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     OPERATION TRACE (JSON)                      │
│  {                                                              │
│    "input": "The dog is cuter than the cat",                    │
│    "tokens": [...],                                             │
│    "operations": [                                              │
│      {"op": "BIND", "args": ["word:dog", "sent:SYN_SUBJ"]},     │
│      {"op": "COMP_THAN", "args": ["dog+cuter", "cat"],          │
│       "semantics": "SET_DIFF"}                                  │
│    ],                                                           │
│    "vector_hash": "a3f8c2...",                                  │
│    "primitives_activated": ["SOMETHING", "BODY", "GOOD", ...]   │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        GSE DECODER                              │
│  (Future: reconstruct to NL or other modalities)                │
└─────────────────────────────────────────────────────────────────┘
```

---

## JSON Operation Trace Format

```json
{
  "version": "1.0",
  "input": {
    "text": "The dog is cuter than the cat",
    "language": "en"
  },

  "parse": {
    "tokens": [
      {"id": 0, "text": "The", "lemma": "the", "pos": "DET", "dep": "det"},
      {"id": 1, "text": "dog", "lemma": "dog", "pos": "NOUN", "dep": "nsubj"},
      {"id": 2, "text": "is", "lemma": "be", "pos": "AUX", "dep": "ROOT"},
      {"id": 3, "text": "cuter", "lemma": "cute", "pos": "ADJ", "dep": "acomp"},
      {"id": 4, "text": "than", "lemma": "than", "pos": "ADP", "dep": "prep"},
      {"id": 5, "text": "the", "lemma": "the", "pos": "DET", "dep": "det"},
      {"id": 6, "text": "cat", "lemma": "cat", "pos": "NOUN", "dep": "pobj"}
    ]
  },

  "encodings": [
    {
      "token_id": 1,
      "lemma": "dog",
      "word_scale": {
        "primitives": {"SOMETHING": 1, "BODY": 1, "ALIVE": 1},
        "vector_nnz": 153
      },
      "sentence_scale": {
        "primitives": {"SYN_SUBJ": 1, "SYN_OBJ": 1},
        "vector_nnz": 102
      },
      "composed": {
        "operation": "BIND(word_vec, sent_vec)",
        "vector_nnz": 11
      }
    }
  ],

  "operators": [
    {
      "type": "COMP_THAN",
      "position": 4,
      "semantics": "SET_DIFF",
      "arity": 2,
      "arguments": {
        "arg1": {"tokens": [1, 3], "description": "comparee (dog + cuter)"},
        "arg2": {"tokens": [6], "description": "standard (cat)"}
      },
      "result": {
        "operation": "BIND(bundle(arg1), negate(bundle(arg2)))",
        "interpretation": "Degree difference: dog's cuteness exceeds cat's"
      }
    }
  ],

  "composition": {
    "operations": [
      {"op": "PERMUTE", "token_id": 1, "shift": 100},
      {"op": "PERMUTE", "token_id": 3, "shift": 300},
      {"op": "PERMUTE", "token_id": 6, "shift": 600},
      {"op": "BUNDLE", "inputs": ["token_1", "token_3", "token_6", "COMP_THAN_result"]}
    ]
  },

  "output": {
    "vector_hash": "sha256:a3f8c2d1e5b7...",
    "vector_nnz": 44,
    "sparsity": 0.0054,
    "dominant_primitives": [
      {"name": "SOMETHING", "activation": 0.82},
      {"name": "BODY", "activation": 0.71},
      {"name": "GOOD", "activation": 0.45}
    ]
  },

  "metadata": {
    "timestamp": "2026-01-04T12:00:00Z",
    "gse_version": "2.0",
    "deterministic": true
  }
}
```

---

## Implementation Plan

### Phase 1: GSE Encoder API (1 day)

**File: `gse/api/encoder.py`**

```python
class GSEEncoder:
    def encode(self, text: str) -> OperationTrace:
        """Full encoding pipeline returning structured trace."""

    def encode_batch(self, texts: List[str]) -> List[OperationTrace]:
        """Batch encoding for efficiency."""

    def to_json(self, trace: OperationTrace) -> str:
        """Serialize trace to JSON."""

    def to_vector(self, trace: OperationTrace) -> np.ndarray:
        """Extract final vector from trace."""
```

### Phase 2: Verification Suite (1 day)

**File: `gse/verification/`**

1. **Reproducibility Test**
   - Same input → identical JSON trace
   - Same input → identical vector hash

2. **Similarity Preservation Test**
   - "The dog is cute" ~ "The cat is cute" (high similarity)
   - "The dog is cute" ≁ "Mathematics is abstract" (low similarity)

3. **Compositional Sanity Tests**
   - "dog is cuter than cat" ≠ "cat is cuter than dog" (argument order matters)
   - COMP_THAN(A, B) ≈ -COMP_THAN(B, A) (antisymmetry)

4. **Operator Semantics Tests**
   - SET_DIFF produces measurable difference
   - DEGREE_QUERY extracts scalar information

5. **Round-Trip Verification**
   - Encode → Vector → Nearest neighbors → Semantically related

### Phase 3: CLI/Demo Interface (0.5 day)

```bash
# Encode and show trace
gse encode "The dog is cuter than the cat" --format json

# Compare two sentences
gse compare "Dogs are loyal" "Cats are independent"

# Verify system
gse verify --suite all
```

### Phase 4: Decoder Prototype (Future)

For reconstruction, we need:
1. **Nearest-neighbor lexeme lookup** from vector
2. **Template generation** from operator structure
3. **LLM-assisted verbalization** (use trace as structured prompt)

---

## Verification Metrics

### 1. Determinism Score
```
Input: 1000 random sentences
Expected: 100% identical traces on re-encoding
```

### 2. Similarity Correlation
```
Human similarity judgments (SimLex-999, WordSim-353)
vs GSE cosine similarity
Target: Spearman ρ > 0.5
```

### 3. Compositional Accuracy
```
Synthetic test pairs with known relationships:
- Antonym detection: "good" vs "bad" → negative cosine
- Hypernym detection: "dog" ~ "animal"
- Operator antisymmetry: THAN(A,B) ≈ -THAN(B,A)
```

### 4. Primitive Activation Sanity
```
"The dog runs" → BODY, ALIVE, MOVE activated
"Abstract mathematics" → THINK activated, BODY not activated
```

---

## Success Criteria

The system is **proven working** when:

1. **Reproducibility**: Same input → identical output (100%)
2. **Semantic preservation**: Similar meanings → similar vectors (ρ > 0.5)
3. **Compositional correctness**: Operators produce expected transformations
4. **Primitive sanity**: Activations match human intuition
5. **Documentation**: Full trace is human-interpretable

---

## Files to Create

```
gse/
├── api/
│   ├── __init__.py
│   ├── encoder.py          # Main encoding API
│   ├── trace.py            # OperationTrace dataclass
│   └── serialization.py    # JSON/MessagePack serialization
├── verification/
│   ├── __init__.py
│   ├── reproducibility.py  # Determinism tests
│   ├── similarity.py       # Semantic similarity tests
│   ├── compositional.py    # Operator sanity tests
│   └── suite.py            # Run all verifications
└── cli/
    └── main.py             # Command-line interface
```

---

## Timeline

| Phase | Task | Effort |
|-------|------|--------|
| 1 | GSE Encoder API | 1 day |
| 2 | Verification Suite | 1 day |
| 3 | CLI/Demo | 0.5 day |
| 4 | Documentation | 0.5 day |
| **Total** | **MVP Complete** | **3 days** |

---

## Next Steps

1. Implement `gse/api/encoder.py` with full trace generation
2. Create verification suite with concrete test cases
3. Run verification and document results
4. Package as importable library
