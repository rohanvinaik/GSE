# GSE Lexicon Audit V3: Data Quality & Encoding

**Scope:** All lexemes in database
**Mode:** AUDIT ONLY - no modifications

## Overview

This audit identifies data quality issues in the lexicon: spelling errors, abbreviations, inflected forms, contractions, encoding problems, and other anomalies that reduce lexicon quality.

## Files

**Main database:** `data/lexicon.db` (SQLite)
**Schema:**
```sql
-- lexemes: id, lemma, pos, frequency_rank
-- primitive_values: lexeme_id, primitive, value (-1/0/+1), confidence, source
```

---

## Part 1: Spelling & Typo Detection

### 1.1 Non-Dictionary Words

Use a spell checker to identify entries that aren't valid English words:

```python
from spellchecker import SpellChecker

spell = SpellChecker()

# Get all lemmas
lemmas = [row[0] for row in cursor.execute("SELECT lemma FROM lexemes")]

# Find misspelled words
misspelled = spell.unknown(lemmas)
```

**Flag categories:**
- **Typos:** Words with edit distance 1-2 from valid words
- **Non-words:** No close dictionary match
- **Domain-specific:** Technical terms not in standard dictionary

### 1.2 Common Typo Patterns

Search for patterns indicating data entry errors:

| Pattern | Example | Issue |
|---------|---------|-------|
| Double letters | `commmon`, `deffinitely` | Extra letter |
| Missing letters | `defintion`, `recieve` | Missing letter |
| Transposed letters | `teh`, `hte` | Adjacent swap |
| Wrong vowel | `definately`, `seperate` | Vowel confusion |

```sql
-- Find potential typos by checking words similar to high-frequency words
SELECT l1.lemma as potential_typo, l2.lemma as likely_correct, l1.frequency_rank
FROM lexemes l1, lexemes l2
WHERE l1.frequency_rank > 5000
  AND l2.frequency_rank < 1000
  AND LENGTH(l1.lemma) = LENGTH(l2.lemma)
  AND l1.lemma != l2.lemma
  -- Check for 1-char difference (simplified check)
```

### 1.3 Spell Correction Suggestions

For each flagged word, provide:
- Original word
- Suggested correction(s)
- Edit distance
- Confidence score

---

## Part 2: Abbreviations & Acronyms

### 2.1 Abbreviation Detection

Identify abbreviated forms that should map to full words:

**Pattern-based detection:**
```python
import re

# Common abbreviation patterns
ABBREV_PATTERNS = [
    r"^[a-z]{1,3}$",  # Very short (mm, kg, etc)
    r"^[A-Z]{2,5}$",  # All caps acronyms (NASA, FBI)
    r"^[A-Z][a-z]*\.$",  # Ends with period (Dr., Mr.)
    r"^[a-z]+\.$",  # Lowercase with period (etc., vs.)
    r"^\d+[a-z]+$",  # Number+letter (3D, 2nd)
]
```

**Common abbreviation categories:**

| Category | Examples | Should Map To |
|----------|----------|---------------|
| Units | mm, cm, kg, lb, oz | millimeter, centimeter, kilogram, pound, ounce |
| Titles | dr, mr, mrs, ms, prof | doctor, mister, missus, miss, professor |
| Latin | etc, ie, eg, vs, et | et cetera, id est, exempli gratia, versus |
| Technical | api, url, html, cpu | application programming interface, ... |
| Time | hr, min, sec, yr, mo | hour, minute, second, year, month |

### 2.2 Acronym Expansion

Flag all-caps entries:
```sql
SELECT lemma, frequency_rank
FROM lexemes
WHERE lemma = UPPER(lemma)
  AND LENGTH(lemma) >= 2
ORDER BY frequency_rank;
```

### 2.3 Abbreviation-Full Form Pairs

Check if both abbreviated and full forms exist:
```sql
-- Find cases where we have both "dr" and "doctor"
SELECT a.lemma as abbrev, f.lemma as full_form
FROM lexemes a, lexemes f
WHERE (a.lemma = 'dr' AND f.lemma = 'doctor')
   OR (a.lemma = 'mr' AND f.lemma = 'mister')
   -- ... extend for known pairs
```

---

## Part 3: Inflection & Morphological Issues

### 3.1 Plural/Singular Duplicates

Identify words where both singular and plural forms exist:

```python
import nltk
from nltk.stem import WordNetLemmatizer

lemmatizer = WordNetLemmatizer()

# Common plural patterns
PLURAL_PATTERNS = [
    (r"(.+)s$", r"\1"),  # cats -> cat
    (r"(.+)es$", r"\1"),  # boxes -> box
    (r"(.+)ies$", r"\1y"),  # cities -> city
    (r"(.+)ves$", r"\1f"),  # wolves -> wolf
    (r"(.+)men$", r"\1man"),  # women -> woman
]


def get_singular(word):
    lemma = lemmatizer.lemmatize(word, "n")
    return lemma if lemma != word else None
```

**Flag pairs:**
| Plural | Singular | Action |
|--------|----------|--------|
| cats | cat | Merge primitives |
| children | child | Keep separate (irregular) |
| data | datum | Keep separate (domain-specific) |

### 3.2 Verb Conjugation Duplicates

Check for multiple verb forms:

```python
# Verb inflection patterns
VERB_FORMS = {
    "base": "",  # run
    "third_person": "s",  # runs
    "past": "ed",  # ran (irregular)
    "gerund": "ing",  # running
    "past_part": "ed",  # run (irregular)
}


def get_verb_base(word):
    return lemmatizer.lemmatize(word, "v")
```

**Flag groups:**
| Forms Present | Base | Action |
|---------------|------|--------|
| run, runs, running, ran | run | Consolidate |
| go, goes, going, went, gone | go | Keep base only |

### 3.3 Adjective/Adverb Forms

Check for related forms:
- quick / quickly (adj/adv)
- happy / happier / happiest (comparative/superlative)
- good / better / best (irregular)

### 3.4 Derivational Morphology

Flag word families that might need consolidation:

| Root | Derived Forms | Issue |
|------|---------------|-------|
| happy | unhappy, happiness, happily | Should share core primitives |
| create | creation, creative, creator | May have different primitives |

---

## Part 4: Contractions

### 4.1 Contraction Detection

```python
CONTRACTIONS = {
    "n't": " not",
    "'re": " are",
    "'ve": " have",
    "'ll": " will",
    "'d": " would",  # or "had"
    "'m": " am",
    "'s": " is",  # or possessive
}

COMMON_CONTRACTIONS = [
    ("don't", "do not"),
    ("can't", "cannot"),
    ("won't", "will not"),
    ("isn't", "is not"),
    ("aren't", "are not"),
    ("wasn't", "was not"),
    ("weren't", "were not"),
    ("haven't", "have not"),
    ("hasn't", "has not"),
    ("hadn't", "had not"),
    ("couldn't", "could not"),
    ("wouldn't", "would not"),
    ("shouldn't", "should not"),
    ("i'm", "i am"),
    ("you're", "you are"),
    ("we're", "we are"),
    ("they're", "they are"),
    ("i've", "i have"),
    ("you've", "you have"),
    ("we've", "we have"),
    ("they've", "they have"),
    ("i'll", "i will"),
    ("you'll", "you will"),
    ("he'll", "he will"),
    ("she'll", "she will"),
    ("we'll", "we will"),
    ("they'll", "they will"),
    ("i'd", "i would"),
    ("you'd", "you would"),
    ("he'd", "he would"),
    ("she'd", "she would"),
    ("we'd", "we would"),
    ("they'd", "they would"),
    ("let's", "let us"),
    ("that's", "that is"),
    ("what's", "what is"),
    ("here's", "here is"),
    ("there's", "there is"),
    ("who's", "who is"),
    ("it's", "it is"),
]
```

```sql
-- Find contractions in database
SELECT lemma, frequency_rank
FROM lexemes
WHERE lemma LIKE '%''%'
   OR lemma LIKE '%n''t%'
ORDER BY frequency_rank;
```

### 4.2 Contraction Handling Strategy

| Contraction | Components | Recommendation |
|-------------|------------|----------------|
| don't | do + not | Remove, use components |
| it's | it + is | Remove, use components |
| let's | let + us | Keep (idiomatic) |

---

## Part 5: Encoding & Character Issues

### 5.1 Non-ASCII Characters

```sql
-- Find entries with non-ASCII characters
SELECT lemma, frequency_rank, HEX(lemma)
FROM lexemes
WHERE lemma != CAST(lemma AS TEXT)
   OR lemma GLOB '*[^a-zA-Z0-9_-]*';
```

**Issue categories:**
- Unicode quotes: ' ' " " vs ' "
- Accented characters: café, naïve, résumé
- Special symbols: ©, ®, ™
- Zero-width characters
- En/em dashes: – —

### 5.2 Encoding Normalization

```python
import unicodedata


def normalize_text(text):
    # Normalize to NFC form
    text = unicodedata.normalize("NFC", text)
    # Remove accents (optional)
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return text
```

### 5.3 Whitespace Issues

```sql
-- Find entries with leading/trailing whitespace
SELECT lemma, LENGTH(lemma), LENGTH(TRIM(lemma))
FROM lexemes
WHERE lemma != TRIM(lemma);

-- Find entries with internal whitespace (phrases, not words)
SELECT lemma, frequency_rank
FROM lexemes
WHERE lemma LIKE '% %';
```

---

## Part 6: Non-Word Entries

### 6.1 Single Characters

```sql
SELECT lemma, frequency_rank
FROM lexemes
WHERE LENGTH(lemma) = 1
ORDER BY frequency_rank;
```

**Valid single chars:** a, I (pronoun)
**Invalid:** b, c, d, ... (unless specific meaning)

### 6.2 Numbers & Numeric Entries

```sql
-- Pure numbers
SELECT lemma FROM lexemes WHERE lemma GLOB '[0-9]*';

-- Mixed alphanumeric
SELECT lemma FROM lexemes WHERE lemma GLOB '*[0-9]*';
```

| Entry | Type | Action |
|-------|------|--------|
| 1, 2, 3 | Pure number | Remove or keep for "one", "two" |
| 1st, 2nd | Ordinal | Map to "first", "second" |
| 3D | Technical | Keep |
| covid19 | Compound | Normalize to "covid-19" |

### 6.3 Punctuation-Only Entries

```sql
SELECT lemma FROM lexemes
WHERE lemma GLOB '[^a-zA-Z0-9]*';
```

### 6.4 Empty or Null Entries

```sql
SELECT id, lemma FROM lexemes
WHERE lemma IS NULL OR lemma = '' OR TRIM(lemma) = '';
```

---

## Part 7: Proper Nouns & Named Entities

### 7.1 Capitalized Entries

```sql
SELECT lemma, pos, frequency_rank
FROM lexemes
WHERE lemma GLOB '[A-Z]*'
  AND LENGTH(lemma) > 1
ORDER BY frequency_rank;
```

**Categories:**
- Personal names: John, Mary, Michael
- Place names: London, Paris, America
- Organization names: Google, Microsoft, NASA
- Brand names: iPhone, PlayStation

### 7.2 Proper Noun Handling

Proper nouns typically should:
- Have SOMEONE=1 (for people)
- Have minimal other primitives
- NOT have GOOD/BAD evaluations (neutral)

```sql
-- Check if proper nouns have appropriate primitives
SELECT l.lemma, GROUP_CONCAT(pv.primitive || '=' || pv.value)
FROM lexemes l
JOIN primitive_values pv ON l.id = pv.lexeme_id
WHERE l.lemma GLOB '[A-Z]*'
  AND pv.value != 0
GROUP BY l.id
HAVING COUNT(*) > 5;  -- Too many primitives for a name
```

---

## Part 8: Compound Words & Phrases

### 8.1 Multi-Word Entries

```sql
SELECT lemma, frequency_rank
FROM lexemes
WHERE lemma LIKE '% %'
   OR lemma LIKE '%-%'
   OR lemma LIKE '%_%'
ORDER BY frequency_rank;
```

**Types:**
| Entry | Type | Recommendation |
|-------|------|----------------|
| ice cream | Space-separated | Keep or hyphenate |
| well-known | Hyphenated | Keep |
| self_aware | Underscore | Normalize to hyphen |
| cannot | Closed compound | Keep |

### 8.2 Consistency Check

Ensure compound forms are consistent:
```sql
-- Check for variant forms of same compound
SELECT * FROM lexemes
WHERE lemma IN ('ice cream', 'ice-cream', 'icecream');
```

---

## Part 9: Homonym & Polysemy Handling

### 9.1 Homonym Detection

Homonyms are words spelled the same but with different meanings requiring different primitive encodings.

**Detection strategies:**

```python
# Words with conflicting primitive signals may be homonyms
# E.g., "bank" (financial) vs "bank" (river) should have different encodings

# Check for words with unusual primitive combinations
cursor.execute("""
    SELECT l.lemma, GROUP_CONCAT(pv.primitive || '=' || pv.value)
    FROM lexemes l
    JOIN primitive_values pv ON l.id = pv.lexeme_id
    WHERE pv.value != 0
    GROUP BY l.id
    HAVING
        -- Has both MONEY-related and NATURE-related primitives
        (primitives LIKE '%HAVE%' AND primitives LIKE '%WATER%')
        -- Has both BODY and abstract THINK
        OR (primitives LIKE '%BODY%' AND primitives LIKE '%THINK%')
""")
```

**Common homonym categories:**

| Word | Sense 1 | Primitives | Sense 2 | Primitives |
|------|---------|------------|---------|------------|
| bank | financial institution | HAVE, MONEY, PLACE | river edge | WATER, SIDE, PLACE |
| bat | animal | ALIVE, MOVE, BODY | sports equipment | SOMETHING, DO, BODY |
| bear | animal | ALIVE, MOVE, BIG | carry/endure | DO, HAVE, FEEL |
| light | illumination | SEE, EXIST | not heavy | BIG=-1, BODY |
| spring | season | WHEN, START | water source | WATER, PLACE | coil | SOMETHING, MOVE |
| run | move quickly | MOVE, DO, BODY | manage | DO, THINK, PEOPLE |
| play | recreation | DO, GOOD, FEEL | theater | SAY, WORDS, SEE |
| right | correct | TRUE, GOOD | direction | SIDE, TOWARD |
| left | departed | MOVE, AWAY | direction | SIDE |
| mean | intend | THINK, WANT | unkind | BAD, FEEL |
| ring | jewelry | SOMETHING, BODY | sound | HEAR |
| wave | ocean | WATER, MOVE | gesture | BODY, DO, SAY |
| match | competition | DO, SAME | fire starter | SOMETHING, CHANGE |
| date | calendar | WHEN, NOW | romantic | SOMEONE, WITH, GOOD |
| tire | exhaustion | FEEL, BODY | wheel | SOMETHING, MOVE |
| pound | weight | QUANTITY, BIG | hit | DO, BODY | currency | HAVE |
| saw | past tense see | SEE, BEFORE | cutting tool | SOMETHING, DO |
| well | healthy | GOOD, BODY, ALIVE | water source | WATER, PLACE |
| fair | just | GOOD, SAME | event | PLACE, PEOPLE |
| kind | type | KIND, SAME | compassionate | GOOD, FEEL, SOMEONE |

### 9.2 Recommended Schema for Homonyms

Allow duplicate lemma entries with different sense IDs:

```sql
-- Current schema (problematic for homonyms)
-- lexemes: id, lemma, pos, frequency_rank

-- Recommended extended schema
-- lexemes: id, lemma, pos, frequency_rank, sense_id, gloss
-- Where sense_id distinguishes homonyms:
--   bank.1 = "financial institution"
--   bank.2 = "edge of river"
```

### 9.3 Homonym Audit Checklist

For each potential homonym:

1. **Identify senses:** List distinct meanings from dictionary
2. **Check current encoding:** Does it conflate multiple senses?
3. **Assess frequency:** Which sense is most common in corpus?
4. **Primitive conflict:** Do primitives contradict each other?
5. **Recommend action:**
   - KEEP: Single dominant sense, others rare
   - SPLIT: Multiple common senses with different primitives
   - FLAG: Uncertain, needs human review

### 9.4 Automated Homonym Flagging

```python
# Flag words that appear in multiple WordNet synsets with very different hypernyms
from nltk.corpus import wordnet as wn


def get_homonym_candidates(lemmas):
    candidates = []
    for lemma in lemmas:
        synsets = wn.synsets(lemma)
        if len(synsets) >= 3:
            # Check if synsets have different top-level hypernyms
            top_hypernyms = set()
            for syn in synsets[:5]:
                hyper = syn.hypernyms()
                if hyper:
                    # Get root hypernym
                    root = hyper[0].hypernyms()
                    top_hypernyms.add(root[0].name() if root else hyper[0].name())

            if len(top_hypernyms) >= 2:
                candidates.append({"word": lemma, "synset_count": len(synsets), "top_hypernyms": list(top_hypernyms)})
    return candidates
```

### 9.5 Polysemy vs Homonymy

- **Polysemy:** Related senses (same etymology) - may share core primitives
  - "head" (body part) → "head" (leader) - both involve TOP, HIER_PLUS

- **Homonymy:** Unrelated senses (different etymology) - need separate entries
  - "bear" (animal) vs "bear" (carry) - completely different primitives

**Recommendation:** For true homonyms with >20% frequency for secondary sense, create duplicate entries with sense disambiguation.

---

## Part 10: Duplicate Detection

### 10.1 Exact Duplicates

```sql
SELECT lemma, COUNT(*) as count
FROM lexemes
GROUP BY lemma
HAVING count > 1;
```

### 10.2 Case-Insensitive Duplicates

```sql
SELECT LOWER(lemma) as normalized, GROUP_CONCAT(lemma), COUNT(*)
FROM lexemes
GROUP BY LOWER(lemma)
HAVING COUNT(*) > 1;
```

### 10.3 Near-Duplicates (Levenshtein)

Use external tool or implement:
```python
from difflib import SequenceMatcher


def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()


# Find pairs with >90% similarity
```

---

## Part 10: External Tool Integration

### Recommended Tools

**Spell Checking:**
- [pyspellchecker](https://github.com/barrust/pyspellchecker) - Pure Python, frequency-based
- [SymSpell](https://github.com/mammothb/symspellpy) - Fast, Levenshtein-based
- [Hunspell](https://hunspell.github.io/) - Most accurate, morphology-aware

**Lemmatization:**
- [NLTK WordNetLemmatizer](https://www.nltk.org/api/nltk.stem.wordnet.html) - Dictionary-based
- [spaCy](https://spacy.io/) - Fast, neural-based
- [Stanza](https://stanfordnlp.github.io/stanza/) - Stanford NLP tools

**Morphological Analysis:**
- [MorphoPy](https://github.com/Linguistic/MorphoPy) - Morpheme segmentation
- [polyglot](https://polyglot.readthedocs.io/) - Multi-language support

### Installation

```bash
pip install pyspellchecker symspellpy nltk spacy
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
```

---

## Output Format

Generate a structured report:

### Executive Summary
- Total lexemes analyzed: X
- Potential spelling errors: X
- Abbreviations found: X
- Inflected duplicates: X
- Contractions: X
- Encoding issues: X
- Non-word entries: X
- Proper nouns: X

### Issue Tables

For each category, provide detailed tables with:
- Entry
- Issue type
- Severity (Critical/High/Medium/Low)
- Suggested action
- Confidence score

### Recommended Actions

Prioritized list of fixes:
1. **Critical:** Remove/fix broken entries
2. **High:** Consolidate obvious duplicates
3. **Medium:** Normalize spelling variants
4. **Low:** Review edge cases

---

## Execution Script

```python
#!/usr/bin/env python3
"""
Lexicon Data Quality Audit
"""

import sqlite3
import re
from collections import defaultdict

# Optional: install with pip install pyspellchecker nltk
try:
    from spellchecker import SpellChecker

    HAS_SPELLCHECKER = True
except ImportError:
    HAS_SPELLCHECKER = False

try:
    import nltk
    from nltk.stem import WordNetLemmatizer

    nltk.download("wordnet", quiet=True)
    nltk.download("omw-1.4", quiet=True)
    HAS_NLTK = True
except ImportError:
    HAS_NLTK = False


def audit_lexicon(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    results = {
        "spelling_errors": [],
        "abbreviations": [],
        "inflected_forms": [],
        "contractions": [],
        "encoding_issues": [],
        "non_words": [],
        "proper_nouns": [],
        "duplicates": [],
    }

    # Get all lemmas
    cursor.execute("SELECT id, lemma, pos, frequency_rank FROM lexemes")
    all_entries = cursor.fetchall()

    print(f"Auditing {len(all_entries)} lexemes...")

    # 1. Spelling check
    if HAS_SPELLCHECKER:
        spell = SpellChecker()
        lemmas = [e[1] for e in all_entries if e[1].isalpha()]
        misspelled = spell.unknown(lemmas)
        for word in misspelled:
            correction = spell.correction(word)
            results["spelling_errors"].append(
                {"word": word, "suggestion": correction, "candidates": list(spell.candidates(word) or [])[:5]}
            )

    # 2. Abbreviations
    abbrev_pattern = re.compile(r"^[a-z]{1,3}$|^[A-Z]{2,6}$|.*\.$")
    for id_, lemma, pos, rank in all_entries:
        if abbrev_pattern.match(lemma):
            results["abbreviations"].append({"word": lemma, "frequency_rank": rank})

    # 3. Inflected forms
    if HAS_NLTK:
        lemmatizer = WordNetLemmatizer()
        lemma_groups = defaultdict(list)
        for id_, lemma, pos, rank in all_entries:
            if lemma.isalpha():
                base_n = lemmatizer.lemmatize(lemma, "n")
                base_v = lemmatizer.lemmatize(lemma, "v")
                base = base_n if base_n != lemma else base_v
                if base != lemma:
                    lemma_groups[base].append(lemma)

        for base, variants in lemma_groups.items():
            if len(variants) > 0:
                results["inflected_forms"].append({"base": base, "variants": variants})

    # 4. Contractions
    contraction_pattern = re.compile(r".*'.*|.*n't$")
    for id_, lemma, pos, rank in all_entries:
        if contraction_pattern.match(lemma):
            results["contractions"].append({"word": lemma, "frequency_rank": rank})

    # 5. Encoding issues
    for id_, lemma, pos, rank in all_entries:
        if not lemma.isascii():
            results["encoding_issues"].append({"word": lemma, "frequency_rank": rank})

    # 6. Non-words (single chars, numbers, punctuation)
    for id_, lemma, pos, rank in all_entries:
        if len(lemma) == 1 and lemma.lower() not in ("a", "i"):
            results["non_words"].append({"word": lemma, "reason": "single_char"})
        elif lemma.isdigit():
            results["non_words"].append({"word": lemma, "reason": "number"})
        elif not any(c.isalnum() for c in lemma):
            results["non_words"].append({"word": lemma, "reason": "punctuation"})

    # 7. Proper nouns
    for id_, lemma, pos, rank in all_entries:
        if lemma[0].isupper() and lemma[1:].islower() and len(lemma) > 1:
            results["proper_nouns"].append({"word": lemma, "frequency_rank": rank})

    # 8. Duplicates
    cursor.execute("""
        SELECT LOWER(lemma), GROUP_CONCAT(lemma), COUNT(*)
        FROM lexemes GROUP BY LOWER(lemma) HAVING COUNT(*) > 1
    """)
    for norm, variants, count in cursor.fetchall():
        results["duplicates"].append({"normalized": norm, "variants": variants.split(","), "count": count})

    conn.close()
    return results


if __name__ == "__main__":
    results = audit_lexicon("data/lexicon.db")

    print("\n" + "=" * 60)
    print("LEXICON DATA QUALITY AUDIT")
    print("=" * 60)

    for category, items in results.items():
        print(f"\n{category.upper()}: {len(items)} issues")
        for item in items[:10]:  # Show first 10
            print(f"  {item}")
        if len(items) > 10:
            print(f"  ... and {len(items) - 10} more")
```

Save the audit report to `data/audit_report_v3_data_quality.md`.
