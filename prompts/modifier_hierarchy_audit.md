# Modifier Hierarchy Audit System

**Purpose:** Validate that intensity/quantity/certainty modifiers use correct hierarchical stacking
**Core Principle:** No arbitrary scalars - only balanced ternary markers [+]/[-] stacking on base primitives

---

## The Hierarchy System

GSE encodes intensity hierarchically using stacked markers rather than arbitrary multipliers:

### Quantity Hierarchy (7 levels)

| Word | Level | Encoding |
|------|-------|----------|
| NONE | -3 | [−][−][−][QUANTITY] |
| FEW | -2 | [−][−][QUANTITY] |
| SOME | -1 | [−][QUANTITY] |
| MIDDLE | 0 | [QUANTITY] (neutral anchor) |
| MORE | +1 | [+][QUANTITY] |
| MANY | +2 | [+][+][QUANTITY] |
| ALL | +3 | [+][+][+][QUANTITY] |

### Intensity Hierarchy (5 levels)

| Word | Level | Encoding |
|------|-------|----------|
| BARELY | -2 | [−][−][INTENSITY] |
| SLIGHTLY | -1 | [−][INTENSITY] |
| MODERATE | 0 | [INTENSITY] (neutral anchor) |
| VERY | +1 | [+][INTENSITY] |
| EXTREMELY | +2 | [+][+][INTENSITY] |

### Certainty Hierarchy (7 levels)

| Word | Level | Encoding |
|------|-------|----------|
| IMPOSSIBLE | -3 | [−][−][−][CERTAINTY] |
| UNLIKELY | -2 | [−][−][CERTAINTY] |
| DOUBTFUL | -1 | [−][CERTAINTY] |
| POSSIBLE | 0 | [CERTAINTY] (= MAYBE) |
| PROBABLE | +1 | [+][CERTAINTY] |
| LIKELY | +2 | [+][+][CERTAINTY] |
| CERTAIN | +3 | [+][+][+][CERTAINTY] |

---

## Database Encoding Rules

In the primitive_values table:

1. **HIER_PLUS=1**: Means one positive marker [+]
2. **HIER_MINUS=1**: Means one negative marker [−]
3. **Multiple markers**: Stack by using hierarchy_level column or multiple entries
4. **INTENSITY=1**: Means base intensity primitive is active (NOT the intensity level!)
5. **INTENSITY=-1 is WRONG**: The base primitive is always +1; direction comes from HIER markers

### Correct Examples

```sql
-- "very" = [+][INTENSITY] (level +1)
INSERT INTO primitive_values (lexeme_id, primitive, value) VALUES
  (123, 'INTENSITY', 1),    -- Base primitive active
  (123, 'HIER_PLUS', 1);    -- One positive marker

-- "barely" = [−][−][INTENSITY] (level -2)
INSERT INTO primitive_values (lexeme_id, primitive, value) VALUES
  (456, 'INTENSITY', 1),    -- Base primitive active
  (456, 'HIER_MINUS', 2);   -- Two negative markers (or repeat entry)

-- "many" = [+][+][QUANTITY] (level +2)
INSERT INTO primitive_values (lexeme_id, primitive, value) VALUES
  (789, 'QUANTITY', 1),
  (789, 'HIER_PLUS', 2);
```

### Wrong Examples (Common Errors)

```sql
-- WRONG: "very" with INTENSITY=-1
-- The base primitive should always be +1!
-- Negative direction comes from HIER_MINUS markers, not base polarity

-- WRONG: Missing HIER markers
-- "extremely" needs HIER_PLUS=2, not just INTENSITY=1
```

---

## Audit Validation Rules

### Rule 1: Base Primitive Polarity
- INTENSITY, QUANTITY, CERTAINTY should always be +1 when present
- Never encode these with -1; direction is encoded via HIER markers

### Rule 2: Marker Presence Required
- Any word at level ≠ 0 MUST have corresponding HIER_PLUS or HIER_MINUS
- Words at level 0 (MODERATE, MIDDLE, POSSIBLE) need only the base primitive

### Rule 3: Marker Count Matches Level
- Level ±1: 1 marker
- Level ±2: 2 markers
- Level ±3: 3 markers

### Rule 4: Consistency with English Semantics
External ground truth: [scalar-adj dataset](https://github.com/acocos/scalar-adj)

Common English intensity words and their correct levels:

| Word | Type | Level | HIER_PLUS | HIER_MINUS |
|------|------|-------|-----------|------------|
| barely | INTENSITY | -2 | 0 | 2 |
| hardly | INTENSITY | -2 | 0 | 2 |
| slightly | INTENSITY | -1 | 0 | 1 |
| somewhat | INTENSITY | -1 | 0 | 1 |
| fairly | INTENSITY | 0 | 0 | 0 |
| rather | INTENSITY | 0 | 0 | 0 |
| quite | INTENSITY | +1 | 1 | 0 |
| very | INTENSITY | +1 | 1 | 0 |
| highly | INTENSITY | +1 | 1 | 0 |
| extremely | INTENSITY | +2 | 2 | 0 |
| incredibly | INTENSITY | +2 | 2 | 0 |
| exceedingly | INTENSITY | +2 | 2 | 0 |

| Word | Type | Level | HIER_PLUS | HIER_MINUS |
|------|------|-------|-----------|------------|
| none | QUANTITY | -3 | 0 | 3 |
| few | QUANTITY | -2 | 0 | 2 |
| little (qty) | QUANTITY | -2 | 0 | 2 |
| some | QUANTITY | -1 | 0 | 1 |
| several | QUANTITY | 0 | 0 | 0 |
| more | QUANTITY | +1 | 1 | 0 |
| much | QUANTITY | +1 | 1 | 0 |
| many | QUANTITY | +2 | 2 | 0 |
| most | QUANTITY | +2 | 2 | 0 |
| all | QUANTITY | +3 | 3 | 0 |

| Word | Type | Level | HIER_PLUS | HIER_MINUS |
|------|------|-------|-----------|------------|
| impossible | CERTAINTY | -3 | 0 | 3 |
| unlikely | CERTAINTY | -2 | 0 | 2 |
| doubtful | CERTAINTY | -1 | 0 | 1 |
| possible | CERTAINTY | 0 | 0 | 0 |
| maybe | CERTAINTY | 0 | 0 | 0 |
| probably | CERTAINTY | +1 | 1 | 0 |
| likely | CERTAINTY | +2 | 2 | 0 |
| certainly | CERTAINTY | +3 | 3 | 0 |
| definitely | CERTAINTY | +3 | 3 | 0 |

---

## External Ground Truth Sources (Downloaded)

GSE now includes downloaded external datasets for ground truth validation.

### Installed: acocos/scalar-adj Dataset
- **Location**: `data/external/scalar-adj/`
- **DeMelo Rankings**: `globalorder/data/demelo/gold_rankings/` (87 scales)
- **Crowd Rankings**: `globalorder/data/crowd/gold_rankings/` (79 scales)
- **Wilkinson Terms**: `globalorder/data/wilkinson/terms/` (21 scales)
- **SO-CAL Dictionary**: `globalorder/data/socal/adj_dictionary1.11.txt`
- **Paper**: Cocos et al. (2018) "Learning Scalar Adjective Intensity from Paraphrases" (EMNLP)

### Consolidated Ground Truth
- **Location**: `data/external/intensity_ground_truth.json`
- **Contents**: 74 modifier words with hierarchy levels, 191 scalar scales
- **Loader**: `scripts/load_intensity_ground_truth.py`

### Usage in Audit
```python
from scripts.load_intensity_ground_truth import get_modifier_ground_truth

gt = get_modifier_ground_truth()
level = gt.get_level("extremely")  # Returns 2
expected = gt.get_expected_encoding("very")  # Returns {"INTENSITY": 1, "HIER_PLUS": 1}
comparison = gt.compare_intensity("slightly", "barely")  # Returns 1 (slightly > barely)
```

### Academic Sources
- **DeMelo & Bansal (2013)**: "Good, Great, Excellent: Global Inference of Semantic Intensities"
- **Garí Soler & Apidianaki (2021)**: "Scalar Adjective Identification and Multilingual Ranking" [ACL Anthology](https://aclanthology.org/2021.naacl-main.370/)
- **Cambridge Grammar**: Degree adverb classification (intensifying, moderating, diminishing)

---

## LLM Audit Prompt Template

```
You are validating modifier hierarchy encoding in a semantic lexicon.

GSE uses balanced ternary stacking, NOT arbitrary scalars:
- Base primitive (INTENSITY/QUANTITY/CERTAINTY) is always +1
- Direction encoded via HIER_PLUS (+) or HIER_MINUS (-) markers
- Level = number of markers (e.g., "extremely" = INTENSITY +1, HIER_PLUS +2)

Review this word's encoding:

Word: {word}
Current encoding:
  INTENSITY: {intensity_value}
  QUANTITY: {quantity_value}
  CERTAINTY: {certainty_value}
  HIER_PLUS: {hier_plus_value}
  HIER_MINUS: {hier_minus_value}

Reference orderings:
- Intensity: barely < slightly < [moderate] < very < extremely
- Quantity: none < few < some < [middle] < more < many < all
- Certainty: impossible < unlikely < doubtful < possible < likely < certain

Is this encoding correct? Output ONE of:
CORRECT - encoding matches expected hierarchy
FIX:base:{primitive}:1 - base primitive should be +1, not -1
FIX:hier_plus:{count} - needs {count} HIER_PLUS markers
FIX:hier_minus:{count} - needs {count} HIER_MINUS markers
ADD:{primitive}:1 - missing primitive needed
REMOVE:{primitive} - spurious primitive should be removed
```

---

## Integration with Multi-Model Audit

Add to `scripts/multi_model_audit.py`:

```python
MODIFIER_WORDS = {
    # Intensity modifiers
    "barely": ("INTENSITY", -2),
    "hardly": ("INTENSITY", -2),
    "slightly": ("INTENSITY", -1),
    "somewhat": ("INTENSITY", -1),
    "fairly": ("INTENSITY", 0),
    "rather": ("INTENSITY", 0),
    "quite": ("INTENSITY", 1),
    "very": ("INTENSITY", 1),
    "highly": ("INTENSITY", 1),
    "extremely": ("INTENSITY", 2),
    "incredibly": ("INTENSITY", 2),
    # Quantity modifiers
    "none": ("QUANTITY", -3),
    "few": ("QUANTITY", -2),
    "some": ("QUANTITY", -1),
    "several": ("QUANTITY", 0),
    "more": ("QUANTITY", 1),
    "much": ("QUANTITY", 1),
    "many": ("QUANTITY", 2),
    "most": ("QUANTITY", 2),
    "all": ("QUANTITY", 3),
    # Certainty modifiers
    "impossible": ("CERTAINTY", -3),
    "unlikely": ("CERTAINTY", -2),
    "doubtful": ("CERTAINTY", -1),
    "possible": ("CERTAINTY", 0),
    "probably": ("CERTAINTY", 1),
    "likely": ("CERTAINTY", 2),
    "certainly": ("CERTAINTY", 3),
}


def check_modifier_hierarchy(lemma: str, primitives: dict) -> list:
    """Validate modifier hierarchy encoding."""
    issues = []

    if lemma not in MODIFIER_WORDS:
        return issues

    base_type, expected_level = MODIFIER_WORDS[lemma]

    # Check base primitive is +1
    base_value = primitives.get(base_type, 0)
    if base_value != 1:
        issues.append(
            {
                "type": "modifier_base",
                "description": f"{base_type} should be +1, got {base_value}",
                "fix": f"SET:{base_type}:1",
            }
        )

    # Check HIER markers
    hier_plus = primitives.get("HIER_PLUS", 0)
    hier_minus = primitives.get("HIER_MINUS", 0)

    if expected_level > 0:
        if hier_plus != expected_level:
            issues.append(
                {
                    "type": "modifier_hier",
                    "description": f"HIER_PLUS should be {expected_level}, got {hier_plus}",
                    "fix": f"SET:HIER_PLUS:{expected_level}",
                }
            )
        if hier_minus != 0:
            issues.append(
                {
                    "type": "modifier_hier",
                    "description": f"HIER_MINUS should be 0 for positive level, got {hier_minus}",
                    "fix": "SET:HIER_MINUS:0",
                }
            )
    elif expected_level < 0:
        if hier_minus != abs(expected_level):
            issues.append(
                {
                    "type": "modifier_hier",
                    "description": f"HIER_MINUS should be {abs(expected_level)}, got {hier_minus}",
                    "fix": f"SET:HIER_MINUS:{abs(expected_level)}",
                }
            )
        if hier_plus != 0:
            issues.append(
                {
                    "type": "modifier_hier",
                    "description": f"HIER_PLUS should be 0 for negative level, got {hier_plus}",
                    "fix": "SET:HIER_PLUS:0",
                }
            )
    else:  # level == 0
        if hier_plus != 0 or hier_minus != 0:
            issues.append(
                {
                    "type": "modifier_hier",
                    "description": f"Level 0 needs no HIER markers",
                    "fix": "SET:HIER_PLUS:0,HIER_MINUS:0",
                }
            )

    return issues
```

---

## Priority Classification

### HIGH PRIORITY (Immediate fix)
- Base primitive has wrong polarity (-1 instead of +1)
- Missing required HIER markers
- Wrong HIER marker type (PLUS when should be MINUS)

### MEDIUM PRIORITY
- Incorrect marker count (off by 1)
- Extra unneeded HIER markers

### LOW PRIORITY
- Missing modifier encoding entirely (needs full decomposition)

---

## Notes on Balanced Ternary

The [+]/[-] markers are NOT multipliers - they are structural markers in the encoding:

1. **Not multiplication**: "very" is not 1.5 × base intensity
2. **Ordinal ranking**: [+] means "one step higher on scale"
3. **Additive stacking**: [+][+] means "two steps higher"
4. **Geometric encoding**: Stacked markers occupy adjacent vector dimensions
5. **Lossless**: Any intensity level can be reconstructed exactly from markers

This design allows:
- Balanced ternary compatibility (-1, 0, +1 values only)
- Exact intensity comparison via marker counting
- Cross-bank consistency (same mechanism for all hierarchies)
