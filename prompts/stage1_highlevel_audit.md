# Stage 1: High-Level Lexicon Audit

**Executor:** Google Antigravity (agent-focused IDE)
**Mode:** AUDIT ONLY - produce report, do not modify database

---

## Purpose

Perform high-level common-sense validation of the GSE lexicon database to ensure:
1. Every word has confident +1/0/-1 assignment in all required semantic banks
2. No empty banks among required fields
3. Structural conformity with the new sentence-scale architecture
4. SYN_* dimension instantiation based on grammatical roles
5. **NEW**: Proper encoding of SING/PLUR/ZERO for numerals and quantifiers
6. **NEW**: Grammatical features stored in gram_feature_values table

---

## Files

**Main database:** `data/lexicon.db` (SQLite)

**Schema:**
```sql
-- Core tables
-- lexemes: id, lemma, pos, frequency_rank, component_type, operator_type, binding_behavior, gram_features, animacy
-- primitive_values: lexeme_id, primitive, value (-1/0/+1), confidence, source

-- NEW sentence-scope tables
-- gram_feature_values: id, lexeme_id, feature, value, source
--   Features: person (1/2/3), number (SINGULAR/PLURAL), gender (MASC/FEM/NEUT),
--             case (NOM/ACC/GEN/DAT), definiteness (DEFINITE/INDEFINITE),
--             reflexivity (REFLEXIVE/NON_REFLEXIVE), deixis (PROXIMAL/DISTAL),
--             entity_type (PERSON/PLACE/ORG)
-- hierarchy_levels: id, lexeme_id, scale, direction, level, source
--   Scales: INTENSITY, QUANTITY, CERTAINTY, FREQUENCY
--   Direction: -1 (diminishing) or +1 (intensifying)
--   Level: 1-5 (magnitude)
-- syn_dimensions: id, lexeme_id, dimension, instantiated, source
--   Dimensions: SYN_SUBJ, SYN_OBJ, SYN_OBJ2, SYN_COMPL, SYN_PRED,
--               SYN_ADJ_MOD, SYN_ADV_MOD, SYN_DET, SYN_PP_MOD, SYN_CLAUSE_MOD
```

## New Primitives (v2.0)

The following primitives have been added for grammatical encoding:

| Primitive | Description | Usage |
|-----------|-------------|-------|
| **SING** | Singular entity marker | Pronouns (I, you, he), numerals (one, first) |
| **PLUR** | Plural entity marker | Pronouns (we, they), numerals (two, many) |
| **ZERO** | Absence/non-existence marker | Numerals (zero, none), negation |
| **ONE**, **TWO** | Cardinality markers | Numerals (stacked on SING/PLUR) |

### SING/PLUR/ZERO Mutual Transparency Rule

This is a **critical constraint** that must be validated:

```
If ZERO=1, then SING≠1 AND PLUR≠1
```

The SING/ZERO and PLUR/ZERO banks are **orthogonal systems**:
- SING/ZERO: encodes existence vs non-existence of a single entity
- PLUR/ZERO: encodes presence vs absence of multiples

Examples:
- "one" → SING=1, PLUR=0, ZERO=0 (singular entity exists)
- "two" → SING=1, PLUR=1, ZERO=0 (singular + multiples exist)
- "zero" → SING=0, PLUR=0, ZERO=1 (non-existence)
- "none" → SING=0, PLUR=0, ZERO=1 (non-existence)

**External validation sources (for reference):**
- `data/external/nrc_vad.txt` - Valence/Arousal/Dominance
- `data/external/lancaster_sensorimotor.csv` - Sensorimotor norms
- `data/external/concreteness.csv` - Concreteness ratings
- `data/external/intensity_ground_truth.json` - Modifier hierarchy ground truth

---

## Architecture Requirements

### Component Types
Every word in the lexicon must be classified as one of:

| Type | Description | Examples |
|------|-------------|----------|
| **ATOMIC** | Content words with semantic meaning | nouns, verbs, adjectives, adverbs |
| **OPERATOR** | Function words that perform operations | aux, det, neg, prep, conj, degree |

Note: ABSORBED (inflectional morphemes like -ed, -s, -ing) are not standalone words in the lexicon.

### Operator Subtypes
Every OPERATOR must have an operator_type:

| Subtype | Binding | Examples |
|---------|---------|----------|
| TAM_AUXILIARY | LAZY | did, will, have, be, can, must, shall, may, might |
| NEGATOR | GREEDY | not, never, no, neither, nor |
| DETERMINER | GREEDY | the, a, an, this, that, some, every, each |
| DEGREE | GREEDY | very, extremely, barely, slightly, quite, rather |
| PREPOSITION | GREEDY | in, on, at, by, for, with, to, from, of |
| CONJUNCTION | N/A | and, or, but, nor, yet, so |
| COMPLEMENTIZER | N/A | that, if, whether, because, although, while |

### SYN_* Dimensions (Informational Zero)
Each word must have SYN_* dimensions instantiated with 0 based on possible grammatical roles:

| POS | Instantiate (set to 0) |
|-----|------------------------|
| Nouns (NN, NNS, NNP, NNPS) | SYN_SUBJ, SYN_OBJ, SYN_COMPL |
| Pronouns (PRP, PRP$, WP) | SYN_SUBJ, SYN_OBJ, SYN_COMPL |
| Verbs (VB, VBD, VBG, VBN, VBP, VBZ) | SYN_PRED |
| Adjectives (JJ, JJR, JJS) | SYN_ADJ_MOD, SYN_COMPL |
| Adverbs (RB, RBR, RBS) | SYN_ADV_MOD |
| Determiners (DT, PDT, WDT) | SYN_DET |

### Modifier Hierarchy Encoding
Degree modifiers must use hierarchical stacking:
- Base primitive (INTENSITY/QUANTITY/CERTAINTY) = always **+1** (NOT -1)
- Direction via HIER_PLUS or HIER_MINUS
- Level = marker count

| Word | Expected |
|------|----------|
| very | INTENSITY=1, HIER_PLUS=1, HIER_MINUS=0 |
| extremely | INTENSITY=1, HIER_PLUS=2, HIER_MINUS=0 |
| barely | INTENSITY=1, HIER_PLUS=0, HIER_MINUS=2 |
| slightly | INTENSITY=1, HIER_PLUS=0, HIER_MINUS=1 |

---

## Audit Checks

Run these checks on the **top 5000 words by frequency_rank**:

### 1. Component Type Assignment

```sql
-- Words missing component_type
SELECT COUNT(*) as missing_component_type
FROM lexemes WHERE component_type IS NULL;

-- OPERATORs missing operator_type
SELECT lemma, pos FROM lexemes
WHERE component_type = 'OPERATOR' AND operator_type IS NULL;

-- Known function words incorrectly marked ATOMIC
SELECT lemma, pos, component_type FROM lexemes
WHERE lemma IN ('the', 'a', 'not', 'very', 'in', 'on', 'and', 'or', 'is', 'are', 'was', 'were', 'did', 'will', 'have', 'be')
AND component_type = 'ATOMIC';

-- Auxiliaries not marked as TAM_AUXILIARY
SELECT lemma FROM lexemes
WHERE lemma IN ('be', 'am', 'is', 'are', 'was', 'were', 'been', 'being',
                'have', 'has', 'had', 'do', 'does', 'did',
                'can', 'could', 'will', 'would', 'shall', 'should', 'may', 'might', 'must')
AND (component_type != 'OPERATOR' OR operator_type != 'TAM_AUXILIARY');
```

### 2. SYN_* Dimension Instantiation

```sql
-- Nouns missing SYN_SUBJ
SELECT COUNT(*) as nouns_missing_syn_subj FROM lexemes l
WHERE l.pos IN ('NOUN', 'NN', 'NNS', 'NNP', 'NNPS')
AND NOT EXISTS (
    SELECT 1 FROM primitive_values pv
    WHERE pv.lexeme_id = l.id AND pv.primitive = 'SYN_SUBJ'
);

-- Verbs missing SYN_PRED (excluding OPERATORs)
SELECT COUNT(*) as verbs_missing_syn_pred FROM lexemes l
WHERE l.pos IN ('VERB', 'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ')
AND l.component_type = 'ATOMIC'
AND NOT EXISTS (
    SELECT 1 FROM primitive_values pv
    WHERE pv.lexeme_id = l.id AND pv.primitive = 'SYN_PRED'
);

-- Adjectives missing SYN_ADJ_MOD
SELECT COUNT(*) as adj_missing_syn_adj_mod FROM lexemes l
WHERE l.pos IN ('ADJ', 'JJ', 'JJR', 'JJS')
AND NOT EXISTS (
    SELECT 1 FROM primitive_values pv
    WHERE pv.lexeme_id = l.id AND pv.primitive = 'SYN_ADJ_MOD'
);
```

### 3. Semantic Consistency (9 Core Rules + 1 New Rule)

```sql
-- Rule 1: FEEL=1 without experiencer
SELECT l.lemma, l.pos FROM lexemes l
JOIN primitive_values feel ON l.id = feel.lexeme_id AND feel.primitive = 'FEEL'
WHERE feel.value = 1
AND NOT EXISTS (
    SELECT 1 FROM primitive_values pv
    WHERE pv.lexeme_id = l.id AND pv.primitive IN ('SOMEONE', 'I', 'YOU') AND pv.value = 1
)
LIMIT 50;

-- Rule 2: SAY=1 without WORDS
SELECT l.lemma FROM lexemes l
JOIN primitive_values say ON l.id = say.lexeme_id AND say.primitive = 'SAY'
LEFT JOIN primitive_values words ON l.id = words.lexeme_id AND words.primitive = 'WORDS'
WHERE say.value = 1 AND (words.value IS NULL OR words.value != 1)
LIMIT 50;

-- Rule 3: Bipolar violations (GOOD=1 AND BAD=1)
SELECT l.lemma, 'GOOD/BAD' as pair FROM lexemes l
JOIN primitive_values g ON l.id = g.lexeme_id AND g.primitive = 'GOOD'
JOIN primitive_values b ON l.id = b.lexeme_id AND b.primitive = 'BAD'
WHERE g.value = 1 AND b.value = 1;

-- Rule 5: Verbs missing DO/HAPPEN
SELECT l.lemma FROM lexemes l
WHERE l.pos IN ('VERB', 'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ')
AND l.component_type = 'ATOMIC'
AND NOT EXISTS (
    SELECT 1 FROM primitive_values pv
    WHERE pv.lexeme_id = l.id AND pv.primitive IN ('DO', 'HAPPEN') AND pv.value = 1
)
LIMIT 50;

-- Rule 8: OPERATORs with too many primitives
SELECT l.lemma, l.operator_type, COUNT(*) as prim_count
FROM lexemes l
JOIN primitive_values pv ON l.id = pv.lexeme_id
WHERE l.component_type = 'OPERATOR' AND pv.value != 0
GROUP BY l.lemma
HAVING prim_count > 2
ORDER BY prim_count DESC
LIMIT 30;

-- NEW Rule 10: SING/PLUR/ZERO Mutual Transparency Violation
-- If ZERO=1, neither SING nor PLUR should be 1
SELECT l.lemma,
       sing.value as SING,
       plur.value as PLUR,
       zero.value as ZERO
FROM lexemes l
JOIN primitive_values zero ON l.id = zero.lexeme_id AND zero.primitive = 'ZERO'
LEFT JOIN primitive_values sing ON l.id = sing.lexeme_id AND sing.primitive = 'SING'
LEFT JOIN primitive_values plur ON l.id = plur.lexeme_id AND plur.primitive = 'PLUR'
WHERE zero.value = 1
  AND (COALESCE(sing.value, 0) = 1 OR COALESCE(plur.value, 0) = 1);
```

### 3a. Grammatical Feature Validation

```sql
-- Pronouns with SOMEONE=1 should have person feature
SELECT l.lemma, 'missing person' as issue
FROM lexemes l
JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.primitive = 'SOMEONE' AND pv.value = 1
WHERE l.lemma IN ('i', 'me', 'my', 'mine', 'myself',
                  'you', 'your', 'yours', 'yourself',
                  'he', 'him', 'his', 'she', 'her', 'hers',
                  'it', 'its', 'we', 'us', 'our', 'ours',
                  'they', 'them', 'their', 'theirs')
AND NOT EXISTS (
    SELECT 1 FROM gram_feature_values gf
    WHERE gf.lexeme_id = l.id AND gf.feature = 'person'
);

-- Determiners should have definiteness feature
SELECT l.lemma, 'missing definiteness' as issue
FROM lexemes l
WHERE l.operator_type = 'DETERMINER'
AND NOT EXISTS (
    SELECT 1 FROM gram_feature_values gf
    WHERE gf.lexeme_id = l.id AND gf.feature = 'definiteness'
);

-- Numerals should have SING or ZERO
SELECT l.lemma, 'missing SING/ZERO' as issue
FROM lexemes l
WHERE l.lemma IN ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
                  'eight', 'nine', 'ten', 'first', 'second', 'third', 'fourth')
AND NOT EXISTS (
    SELECT 1 FROM primitive_values pv
    WHERE pv.lexeme_id = l.id AND pv.primitive IN ('SING', 'ZERO') AND pv.value = 1
);
```

### 4. Modifier Hierarchy Encoding

```sql
-- INTENSITY=-1 is WRONG (should be +1 with HIER_MINUS)
SELECT l.lemma, i.value as INTENSITY
FROM lexemes l
JOIN primitive_values i ON l.id = i.lexeme_id AND i.primitive = 'INTENSITY'
WHERE i.value < 0;

-- Check degree modifiers for correct encoding
SELECT l.lemma, l.operator_type,
       COALESCE(i.value, 'NULL') as INTENSITY,
       COALESCE(hp.value, 'NULL') as HIER_PLUS,
       COALESCE(hm.value, 'NULL') as HIER_MINUS
FROM lexemes l
LEFT JOIN primitive_values i ON l.id = i.lexeme_id AND i.primitive = 'INTENSITY'
LEFT JOIN primitive_values hp ON l.id = hp.lexeme_id AND hp.primitive = 'HIER_PLUS'
LEFT JOIN primitive_values hm ON l.id = hm.lexeme_id AND hm.primitive = 'HIER_MINUS'
WHERE l.operator_type = 'DEGREE';
```

### 5. Empty Banks Check

```sql
-- Words with zero active primitives (excluding OPERATORs)
SELECT l.lemma, l.pos, l.component_type FROM lexemes l
WHERE l.component_type = 'ATOMIC'
AND l.frequency_rank <= 5000
AND NOT EXISTS (
    SELECT 1 FROM primitive_values pv
    WHERE pv.lexeme_id = l.id AND pv.value != 0
);
```

---

## Output Format

Generate an audit report with these sections:

```markdown
# Stage 1 Audit Report

## Summary
- Words audited: X
- Total issues found: X

### Issue Counts by Category
| Category | Count |
|----------|-------|
| Missing component_type | X |
| OPERATORs missing operator_type | X |
| Function words incorrectly ATOMIC | X |
| Missing SYN_* dimensions | X |
| FEEL without experiencer | X |
| SAY without WORDS | X |
| Bipolar violations | X |
| Verbs missing DO/HAPPEN | X |
| OPERATORs with excessive primitives | X |
| Wrong INTENSITY encoding | X |
| ATOMICs with no primitives | X |
| **SING/PLUR/ZERO violations** | X |
| **Pronouns missing gram features** | X |
| **Determiners missing definiteness** | X |
| **Numerals missing SING/ZERO** | X |

## Component Type Issues
| Word | POS | Current Type | Expected Type | Issue |
|------|-----|--------------|---------------|-------|

## SYN_* Dimension Issues
| POS Category | Missing Count | Sample Words |
|--------------|---------------|--------------|

## Semantic Consistency Issues
| Word | Rule | Issue | Current | Expected |
|------|------|-------|---------|----------|

## SING/PLUR/ZERO Mutual Transparency Violations (NEW)
| Word | SING | PLUR | ZERO | Expected Fix |
|------|------|------|------|--------------|

## Grammatical Feature Issues (NEW)
| Word | Category | Missing Feature | Expected Value |
|------|----------|-----------------|----------------|

## Modifier Hierarchy Issues
| Word | Scale | Direction | Level | Issue |
|------|-------|-----------|-------|-------|

## Empty Bank Issues
| Word | POS | Issue |
|------|-----|-------|
```

Save the audit report to `data/stage1_audit_report.md`.

---

## Execution

Run the SQL queries above against `data/lexicon.db` and compile the results into the audit report format. Focus on:

1. **Structural issues first** (component_type, operator_type, SYN_*)
2. **Semantic consistency** (the 9 core rules)
3. **Modifier hierarchy** (INTENSITY encoding)

The audit report will be passed to Claude Code (Stage 2) for validation and Qwen prompt preparation.
