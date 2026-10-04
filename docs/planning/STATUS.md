> **Unverified planning document** — moved from the repository root on 2026-10-04. It predates GSE's
> current core and has not been checked against the code; where they disagree, the code and
> [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) are authoritative.

# GSE: Geometric Semantic Encoding

## System Overview

GSE is a semantic encoding system based on Hyperdimensional Computing (HDC) principles. It represents word and sentence meanings as high-dimensional sparse ternary vectors, enabling mathematical operations on semantic content.

### Core Concept

Words are decomposed into **semantic primitives** (from Natural Semantic Metalanguage theory) bound with **semantic roles**, then composed into vectors. This allows:

- Computing semantic similarity between words/sentences
- Detecting semantic anomalies
- Preserving compositional structure

---

## Architecture: Hadamard-OTP

The system uses a **Hadamard Orthogonal Ternary Projection** architecture:

| Property | Value |
|----------|-------|
| Dimensions | 8,192 (2^13) |
| Semantic Banks | 8 (matching NSM categories) |
| Dims per Bank | 1,024 |
| Vector Values | {-1, 0, +1} (ternary) |

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

### Key Properties

- **Perfect Orthogonality**: Non-antonym primitives have exactly 0 similarity
- **Exact Antonymy**: Antonym pairs (GOOD/BAD, BIG/SMALL, etc.) have exactly -1.0 similarity
- **Guaranteed Binding**: Primitive × Role always produces 51 non-zero dimensions

---

## Current Status

### Test Results

```
40/40 unit tests passing
```

### Validation Results

| Category | Result |
|----------|--------|
| Synonyms | 10/10 (100%) |
| Antonyms | 10/10 (100%) |
| Unrelated | 10/10 (100%) |
| Primitive Antonyms | 8/8 (100%) |

### Sentence Differentiation

| Test Case | Result |
|-----------|--------|
| Agent/patient reversal | ~0.49 similarity (correctly different) |
| Identical sentences | 1.0 similarity |
| Active vs passive voice | ~0.57 similarity (related but different) |

### Lexicon

- **183 words** with semantic decompositions
- Generated using Claude Code (no API key required)
- Stored in SQLite database

---

## Components

### Core Modules

| Module | Purpose |
|--------|---------|
| `gse/vectors.py` | Hadamard-OTP vector operations |
| `gse/primitives.py` | NSM primitive definitions, intensity/aspect markers |
| `gse/lexicon_generator.py` | Lexicon creation and lookup |
| `gse/parser.py` | Dependency parsing (spaCy) |
| `gse/composer.py` | Sentence composition with syntactic permutation |
| `gse/coherence.py` | Semantic coherence checking with bank-based selectional restrictions |
| `gse/pipeline.py` | End-to-end processing |

### Enhancement Modules (New)

| Module | Purpose |
|--------|---------|
| `gse/morphology.py` | Morphological decomposition (un-, re-, -ness, -ful, etc.) |
| `gse/antonymy.py` | Graded antonymy scales (hot → warm → cool → cold) |
| `gse/verb_templates.py` | Verb argument structure templates |
| `gse/sense_selection.py` | Context-sensitive word sense disambiguation |
| `gse/discourse.py` | Cross-sentence discourse coherence tracking |

### Data Files

| File | Purpose |
|------|---------|
| `data/basis.msgpack` | Serialized primitive/role vectors |
| `data/lexicon.db` | SQLite word database |
| `data/word_decompositions.json` | Word → primitive mappings |

---

## Usage

### Basic Example

```python
from gse.pipeline import load_pipeline

pipeline = load_pipeline()

# Process a sentence
result = pipeline.process("The happy child runs.")
print(f"Confidence: {result.confidence:.2f}")
print(f"Coherent: {result.coherence_passed}")

# Compare sentences
sim = pipeline.similarity(
    "The dog runs quickly.",
    "The cat runs fast."
)
print(f"Similarity: {sim:.2f}")

# Detect anomalies
is_anomalous, reasons = pipeline.is_anomalous(
    "The rock thinks deeply."
)
```

### Rebuild Lexicon

```bash
python scripts/rebuild_lexicon.py
```

### Run Tests

```bash
python -m pytest tests/ -v
```

### Validate Lexicon

```bash
python scripts/validate_lexicon.py
```

---

## How It Works

### 1. Word Decomposition

Words are decomposed into primitive-role pairs:

```
"happy" → [(FEEL, state), (GOOD, evaluation)]
"murder" → [(SOMEONE, agent), (DO, action), (SOMEONE, patient),
            (DIE, result), (WANT, intention), (BAD, evaluation)]
```

### 2. Vector Encoding

Each primitive-role pair is **bound** (element-wise multiplication), then pairs are **bundled** (element-wise sum with sign):

```
happy_vec = bundle([
    bind(FEEL, state),
    bind(GOOD, evaluation)
])
```

### 3. Sentence Composition

Sentences are parsed into dependency trees, then composed using **permutation-based syntactic encoding**:

```
"The dog bites the man"
    → bundle(
        permute(dog_vec, AGENT_SHIFT),     # Subject as agent
        permute(bites_vec, PREDICATE_SHIFT),
        permute(man_vec, PATIENT_SHIFT)    # Object as patient
      )
```

This ensures structural differentiation:
- `"The dog bites the man"` ≠ `"The man bites the dog"` (similarity ~0.49)
- Identical sentences produce identical vectors (similarity 1.0)

| Syntactic Role | Permutation Shift |
|----------------|-------------------|
| agent | 0 (reference) |
| predicate | 512 |
| patient | 1024 |
| recipient | 2048 |
| attribute | 256 |
| manner | 768 |

### 4. Similarity Computation

Semantic similarity is computed via cosine similarity:

```python
sim = vec1.cosine(vec2)  # Range: [-1, 1]
```

---

## Semantic Relationships

### Antonyms

Antonym pairs use opposing primitives, producing low or negative similarity:

| Pair | Similarity |
|------|------------|
| good / bad | -1.00 |
| happy / sad | 0.00 |
| love / hate | 0.00 |
| hot / cold | 0.00 |

### Synonyms

Synonym pairs share primitive structures, producing high similarity:

| Pair | Similarity |
|------|------------|
| happy / joyful | 0.71 |
| big / large | 0.71 |
| begin / start | 1.00 |

---

## Adding New Words

1. Add decomposition to `data/word_decompositions.json`:

```json
{
  "word": "example",
  "pos": "NOUN",
  "decomposition": [["SOMETHING", "theme"], ["KNOW", "content"]],
  "frequency": 0.5
}
```

2. Rebuild the lexicon:

```bash
python scripts/rebuild_lexicon.py
```

---

## Dependencies

- Python 3.9+
- NumPy
- SciPy (for Hadamard matrices)
- spaCy (for parsing)
- msgpack (for serialization)

---

---

## Enhancement Features

### Morphological Decomposition

Automatically decomposes morphologically complex words:

```python
from gse.morphology import get_morphological_analyzer

analyzer = get_morphological_analyzer()
result = analyzer.analyze("unhappy")
# base_form: "happy"
# prefixes: ["un-"]
# semantic_additions: [("NOT", "state")]

result = analyzer.analyze("teacher")
# base_form: "teach"
# suffixes: ["-er"]
# semantic_additions: [("SOMEONE", "agent")]
```

Supported affixes:
- Prefixes: un-, dis-, in-, re-, pre-, post-, over-, under-, mis-, super-, ultra-, semi-, multi-, co-
- Suffixes: -ness, -ity, -er, -or, -ist, -ee, -able, -ful, -less, -ly, -ize, -ify, -en

### Graded Antonymy

Handles graded opposition between words:

```python
from gse.antonymy import get_antonymy_handler

antonymy = get_antonymy_handler()

antonymy.compute_graded_similarity("hot", "cold")   # -0.60 (opposite)
antonymy.compute_graded_similarity("hot", "warm")   #  0.60 (similar)
antonymy.compute_graded_similarity("hot", "cool")   # -0.20 (contrast)
```

Scales: temperature, size, quality, speed, age, height, weight, emotion, certainty, quantity

### Verb Argument Templates

Defines expected argument structures:

```python
from gse.verb_templates import get_verb_template_handler

verbs = get_verb_template_handler()
template = verbs.get_template("give")  # ditransitive
required = verbs.get_required_roles("give")  # ['agent', 'action', 'theme', 'recipient']
```

Template types: transitive, intransitive, ditransitive, mental_state, emotion, perception, motion, stative, communication, causative

### Context-Sensitive Sense Selection

Disambiguates polysemous words:

```python
from gse.sense_selection import get_sense_selector

selector = get_sense_selector()

# "bank" in financial context
result = selector.select_sense("bank", "NOUN", context_words=["money", "account"])
# → bank.NOUN.financial

# "bank" in geographical context
result = selector.select_sense("bank", "NOUN", context_words=["river", "water"])
# → bank.NOUN.river
```

### Discourse Coherence

Tracks coherence across sentences:

```python
from gse.discourse import get_discourse_tracker

tracker = get_discourse_tracker()
tracker.reset()

# Process sentences and track entities, relations, topic shifts
result = tracker.process_sentence(0, composition, tokens, noun_indices)
# → new_entities, coherence_score, rhetorical_relation, topic_shift

summary = tracker.get_discourse_summary()
# → overall_coherence, num_entities, relation_types
```

Detects: entity coreference, topic shifts, rhetorical relations (elaboration, contrast, cause, temporal, addition)

### Bank-Based Selectional Restrictions

Coherence checking uses semantic bank structure:

```python
# Mental verbs (think, know, believe) require animate agents
# Motion verbs (go, run, walk) require spatial goals
# Perception verbs (see, hear) require experiencer subjects
```

Violations detected:
- "The rock thinks deeply" → Selectional restriction: 'think' (mental) expects agent with SUBSTANTIVES semantics
- Contradictory modifiers → Semantic conflict: 'hot' may conflict with 'cold'

---

## References

- Natural Semantic Metalanguage (Wierzbicka & Goddard)
- Hyperdimensional Computing (Kanerva)
- Geometric Semantic Encoding theory documents in `gse/gse_otp_architecture.md`
