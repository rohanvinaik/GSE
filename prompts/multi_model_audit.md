# Multi-Model Local Audit System

**Purpose:** Continuous background audit using small local LLMs for quality improvement
**Models:** smollm:1.7b, granite3-moe:1b, gemma2:2b
**Mode:** AUDIT ONLY - flags issues, no database modifications
**Architecture:** v5 - ATOMIC/OPERATOR/ABSORBED with TAM_AUXILIARY, NEGATOR, DEGREE, DETERMINER

## Model Agreement Protocol

- **3/3 Agreement** = HIGH PRIORITY FIX (all models agree on issue)
- **2/3 Agreement** = MEDIUM PRIORITY (likely issue, needs verification)
- **1/3 or Disagreement** = FLAG FOR DEEPER ANALYSIS (needs larger model review)

---

## Core Semantic Rules (Condensed for Small Models)

### Rule 1: Function Words = Minimal Primitives
Function words (the, of, and, to, a, in, is, that, for, with, as, on, at, by, from, or, an, be, are, was, were, been, being, have, has, had, not, but, if, which, so, what, when, into, than, its, any, no, do, how, up, out, just, about) should have 0-2 active primitives.

### Rule 2: FEEL Requires Experiencer
If FEEL=1, then SOMEONE=1 or I=1 or YOU=1 must also be true.
- CORRECT: "happy" has FEEL=1, SOMEONE=1
- INCORRECT: "system" has FEEL=1 but no experiencer

### Rule 3: SAY Requires WORDS
If SAY=1, then WORDS=1 should be true.
- CORRECT: "speak" has SAY=1, WORDS=1
- INCORRECT: "water" has SAY=1 but no WORDS

### Rule 4: Bipolar Consistency
These pairs cannot both be +1:
- GOOD/BAD
- TRUE/FALSE
- BIG/SMALL
- LONG_TIME/SHORT_TIME
- NEAR/FAR
- ABOVE/BELOW
- BEFORE/AFTER
- INSIDE/OUTSIDE
- MORE/LESS

### Rule 5: BODY Requires Physical Object
BODY=1 should only apply to physical things (body parts, tangible objects).
- CORRECT: "hand" has BODY=1
- INCORRECT: "theory" has BODY=1

### Rule 6: DO/HAPPEN for Verbs
Verbs should have either DO=1 (agentive) or HAPPEN=1 (non-agentive) or both.
- "run" = DO=1 (intentional action)
- "fall" = HAPPEN=1 (unintentional event)
- "break" = both (can be done or can happen)

### Rule 7: Pronouns Need SOMEONE
Personal pronouns (I, me, you, he, she, they, etc.) should have SOMEONE=1.

### Rule 8: Emotion Words Need FEEL
Words expressing emotions (happy, sad, angry, afraid, etc.) should have FEEL=1.

### Rule 9: Modifier Hierarchy Encoding
Intensity/quantity/certainty modifiers use hierarchical stacking:
- Base primitive (INTENSITY/QUANTITY/CERTAINTY) always +1
- Direction via HIER_PLUS (positive level) or HIER_MINUS (negative level)
- Level = marker count

**Ground truth:** `data/external/intensity_ground_truth.json` (74 modifiers, 191 scalar scales)

Examples:
- "very" = INTENSITY=1, HIER_PLUS=1 (level +1)
- "extremely" = INTENSITY=1, HIER_PLUS=2 (level +2)
- "barely" = INTENSITY=1, HIER_MINUS=2 (level -2)
- "many" = QUANTITY=1, HIER_PLUS=2 (level +2)
- "likely" = CERTAINTY=1, HIER_PLUS=2 (level +2)

**Common errors:**
- INTENSITY=-1 is WRONG (should be +1 with HIER_MINUS markers)
- Missing HIER markers for non-neutral modifiers

---

## Prompt Templates for Small Models

### Template A: Quick Check (5 words per batch)
```
Review these word-primitive assignments. For each word, identify any rule violations.

Rules:
1. FEEL=1 requires SOMEONE/I/YOU=1
2. SAY=1 requires WORDS=1
3. Bipolar pairs (GOOD/BAD, TRUE/FALSE) cannot both be 1
4. Function words should have 0-2 primitives

Words:
{word1}: {primitives1}
{word2}: {primitives2}
{word3}: {primitives3}
{word4}: {primitives4}
{word5}: {primitives5}

For each violation found, output:
WORD:RULE:ISSUE

If no violations, output: OK
```

### Template B: Semantic Validation (1 word deep check)
```
Is this primitive assignment correct?

Word: {word}
POS: {pos}
Active primitives: {primitives}

Check:
1. Does FEEL=1 make sense? (requires subjective experience)
2. Does SAY=1 make sense? (requires speech/language)
3. Does BODY=1 make sense? (requires physical object)
4. Are there contradictory primitives?

Output ONE of:
CORRECT - assignment is accurate
WRONG:primitive:reason - specify which primitive is wrong
MISSING:primitive - specify which primitive should be added
```

### Template C: Comparative Check (2 words)
```
Compare these two word assignments for consistency:

Word A: {word_a} - {primitives_a}
Word B: {word_b} - {primitives_b}

These words are semantically similar. Do their primitives match appropriately?

Output:
CONSISTENT - both assignments make sense
INCONSISTENT:reason - explain the inconsistency
```

---

## Batch Processing Strategy

### Phase 1: Quick Scan (All Words)
- Process in batches of 5 words
- Use Template A
- Flag any violations
- ~1 min per batch with small models

### Phase 2: Deep Check (Flagged Words)
- Process individually
- Use Template B
- Get detailed reasoning
- ~30 sec per word

### Phase 3: Cross-Validation (Similar Words)
- Compare semantically similar words
- Use Template C
- Check for consistency
- Sample-based (not exhaustive)

---

## Output Format

### Per-Word Result
```json
{
  "word": "example",
  "pos": "NOUN",
  "models": {
    "smollm": {"verdict": "WRONG", "issue": "FEEL:abstract_noun", "confidence": 0.8},
    "granite3-moe": {"verdict": "WRONG", "issue": "FEEL:abstract_noun", "confidence": 0.7},
    "gemma2": {"verdict": "CORRECT", "issue": null, "confidence": 0.6}
  },
  "agreement": 2,
  "priority": "MEDIUM",
  "action": "review_feel_primitive"
}
```

### Session Summary
```json
{
  "timestamp": "2026-01-03T10:00:00",
  "words_processed": 500,
  "high_priority": 12,
  "medium_priority": 45,
  "needs_analysis": 23,
  "no_issues": 420
}
```

---

## Continuous Improvement Loop

```
REPEAT FOREVER:
  1. Select next batch of words (by frequency rank)
  2. Run through all 3 models
  3. Aggregate results
  4. Write findings to audit log
  5. Sleep 1 second between batches (prevent overload)
  6. After every 100 batches, write summary report
  7. Restart from beginning when all words processed
```

---

## Priority Classification

### HIGH PRIORITY (Immediate flag)
- All 3 models agree there's an issue
- Bipolar violations detected
- Function word with >5 primitives

### MEDIUM PRIORITY (Likely issue)
- 2/3 models agree
- Single rule violation
- Semantic inconsistency

### NEEDS DEEPER ANALYSIS
- Models disagree
- Complex polysemy
- Unusual word

### NO ACTION
- All models agree word is correct
- No rule violations detected
