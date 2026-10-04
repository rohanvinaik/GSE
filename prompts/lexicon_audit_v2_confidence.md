# GSE Lexicon Audit V2: Confidence Analysis

**Scope:** Top 25,000 words by frequency_rank
**Mode:** AUDIT ONLY - no modifications

## Overview

This audit focuses on **semantic confidence signals** derived from cross-database agreement/disagreement. Words with consistent signals across multiple external sources have high confidence; words with conflicting signals need higher-attention review.

## Files

**Main database:** `data/lexicon.db` (SQLite)

**External validation sources:**
- `data/external/nrc_vad.txt` - Valence/Arousal/Dominance (0-1 scale)
- `data/external/lancaster_sensorimotor.csv` - Sensorimotor norms (39k words)
- `data/external/concreteness.csv` - Concreteness ratings (1-5 scale)
- `data/external/nrc_emotion.txt` - Emotion associations (binary)

**Schema:**
```sql
-- lexemes: id, lemma, pos, frequency_rank
-- primitive_values: lexeme_id, primitive, value (-1/0/+1), confidence, source
```

---

## Part 1: Cross-Database Agreement Analysis

### 1.1 Source Coverage Matrix

For each word in top 25K, compute coverage across sources:

| Word | NRC-VAD | Lancaster | Concreteness | NRC-Emotion | VerbNet | SentiWordNet | Total Sources |
|------|---------|-----------|--------------|-------------|---------|--------------|---------------|

**High Coverage (4+ sources):** Flag these as HIGH CONFIDENCE candidates
**Low Coverage (1-2 sources):** Flag these as UNCERTAIN - need LLM verification

### 1.2 Agreement Score

For primitives with multiple source signals, compute agreement:

```python
def compute_agreement(word, primitive):
    """
    Returns: (agreement_score, sources_agreeing, sources_disagreeing)

    Agreement = 1.0: All sources agree on same value
    Agreement = 0.5: Mixed signals (some +1, some 0)
    Agreement = 0.0: Direct conflict (some +1, some -1)
    """
```

**Primitives with multi-source signals:**
- GOOD: NRC-VAD valence, SentiWordNet polarity, NRC-Emotion (joy/trust vs anger/disgust)
- BODY: Lancaster Haptic/Interoceptive, Concreteness > 4.0
- SEE: Lancaster Visual
- HEAR: Lancaster Auditory
- MOVE: Lancaster Motor, VerbNet motion class
- FEEL: NRC-VAD dominance (low), NRC-Emotion emotional, Lancaster Interoceptive

### 1.3 Cross-Source Conflict Detection

Flag words where sources give OPPOSITE signals:

| Word | Primitive | Source A | Value A | Source B | Value B | Conflict Type |
|------|-----------|----------|---------|----------|---------|---------------|

**Conflict Types:**
- `POLARITY`: One source says +1, another says -1
- `PRESENCE`: One source indicates presence (1), another indicates absence (0 or -1)
- `MAGNITUDE`: Both indicate same direction but vastly different magnitudes

---

## Part 2: Confidence Tier Classification

Classify each word-primitive pair into confidence tiers:

### Tier 1: HIGH CONFIDENCE (No Review Needed)
- 3+ sources agree
- Agreement score > 0.8
- Consistent with lexical semantics

### Tier 2: MEDIUM CONFIDENCE (Spot Check)
- 2 sources agree
- Agreement score 0.5-0.8
- Minor inconsistencies

### Tier 3: LOW CONFIDENCE (Full Review Needed)
- Single source only
- Agreement score < 0.5
- Source conflicts detected

### Tier 4: UNCERTAIN (LLM Required)
- No external source data
- Only LLM-derived values
- Unusual semantic patterns

---

## Part 3: Semantic Consistency Checks

### 3.1 Category Coherence

Words should have consistent primitives within semantic categories:

**Emotion Words** (fear, joy, anger, sadness, etc.):
- Expected: FEEL=1, SOMEONE=1 (experiencer)
- Check: GOOD/BAD matches valence

**Body Part Words** (hand, eye, leg, etc.):
- Expected: BODY=1, SOMETHING=1
- Check: ALIVE=0 (body parts aren't alive themselves)

**Action Verbs** (run, jump, speak, etc.):
- Expected: DO=1 or HAPPEN=1
- Check: MOVE=1 for motion verbs

**Mental Verbs** (think, believe, know, etc.):
- Expected: THINK=1 or KNOW=1, SOMEONE=1
- Check: FEEL=1 if emotional component

**Communication Words** (say, speak, tell, etc.):
- Expected: SAY=1, WORDS=1
- Check: SOMEONE=1 (speaker)

**Modifier Words** (very, extremely, barely, many, few, likely, etc.):
- Expected: Hierarchical stacking with HIER_PLUS/HIER_MINUS markers
- Check: Base primitive (INTENSITY/QUANTITY/CERTAINTY) = +1
- Check: Marker count matches expected level
- Ground truth: `data/external/intensity_ground_truth.json`

| Modifier Type | Words | Expected Pattern |
|---------------|-------|------------------|
| Intensity (+) | very, highly, extremely | INTENSITY=1, HIER_PLUS=level |
| Intensity (-) | barely, slightly, somewhat | INTENSITY=1, HIER_MINUS=level |
| Quantity (+) | many, most, all | QUANTITY=1, HIER_PLUS=level |
| Quantity (-) | few, little, some | QUANTITY=1, HIER_MINUS=level |
| Certainty (+) | likely, certainly | CERTAINTY=1, HIER_PLUS=level |
| Certainty (-) | unlikely, impossible | CERTAINTY=1, HIER_MINUS=level |

### 3.2 Primitive Clustering

Identify unusual primitive co-occurrence patterns:

```sql
-- Find unusual combinations
SELECT l.lemma, GROUP_CONCAT(pv.primitive) as primitives
FROM lexemes l
JOIN primitive_values pv ON l.id = pv.lexeme_id
WHERE pv.value = 1
GROUP BY l.id
HAVING primitives LIKE '%ALIVE%' AND primitives LIKE '%DEAD%'  -- Should never happen
    OR primitives LIKE '%SAY%' AND primitives NOT LIKE '%SOMEONE%'  -- SAY needs speaker
```

---

## Part 4: Source-Specific Quality Analysis

### 4.1 NRC-VAD Mapping Quality

The arousal-to-INTENSITY mapping may have issues. Analyze:

| Arousal Range | Expected INTENSITY | Actual INTENSITY Count | Mismatch Rate |
|---------------|-------------------|------------------------|---------------|
| 0.0 - 0.3     | -1 (calm)         | ?                      | ?             |
| 0.3 - 0.6     | 0 (neutral)       | ?                      | ?             |
| 0.6 - 1.0     | +1 (intense)      | ?                      | ?             |

Flag words where:
- Arousal > 0.7 but INTENSITY ≠ 1
- Arousal < 0.3 but INTENSITY ≠ -1
- Word is semantically calm but has INTENSITY=1

### 4.2 Lancaster Sensorimotor Threshold Analysis

Review the thresholds used for binary conversion:

| Modality | Current Threshold | Words Activated | False Positive Rate |
|----------|-------------------|-----------------|---------------------|
| Visual   | ?                 | ?               | ?                   |
| Haptic   | ?                 | ?               | ?                   |
| Motor    | ?                 | ?               | ?                   |

**Sample high-scoring words** for each modality to verify threshold appropriateness.

### 4.3 Concreteness-to-Primitive Mapping

| Concreteness Range | Expected Primitives | Actual Pattern |
|--------------------|---------------------|----------------|
| 4.5 - 5.0 (very concrete) | SOMETHING=1, BODY possible | ? |
| 3.0 - 4.5 (moderate) | Mixed | ? |
| 1.0 - 3.0 (abstract) | THINK=1 likely, no BODY | ? |

### 4.4 Modifier Hierarchy Validation (External Ground Truth)

**Source:** `data/external/scalar-adj/` (acocos/scalar-adj dataset)

Contains:
- DeMelo gold rankings: 87 adjective intensity scales
- Crowd gold rankings: 79 crowdsourced scales
- Wilkinson terms: 21 antonym pair orderings

**Validation Process:**
```python
from scripts.load_intensity_ground_truth import get_modifier_ground_truth

gt = get_modifier_ground_truth()
print(f"Loaded {len(gt.modifiers)} modifiers from external ground truth")

# For each modifier in lexicon, check against ground truth
for word in lexicon_modifiers:
    expected = gt.get_expected_encoding(word)
    actual = get_word_primitives(word)

    # Flag mismatches
    if expected and expected != actual:
        issues.append({
            'word': word,
            'expected': expected,
            'actual': actual,
            'source': 'scalar-adj'
        })
```

**Common Issues to Flag:**
- INTENSITY=-1 (wrong! should be INTENSITY=1 + HIER_MINUS markers)
- Missing HIER_PLUS/HIER_MINUS markers
- Incorrect marker counts

---

## Part 5: LLM-Derived Value Quality

### 5.1 LLM Source Distribution

```sql
SELECT source, COUNT(*) as count
FROM primitive_values
WHERE source LIKE 'llm:%'
GROUP BY source
ORDER BY count DESC;
```

### 5.2 LLM vs External Agreement

For words with both LLM and external source values:

| Primitive | LLM-External Agreement Rate | Disagreement Examples |
|-----------|----------------------------|----------------------|
| GOOD      | ?%                         | word1, word2, ...    |
| BAD       | ?%                         | ...                  |
| ...       | ...                        | ...                  |

### 5.3 LLM-Only Primitives Quality

These primitives have NO external source coverage - entirely LLM-derived:
```
AFTER, BAD, BECAUSE, BELOW, CERTAINTY, DEAD, FALSE, FAR, HERE, HIER_MINUS,
HIER_PLUS, I, IF, INFER, KIND, LIKE, LONG_TIME, MOMENT, NEAR, NOT, NOW,
ONE, OTHER, OUTSIDE, PART, PEOPLE, QUANTITY, SAME, SHORT_TIME, SIDE,
SMALL, THEN, TOWARD, TRUE, TWO, WITHOUT, YOU
```

For each, sample 20 words and verify semantic correctness.

---

## Part 6: Statistical Anomalies

### 6.1 Activation Frequency by Primitive

| Primitive | Total +1 | Total -1 | Total 0 | Activation Rate | Expected Rate |
|-----------|----------|----------|---------|-----------------|---------------|

Flag primitives with unusual rates:
- Too high (>50% activation) - may be over-assigned
- Too low (<1% activation) - may be mapping issue

### 6.2 Confidence Score Distribution

| Source | Mean Confidence | Std Dev | Min | Max |
|--------|-----------------|---------|-----|-----|
| nrc_vad | ? | ? | ? | ? |
| lancaster | ? | ? | ? | ? |
| llm:* | ? | ? | ? | ? |

### 6.3 Sparse Words

Words with very few (0-3) active primitives that aren't function words:

| Word | POS | Freq Rank | Active Count | Primitives |
|------|-----|-----------|--------------|------------|

These may indicate incomplete processing.

---

## Output Format

Generate a structured report with:

### Executive Summary
- Total words analyzed: X
- High confidence words: X (X%)
- Medium confidence: X (X%)
- Low confidence/needs review: X (X%)
- Cross-source conflicts found: X

### Confidence Tier Lists
For each tier, list top 100 words with:
- Word, POS, frequency rank
- Confidence score
- Source coverage
- Primary issues (if any)

### Cross-Source Conflicts Table
Full list of detected conflicts with:
- Word, primitive, conflicting sources, values, recommended action

### LLM Review Queue
Prioritized list of words needing LLM validation:
- Reason for flagging
- Current values
- Expected values (if determinable)

### Primitive-Specific Reports
For each primitive with issues:
- Issue description
- Affected word count
- Sample problematic words
- Suggested investigation

---

## Execution

```python
import sqlite3
import pandas as pd
import numpy as np

conn = sqlite3.connect('data/lexicon.db')

# Get top 25000 words
top_words = pd.read_sql('''
    SELECT l.id, l.lemma, l.pos, l.frequency_rank
    FROM lexemes l
    WHERE l.frequency_rank <= 25000
    ORDER BY l.frequency_rank
''', conn)

# Get all primitive values for these words
primitives = pd.read_sql('''
    SELECT pv.lexeme_id, pv.primitive, pv.value, pv.confidence, pv.source
    FROM primitive_values pv
    JOIN lexemes l ON pv.lexeme_id = l.id
    WHERE l.frequency_rank <= 25000
''', conn)

# Load external sources
nrc_vad = pd.read_csv('data/external/nrc_vad.txt', sep='\\t',
                       names=['word','valence','arousal','dominance'], skiprows=1)

# Compute source coverage matrix...
# Compute agreement scores...
# Detect conflicts...
# Generate report...
```

Save the audit report to `data/audit_report_v2_confidence.md`.
