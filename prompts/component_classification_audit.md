# Component Classification Audit

**Purpose:** Assign ComponentType, OperatorType, and BindingBehavior to all lexemes
**Stage:** 1 (after Data Quality, before Semantic Primitives)

---

## Overview

The GSE three-layer architecture requires every word to be classified:

```python
class ComponentType(Enum):
    ATOMIC = auto()  # Content word: receives operations
    OPERATOR = auto()  # Function word: performs operations
    HYBRID = auto()  # Context-dependent (e.g., "have")
```

This classification determines how words participate in sentence-level parsing and composition.

---

## Component Type Definitions

### ATOMIC (Content Words)

Words that carry semantic content and RECEIVE operations from operators.

**Characteristics:**
- Full semantic primitive encoding
- Can fill argument slots (subject, object, complement)
- Modified by operators (negation, intensity, determiners)

**POS Mapping:**
| POS | Default Type | Notes |
|-----|--------------|-------|
| NOUN | ATOMIC | Always content |
| VERB | ATOMIC or HYBRID | Main verbs = ATOMIC, auxiliaries = HYBRID |
| ADJ | ATOMIC | Always content |
| ADV | ATOMIC or OPERATOR | Content adverbs = ATOMIC, degree modifiers = OPERATOR |

**Examples:**
```
dog, cat, house, tree → ATOMIC (nouns)
run, walk, think, see → ATOMIC (main verbs)
happy, sad, big, small → ATOMIC (adjectives)
quickly, slowly, here, now → ATOMIC (content adverbs)
```

### OPERATOR (Function Words)

Words that PERFORM operations on atomics or other operators.

**Characteristics:**
- Minimal semantic primitives (operationally relevant only)
- Cannot fill argument slots directly
- Modify or connect other words

**Operator Subtypes:**

| Subtype | Function | Binding | Seeks | Examples |
|---------|----------|---------|-------|----------|
| SIGN | Negation/polarity | GREEDY | VERB, ADJ, ADV | not, never, no |
| HIERARCHY | Intensity/degree | GREEDY | ADJ, ADV | very, extremely, barely |
| AUXILIARY | TAM marking | LAZY | VERB only | did, will, have, been |
| DETERMINER | Reference | GREEDY | NOUN, ADJ | the, a, this, every |
| PREPOSITION | Relation | GREEDY | NOUN | in, on, at, by, with |
| CONJUNCTION | Coordination | N/A | Parallel | and, or, but |
| COMPLEMENTIZER | Embedding | N/A | Clause | that, if, whether |

### HYBRID (Context-Dependent)

Words that can be either ATOMIC or OPERATOR depending on context.

**Examples:**
```
have: "I have a dog" (ATOMIC verb) vs "I have eaten" (AUXILIARY)
be: "I am happy" (ATOMIC copula) vs "I am running" (AUXILIARY)
do: "I do work" (ATOMIC verb) vs "Did you go?" (AUXILIARY)
```

---

## Binding Behavior

For OPERATOR words, binding behavior determines argument resolution:

### GREEDY Binding
- Binds to immediately adjacent compatible token
- Processes left-to-right, applies to first match
- Used by: SIGN, HIERARCHY, DETERMINER, PREPOSITION

```
"not very happy"
  → "not" is GREEDY, binds to "very" (or passes sign to it)
  → "very" is GREEDY, binds to "happy"
```

### LAZY Binding
- Waits for specific target type
- May skip intermediate tokens
- Used by: AUXILIARY

```
"He did not run fast"
  → "did" is LAZY, waits for VERB
  → "not" applies to "run" immediately
  → "did" finally binds to "run"
```

---

## Classification Rules

### Rule 1: Closed-Class Words are OPERATOR

```python
CLOSED_CLASS_OPERATORS = {
    # Determiners
    "the",
    "a",
    "an",
    "this",
    "that",
    "these",
    "those",
    "my",
    "your",
    "his",
    "her",
    "its",
    "our",
    "their",
    "some",
    "any",
    "no",
    "every",
    "each",
    "all",
    "both",
    "few",
    "many",
    "much",
    "several",
    "most",
    # Prepositions
    "in",
    "on",
    "at",
    "by",
    "for",
    "with",
    "to",
    "from",
    "of",
    "about",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "over",
    # Conjunctions
    "and",
    "or",
    "but",
    "nor",
    "yet",
    "so",
    "for",
    # Complementizers
    "that",
    "if",
    "whether",
    "because",
    "although",
    "while",
    # Negators
    "not",
    "never",
    "n't",
    # Degree modifiers
    "very",
    "extremely",
    "quite",
    "rather",
    "somewhat",
    "barely",
    "hardly",
    "slightly",
    "highly",
    "totally",
}
```

### Rule 2: Auxiliary Verbs are HYBRID

```python
AUXILIARY_VERBS = {
    # Primary auxiliaries
    "be",
    "am",
    "is",
    "are",
    "was",
    "were",
    "been",
    "being",
    "have",
    "has",
    "had",
    "having",
    "do",
    "does",
    "did",
    "doing",
    # Modal auxiliaries
    "can",
    "could",
    "will",
    "would",
    "shall",
    "should",
    "may",
    "might",
    "must",
}
```

### Rule 3: Content Words are ATOMIC

Any word not in Rules 1-2 defaults to ATOMIC.

### Rule 4: Operator Subtype Assignment

```python
def get_operator_type(lemma: str) -> Optional[str]:
    if lemma in {"not", "never", "no", "n't"}:
        return "SIGN"
    if lemma in {"very", "extremely", "quite", "rather", "barely", "hardly", "slightly", "highly"}:
        return "HIERARCHY"
    if lemma in {"be", "have", "do", "can", "could", "will", "would", "shall", "should", "may", "might", "must"}:
        return "AUXILIARY"
    if lemma in {"the", "a", "an", "this", "that", "some", "any", "every", "each", "all"}:
        return "DETERMINER"
    if lemma in {"in", "on", "at", "by", "for", "with", "to", "from", "of", "about"}:
        return "PREPOSITION"
    if lemma in {"and", "or", "but", "nor"}:
        return "CONJUNCTION"
    if lemma in {"that", "if", "whether", "because", "although"}:
        return "COMPLEMENTIZER"
    return None
```

### Rule 5: Binding Behavior Assignment

```python
def get_binding_behavior(operator_type: str) -> str:
    if operator_type in {"SIGN", "HIERARCHY", "DETERMINER", "PREPOSITION"}:
        return "GREEDY"
    if operator_type == "AUXILIARY":
        return "LAZY"
    return None  # CONJUNCTION, COMPLEMENTIZER don't have directional binding
```

---

## Semantic Primitives for Operators

Operators should have MINIMAL semantic primitives. The operation they perform is encoded in their operator_type, not in primitives.

### SIGN Operators
```sql
-- "not" should have:
NOT=1  -- That's it. No other semantic content.
```

### HIERARCHY Operators
```sql
-- "very" should have:
INTENSITY=1, HIER_PLUS=1  -- Hierarchy encoding only

-- "barely" should have:
INTENSITY=1, HIER_MINUS=2  -- Hierarchy encoding only
```

### AUXILIARY Operators
```sql
-- "did" should have:
-- Minimal or NO semantic primitives
-- Tense information is in gram_features metadata
```

### DETERMINER Operators
```sql
-- "the" might have:
THIS=1, SAME=1  -- Reference/definiteness only

-- "a" might have:
ONE=1  -- Indefinite singular only
```

### PREPOSITION Operators
```sql
-- "in" should have spatial primitives:
INSIDE=1, WHERE=1

-- "on" should have:
ABOVE=1, TOUCH=1, WHERE=1
```

---

## LLM Audit Prompt Template

```
You are classifying words in a semantic lexicon by their grammatical function.

Classification types:
- ATOMIC: Content words (nouns, main verbs, adjectives) that carry meaning
- OPERATOR: Function words that perform operations on other words
- HYBRID: Words that can be either depending on context

For OPERATOR words, also classify:
- SIGN: Negators (not, never, no)
- HIERARCHY: Degree modifiers (very, extremely, barely)
- AUXILIARY: Helping verbs (did, will, have)
- DETERMINER: Articles and demonstratives (the, a, this)
- PREPOSITION: Spatial/relational (in, on, with)
- CONJUNCTION: Connectors (and, or, but)
- COMPLEMENTIZER: Clause markers (that, if, whether)

And binding behavior:
- GREEDY: Binds to immediately adjacent word
- LAZY: Waits for specific target type

Review this word:
Word: {word}
POS: {pos}
Current primitives: {primitives}

Output ONE of:
ATOMIC - this is a content word
OPERATOR:SIGN:GREEDY - negator, binds immediately
OPERATOR:HIERARCHY:GREEDY - degree modifier
OPERATOR:AUXILIARY:LAZY - helping verb, waits for main verb
OPERATOR:DETERMINER:GREEDY - article/demonstrative
OPERATOR:PREPOSITION:GREEDY - relational word
OPERATOR:CONJUNCTION - coordinator
OPERATOR:COMPLEMENTIZER - clause marker
HYBRID:AUXILIARY - can be main verb or auxiliary
```

---

## Audit Queries

### Find words missing component_type
```sql
SELECT lemma, pos FROM lexemes
WHERE component_type IS NULL
ORDER BY frequency_rank
LIMIT 100;
```

### Find OPERATORs missing operator_type
```sql
SELECT lemma, pos FROM lexemes
WHERE component_type = 'OPERATOR'
AND operator_type IS NULL;
```

### Find OPERATORs with too many primitives
```sql
SELECT l.lemma, COUNT(*) as prim_count
FROM lexemes l
JOIN primitive_values pv ON l.id = pv.lexeme_id
WHERE l.component_type = 'OPERATOR'
AND pv.value != 0
GROUP BY l.lemma
HAVING prim_count > 5
ORDER BY prim_count DESC;
```

### Verify auxiliary verbs are HYBRID
```sql
SELECT lemma, component_type
FROM lexemes
WHERE lemma IN ('be', 'have', 'do', 'can', 'will', 'shall', 'may', 'must')
AND component_type != 'HYBRID';
```

---

## Implementation Script

```python
#!/usr/bin/env python3
"""
Component Classification Script
Assigns component_type, operator_type, binding_behavior to all lexemes
"""

import sqlite3
from typing import Optional, Tuple

# Classification lists
SIGN_OPERATORS = {"not", "never", "no", "n't", "neither", "nor"}

HIERARCHY_OPERATORS = {
    "very",
    "extremely",
    "quite",
    "rather",
    "somewhat",
    "barely",
    "hardly",
    "slightly",
    "highly",
    "totally",
    "really",
    "truly",
    "fairly",
    "pretty",
    "incredibly",
    "exceedingly",
    "remarkably",
    "awfully",
    "terribly",
}

AUXILIARY_VERBS = {
    "be",
    "am",
    "is",
    "are",
    "was",
    "were",
    "been",
    "being",
    "have",
    "has",
    "had",
    "having",
    "do",
    "does",
    "did",
    "doing",
    "can",
    "could",
    "will",
    "would",
    "shall",
    "should",
    "may",
    "might",
    "must",
}

DETERMINERS = {
    "the",
    "a",
    "an",
    "this",
    "that",
    "these",
    "those",
    "my",
    "your",
    "his",
    "her",
    "its",
    "our",
    "their",
    "some",
    "any",
    "no",
    "every",
    "each",
    "all",
    "both",
    "few",
    "many",
    "much",
    "several",
    "most",
    "either",
    "neither",
    "another",
    "such",
    "what",
    "which",
    "whose",
}

PREPOSITIONS = {
    "in",
    "on",
    "at",
    "by",
    "for",
    "with",
    "to",
    "from",
    "of",
    "about",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "over",
    "across",
    "against",
    "along",
    "among",
    "around",
    "behind",
    "beneath",
    "beside",
    "beyond",
    "down",
    "inside",
    "near",
    "off",
    "onto",
    "outside",
    "past",
    "toward",
    "towards",
    "up",
    "upon",
    "within",
    "without",
}

CONJUNCTIONS = {"and", "or", "but", "nor", "yet", "so", "for"}

COMPLEMENTIZERS = {
    "that",
    "if",
    "whether",
    "because",
    "although",
    "while",
    "when",
    "where",
    "whereas",
    "unless",
    "until",
    "since",
    "though",
    "as",
}


def classify_word(lemma: str, pos: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Classify a word into component_type, operator_type, binding_behavior.

    Returns: (component_type, operator_type, binding_behavior)
    """
    lemma_lower = lemma.lower()

    # Check SIGN operators first
    if lemma_lower in SIGN_OPERATORS:
        return ("OPERATOR", "SIGN", "GREEDY")

    # Check HIERARCHY operators
    if lemma_lower in HIERARCHY_OPERATORS:
        return ("OPERATOR", "HIERARCHY", "GREEDY")

    # Check auxiliaries - these are HYBRID
    if lemma_lower in AUXILIARY_VERBS:
        return ("HYBRID", "AUXILIARY", "LAZY")

    # Check determiners
    if lemma_lower in DETERMINERS:
        return ("OPERATOR", "DETERMINER", "GREEDY")

    # Check prepositions
    if lemma_lower in PREPOSITIONS:
        return ("OPERATOR", "PREPOSITION", "GREEDY")

    # Check conjunctions
    if lemma_lower in CONJUNCTIONS:
        return ("OPERATOR", "CONJUNCTION", None)

    # Check complementizers
    if lemma_lower in COMPLEMENTIZERS:
        return ("OPERATOR", "COMPLEMENTIZER", None)

    # Default: ATOMIC
    return ("ATOMIC", None, None)


def apply_classifications(db_path: str):
    """Apply component classifications to all lexemes."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Add columns if they don't exist
    try:
        cursor.execute("ALTER TABLE lexemes ADD COLUMN component_type TEXT DEFAULT 'ATOMIC'")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE lexemes ADD COLUMN operator_type TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE lexemes ADD COLUMN binding_behavior TEXT")
    except:
        pass

    # Get all lexemes
    cursor.execute("SELECT id, lemma, pos FROM lexemes")
    rows = cursor.fetchall()

    updated = 0
    for id_, lemma, pos in rows:
        comp_type, op_type, binding = classify_word(lemma, pos or "")

        cursor.execute(
            """
            UPDATE lexemes
            SET component_type = ?,
                operator_type = ?,
                binding_behavior = ?
            WHERE id = ?
        """,
            (comp_type, op_type, binding, id_),
        )
        updated += 1

    conn.commit()
    print(f"Classified {updated} lexemes")

    # Summary
    cursor.execute("""
        SELECT component_type, COUNT(*) FROM lexemes GROUP BY component_type
    """)
    print("\nComponent Type Distribution:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")

    cursor.execute("""
        SELECT operator_type, COUNT(*) FROM lexemes
        WHERE operator_type IS NOT NULL
        GROUP BY operator_type
    """)
    print("\nOperator Type Distribution:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")

    conn.close()


if __name__ == "__main__":
    apply_classifications("data/lexicon.db")
```

---

## Validation Checklist

- [ ] All lexemes have component_type assigned
- [ ] All OPERATOR words have operator_type set
- [ ] SIGN/HIERARCHY/AUXILIARY have binding_behavior set
- [ ] HYBRID words are auxiliaries only
- [ ] OPERATOR words have minimal semantic primitives (≤5)
- [ ] ATOMIC content words have full primitive encoding
