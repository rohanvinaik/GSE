# Stage 4: Claude Code Fix Validation

**Executor:** Claude Code
**Input:** Fix log from Stage 3 (Qwen 32B)
**Output:** Validated database state (or rollback if issues found)

---

## Purpose

Validate that all fixes applied by Qwen 32B are semantically correct and structurally sound. Catch any errors before proceeding to deep audit.

---

## Fix Log Parsing

### Expected Structure

```
=== Stage 3 Fix Log ===
Batch: {BATCH_ID}
...

--- Component Type Fixes ---
{lemma}: Set component_type={TYPE}, operator_type={SUBTYPE} (reason: {REASON})
...

--- SYN_* Instantiation ---
{lemma}: Added {SYN_DIM}=0 (reason: {REASON})
...

--- Summary ---
Total changes: {N}
```

### Parse and Categorize

```python
import re

def parse_fix_log(log_path):
    with open(log_path, 'r') as f:
        content = f.read()

    fixes = {
        'component': [],
        'syn': [],
        'semantic': [],
        'hierarchy': [],
        'cleanup': [],
        'skipped': []
    }

    current_section = None
    for line in content.split('\n'):
        if '--- Component Type Fixes ---' in line:
            current_section = 'component'
        elif '--- SYN_* Instantiation ---' in line:
            current_section = 'syn'
        elif '--- Semantic Consistency Fixes ---' in line:
            current_section = 'semantic'
        elif '--- Modifier Hierarchy Fixes ---' in line:
            current_section = 'hierarchy'
        elif '--- OPERATOR Cleanup ---' in line:
            current_section = 'cleanup'
        elif '--- Skipped ---' in line:
            current_section = 'skipped'
        elif current_section and ':' in line:
            fixes[current_section].append(line.strip())

    return fixes
```

---

## Validation Checks

### 1. Component Type Validation

Verify each component type assignment:

```sql
-- Check assigned component types exist
SELECT l.lemma, l.component_type, l.operator_type
FROM lexemes l
WHERE l.component_type NOT IN ('ATOMIC', 'OPERATOR')
   OR (l.component_type = 'OPERATOR' AND l.operator_type IS NULL);
```

**Semantic spot-check (sample 20):**

| Lemma | Assigned Type | Correct? |
|-------|---------------|----------|
| the | OPERATOR/DETERMINER | Yes |
| run | ATOMIC/NULL | Yes |
| very | OPERATOR/DEGREE | Yes |

Flag if >10% incorrect.

### 2. SYN_* Instantiation Validation

Verify dimensions match POS:

```sql
-- Nouns should have SYN_SUBJ, SYN_OBJ, SYN_COMPL
SELECT l.lemma, l.pos, GROUP_CONCAT(pv.primitive) as syn_dims
FROM lexemes l
JOIN primitive_values pv ON l.id = pv.lexeme_id
WHERE l.pos IN ('NOUN', 'NN', 'NNS')
AND pv.primitive LIKE 'SYN_%'
GROUP BY l.id
HAVING syn_dims NOT LIKE '%SYN_SUBJ%'
    OR syn_dims NOT LIKE '%SYN_OBJ%'
    OR syn_dims NOT LIKE '%SYN_COMPL%';
```

**Check for wrong dimensions:**

| POS | Should NOT have |
|-----|-----------------|
| NOUN | SYN_PRED, SYN_ADV_MOD |
| VERB | SYN_DET, SYN_ADJ_MOD (unless also ADJ) |
| ADJ | SYN_PRED, SYN_DET |

### 3. Semantic Consistency Validation

Verify semantic fixes make sense:

```sql
-- FEEL+SOMEONE should co-occur
SELECT l.lemma FROM lexemes l
JOIN primitive_values feel ON l.id = feel.lexeme_id AND feel.primitive = 'FEEL'
LEFT JOIN primitive_values someone ON l.id = someone.lexeme_id AND someone.primitive = 'SOMEONE'
WHERE feel.value = 1 AND (someone.value IS NULL OR someone.value != 1);
```

**Sample check:** For each SOMEONE=1 addition, verify the word actually involves an experiencer.

### 4. Modifier Hierarchy Validation

Check hierarchy encoding is correct:

```sql
-- INTENSITY should be +1, not -1
SELECT l.lemma, pv.value
FROM lexemes l
JOIN primitive_values pv ON l.id = pv.lexeme_id
WHERE pv.primitive = 'INTENSITY' AND pv.value < 0;

-- Downward modifiers need HIER_MINUS
SELECT l.lemma, l.operator_type,
       COALESCE(hm.value, 'NULL') as hier_minus
FROM lexemes l
LEFT JOIN primitive_values hm ON l.id = hm.lexeme_id AND hm.primitive = 'HIER_MINUS'
WHERE l.operator_type = 'DEGREE'
AND l.lemma IN ('barely', 'slightly', 'somewhat', 'hardly')
AND (hm.value IS NULL OR hm.value = 0);
```

### 5. OPERATOR Cleanup Validation

Verify OPERATORs don't have excessive primitives:

```sql
-- OPERATORs should have few primitives
SELECT l.lemma, l.operator_type, COUNT(*) as prim_count
FROM lexemes l
JOIN primitive_values pv ON l.id = pv.lexeme_id
WHERE l.component_type = 'OPERATOR' AND pv.value != 0
GROUP BY l.id
HAVING prim_count > 3
ORDER BY prim_count DESC;
```

### 6. SING/PLUR/ZERO Validation (NEW)

Verify mutual transparency constraint:

```sql
-- ZERO=1 should never co-occur with SING=1 or PLUR=1
SELECT l.lemma, sing.value as SING, plur.value as PLUR, zero.value as ZERO
FROM lexemes l
JOIN primitive_values zero ON l.id = zero.lexeme_id AND zero.primitive = 'ZERO' AND zero.value = 1
LEFT JOIN primitive_values sing ON l.id = sing.lexeme_id AND sing.primitive = 'SING'
LEFT JOIN primitive_values plur ON l.id = plur.lexeme_id AND plur.primitive = 'PLUR'
WHERE COALESCE(sing.value, 0) = 1 OR COALESCE(plur.value, 0) = 1;
```

**CRITICAL:** If any results are returned, this is a critical error requiring rollback.

### 7. Pronoun Encoding Validation (NEW)

Verify pronouns have correct encoding:

```sql
-- Pronouns should have SOMEONE=1 + gram features
SELECT l.lemma,
       COALESCE(s.value, 0) as SOMEONE,
       COALESCE(sing.value, 0) as SING,
       COALESCE(plur.value, 0) as PLUR,
       gf.value as person
FROM lexemes l
LEFT JOIN primitive_values s ON l.id = s.lexeme_id AND s.primitive = 'SOMEONE'
LEFT JOIN primitive_values sing ON l.id = sing.lexeme_id AND sing.primitive = 'SING'
LEFT JOIN primitive_values plur ON l.id = plur.lexeme_id AND plur.primitive = 'PLUR'
LEFT JOIN gram_feature_values gf ON l.id = gf.lexeme_id AND gf.feature = 'person'
WHERE l.lemma IN ('i', 'me', 'you', 'he', 'she', 'it', 'we', 'they');
```

### 8. Numeral Encoding Validation (NEW)

Verify numerals have correct SING/PLUR/ZERO:

```sql
-- Check numeral encoding
SELECT l.lemma,
       COALESCE(zero.value, 0) as ZERO,
       COALESCE(sing.value, 0) as SING,
       COALESCE(plur.value, 0) as PLUR
FROM lexemes l
LEFT JOIN primitive_values zero ON l.id = zero.lexeme_id AND zero.primitive = 'ZERO'
LEFT JOIN primitive_values sing ON l.id = sing.lexeme_id AND sing.primitive = 'SING'
LEFT JOIN primitive_values plur ON l.id = plur.lexeme_id AND plur.primitive = 'PLUR'
WHERE l.lemma IN ('zero', 'one', 'two', 'three', 'four', 'five', 'many', 'few', 'none');
```

---

## Error Detection

### Critical Errors (Rollback Required)

- [ ] Component type set to invalid value
- [ ] SYN_* dimension value != 0
- [ ] Primitive value outside {-1, 0, 1}
- [ ] Orphaned primitive_values (no matching lexeme_id)
- [ ] Duplicate primitive entries for same lexeme

### Major Errors (Manual Review)

- [ ] >20% of sampled fixes semantically incorrect
- [ ] Missing fixes (audit said 500, log shows 300)
- [ ] Unexplained skips (>30% of batch)

### Minor Issues (Log and Continue)

- [ ] Redundant fixes (already correct)
- [ ] Over-cautious skips (could have been fixed)

---

## Rollback Procedure

If critical errors found:

```sql
-- Rollback fixes from this batch
DELETE FROM primitive_values WHERE source = 'fix:syn_instantiation';
DELETE FROM primitive_values WHERE source = 'fix:feel_experiencer';
DELETE FROM primitive_values WHERE source = 'fix:say_words';
DELETE FROM primitive_values WHERE source = 'fix:verb_eventuality';
DELETE FROM primitive_values WHERE source = 'fix:modifier_hierarchy';

-- Reset component types (requires backup of pre-fix state)
-- Use backup table if available
```

---

## Validation Report Format

```markdown
# Stage 4 Validation Report

## Summary
- Total fixes in log: {N}
- Verified correct: {N} ({%})
- Issues found: {N}
- Critical errors: {N}

## Component Type Validation
- Sample size: 20
- Correct: {N}
- Incorrect: {list}

## SYN_* Validation
- Wrong dimensions found: {N}
- Missing dimensions: {N}

## Semantic Consistency Validation
- FEEL+SOMEONE verified: {N}/{M}
- SAY+WORDS verified: {N}/{M}
- DO/HAPPEN verified: {N}/{M}

## Modifier Hierarchy Validation
- Negative INTENSITY remaining: {N}
- Missing HIER_MINUS: {N}

## OPERATOR Cleanup Validation
- Excessive primitives remaining: {N}

## Decision
[ ] PASS - Proceed to Stage 5
[ ] REVIEW - Manual review required for {items}
[ ] ROLLBACK - Critical errors, reverting fixes

## Issues for Manual Review
| Lemma | Issue | Current State | Expected |
|-------|-------|---------------|----------|
```

---

## Checklist

Before proceeding to Stage 5:

- [ ] Fix log parsed successfully
- [ ] 20-item sample verified for each category
- [ ] No critical errors detected
- [ ] No orphaned/duplicate entries
- [ ] All primitive values in {-1, 0, 1}
- [ ] Validation report generated
- [ ] Decision documented (PASS/REVIEW/ROLLBACK)
