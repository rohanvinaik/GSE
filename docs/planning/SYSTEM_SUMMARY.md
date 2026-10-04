> **Unverified planning document** — moved from the repository root on 2026-10-04. It predates GSE's
> current core and has not been checked against the code; where they disagree, the code and
> [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) are authoritative.

# GSE System Summary

## Overview

**Geometric Semantic Encoding (GSE)** is a semantic representation system based on Hyperdimensional Computing (HDC) principles. It encodes word and sentence meanings as high-dimensional sparse ternary vectors, enabling mathematical operations on semantic content.

---

## Architecture

| Property | Value |
|----------|-------|
| **Vector Dimensions** | 8,192 (2^13) |
| **Vector Values** | Ternary {-1, 0, +1} |
| **Semantic Banks** | 8 (1,024 dims each) |
| **Primitives** | 62 (from Natural Semantic Metalanguage) |
| **Semantic Roles** | 30 |
| **Lexicon Size** | 15,909 words |

### Semantic Banks

| Bank | Category | Example Primitives |
|------|----------|-------------------|
| 0 | Substantives | I, YOU, SOMEONE, SOMETHING |
| 1 | Determiners | THIS, SAME, ONE, ALL, MUCH |
| 2 | Evaluators | GOOD, BAD, BIG, SMALL |
| 3 | Mental | THINK, KNOW, WANT, FEEL |
| 4 | Action | DO, HAPPEN, MOVE, LIVE, DIE |
| 5 | Temporal | WHEN, NOW, BEFORE, AFTER |
| 6 | Spatial | WHERE, HERE, ABOVE, BELOW |
| 7 | Logical | NOT, MAYBE, CAN, BECAUSE |

---

## Performance Metrics

### Semantic Relationship Validation

| Category | Accuracy | Description |
|----------|----------|-------------|
| **Synonyms** | 100% (10/10) | High similarity between synonym pairs |
| **Antonyms** | 100% (10/10) | Low/negative similarity between antonyms |
| **Unrelated** | 80% (8/10) | Near-zero similarity for unrelated pairs |
| **Primitive Antonyms** | 100% (8/8) | Exact -1.0 similarity (guaranteed) |

### Sample Similarity Scores

| Pair | Similarity | Expected |
|------|------------|----------|
| happy / good | 0.71 | High (synonyms) |
| good / bad | -1.00 | Negative (antonyms) |
| big / small | -1.00 | Negative (antonyms) |
| fast / slow | -1.00 | Negative (antonyms) |
| dog / philosophy | 0.00 | Zero (unrelated) |

### Sentence Differentiation

| Test Case | Similarity | Interpretation |
|-----------|------------|----------------|
| "The dog runs" vs "The cat runs" | 0.94 | Same structure, similar actors |
| "John loves Mary" vs "Mary loves John" | 0.35 | Role reversal detected |
| "The child is happy" vs "The child is sad" | 0.81 | Same structure, opposite emotion |

### Unit Tests

```
40/40 tests passing (100%)
```

---

## Capabilities

### 1. Word Decomposition
Words are decomposed into primitive-role pairs:
```
"happy"  → [(FEEL, state), (GOOD, evaluation)]
"murder" → [(SOMEONE, agent), (DO, action), (SOMEONE, patient),
            (DIE, result), (WANT, intention), (BAD, evaluation)]
```

### 2. Sentence Composition
- Bottom-up composition following dependency structure
- Syntactic role encoding via permutation shifts
- Preserves agent/patient distinctions

### 3. Semantic Similarity
- Cosine similarity between vectors
- Range: [-1, 1]
- Antonyms approach -1, synonyms approach +1

### 4. Anomaly Detection
Detects semantic violations:
- **Animacy violations**: "The rock thinks" (inanimate agent + mental verb)
- **Selectional restrictions**: Bank-based verb-argument compatibility
- **Completeness checking**: Missing required semantic roles

### 5. Morphological Analysis
Handles prefixes and suffixes:
- `un-happy` → NOT + happy
- `teach-er` → SOMEONE who teaches
- `re-build` → build AGAIN

### 6. Graded Antonymy
Temperature scale example:
```
freezing → cold → cool → lukewarm → warm → hot → scalding
   -1.0    -0.8   -0.4     0.0      0.4   0.8    1.0
```

### 7. Context-Sensitive Sense Selection
Disambiguates polysemous words:
- "bank" + [money, account] → financial institution
- "bank" + [river, water] → river bank

---

## Usage

### Basic Processing
```python
from gse.pipeline import load_pipeline

pipeline = load_pipeline()

# Process a sentence
result = pipeline.process("The happy child runs quickly.")
print(f"Confidence: {result.confidence:.2f}")
print(f"Coherent: {result.coherence_passed}")

# Compare sentences
sim = pipeline.similarity(
    "The dog runs fast.",
    "The cat runs quickly."
)
print(f"Similarity: {sim:.2f}")  # ~0.61

# Detect anomalies
result = pipeline.process("The rock thinks deeply.")
print(f"Anomalies: {result.anomalies}")
# ['Possible animacy violation: agent may be inanimate (score 0.10)']
```

### CLI
```bash
# Rebuild lexicon
python scripts/rebuild_lexicon.py

# Validate semantic relationships
python scripts/validate_lexicon.py

# Run tests
python -m pytest tests/ -v
```

---

## Key Properties

### Guaranteed by Architecture
- **Perfect Orthogonality**: Non-antonym primitives have exactly 0 similarity
- **Exact Antonymy**: Primitive antonym pairs have exactly -1.0 similarity
- **Deterministic**: Same input always produces same output
- **Composable**: Sentence vectors built from word vectors

### Semantic Features
- Role-based binding preserves argument structure
- Syntactic permutation encodes grammatical relations
- Bank structure enables selectional restriction checking
- Sparse ternary vectors enable efficient computation

---

## Data Sources

| Source | Words | Purpose |
|--------|-------|---------|
| NLTK FrameNet | ~9,000 | Frame-semantic mappings |
| NLTK WordNet | ~6,500 | Synset definitions, relations |
| Core Vocabulary | 37 | Essential primitives |
| Enriched Decompositions | 102 | Curated high-frequency words |

---

## Limitations

1. **Lexicon Coverage**: Words not in lexicon use fallback encoding
2. **Polysemy**: Context-sensitive selection is rule-based, not learned
3. **Compositionality**: Some idiomatic expressions may not compose correctly
4. **Languages**: Currently English only

---

## References

- Natural Semantic Metalanguage (Wierzbicka & Goddard)
- Hyperdimensional Computing (Kanerva)
- FrameNet (Fillmore et al.)
- WordNet (Miller et al.)
