# GSE Lexicon Audit Pipeline (v7)

## Quick Reference

**Main Document:** `prompts/GSE_LEXICON_AUDIT_SYSTEM.md`
**Database:** `data/lexicon.db`

---

## v7 Changes (SING/PLUR/ZERO Expansion)

New primitives and tables added:

### New Primitives
| Primitive | Description | Examples |
|-----------|-------------|----------|
| SING | Singular entity | pronouns (I, he), numerals (one) |
| PLUR | Plural entity | pronouns (we, they), numerals (two+) |
| ZERO | Non-existence | zero, none, nothing |
| ONE, TWO | Cardinality | one, first, two, pair |

### Mutual Transparency Rule (CRITICAL)
```
If ZERO=1, then SING≠1 AND PLUR≠1
```

### New Tables
```sql
-- gram_feature_values: person, gender, case, definiteness, deixis
-- hierarchy_levels: INTENSITY/QUANTITY/CERTAINTY/FREQUENCY scales
-- syn_dimensions: SYN_SUBJ, SYN_OBJ, SYN_PRED, etc.
```

---

## 6-Stage Pipeline

| Stage | Prompt File | Executor | Output |
|-------|-------------|----------|--------|
| 1 | `stage1_highlevel_audit.md` | Google Antigravity | Audit report |
| 2 | `stage2_claude_validation.md` | Claude Code | Validated audit + Qwen prompt |
| 3 | `stage3_qwen_fixes.md` | Qwen 32B | Fix log |
| 4 | `stage4_claude_fix_validation.md` | Claude Code | Validated database |
| 5 | `stage5_triangulation_audit.md` | NLP + 3 models + Qwen | Confidence-tiered assignments |
| 6 | `stage6_granular_audit.md` | smollm, granite3-moe, gemma2 | Deep layer issues |

---

## Pipeline Flow

```
Stage 1: Google Antigravity
    ↓ Audit report
Stage 2: Claude Code (validate)
    ↓ Qwen prompt
Stage 3: Qwen 32B (apply fixes)
    ↓ Fix log
Stage 4: Claude Code (validate)
    ↓ Confirmed database
Stage 5: Triangulation (NLP + LLMs)
    ↓ Confidence tiers
Stage 6: Granular (3 tiny models)
    ↓ Final issues
```

---

## Models Required

```bash
ollama pull smollm:1.7b
ollama pull granite3-moe:1b
ollama pull gemma2:2b
ollama pull qwen3:32b
```

---

## Stage 5: Triangulation Sources

| Source | Type | Purpose |
|--------|------|---------|
| NLP Databases | Data | NRC-VAD, Lancaster, Concreteness |
| 3 Small Models | LLM | Generative primitive assignment |
| Qwen 32B | LLM | Common-sense validation |

**Agreement:**
- All 3 agree → HIGH confidence
- 2/3 agree (no NLP) → HIGH confidence
- Disagreement → Manual review

---

## Architecture Essentials

### Component Types
- **ATOMIC**: Content words (nouns, verbs, adj, adv)
- **OPERATOR**: Function words (aux, det, neg, prep, conj, degree)

### Operator Subtypes
| Subtype | Binding | Examples |
|---------|---------|----------|
| TAM_AUXILIARY | LAZY | did, will, have, be, can |
| NEGATOR | GREEDY | not, never, no |
| DETERMINER | GREEDY | the, a, this, that |
| DEGREE | GREEDY | very, extremely, barely |
| PREPOSITION | GREEDY | in, on, at, by, for |
| CONJUNCTION | N/A | and, or, but |
| COMPLEMENTIZER | N/A | that, if, whether |

### SYN_* Dimensions
| POS | Dimensions (all set to 0) |
|-----|---------------------------|
| Nouns | SYN_SUBJ, SYN_OBJ, SYN_COMPL |
| Verbs (ATOMIC) | SYN_PRED |
| Adjectives | SYN_ADJ_MOD, SYN_COMPL |
| Adverbs | SYN_ADV_MOD |

### Modifier Hierarchy
| Word | INTENSITY | HIER_PLUS | HIER_MINUS |
|------|-----------|-----------|------------|
| very | 1 | 1 | 0 |
| extremely | 1 | 2 | 0 |
| barely | 1 | 0 | 2 |

### Pronoun Encoding (v7)
| Pronoun | SOMEONE | SING | PLUR | Gram Features |
|---------|---------|------|------|---------------|
| I, me | 1 | 1 | 0 | person=1 |
| we, us | 1 | 1 | 1 | person=1 |
| he, him | 1 | 1 | 0 | person=3, gender=MASC |
| they, them | 1 | 1 | 1 | person=3 |
| it | SOMETHING=1 | 1 | 0 | person=3, gender=NEUT |

### Numeral Encoding (v7)
| Word | ZERO | SING | PLUR |
|------|------|------|------|
| zero, none | 1 | 0 | 0 |
| one, first | 0 | 1 | 0 |
| two, many | 0 | 1 | 1 |

---

## Key Files

| File | Purpose |
|------|---------|
| `prompts/GSE_LEXICON_AUDIT_SYSTEM.md` | Complete system overview |
| `prompts/stage1_highlevel_audit.md` | Stage 1 prompt |
| `prompts/stage2_claude_validation.md` | Stage 2 guidelines |
| `prompts/stage3_qwen_fixes.md` | Stage 3 prompt |
| `prompts/stage4_claude_fix_validation.md` | Stage 4 guidelines |
| `prompts/stage5_triangulation_audit.md` | Stage 5 prompt |
| `prompts/stage6_granular_audit.md` | Stage 6 prompt |
| `data/external/nrc_vad.txt` | Valence/Arousal/Dominance |
| `data/external/lancaster_sensorimotor.csv` | Sensorimotor norms |
| `data/external/intensity_ground_truth.json` | Modifier ground truth |

---

## Verification

```sql
-- Final state check (v7)
SELECT
    (SELECT COUNT(*) FROM lexemes) as total_lexemes,
    (SELECT COUNT(*) FROM lexemes WHERE component_type = 'OPERATOR') as operators,
    (SELECT COUNT(*) FROM primitive_values WHERE source LIKE 'fix:%') as fixes,
    (SELECT COUNT(*) FROM syn_dimensions) as syn_dims,
    (SELECT COUNT(*) FROM gram_feature_values) as gram_features,
    (SELECT COUNT(*) FROM hierarchy_levels) as hierarchy_levels;

-- SING/PLUR/ZERO mutual transparency check (must return 0)
SELECT COUNT(*) as violations FROM lexemes l
JOIN primitive_values zero ON l.id = zero.lexeme_id AND zero.primitive = 'ZERO' AND zero.value = 1
LEFT JOIN primitive_values sing ON l.id = sing.lexeme_id AND sing.primitive = 'SING'
LEFT JOIN primitive_values plur ON l.id = plur.lexeme_id AND plur.primitive = 'PLUR'
WHERE COALESCE(sing.value, 0) = 1 OR COALESCE(plur.value, 0) = 1;

-- Words with 0 primitives (target: minimize this)
SELECT COUNT(*) as zero_prim_words FROM lexemes l
WHERE l.component_type = 'ATOMIC'
AND NOT EXISTS (SELECT 1 FROM primitive_values pv WHERE pv.lexeme_id = l.id AND pv.value <> 0);
```
