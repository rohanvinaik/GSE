# GSE Lexicon Audit Optimization Plan

## Executive Summary

The current audit system processes **1 word in ~80 minutes** due to excessive LLM calls for primitives with no source coverage. This plan reduces that to **~5-10 minutes/word** while improving quality through better source coverage.

**Key insight**: 45 of 86 primitives (52%) have NO external source coverage, causing unnecessary LLM calls with no context to translate.

---

## Part 1: Immediate Optimizations (No New Data)

### 1.1 Bipolar Primitive Inference

These primitives can be automatically inferred from their opposites:

| Primitive | Infer From | Logic |
|-----------|------------|-------|
| BAD | GOOD | `BAD = -GOOD` (if GOOD=+1, BAD=-1) |
| SMALL | BIG | `SMALL = -BIG` |
| DEAD | ALIVE | `DEAD = -ALIVE` |
| FALSE | TRUE | `FALSE = -TRUE` |

**Impact**: 4 fewer LLM calls per word, guaranteed consistency.

### 1.2 Grammatical/Closed-Class Rules

These primitives apply to specific closed-class words only:

| Primitive | Rule |
|-----------|------|
| I | Only applies to "I", "me", "my", "myself", "mine" |
| YOU | Only applies to "you", "your", "yourself", "yours" |
| ONE | Applies to "one", "a", "an", "single", cardinal "1" |
| TWO | Applies to "two", "both", "pair", cardinal "2" |
| SING | Singular nouns (morphological analysis) |
| PLUR | Plural nouns (morphological analysis) |

**Impact**: 6 primitives handled by rules, no LLM needed.

### 1.3 Source-Gated LLM Calls

**Current behavior**: Call LLM for ALL primitives without auto-apply constraints.

**New behavior**: Only call LLM when there's source context to translate.

```python
# Before (current)
if not constraint or constraint.status != "auto_apply":
    llm_value = ollama.query_primitive_with_context(...)  # Always calls

# After (optimized)
if constraint and constraint.status != "auto_apply":
    # Has partial source data - LLM translates it
    llm_value = ollama.query_primitive_with_context(...)
elif primitive in BIPOLAR_PAIRS:
    # Infer from opposite
    value = infer_bipolar(...)
elif primitive in GRAMMATICAL_PRIMITIVES:
    # Apply rule
    value = apply_grammatical_rule(...)
else:
    # No source data, no rule - default to 0 (neutral)
    value = 0  # Conservative default
```

**Impact**: LLM calls reduced from ~63 to ~20 per word.

### 1.4 Reduced Throttling

Current settings are overly conservative:

| Setting | Current | Proposed | Rationale |
|---------|---------|----------|-----------|
| `after_ollama_call` | 5.0s | 1.0s | 2013 Mac Pro can handle this |
| `between_primitives` | 0.1s | 0.05s | Minimal impact |
| `ollama_calls_per_hour` | 50 | 500 | Was blocking mid-word |
| `memory_threshold_gb` | 12 | 50 | Allow swap, it's fine for background |

**Impact**: ~4x faster per LLM call.

### 1.5 Combined Impact

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| LLM calls/word | 63 | ~20 | 3x fewer |
| Time per LLM call | ~70s | ~15s | 4x faster |
| **Time per word** | **80 min** | **~5 min** | **16x faster** |
| 5000 words | 278 days | ~17 days | 16x faster |

---

## Part 2: New External Sources

### 2.1 USAS Semantic Lexicon (Recommended - High Priority)

**Source**: [UCREL Multilingual-USAS](https://github.com/UCREL/Multilingual-USAS)

The USAS tagset has 21 major semantic fields with 232 fine-grained tags covering:

| USAS Category | Maps to GSE Primitives |
|---------------|------------------------|
| M6 (Location/direction) | ABOVE, BELOW, NEAR, FAR, HERE, SIDE |
| T1 (Time) | NOW, MOMENT, THEN, LONG_TIME, SHORT_TIME |
| N1-N5 (Numbers/Quantities) | ONE, TWO, SOME, ALL, MUCH, LITTLE, QUANTITY |
| L1 (Life/Living) | LIVE, DIE, ALIVE, DEAD |
| X2 (Mental actions) | BELIEVE, INFER, THINK, KNOW |
| A6 (Comparing) | SAME, OTHER, LIKE |
| S (Social) | PEOPLE, SOMEONE |

**Format**: TSV files, easy to parse
**Coverage**: ~37,000 English words
**License**: CC-BY-NC-SA 4.0

**Estimated new coverage**: 20+ primitives

### 2.2 MRC Psycholinguistic Database (Medium Priority)

**Source**: [UWA MRC Database](https://websites.psychology.uwa.edu.au/school/MRCDatabase/uwa_mrc.htm)

| MRC Variable | Maps to GSE |
|--------------|-------------|
| Imageability (100-700) | SOMETHING (concrete), THINK (abstract) |
| Familiarity | Confidence weighting |
| Age of Acquisition | Frequency priority |

**Entries**: 150,837 words with psycholinguistic norms

### 2.3 TimeML/TimeBank (Lower Priority)

**Source**: [TimeBank 1.2](https://catalog.ldc.upenn.edu/LDC2006T08)

Temporal annotation for:
- Duration: LONG_TIME, SHORT_TIME, MOMENT
- Temporal relations: BEFORE, AFTER, NOW, THEN

**Coverage**: 183 articles, 27,000+ temporal annotations

### 2.4 WordNet Animacy Extension

Already have WordNet - extend to extract:

| WordNet Feature | Maps to GSE |
|-----------------|-------------|
| entity.n.01 hyponyms | ALIVE (organism branch) |
| artifact.n.01 hyponyms | SOMETHING (inanimate) |
| person.n.01 hyponyms | SOMEONE, PEOPLE |

### 2.5 Summary: New Source Priority

| Source | Priority | Coverage | Effort |
|--------|----------|----------|--------|
| USAS Lexicon | HIGH | 20+ primitives | Medium (TSV parsing) |
| Bipolar inference | HIGH | 4 primitives | Low (logic) |
| Grammatical rules | HIGH | 6 primitives | Low (closed lists) |
| WordNet animacy | MEDIUM | 4 primitives | Low (already loaded) |
| MRC Database | MEDIUM | 3 primitives | Medium (data download) |
| TimeML | LOW | 5 primitives | High (complex format) |

---

## Part 3: Implementation Roadmap

### Phase 1: Immediate (Can do now)

1. **Implement bipolar inference** in `daemon/audit_daemon.py`
2. **Add grammatical rules** for closed-class primitives
3. **Reduce throttling** in `daemon/config.py`
4. **Source-gate LLM calls** - only call when context exists

**Expected result**: 16x speedup, same quality

### Phase 2: USAS Integration (1-2 sessions)

1. Download USAS English lexicon from GitHub
2. Create `gse/curation/external_sources/usas.py` parser
3. Map USAS categories to GSE primitives
4. Add to constraint aggregation engine

**Expected result**: 20+ more primitives covered by sources

### Phase 3: Extend Existing Sources (1 session)

1. Extract animacy from WordNet
2. Extract more spatial/temporal info from FrameNet
3. Improve NRC-VAD mapping (dominance → CERTAINTY)

**Expected result**: Better use of data we already have

### Phase 4: Optional Additions

1. MRC database integration
2. TimeML parsing (if temporal coverage still needed)
3. Epistemic marker lists for BELIEVE/INFER/CERTAINTY

---

## Appendix: Complete Primitive Coverage Map

### Currently Covered (41 primitives)

Sources: VerbNet, FrameNet, PropBank, WordNet, Lancaster, NRC-VAD, NRC-Emotion, Concreteness, SentiWordNet

```
DO, SOMEONE, SOMETHING, MOVE, SAY, SEE, HEAR, FEEL, THINK, WANT, KNOW,
GOOD, BODY, WHERE, WHEN, BEFORE, AFTER, TOWARD, AWAY, WITH, CAUSE,
HAVE, START, END, ALIVE, WORDS, TOUCH, INSIDE, PART, BE, EXIST,
HAPPEN, MUST, CAN, MAYBE, BECAUSE, NOT, LIKE, INTENSITY, ...
```

### After Phase 1: +10 primitives (rule-based)

```
BAD (from GOOD), SMALL (from BIG), DEAD (from ALIVE), FALSE (from TRUE)
I, YOU, ONE, TWO, SING, PLUR
```

### After Phase 2: +20 primitives (USAS)

```
ABOVE, BELOW, NEAR, FAR, HERE, SIDE
NOW, MOMENT, THEN, LONG_TIME, SHORT_TIME
SOME, ALL, MUCH, LITTLE, QUANTITY, ZERO
PEOPLE, SAME, OTHER, BEAUTIFUL
BELIEVE, INFER, LIVE, DIE
MAKE, TRANSFER
```

### Remaining (4 primitives - may need LLM)

```
KIND, IF, HIER_PLUS, HIER_MINUS, AGREE
```

---

## References

- [NSM-Approach.net](https://nsm-approach.net/) - Natural Semantic Metalanguage resources
- [UCREL USAS](https://ucrel.lancs.ac.uk/usas/) - Lancaster semantic analysis system
- [Multilingual-USAS GitHub](https://github.com/UCREL/Multilingual-USAS) - Downloadable lexicons
- [MRC Database](https://websites.psychology.uwa.edu.au/school/MRCDatabase/uwa_mrc.htm) - Psycholinguistic norms
- [TimeBank](https://timeml.github.io/site/timebank/timebank.html) - Temporal annotations
- [Lancaster Sensorimotor Norms](https://www.lancaster.ac.uk/psychology/research/luna/publications/) - Perceptual/motor features
