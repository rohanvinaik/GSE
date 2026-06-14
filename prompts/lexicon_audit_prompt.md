# GSE Lexicon Audit Prompt

You are auditing a semantic primitives lexicon database for errors. **Audit only - do not modify any files.**

## Files

**Main database:** `data/lexicon.db` (SQLite)
**External validation sources:**
- `data/external/nrc_vad.txt` - Valence/Arousal/Dominance (tab-separated, 0-1 scale)
- `data/external/lancaster_sensorimotor.csv` - Sensorimotor norms (39k words)
- `data/external/concreteness.csv` - Concreteness ratings (1-5 scale)
- `data/external/nrc_emotion.txt` - Emotion associations (binary)

**Schema:**
```sql
-- lexemes: id, lemma, pos, frequency_rank
-- primitive_values: lexeme_id, primitive, value (-1/0/+1), confidence, source
```

## Audit Rules

Run these checks on the **top 5000 words by frequency_rank**:

### 1. Bipolar Constraint Violations
These pairs must NOT both be non-zero for the same word:
```
GOOD/BAD, BIG/SMALL, ALIVE/DEAD, SAME/OTHER, BEFORE/AFTER,
THEN/NOW, START/END, ABOVE/BELOW, FAR/NEAR, INSIDE/OUTSIDE,
TOWARD/AWAY, WITH/WITHOUT, TRUE/FALSE, LONG_TIME/SHORT_TIME
```

### 2. INTENSITY Bug Investigation
The NRC-VAD arousal score was incorrectly mapped: low arousal → INTENSITY=-1.
**Cross-reference to find false negatives:**
- Query words where `INTENSITY=-1` in lexicon
- Check their arousal in `nrc_vad.txt` (column 3)
- Flag words where arousal > 0.4 but INTENSITY=-1 (likely errors)
- Flag words where arousal < 0.3 AND the word is a verb/action (should probably be 0, not -1)

### 3. Semantic Sanity Checks
Flag these patterns as likely errors:
- Function words (the, a, of, and, to, is, that, for, it, with) having >5 active primitives
- Verbs missing both DO=1 and HAPPEN=1
- Nouns with MOVE=1 but no BODY/SOMETHING
- Words with FEEL=1 but no SOMEONE/I/YOU
- Words with SAY=1 but no WORDS=1
- Words with ALIVE=1 that are clearly inanimate (cross-ref concreteness < 2.0)

### 4. Source Disagreement
Find words where:
- NRC-VAD valence > 0.7 but GOOD ≠ 1
- NRC-VAD valence < 0.3 but GOOD ≠ -1
- Lancaster has high "Hand" or "Foot" scores but BODY=0
- VerbNet categorizes as motion verb but MOVE=0

### 5. Extreme Activation
Flag words with:
- More than 25 active (non-zero) primitives
- Zero active primitives (except function words)

### 6. Modifier Hierarchy Validation
**New:** Validate intensity/quantity/certainty modifiers use correct hierarchical stacking.

**Ground truth:** `data/external/intensity_ground_truth.json` (from acocos/scalar-adj dataset)

**Rules:**
- Base primitive (INTENSITY/QUANTITY/CERTAINTY) should always be +1
- Direction encoded via HIER_PLUS or HIER_MINUS markers
- Level = marker count (e.g., "very" = INTENSITY=1, HIER_PLUS=1)

**Expected encodings:**
| Word | Base | Level | HIER_PLUS | HIER_MINUS |
|------|------|-------|-----------|------------|
| very | INTENSITY | +1 | 1 | 0 |
| extremely | INTENSITY | +2 | 2 | 0 |
| barely | INTENSITY | -2 | 0 | 2 |
| many | QUANTITY | +2 | 2 | 0 |
| few | QUANTITY | -2 | 0 | 2 |
| likely | CERTAINTY | +2 | 2 | 0 |

**Check:**
```python
from scripts.load_intensity_ground_truth import get_modifier_ground_truth
gt = get_modifier_ground_truth()

for word in gt.get_all_modifiers():
    expected = gt.get_expected_encoding(word)
    actual = get_word_primitives(word)
    if expected != actual:
        flag_modifier_issue(word, expected, actual)
```

## Output Format

Generate a report with these sections:

```markdown
# Lexicon Audit Report

## Summary
- Words audited: X
- Total issues found: X
- Critical (bipolar violations): X
- High (semantic inconsistencies): X
- Medium (source disagreements): X

## Bipolar Violations
| Word | Pair | Values | Severity |
|------|------|--------|----------|

## INTENSITY Bug Candidates
| Word | Current Value | NRC Arousal | Suggested | Reason |
|------|---------------|-------------|-----------|--------|

## Semantic Issues
| Word | Issue | Current | Expected | Source |
|------|-------|---------|----------|--------|

## Source Disagreements
| Word | Primitive | Lexicon | External | Source |
|------|-----------|---------|----------|--------|

## Extreme Activations
| Word | Active Count | Issue |
|------|--------------|-------|

## Modifier Hierarchy Issues
| Word | Expected | Actual | Issue |
|------|----------|--------|-------|
```

## Execution

```python
import sqlite3
import pandas as pd

# Load main database
conn = sqlite3.connect('data/lexicon.db')

# Get top 5000 words
top_words = pd.read_sql('''
    SELECT l.id, l.lemma, l.pos, l.frequency_rank
    FROM lexemes l
    WHERE l.frequency_rank <= 5000
    ORDER BY l.frequency_rank
''', conn)

# Load external sources for cross-reference
nrc_vad = pd.read_csv('data/external/nrc_vad.txt', sep='\t',
                       names=['word','valence','arousal','dominance'], skiprows=1)

# Run each audit check and collect issues...
```

Save the audit report to `data/audit_report.md`.
