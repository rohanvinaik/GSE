# GSE Lexicon Audit System v6

## Pipeline Overview

This system uses **LLM-executed stages** with **Python utilities only** for data extraction and fix application. Each stage has a dedicated prompt document passed to a specific LLM executor.

---

## Architecture Reference

### Three-Layer System

```
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 3: SEMANTIC GRAPH                  │
│         (Constraint propagation, role assignment)           │
│  • ParseNode, ParseEdge, ParseGraph                         │
│  • Operator resolution (TAM, NEGATION, DEGREE)              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 2: COMPOSITION                     │
│         (HDC operations on resolved structures)             │
│  • Role binding with pre-computed role vectors              │
│  • Negation/hierarchy modifications via HDC ops             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 1: LEXICON                         │
│         (Word-level HDC encoding)                           │
│  • 62 Semantic primitives (organized into 8 banks)          │
│  • Grammatical metadata (informational zeros)               │
│  • Component type classification                            │
└─────────────────────────────────────────────────────────────┘
```

### Component Types

| Type | Description | Examples |
|------|-------------|----------|
| **ATOMIC** | Content words with semantic meaning | nouns, verbs, adjectives, adverbs |
| **OPERATOR** | Function words that perform operations | aux, det, neg, prep, conj, degree |
| **ABSORBED** | Inflectional morphemes (not standalone) | -ed, -s, -ing, -er, -est |

### Operator Subtypes

| Subtype | Binding | Examples |
|---------|---------|----------|
| TAM_AUXILIARY | LAZY | did, will, have, be, can, must |
| NEGATOR | GREEDY | not, never, no, neither, nor |
| DETERMINER | GREEDY | the, a, this, that, some, every |
| DEGREE | GREEDY | very, extremely, barely, slightly |
| PREPOSITION | GREEDY | in, on, at, by, for, with, to |
| CONJUNCTION | N/A | and, or, but, nor, yet |
| COMPLEMENTIZER | N/A | that, if, whether, because |

### Informational Zero

- **0** = "Dimension applicable but inactive" (explicit orthogonality)
- **NULL/absent** = "Dimension not applicable"
- Result: `semantic_similarity("ran", "run") == 1.0`

### SYN_* Dimensions

Words get SYN_* dimensions instantiated with 0 based on grammatical roles:

| POS | Instantiate |
|-----|-------------|
| Nouns | SYN_SUBJ=0, SYN_OBJ=0, SYN_COMPL=0 |
| Pronouns | SYN_SUBJ=0, SYN_OBJ=0, SYN_COMPL=0 |
| Verbs (ATOMIC) | SYN_PRED=0 |
| Adjectives | SYN_ADJ_MOD=0, SYN_COMPL=0 |
| Adverbs | SYN_ADV_MOD=0 |
| Determiners | SYN_DET=0 |

### Modifier Hierarchy

- Base primitive = always **+1**
- Direction via HIER_PLUS or HIER_MINUS
- Level = marker count

| Word | Encoding |
|------|----------|
| very | INTENSITY=1, HIER_PLUS=1, HIER_MINUS=0 |
| extremely | INTENSITY=1, HIER_PLUS=2, HIER_MINUS=0 |
| barely | INTENSITY=1, HIER_PLUS=0, HIER_MINUS=2 |

---

## 6-Stage Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 1: High-Level Audit                                            │
│   Executor: Google Antigravity (agent-focused IDE)                   │
│   Prompt: prompts/stage1_highlevel_audit.md                          │
│   Output: Audit report                                               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 2: Audit Validation                                            │
│   Executor: Claude Code                                              │
│   Guidelines: prompts/stage2_claude_validation.md                    │
│   Output: Validated audit + Qwen prompt                              │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 3: Fix Application                                             │
│   Executor: Qwen 32B (local via Ollama)                              │
│   Prompt: prompts/stage3_qwen_fixes.md                               │
│   Output: Fix log                                                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 4: Fix Validation                                              │
│   Executor: Claude Code                                              │
│   Guidelines: prompts/stage4_claude_fix_validation.md                │
│   Output: Validated database state                                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 5: Deep Triangulation Audit                                    │
│   THREE PARALLEL SOURCES:                                            │
│   (1) NLP databases (NRC-VAD, Lancaster, concreteness)              │
│   (2) 3 small models (smollm, granite3-moe, gemma2)                 │
│   (3) Qwen 32B common-sense                                          │
│   Prompt: prompts/stage5_triangulation_audit.md                      │
│   Output: Confidence-tiered assignments + manual review queue        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 6: Granular Traversal                                          │
│   Executors: smollm:1.7b, granite3-moe:1b, gemma2:2b                │
│   Prompt: prompts/stage6_granular_audit.md                           │
│   Output: Issues in deeper layers                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Stage Details

### Stage 1: High-Level Audit
**Prompt:** `prompts/stage1_highlevel_audit.md`
**Executor:** Google Antigravity

Common-sense validation of lexicon:
- Confident +1/0/-1 assignment to every word-scale bank
- No empty banks among required fields
- Component type assigned (ATOMIC/OPERATOR)
- Operator subtype assigned for OPERATORs
- SYN_* dimension instantiation based on grammatical roles

### Stage 2: Audit Validation
**Guidelines:** `prompts/stage2_claude_validation.md`
**Executor:** Claude Code

- Validate Stage 1 audit report correctness
- Cross-check issue counts against database
- Sample-verify flagged issues
- Prepare Qwen 32B prompt with embedded data

### Stage 3: Fix Application
**Prompt:** `prompts/stage3_qwen_fixes.md`
**Executor:** Qwen 32B

- Apply fixes systematically by category
- Log each change with reasoning
- Generate SQL for each fix
- Handle uncertain cases by skipping with explanation

### Stage 4: Fix Validation
**Guidelines:** `prompts/stage4_claude_fix_validation.md`
**Executor:** Claude Code

- Parse and categorize fix log
- Verify fixes are semantically correct
- Check for critical errors (rollback if found)
- Generate validation report

### Stage 5: Deep Triangulation Audit
**Prompt:** `prompts/stage5_triangulation_audit.md`
**Three Sources:**

1. **NLP Databases:** NRC-VAD, Lancaster Sensorimotor, Concreteness, NRC-Emotion
2. **3-Model Generative:** smollm:1.7b, granite3-moe:1b, gemma2:2b
3. **Qwen 32B:** Common-sense signal assignment

**Agreement Filtering:**
- All 3 agree → HIGH confidence → Auto-apply
- Source 2 + 3 agree (no NLP coverage) → HIGH confidence
- Disagreement → Manual review target

### Stage 6: Granular Traversal
**Prompt:** `prompts/stage6_granular_audit.md`
**Executors:** smollm:1.7b, granite3-moe:1b, gemma2:2b

- Focus: Words with frequency_rank > 5000
- Entry-by-entry common-sense validation
- Slow traversal to catch issues in deeper layers
- 3-model agreement protocol for issue confirmation

---

## Models Required

```bash
# Install via Ollama
ollama pull smollm:1.7b
ollama pull granite3-moe:1b
ollama pull gemma2:2b
ollama pull qwen3:32b
```

---

## Files

### Stage Prompts

| File | Stage | Executor |
|------|-------|----------|
| `prompts/stage1_highlevel_audit.md` | 1 | Google Antigravity |
| `prompts/stage2_claude_validation.md` | 2 | Claude Code |
| `prompts/stage3_qwen_fixes.md` | 3 | Qwen 32B |
| `prompts/stage4_claude_fix_validation.md` | 4 | Claude Code |
| `prompts/stage5_triangulation_audit.md` | 5 | NLP + 3 models + Qwen |
| `prompts/stage6_granular_audit.md` | 6 | 3 tiny models |

### Supporting Files

| File | Purpose |
|------|---------|
| `prompts/AUDIT_PIPELINE.md` | Quick reference |
| `data/lexicon.db` | Main database |
| `data/external/nrc_vad.txt` | Valence/Arousal/Dominance |
| `data/external/lancaster_sensorimotor.csv` | Sensorimotor norms |
| `data/external/concreteness.csv` | Concreteness ratings |
| `data/external/intensity_ground_truth.json` | Modifier hierarchy ground truth |

### Helper Scripts (Utilities Only)

| Script | Purpose |
|--------|---------|
| `scripts/extract_audit_data.py` | Extract word batches for prompt embedding |
| `scripts/apply_fixes.py` | Parse LLM output, apply SQL |
| `scripts/parse_nlp_databases.py` | Parse external NLP databases |

---

## Database Schema

```sql
-- lexemes: Main word table
CREATE TABLE lexemes (
    id INTEGER PRIMARY KEY,
    lemma TEXT NOT NULL,
    pos TEXT,
    frequency_rank INTEGER,
    component_type TEXT DEFAULT 'ATOMIC',
    operator_type TEXT,
    binding_behavior TEXT,
    gram_features TEXT
);

-- primitive_values: Semantic primitives
CREATE TABLE primitive_values (
    id INTEGER PRIMARY KEY,
    lexeme_id INTEGER NOT NULL,
    primitive TEXT NOT NULL,
    value INTEGER NOT NULL,  -- -1, 0, or 1
    confidence REAL,
    source TEXT,
    FOREIGN KEY (lexeme_id) REFERENCES lexemes(id)
);

-- operator_specs: Operator behavior specifications
CREATE TABLE operator_specs (
    id INTEGER PRIMARY KEY,
    lexeme_id INTEGER NOT NULL,
    operator_class TEXT NOT NULL,
    binding_type TEXT NOT NULL,
    binding_direction TEXT NOT NULL,
    seeks_roles TEXT NOT NULL,
    seeks_component TEXT NOT NULL,
    max_distance INTEGER DEFAULT 3,
    transmits TEXT DEFAULT '{}',
    semantic_primitives TEXT DEFAULT '{}',
    sign_value INTEGER,
    hier_delta INTEGER,
    FOREIGN KEY (lexeme_id) REFERENCES lexemes(id)
);
```

---

## Execution Flow

1. **Prepare Stage 1:** Load `prompts/stage1_highlevel_audit.md` into Google Antigravity
2. **Run Stage 1:** Execute audit, save report to `data/stage1_audit_report.md`
3. **Run Stage 2:** Pass report to Claude Code, validate, prepare Qwen prompt
4. **Run Stage 3:** Pass prompt to Qwen 32B, save fix log to `data/stage3_fixes.log`
5. **Run Stage 4:** Pass log to Claude Code, validate fixes, generate report
6. **Run Stage 5:** Execute triangulation (NLP + 3 models + Qwen), save results
7. **Run Stage 6:** Execute granular traversal with 3 tiny models
8. **Final Verification:** Run verification queries to confirm database integrity

---

## Verification Queries

```sql
-- Final state check
SELECT
    (SELECT COUNT(*) FROM lexemes) as total_lexemes,
    (SELECT COUNT(*) FROM lexemes WHERE component_type = 'OPERATOR') as operators,
    (SELECT COUNT(*) FROM primitive_values WHERE source LIKE 'fix:%') as fixes_applied,
    (SELECT COUNT(*) FROM primitive_values WHERE primitive LIKE 'SYN_%') as syn_dimensions,
    (SELECT COUNT(*) FROM lexemes WHERE gram_features IS NOT NULL) as gram_features_set;

-- Component type distribution
SELECT component_type, COUNT(*) FROM lexemes GROUP BY component_type;

-- Operator type distribution
SELECT operator_type, COUNT(*) FROM lexemes WHERE operator_type IS NOT NULL GROUP BY operator_type;

-- SYN_* dimension coverage
SELECT primitive, COUNT(*) FROM primitive_values WHERE primitive LIKE 'SYN_%' GROUP BY primitive;
```
