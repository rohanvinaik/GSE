# Stage 3: Qwen 32B Fix Application

**Executor:** Qwen 32B (local via Ollama)
**Input:** Validated batch from Stage 2
**Output:** Fix log with all applied changes

---

## Purpose

Systematically apply fixes to the lexicon database based on the validated audit findings. Each fix must be logged with reasoning.

---

## New Primitives (v2.0)

The system now includes these additional primitives for grammatical encoding:

| Primitive | Description | Used For |
|-----------|-------------|----------|
| SING | Singular entity | Pronouns (I, you, he), numerals (one) |
| PLUR | Plural entity | Pronouns (we, they), numerals (two+) |
| ZERO | Non-existence | zero, none, nothing |
| ONE | Cardinality 1 | one, first, single |
| TWO | Cardinality 2 | two, second, pair |

### Mutual Transparency Rule

**CRITICAL**: If ZERO=1, then SING≠1 AND PLUR≠1

This rule must never be violated. ZERO represents non-existence, which is incompatible with singular or plural existence.

---

## Fix Categories

### Category 1: Component Type Assignment

**Rule:** Assign `component_type` and `operator_type` based on word class.

| Word Class | component_type | operator_type |
|------------|----------------|---------------|
| Content nouns, verbs, adjectives, adverbs | ATOMIC | NULL |
| Auxiliaries (be, have, do, modals) | OPERATOR | TAM_AUXILIARY |
| Negators (not, never, no, neither, nor) | OPERATOR | NEGATOR |
| Determiners (the, a, an, this, that, some, every, each, all) | OPERATOR | DETERMINER |
| Degree modifiers (very, extremely, barely, slightly, quite, rather) | OPERATOR | DEGREE |
| Prepositions (in, on, at, by, for, with, to, from, of, about) | OPERATOR | PREPOSITION |
| Conjunctions (and, or, but, nor, yet, so) | OPERATOR | CONJUNCTION |
| Complementizers (that, if, whether, because, although, while) | OPERATOR | COMPLEMENTIZER |

**SQL Template:**
```sql
UPDATE lexemes SET component_type = '{TYPE}', operator_type = '{SUBTYPE}'
WHERE id = {ID};
```

**Log Format:**
```
{lemma}: Set component_type={TYPE}, operator_type={SUBTYPE} (reason: {WORD_CLASS})
```

### Category 2: SYN_* Dimension Instantiation

**Rule:** Add informational zeros for grammatically possible roles.

| POS | Add Dimensions |
|-----|----------------|
| NOUN, NN, NNS, NNP, NNPS | SYN_SUBJ=0, SYN_OBJ=0, SYN_COMPL=0 |
| PRP, PRP$, WP | SYN_SUBJ=0, SYN_OBJ=0, SYN_COMPL=0 |
| VERB, VB, VBD, VBG, VBN, VBP, VBZ (ATOMIC only) | SYN_PRED=0 |
| ADJ, JJ, JJR, JJS | SYN_ADJ_MOD=0, SYN_COMPL=0 |
| ADV, RB, RBR, RBS | SYN_ADV_MOD=0 |
| DT, PDT, WDT | SYN_DET=0 |

**SQL Template:**
```sql
INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
VALUES ({ID}, '{SYN_DIM}', 0, 0.95, 'fix:syn_instantiation');
```

**Log Format:**
```
{lemma}: Added {SYN_DIM}=0 (reason: POS={POS} can fill {ROLE} role)
```

### Category 3: Semantic Consistency Fixes

#### 3a. FEEL without Experiencer

**Rule:** Words with FEEL=1 need SOMEONE=1 (experiencer).

**SQL Template:**
```sql
INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
VALUES ({ID}, 'SOMEONE', 1, 0.9, 'fix:feel_experiencer');
```

**Log Format:**
```
{lemma}: Added SOMEONE=1 (reason: FEEL=1 requires experiencer)
```

#### 3b. SAY without WORDS

**Rule:** Speech act verbs need WORDS=1.

**SQL Template:**
```sql
INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
VALUES ({ID}, 'WORDS', 1, 0.9, 'fix:say_words');
```

**Log Format:**
```
{lemma}: Added WORDS=1 (reason: SAY=1 requires WORDS)
```

#### 3c. Verbs Missing DO/HAPPEN

**Rule:** ATOMIC verbs need either DO=1 (agentive) or HAPPEN=1 (non-agentive).

Decision logic:
- If verb implies intentional action → DO=1
- If verb implies state change without agent → HAPPEN=1
- If unclear → Default to DO=1

**SQL Template:**
```sql
INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
VALUES ({ID}, '{DO_OR_HAPPEN}', 1, 0.85, 'fix:verb_eventuality');
```

**Log Format:**
```
{lemma}: Added {DO_OR_HAPPEN}=1 (reason: ATOMIC verb requires eventuality primitive)
```

### Category 4: Modifier Hierarchy Encoding

**Rule:** Degree modifiers use hierarchical stacking:
- Base primitive (INTENSITY/QUANTITY/CERTAINTY) = always **+1** (NOT -1)
- Direction via HIER_PLUS or HIER_MINUS
- Level = marker count

| Modifier | INTENSITY | HIER_PLUS | HIER_MINUS |
|----------|-----------|-----------|------------|
| very | 1 | 1 | 0 |
| highly | 1 | 1 | 0 |
| extremely | 1 | 2 | 0 |
| incredibly | 1 | 3 | 0 |
| slightly | 1 | 0 | 1 |
| somewhat | 1 | 0 | 1 |
| barely | 1 | 0 | 2 |
| hardly | 1 | 0 | 2 |

**SQL Template (fix negative INTENSITY):**
```sql
UPDATE primitive_values SET value = 1
WHERE lexeme_id = {ID} AND primitive = 'INTENSITY';

INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
VALUES ({ID}, 'HIER_MINUS', {LEVEL}, 0.9, 'fix:modifier_hierarchy');
```

**Log Format:**
```
{lemma}: Fixed INTENSITY=-1 to INTENSITY=1, HIER_MINUS={LEVEL} (reason: downward modifier uses hierarchy markers)
```

### Category 5: OPERATOR Primitive Cleanup

**Rule:** OPERATORs should have minimal semantic primitives. Remove excessive primitives from function words.

Allowed primitives for OPERATORs:
- TAM_AUXILIARY: TIME, BEFORE, AFTER, NOW, CERTAINTY (tense/aspect/mood)
- NEGATOR: NOT only
- DETERMINER: ONE, TWO, ALL, SOME, THIS, OTHER, SING, PLUR (quantification/deixis)
- DEGREE: INTENSITY, HIER_PLUS, HIER_MINUS only
- PREPOSITION: Spatial/relational (NEAR, FAR, INSIDE, TOWARD, etc.)
- CONJUNCTION: No semantic primitives (purely structural)

**SQL Template:**
```sql
DELETE FROM primitive_values
WHERE lexeme_id = {ID}
AND primitive NOT IN ({ALLOWED_PRIMITIVES});
```

**Log Format:**
```
{lemma}: Removed {COUNT} excess primitives (reason: OPERATOR type {SUBTYPE} allows only {ALLOWED})
```

### Category 6: Pronoun Encoding (NEW)

**Rule:** Pronouns get SOMEONE=1 (or SOMETHING=1 for "it") plus grammatical features.

| Pronoun | SOMEONE | SOMETHING | SING | PLUR | Gram Features |
|---------|---------|-----------|------|------|---------------|
| I, me, my, mine, myself | 1 | 0 | 1 | 0 | person=1, case=NOM/ACC/GEN |
| you, your, yours, yourself | 1 | 0 | 1 | 0 | person=2 |
| he, him, his, himself | 1 | 0 | 1 | 0 | person=3, gender=MASC |
| she, her, hers, herself | 1 | 0 | 1 | 0 | person=3, gender=FEM |
| it, its, itself | 0 | 1 | 1 | 0 | person=3, gender=NEUT |
| we, us, our, ours, ourselves | 1 | 0 | 1 | 1 | person=1 |
| they, them, their, theirs | 1 | 0 | 1 | 1 | person=3 |

**SQL Template:**
```sql
-- Set primitive
INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
VALUES ({ID}, '{PRIMITIVE}', 1, 0.95, 'fix:pronoun_encoding');

-- Set gram feature
INSERT INTO gram_feature_values (lexeme_id, feature, value, source)
VALUES ({ID}, '{FEATURE}', '{VALUE}', 'fix:pronoun_encoding')
ON CONFLICT(lexeme_id, feature) DO UPDATE SET value = '{VALUE}';
```

**Log Format:**
```
{lemma}: Set {PRIMITIVE}=1, SING={V}, PLUR={V}, person={P} (reason: pronoun encoding)
```

### Category 7: Numeral Encoding (NEW)

**Rule:** Numbers use SING/PLUR/ZERO with the mutual transparency constraint.

| Word | ZERO | SING | PLUR | Additional |
|------|------|------|------|------------|
| zero, none | 1 | 0 | 0 | - |
| one, first, single | 0 | 1 | 0 | ONE=1 |
| two, second, pair | 0 | 1 | 1 | TWO=1 |
| three+ | 0 | 1 | 1 | - |
| many, several, few | 0 | 1 | 1 | hierarchy_levels entry |

**SQL Template:**
```sql
-- Set SING/PLUR/ZERO
INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
VALUES ({ID}, 'SING', {V}, 0.95, 'fix:numeral_encoding');

-- Set hierarchy level for quantifiers
INSERT INTO hierarchy_levels (lexeme_id, scale, direction, level, source)
VALUES ({ID}, 'QUANTITY', {DIR}, {LEVEL}, 'fix:numeral_encoding')
ON CONFLICT(lexeme_id, scale) DO UPDATE SET direction={DIR}, level={LEVEL};
```

**Log Format:**
```
{lemma}: Set ZERO={V}, SING={V}, PLUR={V} (reason: numeral encoding)
```

### Category 8: Grammatical Feature Assignment (NEW)

**Rule:** Apply grammatical features to pronouns, determiners, and prepositions.

**Feature Types:**
- `person`: 1, 2, or 3
- `number`: SINGULAR or PLURAL
- `gender`: MASC, FEM, NEUT
- `case`: NOM, ACC, GEN, DAT
- `definiteness`: DEFINITE or INDEFINITE
- `deixis`: PROXIMAL or DISTAL

**SQL Template:**
```sql
INSERT INTO gram_feature_values (lexeme_id, feature, value, source)
VALUES ({ID}, '{FEATURE}', '{VALUE}', 'fix:gram_feature')
ON CONFLICT(lexeme_id, feature) DO UPDATE SET value = '{VALUE}';
```

**Log Format:**
```
{lemma}: Set {feature}={value} (reason: {WORD_CLASS} gram feature)
```

### Category 9: SING/PLUR/ZERO Mutual Transparency Fix (NEW)

**Rule:** If a word has ZERO=1, ensure SING=0 and PLUR=0.

**SQL Template:**
```sql
-- Fix ZERO=1 with SING=1 violation
UPDATE primitive_values SET value = 0
WHERE lexeme_id = {ID} AND primitive IN ('SING', 'PLUR');
```

**Log Format:**
```
{lemma}: Fixed ZERO=1 violation, set SING=0, PLUR=0 (reason: mutual transparency rule)
```

---

## Processing Protocol

### Batch Structure

Process fixes in this order:
1. Component type assignments (structural foundation)
2. SYN_* instantiation (depends on component type)
3. Semantic consistency fixes (FEEL, SAY, DO/HAPPEN)
4. Modifier hierarchy corrections
5. OPERATOR cleanup (depends on type assignment)
6. **Pronoun encoding** (SOMEONE/SOMETHING + SING/PLUR + gram features)
7. **Numeral encoding** (SING/PLUR/ZERO + hierarchy levels)
8. **Grammatical feature assignment** (person, gender, case, definiteness)
9. **SING/PLUR/ZERO mutual transparency fixes** (cleanup any violations)

### For Each Fix

1. **Read** the input data (lemma, id, pos, current values)
2. **Decide** what fix to apply based on rules above
3. **Generate** SQL statement
4. **Log** the change with reasoning
5. **Continue** to next item

### Error Handling

If unsure about a fix:
- Log as `{lemma}: SKIPPED (reason: {WHY})`
- Continue to next item
- Do not halt on uncertainty

---

## Output Format

```
=== Stage 3 Fix Log ===
Batch: {BATCH_ID}
Timestamp: {ISO_TIMESTAMP}
Total items: {COUNT}

--- Component Type Fixes ---
the: Set component_type=OPERATOR, operator_type=DETERMINER (reason: determiner)
very: Set component_type=OPERATOR, operator_type=DEGREE (reason: degree modifier)
run: Set component_type=ATOMIC, operator_type=NULL (reason: content verb)
...

--- SYN_* Instantiation ---
dog: Added SYN_SUBJ=0 (reason: POS=NN can fill SUBJ role)
dog: Added SYN_OBJ=0 (reason: POS=NN can fill OBJ role)
dog: Added SYN_COMPL=0 (reason: POS=NN can fill COMPL role)
run: Added SYN_PRED=0 (reason: POS=VB can fill PRED role)
...

--- Semantic Consistency Fixes ---
happy: Added SOMEONE=1 (reason: FEEL=1 requires experiencer)
speak: Added WORDS=1 (reason: SAY=1 requires WORDS)
walk: Added DO=1 (reason: ATOMIC verb requires eventuality primitive)
...

--- Modifier Hierarchy Fixes ---
barely: Fixed INTENSITY=-1 to INTENSITY=1, HIER_MINUS=2 (reason: downward modifier uses hierarchy markers)
...

--- OPERATOR Cleanup ---
the: Removed 5 excess primitives (reason: OPERATOR type DETERMINER allows only ONE, THIS, OTHER)
...

--- Pronoun Encoding (NEW) ---
i: Set SOMEONE=1, SING=1, PLUR=0, person=1, case=NOM (reason: pronoun encoding)
we: Set SOMEONE=1, SING=1, PLUR=1, person=1 (reason: pronoun encoding)
it: Set SOMETHING=1, SING=1, PLUR=0, person=3, gender=NEUT (reason: pronoun encoding)
...

--- Numeral Encoding (NEW) ---
zero: Set ZERO=1, SING=0, PLUR=0 (reason: numeral encoding)
one: Set ZERO=0, SING=1, PLUR=0, ONE=1 (reason: numeral encoding)
two: Set ZERO=0, SING=1, PLUR=1, TWO=1 (reason: numeral encoding)
many: Set ZERO=0, SING=1, PLUR=1, QUANTITY scale +2 (reason: numeral encoding)
...

--- Grammatical Feature Fixes (NEW) ---
the: Set definiteness=DEFINITE (reason: determiner gram feature)
this: Set definiteness=DEFINITE, deixis=PROXIMAL (reason: determiner gram feature)
...

--- SING/PLUR/ZERO Mutual Transparency Fixes (NEW) ---
(none expected if encoding is correct)
...

--- Skipped ---
ambiguous: SKIPPED (reason: multiple senses, needs manual review)
...

=== Summary ===
Component fixes: {N}
SYN_* fixes: {N}
Semantic fixes: {N}
Hierarchy fixes: {N}
OPERATOR cleanup: {N}
Pronoun encoding: {N}
Numeral encoding: {N}
Gram feature fixes: {N}
SING/PLUR/ZERO fixes: {N}
Skipped: {N}
Total changes: {N}
```

---

## SQL Execution Script

After generating the log, apply via Python:

```python
import sqlite3
import re

conn = sqlite3.connect("data/lexicon.db")
cursor = conn.cursor()

# Parse log and execute SQL
with open("data/stage3_fixes.log", "r") as f:
    log = f.read()

# Extract SQL statements (generated separately or inline)
# Apply each with error handling
for sql in sql_statements:
    try:
        cursor.execute(sql)
    except Exception as e:
        print(f"Error: {sql[:50]}... - {e}")

conn.commit()
conn.close()
```

---

## Quality Markers

Good fix log characteristics:
- Every entry has lemma, action, and reason
- Reasons reference specific rules
- Skipped items explain why
- Summary counts match line counts
- No unexplained gaps in processing
