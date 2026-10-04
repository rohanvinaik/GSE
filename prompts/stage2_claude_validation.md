# Stage 2: Claude Code Audit Validation

**Executor:** Claude Code
**Input:** Audit report from Stage 1 (Google Antigravity)
**Output:** Validated audit + Qwen 32B prompt for Stage 3

---

## Purpose

Validate the Stage 1 audit report for correctness and prepare a targeted prompt that guides Qwen 32B to systematically apply fixes.

---

## Input Validation Checklist

### 1. Structural Completeness

Verify the audit report contains all required sections:

- [ ] Summary with total words audited and issue counts
- [ ] Component Type Issues table
- [ ] SYN_* Dimension Issues table
- [ ] Semantic Consistency Issues table
- [ ] Modifier Hierarchy Issues table
- [ ] Empty Bank Issues table

### 2. Issue Counts Sanity Check

Cross-validate reported counts against database:

```sql
-- Verify component_type issues
SELECT COUNT(*) FROM lexemes WHERE component_type IS NULL;

-- Verify OPERATOR issues
SELECT COUNT(*) FROM lexemes
WHERE component_type = 'OPERATOR' AND operator_type IS NULL;

-- Verify SYN_* gaps (sample check for nouns)
SELECT COUNT(*) FROM lexemes l
WHERE l.pos IN ('NOUN', 'NN', 'NNS')
AND NOT EXISTS (
    SELECT 1 FROM primitive_values pv
    WHERE pv.lexeme_id = l.id AND pv.primitive = 'SYN_SUBJ'
);
```

If counts differ by >10%, flag for re-audit.

### 3. Semantic Consistency Validation

For each flagged issue, verify it's a real problem:

| Rule | Validation Query |
|------|------------------|
| FEEL without experiencer | Check word semantics - does it actually describe a feeling? |
| SAY without WORDS | Check if word is truly a speech act |
| Bipolar violations | Confirm GOOD=1 AND BAD=1 is incorrect for this word |
| Verbs missing DO/HAPPEN | Check if it's a content verb (not auxiliary) |
| **SING/PLUR/ZERO violation** | If ZERO=1, verify SING=0 AND PLUR=0 |
| **Pronoun missing gram features** | Verify pronouns have person, number, case |
| **Numeral missing SING/ZERO** | Verify numerals have correct number encoding |

Sample 10 issues from each category and manually verify.

### 3a. New Primitive Validation (v2.0)

```sql
-- Verify SING/PLUR/ZERO mutual transparency
SELECT l.lemma, sing.value as SING, plur.value as PLUR, zero.value as ZERO
FROM lexemes l
JOIN primitive_values zero ON l.id = zero.lexeme_id AND zero.primitive = 'ZERO'
LEFT JOIN primitive_values sing ON l.id = sing.lexeme_id AND sing.primitive = 'SING'
LEFT JOIN primitive_values plur ON l.id = plur.lexeme_id AND plur.primitive = 'PLUR'
WHERE zero.value = 1 AND (COALESCE(sing.value, 0) = 1 OR COALESCE(plur.value, 0) = 1);

-- Verify pronouns have gram features
SELECT l.lemma FROM lexemes l
JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.primitive = 'SOMEONE' AND pv.value = 1
WHERE l.lemma IN ('i', 'you', 'he', 'she', 'we', 'they')
AND NOT EXISTS (SELECT 1 FROM gram_feature_values gf WHERE gf.lexeme_id = l.id AND gf.feature = 'person');
```

### 4. False Positive Detection

Watch for common false positives:

- **Function words flagged for missing primitives** - OPERATORs should have minimal primitives
- **Proper nouns flagged** - May have different primitive profiles
- **Multi-sense words** - Primary sense may differ from flagged issue
- **Already-correct entries** - Audit may have checked stale data

---

## Qwen Prompt Preparation

### Data Extraction

Extract the issues into structured batches for Qwen:

```python
import sqlite3
import json

conn = sqlite3.connect("data/lexicon.db")

# Extract issues by category
component_issues = conn.execute("""
    SELECT l.id, l.lemma, l.pos, l.component_type, l.operator_type
    FROM lexemes l
    WHERE l.component_type IS NULL
       OR (l.component_type = 'OPERATOR' AND l.operator_type IS NULL)
    LIMIT 100
""").fetchall()

syn_issues = conn.execute("""
    SELECT l.id, l.lemma, l.pos, 'SYN_SUBJ' as missing
    FROM lexemes l
    WHERE l.pos IN ('NOUN', 'NN', 'NNS', 'NNP', 'NNPS')
    AND NOT EXISTS (
        SELECT 1 FROM primitive_values pv
        WHERE pv.lexeme_id = l.id AND pv.primitive = 'SYN_SUBJ'
    )
    LIMIT 100
""").fetchall()

# Format for Qwen prompt
batch = {
    "component_fixes": [
        {"id": r[0], "lemma": r[1], "pos": r[2], "current_type": r[3], "current_op": r[4]} for r in component_issues
    ],
    "syn_fixes": [{"id": r[0], "lemma": r[1], "pos": r[2], "missing_dim": r[3]} for r in syn_issues],
}

with open("data/stage3_input_batch.json", "w") as f:
    json.dump(batch, f, indent=2)
```

### Qwen Prompt Template

Generate the Stage 3 prompt with embedded data:

```markdown
# Stage 3: Apply Lexicon Fixes

## Batch Data
[EMBED: data/stage3_input_batch.json]

## Fix Rules
[Reference stage3_qwen_fixes.md rules]

## Expected Output Format
For each fix applied, log:
- word: lemma
- action: what was changed
- reason: why this fix was applied
```

---

## Validation Decision Tree

```
For each issue in audit report:
│
├─ Run verification query
│   ├─ Issue confirmed → Include in Qwen batch
│   └─ Issue not found → Mark as stale, exclude
│
├─ Sample manual check (10%)
│   ├─ Correct identification → Proceed
│   └─ False positive → Review similar issues
│
└─ Final batch
    ├─ < 1000 issues → Single Qwen run
    └─ > 1000 issues → Split into batches of 500
```

---

## Output Artifacts

1. **Validated Audit Summary** (`data/stage2_validation.md`)
   - Confirmed issue counts
   - False positive rate
   - Issues excluded

2. **Qwen Input Batch** (`data/stage3_input_batch.json`)
   - Structured issue data
   - Batch metadata

3. **Stage 3 Prompt** (`data/stage3_prompt_instance.md`)
   - Complete prompt with embedded data
   - Ready to pass to Qwen 32B

---

## Red Flags (Abort Criteria)

Stop and re-run Stage 1 if:
- False positive rate > 30%
- Issue counts differ from database by > 50%
- Missing required sections in audit report
- Obvious semantic errors in flagged issues

---

## Checklist Summary

Before proceeding to Stage 3:

- [ ] All audit sections present
- [ ] Issue counts verified against database
- [ ] 10% sample manually validated
- [ ] False positive rate < 30%
- [ ] Qwen input batch generated
- [ ] Stage 3 prompt prepared
