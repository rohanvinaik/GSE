# Informational Zero Audit

**Purpose:** Instantiate grammatical dimensions with explicit zeros for sentence-level parsing
**Stage:** 4 (after Modifier Hierarchy, before Cross-Source Validation)

---

## Core Principle

> "ran" and "run" should have cosine similarity = 1.0 at word level

This requires separating:
- **Semantic content** → Encoded in HDC vector (similarity-relevant)
- **Grammatical function** → Stored as metadata (masked from similarity)

### The Informational Zero Concept

| Value | Meaning | Example |
|-------|---------|---------|
| +1 | Dimension active, positive | "happy" has FEEL=+1 |
| -1 | Dimension active, negative | "sad" has GOOD=-1 |
| **0 (explicit)** | Dimension applicable but not active | "dog" has SYN_SUBJ=0 (can be subject) |
| **blank/NULL** | Dimension not applicable | "dog" has no SYN_PRED (can't be predicate) |

The difference between 0 and blank is **crucial**:
- **0**: Word CAN play this role, currently inactive
- **blank**: Word CANNOT play this role ever

---

## Why This Matters

### 1. O(1) Sentence Parsing

With pre-instantiated zeros, parsing becomes a mask operation:

```python
# Without informational zeros: Must check each word's possible roles
for word in sentence:
    if can_word_be_subject(word):  # Complex lookup
        possible_subjects.append(word)

# With informational zeros: Direct dimension check
for word in sentence:
    if word.vector[SYN_SUBJ_DIM] is not None:  # Already marked
        possible_subjects.append(word)
```

### 2. Constraint Propagation

Grammar rules collapse the parse space. Pre-marking possible roles enables fast constraint propagation:

```python
# Each word's possible roles are pre-computed
# Grammar rules prune to ~2-3 options per position
# Instead of N^N possibilities, we get ~3^N (orders of magnitude smaller)
```

### 3. Inflected Form Identity

```python
# "ran" and "run" have IDENTICAL semantic vectors
# Only gram_features metadata differs
assert semantic_similarity("ran", "run") == 1.0

# This works because:
# - Semantic primitives (DO, MOVE, BODY) are the same
# - Tense (PAST vs PRESENT) is in metadata, not vector
```

---

## Grammatical Dimensions

### Sentence-Level Syntactic Primitives (SYN_*)

These dimensions mark what grammatical roles a word CAN fill:

| Primitive | Description | Words That Need It |
|-----------|-------------|-------------------|
| SYN_SUBJ | Can be subject | Nouns, pronouns |
| SYN_PRED | Can be predicate | Verbs |
| SYN_OBJ | Can be object | Nouns, pronouns |
| SYN_COMPL | Can be complement | Nouns, adjectives |
| SYN_ADJ_MOD | Can modify noun | Adjectives |
| SYN_ADV_MOD | Can modify verb/adj | Adverbs |
| SYN_DET | Can determine noun | Determiners |

### TAM Features (Tense-Aspect-Mood)

| Primitive | Description | Words That Need It |
|-----------|-------------|-------------------|
| SYN_TENSE_PAST | Past tense form | Past tense verbs |
| SYN_TENSE_PRES | Present tense form | Present tense verbs |
| SYN_TENSE_FUT | Future tense marker | "will", future forms |
| SYN_ASPECT_PERF | Perfect aspect | "have eaten" |
| SYN_ASPECT_PROG | Progressive aspect | "is eating" |
| SYN_MOOD_INTER | Interrogative mood | Question words |
| SYN_MOOD_IMPER | Imperative mood | Command forms |

---

## POS → Grammatical Dimension Mapping

### Nouns
```sql
-- Nouns can be: subject, object, complement
INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_SUBJ', 0, 0.95, 'fix:gram_instantiation'
FROM lexemes WHERE pos = 'NOUN';

INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_OBJ', 0, 0.95, 'fix:gram_instantiation'
FROM lexemes WHERE pos = 'NOUN';

INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_COMPL', 0, 0.95, 'fix:gram_instantiation'
FROM lexemes WHERE pos = 'NOUN';
```

### Pronouns
```sql
-- Pronouns can be: subject, object
INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_SUBJ', 0, 0.95, 'fix:gram_instantiation'
FROM lexemes WHERE pos = 'PRON';

INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_OBJ', 0, 0.95, 'fix:gram_instantiation'
FROM lexemes WHERE pos = 'PRON';
```

### Verbs
```sql
-- Verbs can be: predicate
INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_PRED', 0, 0.95, 'fix:gram_instantiation'
FROM lexemes WHERE pos = 'VERB';

-- Past tense forms get SYN_TENSE_PAST=0 (can express past)
INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_TENSE_PAST', 0, 0.95, 'fix:gram_instantiation'
FROM lexemes WHERE pos = 'VERB';

INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_TENSE_PRES', 0, 0.95, 'fix:gram_instantiation'
FROM lexemes WHERE pos = 'VERB';
```

### Adjectives
```sql
-- Adjectives can be: modifier, complement
INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_ADJ_MOD', 0, 0.95, 'fix:gram_instantiation'
FROM lexemes WHERE pos = 'ADJ';

INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_COMPL', 0, 0.95, 'fix:gram_instantiation'
FROM lexemes WHERE pos = 'ADJ';
```

### Adverbs
```sql
-- Adverbs can be: adverbial modifier
INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_ADV_MOD', 0, 0.95, 'fix:gram_instantiation'
FROM lexemes WHERE pos = 'ADV';
```

### Determiners
```sql
-- Determiners have SYN_DET
INSERT INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_DET', 0, 0.95, 'fix:gram_instantiation'
FROM lexemes WHERE pos = 'DET' OR component_type = 'OPERATOR' AND operator_type = 'DETERMINER';
```

---

## Grammatical Features Metadata

In addition to SYN_* dimension instantiation, store detailed grammatical features as JSON metadata:

### Schema Extension

```sql
ALTER TABLE lexemes ADD COLUMN gram_features TEXT;  -- JSON
```

### GrammaticalFeatures Structure

```python
@dataclass(frozen=True)
class GrammaticalFeatures:
    """
    Features stored as metadata, NOT in HDC vector.
    None = unspecified, specific value = feature active.
    """

    tense: Optional[str] = None  # PAST, PRESENT, FUTURE
    aspect: Optional[str] = None  # SIMPLE, PROGRESSIVE, PERFECT
    mood: Optional[str] = None  # INDICATIVE, SUBJUNCTIVE, IMPERATIVE
    person: Optional[int] = None  # 1, 2, 3
    number: Optional[str] = None  # SINGULAR, PLURAL
    case: Optional[str] = None  # NOM, ACC, GEN, DAT
```

### Example Entries

```sql
-- "run" (base form)
UPDATE lexemes SET gram_features = '{}' WHERE lemma = 'run';

-- "ran" (past tense)
UPDATE lexemes SET gram_features = '{"tense": "PAST"}' WHERE lemma = 'ran';

-- "runs" (3rd person singular present)
UPDATE lexemes SET gram_features = '{"tense": "PRESENT", "person": 3, "number": "SINGULAR"}'
WHERE lemma = 'runs';

-- "running" (progressive)
UPDATE lexemes SET gram_features = '{"aspect": "PROGRESSIVE"}' WHERE lemma = 'running';
```

---

## Inflected Form Handling

### Key Insight: Lemma-Based Encoding

All inflected forms of a word share the **same semantic vector** as their lemma:

```
run, runs, ran, running → Same semantic primitives (DO, MOVE, BODY)
```

Only gram_features differs:
```
run → {}
runs → {"person": 3, "number": "SINGULAR"}
ran → {"tense": "PAST"}
running → {"aspect": "PROGRESSIVE"}
```

### Implementation

```python
def encode_inflected_form(surface_form: str, lemma: str, features: dict) -> LexemeEntry:
    """
    Create lexeme entry for inflected form.
    Semantic vector comes from lemma, gram_features from analysis.
    """
    # Get lemma's semantic vector
    lemma_entry = lexicon.lookup(lemma)

    return LexemeEntry(
        lemma=lemma,
        surface_form=surface_form,
        semantic_vector=lemma_entry.semantic_vector,  # SAME vector!
        possible_roles=lemma_entry.possible_roles,
        gram_features=GrammaticalFeatures(**features),
        component_type=lemma_entry.component_type,
    )
```

### Similarity Verification

```python
# After encoding, verify informational zero principle:
ran_vec = lexicon.lookup("ran").semantic_vector
run_vec = lexicon.lookup("run").semantic_vector

# These should be IDENTICAL (semantic cosine = 1.0)
assert semantic_similarity(ran_vec, run_vec) == 1.0
```

---

## Audit Validation Rules

### Rule 1: POS-Appropriate SYN_* Instantiation

Every word should have SYN_* dimensions instantiated (with 0) for roles it can fill:

| POS | Required SYN_* (value=0) |
|-----|--------------------------|
| NOUN | SYN_SUBJ, SYN_OBJ, SYN_COMPL |
| PRON | SYN_SUBJ, SYN_OBJ |
| VERB | SYN_PRED, SYN_TENSE_PAST, SYN_TENSE_PRES |
| ADJ | SYN_ADJ_MOD, SYN_COMPL |
| ADV | SYN_ADV_MOD |
| DET | SYN_DET |

### Rule 2: No SYN_* for Inapplicable Roles

Words should NOT have SYN_* dimensions they can't fill:
- Nouns shouldn't have SYN_PRED
- Verbs shouldn't have SYN_ADJ_MOD
- etc.

### Rule 3: gram_features for Inflected Forms

All non-base forms should have gram_features metadata:
```sql
-- Find inflected forms missing gram_features
SELECT lemma FROM lexemes
WHERE pos = 'VERB'
AND lemma != (SELECT base FROM verb_lemmas WHERE inflected = lexemes.lemma)
AND (gram_features IS NULL OR gram_features = '{}');
```

### Rule 4: Consistent Semantic Vectors for Inflections

All forms of a lemma should have identical semantic primitives:
```sql
-- Find inconsistent verb forms
SELECT l1.lemma, l2.lemma, p1.primitive,
       p1.value as val1, p2.value as val2
FROM lexemes l1, lexemes l2
JOIN primitive_values p1 ON l1.id = p1.lexeme_id
JOIN primitive_values p2 ON l2.id = p2.lexeme_id
WHERE l1.lemma IN ('run', 'ran', 'runs', 'running')
AND l2.lemma IN ('run', 'ran', 'runs', 'running')
AND l1.id < l2.id
AND p1.primitive = p2.primitive
AND p1.value != p2.value;
-- Should return empty (all values should match)
```

---

## Implementation Script

```python
#!/usr/bin/env python3
"""
Informational Zero Instantiation Script
Adds SYN_* dimensions and gram_features metadata
"""

import sqlite3
import json
from typing import Dict, List, Optional

# POS to SYN_* dimension mapping
POS_SYN_MAPPING = {
    "NOUN": ["SYN_SUBJ", "SYN_OBJ", "SYN_COMPL"],
    "PRON": ["SYN_SUBJ", "SYN_OBJ"],
    "VERB": ["SYN_PRED", "SYN_TENSE_PAST", "SYN_TENSE_PRES"],
    "ADJ": ["SYN_ADJ_MOD", "SYN_COMPL"],
    "ADV": ["SYN_ADV_MOD"],
    "DET": ["SYN_DET"],
}

# Common inflection patterns
VERB_INFLECTIONS = {
    # past tense patterns
    "ed": {"tense": "PAST"},
    # progressive patterns
    "ing": {"aspect": "PROGRESSIVE"},
    # 3rd person singular
    "s": {"person": 3, "number": "SINGULAR"},
}


def instantiate_syn_dimensions(db_path: str):
    """Instantiate SYN_* dimensions with 0 for applicable words."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for pos, syn_dims in POS_SYN_MAPPING.items():
        # Get lexemes of this POS
        cursor.execute("SELECT id FROM lexemes WHERE pos = ?", (pos,))
        lexeme_ids = [row[0] for row in cursor.fetchall()]

        for lex_id in lexeme_ids:
            for syn_dim in syn_dims:
                # Check if already exists
                cursor.execute(
                    """
                    SELECT 1 FROM primitive_values
                    WHERE lexeme_id = ? AND primitive = ?
                """,
                    (lex_id, syn_dim),
                )

                if not cursor.fetchone():
                    # Instantiate with 0
                    cursor.execute(
                        """
                        INSERT INTO primitive_values
                        (lexeme_id, primitive, value, confidence, source)
                        VALUES (?, ?, 0, 0.95, 'fix:gram_instantiation')
                    """,
                        (lex_id, syn_dim),
                    )

        print(f"Instantiated SYN_* dimensions for {len(lexeme_ids)} {pos} words")

    conn.commit()
    conn.close()


def add_gram_features_column(db_path: str):
    """Add gram_features column if not exists."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE lexemes ADD COLUMN gram_features TEXT DEFAULT '{}'")
        print("Added gram_features column")
    except sqlite3.OperationalError:
        print("gram_features column already exists")

    conn.commit()
    conn.close()


def infer_gram_features(lemma: str, base_lemma: Optional[str] = None) -> Dict:
    """Infer grammatical features from word form."""
    features = {}

    if base_lemma and lemma != base_lemma:
        # Check for common patterns
        for suffix, feats in VERB_INFLECTIONS.items():
            if lemma.endswith(suffix) and not base_lemma.endswith(suffix):
                features.update(feats)

    return features


def populate_gram_features(db_path: str):
    """Populate gram_features for inflected forms."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all verbs with their potential base forms
    cursor.execute("""
        SELECT id, lemma FROM lexemes WHERE pos = 'VERB'
    """)
    verbs = cursor.fetchall()

    # Build lemma index
    lemma_set = {v[1] for v in verbs}

    updated = 0
    for id_, lemma in verbs:
        # Try to find base form
        base = None
        if lemma.endswith("ed"):
            potential_base = lemma[:-2]
            if potential_base in lemma_set:
                base = potential_base
            elif lemma[:-1] in lemma_set:  # doubled consonant
                base = lemma[:-1]
        elif lemma.endswith("ing"):
            potential_base = lemma[:-3]
            if potential_base in lemma_set:
                base = potential_base
            elif potential_base + "e" in lemma_set:
                base = potential_base + "e"
        elif lemma.endswith("s") and lemma[:-1] in lemma_set:
            base = lemma[:-1]

        features = infer_gram_features(lemma, base)
        if features:
            cursor.execute(
                """
                UPDATE lexemes SET gram_features = ? WHERE id = ?
            """,
                (json.dumps(features), id_),
            )
            updated += 1

    print(f"Updated gram_features for {updated} inflected forms")
    conn.commit()
    conn.close()


def verify_informational_zero(db_path: str):
    """Verify inflected forms have same semantics as base."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check a few known cases
    test_groups = [
        ("run", ["run", "runs", "ran", "running"]),
        ("walk", ["walk", "walks", "walked", "walking"]),
        ("think", ["think", "thinks", "thought", "thinking"]),
    ]

    for base, forms in test_groups:
        # Get primitives for each form
        for form in forms:
            cursor.execute(
                """
                SELECT primitive, value FROM primitive_values pv
                JOIN lexemes l ON pv.lexeme_id = l.id
                WHERE l.lemma = ? AND pv.value != 0
                AND pv.primitive NOT LIKE 'SYN_%'
                ORDER BY primitive
            """,
                (form,),
            )
            primitives = cursor.fetchall()
            print(f"  {form}: {dict(primitives)}")

    conn.close()


if __name__ == "__main__":
    db_path = "data/lexicon.db"

    print("Step 1: Add gram_features column")
    add_gram_features_column(db_path)

    print("\nStep 2: Instantiate SYN_* dimensions")
    instantiate_syn_dimensions(db_path)

    print("\nStep 3: Populate gram_features for inflected forms")
    populate_gram_features(db_path)

    print("\nStep 4: Verify informational zero principle")
    verify_informational_zero(db_path)
```

---

## Verification Queries

```sql
-- 1. Count words with SYN_* dimensions instantiated
SELECT primitive, COUNT(*) as count
FROM primitive_values
WHERE primitive LIKE 'SYN_%'
GROUP BY primitive
ORDER BY count DESC;

-- 2. Find nouns missing SYN_SUBJ
SELECT l.lemma FROM lexemes l
WHERE l.pos = 'NOUN'
AND NOT EXISTS (
    SELECT 1 FROM primitive_values pv
    WHERE pv.lexeme_id = l.id AND pv.primitive = 'SYN_SUBJ'
)
LIMIT 20;

-- 3. Find verbs missing SYN_PRED
SELECT l.lemma FROM lexemes l
WHERE l.pos = 'VERB'
AND NOT EXISTS (
    SELECT 1 FROM primitive_values pv
    WHERE pv.lexeme_id = l.id AND pv.primitive = 'SYN_PRED'
)
LIMIT 20;

-- 4. Check gram_features populated
SELECT gram_features, COUNT(*) FROM lexemes
WHERE pos = 'VERB'
GROUP BY gram_features
ORDER BY COUNT(*) DESC
LIMIT 10;

-- 5. Verify inflected forms have same semantic primitives
-- (Compare 'run' vs 'ran')
SELECT p1.primitive,
       p1.value as run_val,
       p2.value as ran_val
FROM lexemes l1, lexemes l2
JOIN primitive_values p1 ON l1.id = p1.lexeme_id
LEFT JOIN primitive_values p2 ON l2.id = p2.lexeme_id AND p1.primitive = p2.primitive
WHERE l1.lemma = 'run' AND l2.lemma = 'ran'
AND p1.primitive NOT LIKE 'SYN_%'
AND (p1.value != p2.value OR p2.value IS NULL);
-- Should return empty if correctly encoded
```

---

## Summary: Before vs After

| Aspect | Before | After |
|--------|--------|-------|
| SYN_* dimensions | Not present | Instantiated with 0 for applicable roles |
| gram_features | Not stored | JSON metadata for tense/aspect/etc |
| "ran" vs "run" | May have different primitives | Identical semantic vectors |
| Sentence parsing | Must infer possible roles | O(1) dimension check |
| Inflected forms | Treated as separate words | Share lemma's semantics |
