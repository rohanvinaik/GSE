# GSE Lexicon Fix Specification (v4)

## Overview
This document specifies exact fixes to apply to `data/lexicon.db` based on the **Three-Layer Architecture** defined in the GSE system. Fixes are ordered by execution priority.

**Database:** `data/lexicon.db` (SQLite)
**Architecture Document:** `data/system_architecture_dump.md`
**Audit Pipeline:** `prompts/AUDIT_PIPELINE.md`

**Extended Schema:**
```sql
-- lexemes: id, lemma, pos, frequency_rank,
--          component_type, operator_type, binding_behavior, gram_features
-- primitive_values: lexeme_id, primitive, value (-1/0/+1), confidence, source
```

---

## Fix Execution Order

| Priority | Category | Description |
|----------|----------|-------------|
| 0 | Component Classification | ATOMIC/OPERATOR/HYBRID assignment (MUST RUN FIRST) |
| 1 | Function Words | Reset semantic primitives to minimal set |
| 2 | SAY/WORDS Consistency | Fix speech-related semantic constraints |
| 3 | FEEL/Experiencer | Fix subjective experience constraints |
| 4 | Source Disagreements | Apply high-confidence external corrections |
| 5 | Pronouns | Correct person/reference primitives |
| 6 | Modifier Hierarchy | Apply balanced ternary encoding |
| 7 | Informational Zeros | Instantiate SYN_* dimensions |
| 8 | Grammatical Metadata | Add gram_features JSON column |

---

## Fix Category 0: Component Classification (CRITICAL - RUN FIRST)

Every lexeme must be classified by its grammatical function in the three-layer architecture.

### Schema Extension:
```sql
ALTER TABLE lexemes ADD COLUMN component_type TEXT DEFAULT 'ATOMIC';
ALTER TABLE lexemes ADD COLUMN operator_type TEXT;
ALTER TABLE lexemes ADD COLUMN binding_behavior TEXT;
ALTER TABLE lexemes ADD COLUMN gram_features TEXT;  -- JSON
```

### Component Types:
| Type | Description | Examples |
|------|-------------|----------|
| ATOMIC | Content words receiving operations | dog, run, happy, quickly |
| OPERATOR | Function words performing operations | not, very, the, in |
| HYBRID | Context-dependent | have, be, do |

### Classification Rules:

```python
SIGN_OPERATORS = {'not', 'never', 'no', "n't", 'neither', 'nor'}
HIERARCHY_OPERATORS = {
    'very', 'extremely', 'quite', 'rather', 'somewhat',
    'barely', 'hardly', 'slightly', 'highly', 'totally',
    'really', 'truly', 'fairly', 'pretty', 'incredibly',
}
AUXILIARY_VERBS = {
    'be', 'am', 'is', 'are', 'was', 'were', 'been', 'being',
    'have', 'has', 'had', 'having',
    'do', 'does', 'did', 'doing',
    'can', 'could', 'will', 'would', 'shall', 'should',
    'may', 'might', 'must',
}
DETERMINERS = {
    'the', 'a', 'an', 'this', 'that', 'these', 'those',
    'my', 'your', 'his', 'her', 'its', 'our', 'their',
    'some', 'any', 'no', 'every', 'each', 'all', 'both',
}
PREPOSITIONS = {
    'in', 'on', 'at', 'by', 'for', 'with', 'to', 'from',
    'of', 'about', 'into', 'through', 'during', 'before', 'after',
}
CONJUNCTIONS = {'and', 'or', 'but', 'nor', 'yet', 'so'}
COMPLEMENTIZERS = {'that', 'if', 'whether', 'because', 'although', 'while'}
```

### SQL Fix:
```sql
-- SIGN operators
UPDATE lexemes SET component_type = 'OPERATOR', operator_type = 'SIGN', binding_behavior = 'GREEDY'
WHERE lemma IN ('not', 'never', 'no', 'neither', 'nor');

-- HIERARCHY operators
UPDATE lexemes SET component_type = 'OPERATOR', operator_type = 'HIERARCHY', binding_behavior = 'GREEDY'
WHERE lemma IN ('very', 'extremely', 'quite', 'rather', 'somewhat', 'barely', 'hardly', 'slightly', 'highly', 'totally', 'really', 'truly', 'fairly', 'pretty', 'incredibly');

-- HYBRID auxiliaries (can be main verb OR auxiliary)
UPDATE lexemes SET component_type = 'HYBRID', operator_type = 'AUXILIARY', binding_behavior = 'LAZY'
WHERE lemma IN ('be', 'am', 'is', 'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'can', 'could', 'will', 'would', 'shall', 'should', 'may', 'might', 'must');

-- DETERMINER operators
UPDATE lexemes SET component_type = 'OPERATOR', operator_type = 'DETERMINER', binding_behavior = 'GREEDY'
WHERE lemma IN ('the', 'a', 'an', 'this', 'that', 'these', 'those', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'some', 'any', 'every', 'each', 'all', 'both');

-- PREPOSITION operators
UPDATE lexemes SET component_type = 'OPERATOR', operator_type = 'PREPOSITION', binding_behavior = 'GREEDY'
WHERE lemma IN ('in', 'on', 'at', 'by', 'for', 'with', 'to', 'from', 'of', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between', 'under', 'over');

-- CONJUNCTION operators
UPDATE lexemes SET component_type = 'OPERATOR', operator_type = 'CONJUNCTION', binding_behavior = NULL
WHERE lemma IN ('and', 'or', 'but', 'nor', 'yet', 'so');

-- COMPLEMENTIZER operators
UPDATE lexemes SET component_type = 'OPERATOR', operator_type = 'COMPLEMENTIZER', binding_behavior = NULL
WHERE lemma IN ('that', 'if', 'whether', 'because', 'although', 'while', 'when', 'where');

-- Everything else defaults to ATOMIC (already set by DEFAULT)
```

### Verification:
```sql
-- Check component type distribution
SELECT component_type, COUNT(*) FROM lexemes GROUP BY component_type;

-- Verify all OPERATOR words have operator_type set
SELECT lemma FROM lexemes WHERE component_type = 'OPERATOR' AND operator_type IS NULL;

-- Verify SIGN/HIERARCHY/AUXILIARY have binding_behavior
SELECT lemma FROM lexemes
WHERE operator_type IN ('SIGN', 'HIERARCHY', 'AUXILIARY')
AND binding_behavior IS NULL;
```

---

## Fix Category 1: Function Words (CRITICAL)

Function words are grammatical markers with minimal semantic content. They should have 0 or very few active primitives.

### Target Words (Reset ALL primitives to 0):
```
the, of, and, to, a, in, is, that, for, it, with, as, on, at, by, from, or, an, be, this, are, was, were, been, being, have, has, had, not, but, if, which, their, so, what, when, into, than, its, any, no, do, how, up, out, just, about
```

### SQL Fix:
```sql
-- Reset all primitive values for function words to 0
UPDATE primitive_values
SET value = 0, confidence = 0.9, source = 'fix:function_word'
WHERE lexeme_id IN (
    SELECT id FROM lexemes
    WHERE lemma IN ('the', 'of', 'and', 'to', 'a', 'in', 'is', 'that', 'for', 'it',
                    'with', 'as', 'on', 'at', 'by', 'from', 'or', 'an', 'be', 'this',
                    'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had', 'not',
                    'but', 'if', 'which', 'their', 'so', 'what', 'when', 'into', 'than',
                    'its', 'any', 'no', 'do', 'how', 'up', 'out', 'just', 'about')
);
```

### Verification:
```sql
-- Should return 0 for all listed function words
SELECT l.lemma, COUNT(*) as active_count
FROM lexemes l
JOIN primitive_values pv ON l.id = pv.lexeme_id
WHERE l.lemma IN ('the', 'of', 'and', 'to', 'a', 'is', 'that', 'for', 'it', 'with')
AND pv.value != 0
GROUP BY l.lemma;
```

---

## Fix Category 2: SAY=1 False Positives (HIGH)

Many words flagged as SAY=1 without WORDS=1 are actually FALSE POSITIVES for SAY. The word doesn't involve speech/saying at all.

### Fix Strategy:
1. If word genuinely involves speech acts: Set WORDS=1
2. If word does NOT involve speech: Set SAY=0

### Group A - Set SAY=0 (Word doesn't involve speech):
These words were incorrectly marked as SAY=1:
```
you, me, people, life, time, system, being, example, human, social, world, control, something, person, order, love, everything, protein, health, living, water, relationship, sense, feeling, activity, bit, food, air, medicine, hot, reaction, motion, fish, eat, mushroom, caffeine, liquid, consumption, fluid, salt, feed, pleasure, treat
```

### SQL Fix (Group A):
```sql
UPDATE primitive_values
SET value = 0, confidence = 0.8, source = 'fix:say_false_positive'
WHERE primitive = 'SAY'
AND lexeme_id IN (
    SELECT id FROM lexemes
    WHERE lemma IN ('you', 'me', 'people', 'life', 'time', 'system', 'being',
                    'example', 'human', 'social', 'world', 'control', 'something',
                    'person', 'order', 'love', 'everything', 'protein', 'health',
                    'living', 'water', 'relationship', 'sense', 'feeling', 'activity',
                    'bit', 'food', 'air', 'medicine', 'hot', 'reaction', 'motion',
                    'fish', 'eat', 'mushroom', 'caffeine', 'liquid', 'consumption',
                    'fluid', 'salt', 'feed', 'pleasure', 'treat')
);
```

### Group B - Set WORDS=1 (Word genuinely involves speech/language):
```
said, told, word, language, response, communication, expression, teaching, explain, saying, speaking, speech, conversation, ask, answer, describe, introduction, discussion, offer, argument, statement, feedback, storytelling, talking, chat, promise, emphasis, introduce, told, spoke, stated, ordered, conversational, participation, sentence
```

### SQL Fix (Group B):
```sql
UPDATE primitive_values
SET value = 1, confidence = 0.85, source = 'fix:say_requires_words'
WHERE primitive = 'WORDS'
AND lexeme_id IN (
    SELECT id FROM lexemes
    WHERE lemma IN ('said', 'told', 'word', 'language', 'response', 'communication',
                    'expression', 'teaching', 'explain', 'saying', 'speaking', 'speech',
                    'conversation', 'ask', 'answer', 'describe', 'introduction',
                    'discussion', 'offer', 'argument', 'statement', 'feedback',
                    'storytelling', 'talking', 'chat', 'promise', 'emphasis',
                    'introduce', 'spoke', 'stated', 'ordered', 'conversational',
                    'participation', 'sentence')
);
```

---

## Fix Category 3: FEEL=1 False Positives (HIGH)

Many words marked FEEL=1 are abstract concepts or inanimate objects that don't involve subjective experience.

### Fix Strategy:
1. If word genuinely involves subjective experience: Ensure SOMEONE=1 or I=1 or YOU=1
2. If word is abstract/inanimate: Set FEEL=0

### Group A - Set FEEL=0 (Abstract/inanimate, no subjective experience):
```
time, system, structure, theory, energy, network, result, production, resources, quality, war, organization, management, policy, law, school, body, death, past, full, weight, loss, operation, trade, machine, error, music, ground, base, established, period, constant, lines, effort, strength, architecture, exchange, concentration, assembly, statistical, sample, variable, spike, assessment, university, government, economy, budget, differential, mathematical, hypothesis, score, execution, perturbation, mail, sun, fire, electric, phone, birth, frame, title, proof, challenge, abstract nouns
```

### SQL Fix (Group A):
```sql
UPDATE primitive_values
SET value = 0, confidence = 0.8, source = 'fix:feel_false_positive'
WHERE primitive = 'FEEL'
AND lexeme_id IN (
    SELECT id FROM lexemes
    WHERE lemma IN ('time', 'system', 'structure', 'theory', 'energy', 'network',
                    'result', 'production', 'resources', 'quality', 'war',
                    'organization', 'management', 'policy', 'law', 'school',
                    'body', 'death', 'past', 'full', 'weight', 'loss', 'operation',
                    'trade', 'machine', 'error', 'music', 'ground', 'base',
                    'established', 'period', 'constant', 'lines', 'effort',
                    'strength', 'architecture', 'exchange', 'concentration',
                    'assembly', 'statistical', 'sample', 'variable', 'spike',
                    'assessment', 'university', 'government', 'economy', 'budget',
                    'differential', 'mathematical', 'hypothesis', 'score',
                    'execution', 'perturbation', 'mail', 'sun', 'fire', 'electric',
                    'phone', 'birth', 'title', 'proof', 'challenge')
);
```

### Group B - Set SOMEONE=1 (Genuine experiencer words):
Words that correctly have FEEL=1 and need SOMEONE=1:
```
happy, sad, anxious, afraid, angry, jealous, proud, ashamed, guilty, lonely, bored, excited, curious, confused, frustrated, hopeful, grateful, content, satisfied, disappointed, embarrassed, nervous, worried, relaxed, calm, peaceful, joyful, loving, caring, empathetic, emotional, feeling, experienced, aware, conscious, knowing, believing, thinking, wanting, needing, perceiving, sensing, understanding
```

### SQL Fix (Group B):
```sql
UPDATE primitive_values
SET value = 1, confidence = 0.85, source = 'fix:feel_requires_experiencer'
WHERE primitive = 'SOMEONE'
AND lexeme_id IN (
    SELECT id FROM lexemes
    WHERE lemma IN ('happy', 'sad', 'anxious', 'afraid', 'angry', 'jealous',
                    'proud', 'ashamed', 'guilty', 'lonely', 'bored', 'excited',
                    'curious', 'confused', 'frustrated', 'hopeful', 'grateful',
                    'content', 'satisfied', 'disappointed', 'embarrassed',
                    'nervous', 'worried', 'relaxed', 'calm', 'peaceful', 'joyful',
                    'loving', 'caring', 'empathetic', 'emotional', 'feeling',
                    'experienced', 'aware', 'conscious', 'knowing', 'believing',
                    'thinking', 'wanting', 'needing', 'perceiving', 'sensing',
                    'understanding')
)
AND EXISTS (
    SELECT 1 FROM primitive_values pv2
    WHERE pv2.lexeme_id = primitive_values.lexeme_id
    AND pv2.primitive = 'FEEL' AND pv2.value = 1
);
```

---

## Fix Category 4: Source Disagreements - GOOD/NRC-VAD (MEDIUM)

Where NRC-VAD valence strongly indicates positive/negative but GOOD disagrees.

### High-Confidence Positive Words (NRC-VAD valence > 0.7) - Set GOOD=1:
```
life (0.836), birth (0.792), cash (0.734), confidence (0.918), robustness (1.0)
```

### SQL Fix:
```sql
UPDATE primitive_values
SET value = 1, confidence = 0.9, source = 'fix:nrc_vad_positive'
WHERE primitive = 'GOOD'
AND lexeme_id IN (
    SELECT id FROM lexemes
    WHERE lemma IN ('life', 'birth', 'cash', 'confidence', 'robustness')
);
```

---

## Fix Category 5: Pronoun Corrections (HIGH)

Pronouns referring to persons should have SOMEONE=1, not excessive primitives.

### First Person Pronouns - Set I=1, SOMEONE=1:
```
i, me, my, myself, mine
```

### Second Person Pronouns - Set YOU=1, SOMEONE=1:
```
you, your, yourself, yours
```

### Third Person Pronouns - Set SOMEONE=1:
```
he, she, him, her, his, hers, himself, herself, they, them, their, themselves, someone, somebody, anyone, anybody, everyone, everybody, nobody, person, people
```

### SQL Fix (First Person):
```sql
UPDATE primitive_values
SET value = 1, confidence = 0.95, source = 'fix:pronoun_first_person'
WHERE primitive IN ('I', 'SOMEONE')
AND lexeme_id IN (
    SELECT id FROM lexemes
    WHERE lemma IN ('i', 'me', 'my', 'myself', 'mine')
);
```

### SQL Fix (Second Person):
```sql
UPDATE primitive_values
SET value = 1, confidence = 0.95, source = 'fix:pronoun_second_person'
WHERE primitive IN ('YOU', 'SOMEONE')
AND lexeme_id IN (
    SELECT id FROM lexemes
    WHERE lemma IN ('you', 'your', 'yourself', 'yours')
);
```

### SQL Fix (Third Person):
```sql
UPDATE primitive_values
SET value = 1, confidence = 0.9, source = 'fix:pronoun_third_person'
WHERE primitive = 'SOMEONE'
AND lexeme_id IN (
    SELECT id FROM lexemes
    WHERE lemma IN ('he', 'she', 'him', 'her', 'his', 'hers', 'himself', 'herself',
                    'they', 'them', 'their', 'themselves', 'someone', 'somebody',
                    'anyone', 'anybody', 'everyone', 'everybody', 'nobody',
                    'person', 'people')
);
```

---

## Implementation Script

```python
#!/usr/bin/env python3
"""
Lexicon Fix Implementation
Applies fixes specified in lexicon_fixes.md
"""

import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def apply_fixes(db_path: str = "data/lexicon.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Fix 1: Function words - reset all to 0
    FUNCTION_WORDS = [
        'the', 'of', 'and', 'to', 'a', 'in', 'is', 'that', 'for', 'it',
        'with', 'as', 'on', 'at', 'by', 'from', 'or', 'an', 'be', 'this',
        'are', 'was', 'were', 'been', 'being', 'have', 'has', 'had', 'not',
        'but', 'if', 'which', 'their', 'so', 'what', 'when', 'into', 'than',
        'its', 'any', 'no', 'do', 'how', 'up', 'out', 'just', 'about'
    ]

    placeholders = ','.join(['?'] * len(FUNCTION_WORDS))
    cursor.execute(f"""
        UPDATE primitive_values
        SET value = 0, confidence = 0.9, source = 'fix:function_word'
        WHERE lexeme_id IN (
            SELECT id FROM lexemes WHERE lemma IN ({placeholders})
        )
    """, FUNCTION_WORDS)
    logger.info(f"Fix 1: Reset {cursor.rowcount} primitive values for function words")

    # Fix 2a: SAY=0 for false positives
    SAY_FALSE_POSITIVES = [
        'you', 'me', 'people', 'life', 'time', 'system', 'being',
        'example', 'human', 'social', 'world', 'control', 'something',
        'person', 'order', 'love', 'everything', 'protein', 'health',
        'living', 'water', 'relationship', 'sense', 'feeling', 'activity',
        'bit', 'food', 'air', 'medicine', 'hot', 'reaction', 'motion',
        'fish', 'eat', 'mushroom', 'caffeine', 'liquid', 'consumption',
        'fluid', 'salt', 'feed', 'pleasure', 'treat'
    ]

    placeholders = ','.join(['?'] * len(SAY_FALSE_POSITIVES))
    cursor.execute(f"""
        UPDATE primitive_values
        SET value = 0, confidence = 0.8, source = 'fix:say_false_positive'
        WHERE primitive = 'SAY'
        AND lexeme_id IN (
            SELECT id FROM lexemes WHERE lemma IN ({placeholders})
        )
    """, SAY_FALSE_POSITIVES)
    logger.info(f"Fix 2a: Set SAY=0 for {cursor.rowcount} false positives")

    # Fix 2b: WORDS=1 for speech-related words with SAY=1
    SPEECH_WORDS = [
        'said', 'told', 'word', 'language', 'response', 'communication',
        'expression', 'teaching', 'explain', 'saying', 'speaking', 'speech',
        'conversation', 'ask', 'answer', 'describe', 'introduction',
        'discussion', 'offer', 'argument', 'statement', 'feedback',
        'storytelling', 'talking', 'chat', 'promise', 'emphasis',
        'introduce', 'spoke', 'stated', 'ordered', 'conversational',
        'participation', 'sentence'
    ]

    placeholders = ','.join(['?'] * len(SPEECH_WORDS))
    cursor.execute(f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'WORDS', 1, 0.85, 'fix:say_requires_words'
        FROM lexemes WHERE lemma IN ({placeholders})
    """, SPEECH_WORDS)
    logger.info(f"Fix 2b: Set WORDS=1 for {cursor.rowcount} speech-related words")

    # Fix 3: FEEL=0 for abstract/inanimate
    FEEL_FALSE_POSITIVES = [
        'time', 'system', 'structure', 'theory', 'energy', 'network',
        'result', 'production', 'resources', 'quality', 'war',
        'organization', 'management', 'policy', 'law', 'school',
        'body', 'death', 'past', 'full', 'weight', 'loss', 'operation',
        'trade', 'machine', 'error', 'music', 'ground', 'base',
        'established', 'period', 'constant', 'lines', 'effort',
        'strength', 'architecture', 'exchange', 'concentration',
        'assembly', 'statistical', 'sample', 'variable', 'spike',
        'assessment', 'university', 'government', 'economy', 'budget',
        'differential', 'mathematical', 'hypothesis', 'score',
        'execution', 'perturbation', 'mail', 'sun', 'fire', 'electric',
        'phone', 'birth', 'title', 'proof', 'challenge'
    ]

    placeholders = ','.join(['?'] * len(FEEL_FALSE_POSITIVES))
    cursor.execute(f"""
        UPDATE primitive_values
        SET value = 0, confidence = 0.8, source = 'fix:feel_false_positive'
        WHERE primitive = 'FEEL'
        AND lexeme_id IN (
            SELECT id FROM lexemes WHERE lemma IN ({placeholders})
        )
    """, FEEL_FALSE_POSITIVES)
    logger.info(f"Fix 3: Set FEEL=0 for {cursor.rowcount} abstract/inanimate words")

    # Fix 4: GOOD=1 for high-valence words
    HIGH_VALENCE = ['life', 'birth', 'cash', 'confidence', 'robustness']

    placeholders = ','.join(['?'] * len(HIGH_VALENCE))
    cursor.execute(f"""
        UPDATE primitive_values
        SET value = 1, confidence = 0.9, source = 'fix:nrc_vad_positive'
        WHERE primitive = 'GOOD'
        AND lexeme_id IN (
            SELECT id FROM lexemes WHERE lemma IN ({placeholders})
        )
    """, HIGH_VALENCE)
    logger.info(f"Fix 4: Set GOOD=1 for {cursor.rowcount} high-valence words")

    # Fix 5: Pronoun fixes
    # First person: I=1, SOMEONE=1
    cursor.execute("""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'I', 1, 0.95, 'fix:pronoun_first_person'
        FROM lexemes WHERE lemma IN ('i', 'me', 'my', 'myself', 'mine')
    """)
    cursor.execute("""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'SOMEONE', 1, 0.95, 'fix:pronoun_first_person'
        FROM lexemes WHERE lemma IN ('i', 'me', 'my', 'myself', 'mine')
    """)
    logger.info("Fix 5a: Set I=1, SOMEONE=1 for first person pronouns")

    # Second person: YOU=1, SOMEONE=1
    cursor.execute("""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'YOU', 1, 0.95, 'fix:pronoun_second_person'
        FROM lexemes WHERE lemma IN ('you', 'your', 'yourself', 'yours')
    """)
    cursor.execute("""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'SOMEONE', 1, 0.95, 'fix:pronoun_second_person'
        FROM lexemes WHERE lemma IN ('you', 'your', 'yourself', 'yours')
    """)
    logger.info("Fix 5b: Set YOU=1, SOMEONE=1 for second person pronouns")

    # Third person: SOMEONE=1
    THIRD_PERSON = [
        'he', 'she', 'him', 'her', 'his', 'hers', 'himself', 'herself',
        'they', 'them', 'their', 'themselves', 'someone', 'somebody',
        'anyone', 'anybody', 'everyone', 'everybody', 'nobody',
        'person', 'people'
    ]
    placeholders = ','.join(['?'] * len(THIRD_PERSON))
    cursor.execute(f"""
        INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
        SELECT id, 'SOMEONE', 1, 0.9, 'fix:pronoun_third_person'
        FROM lexemes WHERE lemma IN ({placeholders})
    """, THIRD_PERSON)
    logger.info(f"Fix 5c: Set SOMEONE=1 for third person pronouns")

    # Fix 6: Modifier Hierarchy Encoding
    # Load external ground truth for correct encoding
    try:
        import sys
        sys.path.insert(0, '.')
        from scripts.load_intensity_ground_truth import get_modifier_ground_truth
        gt = get_modifier_ground_truth()

        for word, entry in gt.modifiers.items():
            # Get lexeme ID
            cursor.execute("SELECT id FROM lexemes WHERE lemma = ?", (word,))
            row = cursor.fetchone()
            if not row:
                continue
            lex_id = row[0]

            # Set base primitive to +1 (always)
            cursor.execute("""
                INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                VALUES (?, ?, 1, 0.9, 'fix:modifier_hierarchy')
            """, (lex_id, entry.hierarchy_type))

            # Set HIER_PLUS if positive level
            if entry.level > 0:
                cursor.execute("""
                    INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, 'HIER_PLUS', ?, 0.9, 'fix:modifier_hierarchy')
                """, (lex_id, entry.level))
                # Ensure HIER_MINUS is 0
                cursor.execute("""
                    INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, 'HIER_MINUS', 0, 0.9, 'fix:modifier_hierarchy')
                """, (lex_id,))

            # Set HIER_MINUS if negative level
            elif entry.level < 0:
                cursor.execute("""
                    INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, 'HIER_MINUS', ?, 0.9, 'fix:modifier_hierarchy')
                """, (lex_id, abs(entry.level)))
                # Ensure HIER_PLUS is 0
                cursor.execute("""
                    INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, 'HIER_PLUS', 0, 0.9, 'fix:modifier_hierarchy')
                """, (lex_id,))

            # Level 0: No HIER markers
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, 'HIER_PLUS', 0, 0.9, 'fix:modifier_hierarchy')
                """, (lex_id,))
                cursor.execute("""
                    INSERT OR REPLACE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
                    VALUES (?, 'HIER_MINUS', 0, 0.9, 'fix:modifier_hierarchy')
                """, (lex_id,))

        logger.info(f"Fix 6: Applied modifier hierarchy encoding to {len(gt.modifiers)} words")
    except ImportError:
        logger.warning("Fix 6: Skipped - ground truth loader not available")

    conn.commit()

    # Summary
    cursor.execute("SELECT COUNT(DISTINCT lexeme_id) FROM primitive_values WHERE source LIKE 'fix:%'")
    fixed_words = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM primitive_values WHERE source LIKE 'fix:%'")
    fixed_values = cursor.fetchone()[0]

    logger.info(f"\n{'='*50}")
    logger.info(f"FIXES APPLIED")
    logger.info(f"{'='*50}")
    logger.info(f"Words affected: {fixed_words}")
    logger.info(f"Primitive values modified: {fixed_values}")

    conn.close()

if __name__ == "__main__":
    apply_fixes()
```

---

## Fix Category 7: Informational Zero Instantiation (NEW)

**Principle:** SYN_* dimensions should be INSTANTIATED WITH 0 for words that CAN play grammatical roles, rather than left NULL.

- `0` = "Dimension applicable but currently inactive" (explicit orthogonality)
- `NULL/blank` = "Dimension not applicable to this word"

This enables O(1) sentence parsing via pre-computed dimension masks.

### POS → SYN_* Mapping:

| POS | Dimensions to Instantiate |
|-----|---------------------------|
| NOUN | SYN_SUBJ=0, SYN_OBJ=0, SYN_COMPL=0 |
| PRON | SYN_SUBJ=0, SYN_OBJ=0, SYN_COMPL=0 |
| VERB | SYN_PRED=0 |
| ADJ | SYN_ADJ_MOD=0, SYN_COMPL=0 |
| ADV | SYN_ADV_MOD=0 |
| DET | SYN_DET=0 |

### SQL Fix:
```sql
-- Nouns can be subjects, objects, or complements
INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_SUBJ', 0, 0.95, 'fix:informational_zero'
FROM lexemes WHERE pos IN ('NOUN', 'NN', 'NNS', 'NNP', 'NNPS');

INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_OBJ', 0, 0.95, 'fix:informational_zero'
FROM lexemes WHERE pos IN ('NOUN', 'NN', 'NNS', 'NNP', 'NNPS');

INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_COMPL', 0, 0.95, 'fix:informational_zero'
FROM lexemes WHERE pos IN ('NOUN', 'NN', 'NNS', 'NNP', 'NNPS');

-- Pronouns can be subjects, objects, or complements
INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_SUBJ', 0, 0.95, 'fix:informational_zero'
FROM lexemes WHERE pos IN ('PRON', 'PRP', 'PRP$', 'WP', 'WP$');

INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_OBJ', 0, 0.95, 'fix:informational_zero'
FROM lexemes WHERE pos IN ('PRON', 'PRP', 'PRP$', 'WP', 'WP$');

INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_COMPL', 0, 0.95, 'fix:informational_zero'
FROM lexemes WHERE pos IN ('PRON', 'PRP', 'PRP$', 'WP', 'WP$');

-- Verbs can be predicates
INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_PRED', 0, 0.95, 'fix:informational_zero'
FROM lexemes WHERE pos IN ('VERB', 'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ');

-- Adjectives can be modifiers or complements
INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_ADJ_MOD', 0, 0.95, 'fix:informational_zero'
FROM lexemes WHERE pos IN ('ADJ', 'JJ', 'JJR', 'JJS');

INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_COMPL', 0, 0.95, 'fix:informational_zero'
FROM lexemes WHERE pos IN ('ADJ', 'JJ', 'JJR', 'JJS');

-- Adverbs can be modifiers
INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_ADV_MOD', 0, 0.95, 'fix:informational_zero'
FROM lexemes WHERE pos IN ('ADV', 'RB', 'RBR', 'RBS');

-- Determiners
INSERT OR IGNORE INTO primitive_values (lexeme_id, primitive, value, confidence, source)
SELECT id, 'SYN_DET', 0, 0.95, 'fix:informational_zero'
FROM lexemes WHERE pos IN ('DET', 'DT', 'PDT', 'WDT');
```

### Verification:
```sql
-- Verify nouns have SYN_SUBJ instantiated
SELECT l.lemma, l.pos
FROM lexemes l
WHERE l.pos IN ('NOUN', 'NN', 'NNS')
AND NOT EXISTS (
    SELECT 1 FROM primitive_values pv
    WHERE pv.lexeme_id = l.id AND pv.primitive = 'SYN_SUBJ'
)
LIMIT 20;
-- Expected: Empty result set after fix

-- Check SYN_* dimension distribution
SELECT primitive, COUNT(*) as count
FROM primitive_values
WHERE primitive LIKE 'SYN_%'
GROUP BY primitive;
```

---

## Fix Category 8: Grammatical Metadata (NEW)

**Principle:** Tense, aspect, mood, person, number are METADATA stored in `gram_features` JSON, NOT as vector dimensions.

This ensures: `semantic_similarity("ran", "run") == 1.0`

### gram_features Schema:
```json
{
    "tense": "PAST|PRESENT|FUTURE",
    "aspect": "SIMPLE|PROGRESSIVE|PERFECT",
    "mood": "INDICATIVE|SUBJUNCTIVE|IMPERATIVE",
    "person": 1|2|3,
    "number": "SINGULAR|PLURAL",
    "case": "NOM|ACC|GEN|DAT"
}
```

### SQL Fix (for inflected forms):
```sql
-- Past tense verbs
UPDATE lexemes SET gram_features = '{"tense": "PAST"}'
WHERE pos IN ('VBD') AND gram_features IS NULL;

-- Present participles (progressive aspect)
UPDATE lexemes SET gram_features = '{"aspect": "PROGRESSIVE"}'
WHERE pos IN ('VBG') AND gram_features IS NULL;

-- Past participles (perfect aspect)
UPDATE lexemes SET gram_features = '{"aspect": "PERFECT"}'
WHERE pos IN ('VBN') AND gram_features IS NULL;

-- Third person singular present
UPDATE lexemes SET gram_features = '{"tense": "PRESENT", "person": 3, "number": "SINGULAR"}'
WHERE pos IN ('VBZ') AND gram_features IS NULL;

-- Plural nouns
UPDATE lexemes SET gram_features = '{"number": "PLURAL"}'
WHERE pos IN ('NNS', 'NNPS') AND gram_features IS NULL;
```

### Verification:
```sql
-- Check gram_features distribution
SELECT gram_features, COUNT(*) FROM lexemes
WHERE gram_features IS NOT NULL
GROUP BY gram_features;

-- Verify verb forms have appropriate features
SELECT lemma, pos, gram_features FROM lexemes
WHERE lemma IN ('run', 'ran', 'running', 'runs')
ORDER BY lemma;
```

---

## Verification Queries

After applying fixes, run these verification queries:

```sql
-- 1. Verify function words have 0 active primitives
SELECT l.lemma, COUNT(*) as active
FROM lexemes l
JOIN primitive_values pv ON l.id = pv.lexeme_id
WHERE l.lemma IN ('the', 'of', 'and', 'to', 'a', 'is')
AND pv.value != 0
GROUP BY l.lemma;
-- Expected: Empty result set

-- 2. Verify no SAY=1 without WORDS for speech words
SELECT l.lemma, say.value as say_val, words.value as words_val
FROM lexemes l
JOIN primitive_values say ON l.id = say.lexeme_id AND say.primitive = 'SAY'
LEFT JOIN primitive_values words ON l.id = words.lexeme_id AND words.primitive = 'WORDS'
WHERE say.value = 1 AND (words.value IS NULL OR words.value = 0)
AND l.lemma IN ('said', 'told', 'speak', 'conversation', 'speech')
LIMIT 10;
-- Expected: Empty result set

-- 3. Verify pronouns have correct primitives
SELECT l.lemma, p.primitive, p.value
FROM lexemes l
JOIN primitive_values p ON l.id = p.lexeme_id
WHERE l.lemma IN ('i', 'me', 'you', 'he', 'she')
AND p.primitive IN ('I', 'YOU', 'SOMEONE')
ORDER BY l.lemma, p.primitive;

-- 4. Count fixes by source
SELECT source, COUNT(*) as count
FROM primitive_values
WHERE source LIKE 'fix:%'
GROUP BY source
ORDER BY count DESC;

-- 5. Verify modifier hierarchy encoding
SELECT l.lemma,
       i.value as INTENSITY,
       q.value as QUANTITY,
       c.value as CERTAINTY,
       hp.value as HIER_PLUS,
       hm.value as HIER_MINUS
FROM lexemes l
LEFT JOIN primitive_values i ON l.id = i.lexeme_id AND i.primitive = 'INTENSITY'
LEFT JOIN primitive_values q ON l.id = q.lexeme_id AND q.primitive = 'QUANTITY'
LEFT JOIN primitive_values c ON l.id = c.lexeme_id AND c.primitive = 'CERTAINTY'
LEFT JOIN primitive_values hp ON l.id = hp.lexeme_id AND hp.primitive = 'HIER_PLUS'
LEFT JOIN primitive_values hm ON l.id = hm.lexeme_id AND hm.primitive = 'HIER_MINUS'
WHERE l.lemma IN ('very', 'extremely', 'barely', 'many', 'few', 'likely', 'impossible');
-- Expected: very=(INTENSITY=1, HIER_PLUS=1), extremely=(INTENSITY=1, HIER_PLUS=2), etc.
```

---

## Rollback (if needed)

```sql
-- Remove all fixes applied by this script
DELETE FROM primitive_values WHERE source LIKE 'fix:%';

-- Note: This will leave gaps. Re-run prepopulate and gap_filler to restore.
```
