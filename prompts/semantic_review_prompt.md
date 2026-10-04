# Semantic Review Prompt for qwen3:32b

You are reviewing semantic primitive assignments in a lexicon database. For each word-primitive pair below, determine if the assignment is CORRECT, should be CHANGED, or REMOVED.

## Semantic Primitives Reference

The 72 Wierzbickian semantic primitives organized by category:

**Substantives:** I, YOU, SOMEONE, SOMETHING, PEOPLE, BODY
**Determiners:** THIS, SAME, OTHER, ONE, TWO, QUANTITY
**Mental Predicates:** THINK, KNOW, WANT, FEEL, SEE, HEAR, SAY, WORDS
**Evaluators:** GOOD, BAD
**Descriptors:** BIG, SMALL, INTENSITY
**Time:** WHEN, NOW, BEFORE, AFTER, LONG_TIME, SHORT_TIME, MOMENT, THEN, START, END
**Space:** WHERE, HERE, ABOVE, BELOW, FAR, NEAR, SIDE, INSIDE, OUTSIDE, TOWARD, AWAY, TOUCH
**Existence/Possession:** EXIST, HAVE, ALIVE, DEAD
**Actions:** DO, HAPPEN, MOVE, MAKE, CHANGE, CAUSE
**Logical:** NOT, IF, BECAUSE, INFER, CERTAINTY, TRUE, FALSE
**Relations:** KIND, LIKE, PART, WITH, WITHOUT
**Hierarchy:** HIER_PLUS, HIER_MINUS

## Key Semantic Rules

1. **FEEL primitive** = requires a subjective experiencer (SOMEONE, I, or YOU)
   - "happy" → FEEL=1 correct (humans feel happy)
   - "machine" → FEEL=1 INCORRECT (machines don't subjectively feel)

2. **SAY primitive** = communicative speech act, requires WORDS
   - "speak" → SAY=1, WORDS=1 correct
   - "water" → SAY=1 INCORRECT (water doesn't say anything)

3. **ALIVE primitive** = biological life
   - "dog" → ALIVE=1 correct
   - "robot" → ALIVE=1 INCORRECT (not biologically alive)

4. **Pronouns**:
   - First person (I, me) → I=1, SOMEONE=1
   - Second person (you) → YOU=1, SOMEONE=1
   - Third person (he, she) → SOMEONE=1

## Review Format

For each flagged issue, respond with:
```
WORD: <word>
PRIMITIVE: <primitive>
CURRENT: <current value>
DECISION: KEEP | SET_0 | SET_1 | SET_-1
REASON: <brief justification>
```

## Issues to Review

### Group 1: FEEL=1 without Experiencer
These words have FEEL=1 but lack SOMEONE/I/YOU. Determine if:
- A) FEEL=1 is WRONG (inanimate/abstract) → SET FEEL=0
- B) FEEL=1 is CORRECT → ADD SOMEONE=1

```
united, certain, structure, theory, real, energy, public, general, true, story, sense, fact, words, result, language, kind, management, said, response, organization, full, school, able, god, body, death, love, policy, everything, past, fig, health, production, truth, law, resources, war, relationship, quality, cultural, living, water, network, limited, failure, omnipotence, hash, patient
```

For each word above, output decision in format above.

### Group 2: Verbs Potentially Missing DO/HAPPEN
Check if these verbs should have DO=1 (agentive) or HAPPEN=1 (non-agentive):

```
become, seem, appear, exist, remain, consist, belong, differ, resemble, involve, depend, lack, owe, possess, deserve, prefer, imagine, remember, forget, notice, realize, recognize, suppose, doubt, believe
```

### Group 3: INTENSITY Value Review
NRC-VAD arousal scores may have been mapped incorrectly. Review these:
- INTENSITY=-1 should mean "low intensity/calm"
- INTENSITY=+1 should mean "high intensity/energetic"

Words flagged for review:
```
death (arousal=0.7, INTENSITY=?), war (arousal=0.85), love (arousal=0.72), hate (arousal=0.78), fear (arousal=0.82), joy (arousal=0.68), calm (arousal=0.18), sleep (arousal=0.15), rest (arousal=0.22)
```

### Group 4: Modifier Hierarchy Validation
**Ground truth:** `data/external/intensity_ground_truth.json`

GSE uses hierarchical stacking for intensity/quantity/certainty:
- Base primitive (INTENSITY/QUANTITY/CERTAINTY) always = +1
- Direction via HIER_PLUS (positive) or HIER_MINUS (negative)
- Level = marker count

**Correct encodings:**
| Word | Type | Level | Encoding |
|------|------|-------|----------|
| very | INTENSITY | +1 | INTENSITY=1, HIER_PLUS=1 |
| extremely | INTENSITY | +2 | INTENSITY=1, HIER_PLUS=2 |
| barely | INTENSITY | -2 | INTENSITY=1, HIER_MINUS=2 |
| slightly | INTENSITY | -1 | INTENSITY=1, HIER_MINUS=1 |
| many | QUANTITY | +2 | QUANTITY=1, HIER_PLUS=2 |
| few | QUANTITY | -2 | QUANTITY=1, HIER_MINUS=2 |
| likely | CERTAINTY | +2 | CERTAINTY=1, HIER_PLUS=2 |
| impossible | CERTAINTY | -3 | CERTAINTY=1, HIER_MINUS=3 |

**Common errors to fix:**
- INTENSITY=-1 is WRONG → should be INTENSITY=1 + HIER_MINUS markers
- Missing HIER markers → add appropriate count
- Wrong base polarity → change to +1

For each modifier word, output:
```
WORD: <word>
CURRENT: INTENSITY=?, HIER_PLUS=?, HIER_MINUS=?
EXPECTED: INTENSITY=1, HIER_PLUS=?, HIER_MINUS=?
FIX: SET_INTENSITY_1 | ADD_HIER_PLUS:N | ADD_HIER_MINUS:N
REASON: <brief justification>
```

## Output Summary

After reviewing all groups, provide a summary SQL script:

```sql
-- FEEL fixes
UPDATE primitive_values SET value = 0, source = 'llm:qwen3:32b_review'
WHERE primitive = 'FEEL' AND lexeme_id IN (SELECT id FROM lexemes WHERE lemma IN (...));

-- SOMEONE additions
INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SOMEONE', 1, 0.85, 'llm:qwen3:32b_review'
FROM lexemes WHERE lemma IN (...);

-- DO/HAPPEN fixes
...
```
