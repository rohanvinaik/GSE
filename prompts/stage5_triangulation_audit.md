# Stage 5: Deep Triangulation Audit

**Purpose:** Cross-reference multiple sources to establish high-confidence primitive assignments and identify words needing manual review.

## New Primitives (v2.0)

This stage now includes validation for:
- **SING/PLUR/ZERO**: Number encoding for pronouns and numerals
- **gram_feature_values**: Grammatical features (person, gender, case, definiteness)
- **hierarchy_levels**: Modifier scale positions (INTENSITY, QUANTITY, CERTAINTY, FREQUENCY)

### Mutual Transparency Rule (CRITICAL)
If ZERO=1, then SING≠1 AND PLUR≠1 - this constraint must never be violated.

---

## Three Parallel Sources

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SOURCE 1: NLP DATABASES                          │
│  Cross-reference via parse scripts                                  │
│  • NRC-VAD (valence, arousal, dominance)                           │
│  • Lancaster Sensorimotor (visual, haptic, motor, etc.)            │
│  • Concreteness ratings                                             │
│  • NRC-Emotion (joy, trust, fear, anger, etc.)                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SOURCE 2: THREE-MODEL GENERATIVE                 │
│  Executors: smollm:1.7b, granite3-moe:1b, gemma2:2b                │
│  Each model independently assigns primitive values                  │
│  Agreement between models → signal strength                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SOURCE 3: QWEN 32B COMMON-SENSE                  │
│  Executor: Qwen 32B (local)                                         │
│  Common-sense signal assignment                                     │
│  Higher reasoning capacity for edge cases                           │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AGREEMENT FILTERING                              │
│  All 3 agree → HIGH confidence                                      │
│  Source 2 + 3 agree (no NLP) → HIGH confidence                     │
│  Disagreement → MANUAL REVIEW target                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Source 1: NLP Database Cross-Reference

### Available Databases

| Database | File | Coverage | Primitives Mapped |
|----------|------|----------|-------------------|
| NRC-VAD | `data/external/nrc_vad.txt` | ~20k words | GOOD/BAD, INTENSITY, CONTROL |
| Lancaster | `data/external/lancaster_sensorimotor.csv` | ~39k words | SEE, HEAR, TOUCH, MOVE, BODY |
| Concreteness | `data/external/concreteness.csv` | ~40k words | SOMETHING, THINK |
| NRC-Emotion | `data/external/nrc_emotion.txt` | ~14k words | FEEL, GOOD, BAD |

### Mapping Rules

#### NRC-VAD → Primitives

| Dimension | Range | Primitive | Value |
|-----------|-------|-----------|-------|
| Valence | 0.0 - 0.35 | BAD | +1 |
| Valence | 0.35 - 0.65 | (neutral) | 0 |
| Valence | 0.65 - 1.0 | GOOD | +1 |
| Arousal | 0.0 - 0.35 | INTENSITY | -1 (calm) |
| Arousal | 0.35 - 0.65 | INTENSITY | 0 |
| Arousal | 0.65 - 1.0 | INTENSITY | +1 |
| Dominance | 0.0 - 0.35 | CONTROL | -1 |
| Dominance | 0.65 - 1.0 | CONTROL | +1 |

**Note:** INTENSITY=-1 for arousal is the raw mapping. Modifier hierarchy encoding (INTENSITY=1, HIER_MINUS) applies only to degree modifiers.

#### Lancaster → Primitives

| Modality | Threshold | Primitive | Condition |
|----------|-----------|-----------|-----------|
| Visual.mean | > 3.0 | SEE | +1 |
| Auditory.mean | > 3.0 | HEAR | +1 |
| Haptic.mean | > 3.0 | TOUCH | +1 |
| Gustatory.mean | > 3.0 | TASTE | +1 |
| Olfactory.mean | > 3.0 | SMELL | +1 |
| Motor.mean | > 3.0 | MOVE | +1 |
| Interoceptive.mean | > 3.0 | BODY | +1 |

#### Concreteness → Primitives

| Rating | Primitive | Value |
|--------|-----------|-------|
| 4.5 - 5.0 | SOMETHING | +1, THINK | 0 |
| 3.0 - 4.5 | (mixed) | context-dependent |
| 1.0 - 3.0 | THINK | +1, SOMETHING | 0 |

#### NRC-Emotion → Primitives

| Emotion | Primitive Mapping |
|---------|-------------------|
| joy | GOOD=+1, FEEL=+1 |
| trust | GOOD=+1 |
| fear | BAD=+1, FEEL=+1 |
| anger | BAD=+1, FEEL=+1 |
| sadness | BAD=+1, FEEL=+1 |
| disgust | BAD=+1, FEEL=+1 |
| anticipation | FUTURE=+1 |
| surprise | FEEL=+1 |

### Parse Script Usage

```python
# scripts/parse_nlp_databases.py

import pandas as pd
import sqlite3

def load_nrc_vad(path='data/external/nrc_vad.txt'):
    return pd.read_csv(path, sep='\t', names=['word','valence','arousal','dominance'], skiprows=1)

def load_lancaster(path='data/external/lancaster_sensorimotor.csv'):
    return pd.read_csv(path)

def load_concreteness(path='data/external/concreteness.csv'):
    return pd.read_csv(path)

def map_vad_to_primitives(row):
    primitives = {}
    if row['valence'] < 0.35:
        primitives['BAD'] = 1
    elif row['valence'] > 0.65:
        primitives['GOOD'] = 1
    # ... etc
    return primitives

def cross_reference(word, dbs):
    """Get signals from all available databases for a word."""
    signals = {}
    for db_name, db in dbs.items():
        if word in db.index:
            signals[db_name] = extract_signals(db.loc[word])
    return signals
```

---

## Source 2: Three-Model Generative Assignment

### Models

| Model | Size | Strengths |
|-------|------|-----------|
| smollm:1.7b | 1.7B | Fast, good for simple words |
| granite3-moe:1b | 1B | MoE architecture, diverse |
| gemma2:2b | 2B | Strong language understanding |

### Prompt Template (for each model)

```
For the word "{WORD}" (POS: {POS}), assign values to these semantic primitives.
Use only: +1 (present), 0 (neutral/inapplicable), -1 (opposite).

CORE PRIMITIVES:
- GOOD: Is this word positive/desirable?
- BAD: Is this word negative/undesirable?
- FEEL: Does this involve emotion/sensation?
- THINK: Does this involve cognition/mental activity?
- SAY: Does this involve speech/communication?
- DO: Does this involve intentional action?
- HAPPEN: Does this involve an event/state change?
- MOVE: Does this involve physical movement?
- SEE: Does this involve vision?
- HEAR: Does this involve hearing?
- BODY: Does this involve the physical body?
- ALIVE: Is this a living thing?
- SOMEONE: Does this involve a person/experiencer?
- SOMETHING: Is this a concrete thing?

NEW PRIMITIVES (v2.0):
- SING: Does this refer to a singular entity? (pronouns: I, he, she; numerals: one, first)
- PLUR: Does this refer to multiple entities? (pronouns: we, they; numerals: two, many)
- ZERO: Does this indicate non-existence/absence? (zero, none, nothing)
- ONE: Is this exactly one? (one, single, first)
- TWO: Is this exactly two? (two, pair, second)

CRITICAL RULE: If ZERO=1, then SING must be 0 and PLUR must be 0.

Respond in this exact format:
WORD: {word}
GOOD: {value}
BAD: {value}
FEEL: {value}
SING: {value}
PLUR: {value}
ZERO: {value}
...
```

### Execution

```bash
# Run each model in parallel
ollama run smollm:1.7b < batch_prompt.txt > smollm_output.txt &
ollama run granite3-moe:1b < batch_prompt.txt > granite_output.txt &
ollama run gemma2:2b < batch_prompt.txt > gemma_output.txt &
wait
```

### Parse Model Outputs

```python
def parse_model_output(output_path):
    results = {}
    current_word = None
    current_prims = {}

    with open(output_path) as f:
        for line in f:
            if line.startswith('WORD:'):
                if current_word:
                    results[current_word] = current_prims
                current_word = line.split(':')[1].strip()
                current_prims = {}
            elif ':' in line:
                prim, val = line.split(':')
                current_prims[prim.strip()] = int(val.strip())

    return results
```

### Model Agreement

```python
def compute_model_agreement(smollm, granite, gemma, word, primitive):
    votes = [
        smollm.get(word, {}).get(primitive),
        granite.get(word, {}).get(primitive),
        gemma.get(word, {}).get(primitive)
    ]
    votes = [v for v in votes if v is not None]

    if len(votes) < 2:
        return None, 'insufficient'

    if all(v == votes[0] for v in votes):
        return votes[0], 'unanimous'
    elif votes.count(max(set(votes), key=votes.count)) >= 2:
        return max(set(votes), key=votes.count), 'majority'
    else:
        return None, 'split'
```

---

## Source 3: Qwen 32B Common-Sense

### Prompt Template

```
You are a semantic analyst. For each word, assign primitive values based on common-sense understanding.

## Rules
1. Use +1 for "strongly associated", 0 for "neutral/not applicable", -1 for "opposite"
2. Consider the PRIMARY meaning of the word
3. Be conservative - only assign +1 when clearly applicable

## Words to Analyze
{WORD_LIST}

## Primitives
{PRIMITIVE_LIST}

## Output Format
{word}: {PRIM1}={val}, {PRIM2}={val}, ...

Example:
happy: GOOD=1, BAD=0, FEEL=1, SOMEONE=1, INTENSITY=0
sad: GOOD=0, BAD=1, FEEL=1, SOMEONE=1, INTENSITY=0
```

### Execution

```bash
ollama run qwen3:32b < qwen_prompt.txt > qwen_output.txt
```

### Parse Qwen Output

```python
def parse_qwen_output(output_path):
    results = {}
    with open(output_path) as f:
        for line in f:
            if ':' in line:
                word, rest = line.split(':', 1)
                prims = {}
                for pair in rest.split(','):
                    if '=' in pair:
                        prim, val = pair.split('=')
                        prims[prim.strip()] = int(val.strip())
                results[word.strip()] = prims
    return results
```

---

## Agreement Filtering

### Confidence Levels

| Agreement Pattern | Confidence | Action |
|-------------------|------------|--------|
| All 3 sources agree | HIGH | Auto-apply |
| Source 2 + 3 agree (no NLP coverage) | HIGH | Auto-apply |
| Source 1 + 2 agree, 3 differs | MEDIUM | Review if 3 is plausible |
| Source 1 + 3 agree, 2 differs | MEDIUM | Review model outputs |
| Source 2 + 3 agree, 1 differs | MEDIUM | NLP data may be noisy |
| All 3 disagree | LOW | Manual review required |
| Only 1 source available | LOW | Manual review required |

### Filtering Algorithm

```python
def compute_final_assignment(word, nlp_signals, model_signals, qwen_signals):
    """
    nlp_signals: dict of primitive -> value from NLP databases
    model_signals: dict of primitive -> (value, agreement_type) from 3 models
    qwen_signals: dict of primitive -> value from Qwen
    """
    final = {}
    review_queue = []

    for primitive in ALL_PRIMITIVES:
        nlp = nlp_signals.get(primitive)
        model_val, model_agree = model_signals.get(primitive, (None, None))
        qwen = qwen_signals.get(primitive)

        # Case 1: All 3 agree
        if nlp == model_val == qwen and nlp is not None:
            final[primitive] = {'value': nlp, 'confidence': 'HIGH', 'sources': 'all'}

        # Case 2: Model + Qwen agree, no NLP
        elif nlp is None and model_val == qwen and model_val is not None:
            final[primitive] = {'value': model_val, 'confidence': 'HIGH', 'sources': 'model+qwen'}

        # Case 3: 2/3 agree
        elif count_agreements(nlp, model_val, qwen) >= 2:
            majority = get_majority(nlp, model_val, qwen)
            final[primitive] = {'value': majority, 'confidence': 'MEDIUM', 'sources': 'majority'}

        # Case 4: Disagreement or insufficient data
        else:
            review_queue.append({
                'word': word,
                'primitive': primitive,
                'nlp': nlp,
                'model': model_val,
                'qwen': qwen,
                'reason': 'disagreement'
            })

    return final, review_queue
```

---

## Output Format

### Confidence-Tiered Assignments

```json
{
  "high_confidence": {
    "happy": {
      "GOOD": 1, "BAD": 0, "FEEL": 1, "SOMEONE": 1,
      "sources": ["nrc_vad", "3-model", "qwen"]
    },
    "run": {
      "DO": 1, "MOVE": 1, "BODY": 1,
      "sources": ["lancaster", "3-model", "qwen"]
    }
  },
  "medium_confidence": {
    "subtle": {
      "INTENSITY": -1, "THINK": 1,
      "sources": ["qwen", "3-model"],
      "disagreement": "nrc_vad says neutral"
    }
  },
  "manual_review": [
    {
      "word": "fair",
      "primitive": "GOOD",
      "nlp": 1, "model": 0, "qwen": 1,
      "reason": "multi-sense word, model disagrees"
    }
  ]
}
```

### Manual Review Queue

```markdown
# Stage 5 Manual Review Queue

## Priority: HIGH (full disagreement)
| Word | Primitive | NLP | 3-Model | Qwen | Notes |
|------|-----------|-----|---------|------|-------|

## Priority: MEDIUM (2/3 agree, 1 differs)
| Word | Primitive | NLP | 3-Model | Qwen | Majority |
|------|-----------|-----|---------|------|----------|

## Priority: LOW (single source only)
| Word | Primitive | Source | Value | Confidence |
|------|-----------|--------|-------|------------|
```

---

## Execution Script

```python
# scripts/run_stage5_triangulation.py

import json
from parse_nlp_databases import load_all_dbs, cross_reference
from parse_model_outputs import load_model_outputs, compute_model_agreement
from parse_qwen_output import parse_qwen_output

def run_triangulation(word_list):
    # Load sources
    dbs = load_all_dbs()
    smollm, granite, gemma = load_model_outputs()
    qwen = parse_qwen_output('data/qwen_output.txt')

    results = {'high': {}, 'medium': {}, 'review': []}

    for word in word_list:
        nlp_signals = cross_reference(word, dbs)
        model_signals = compute_model_agreement(smollm, granite, gemma, word)
        qwen_signals = qwen.get(word, {})

        final, review = compute_final_assignment(word, nlp_signals, model_signals, qwen_signals)

        # Categorize by confidence
        for prim, data in final.items():
            if data['confidence'] == 'HIGH':
                results['high'].setdefault(word, {})[prim] = data['value']
            else:
                results['medium'].setdefault(word, {})[prim] = data

        results['review'].extend(review)

    return results

if __name__ == '__main__':
    with open('data/word_list.txt') as f:
        words = [w.strip() for w in f]

    results = run_triangulation(words)

    with open('data/stage5_results.json', 'w') as f:
        json.dump(results, f, indent=2)
```

---

## Verification Queries

After applying high-confidence assignments:

```sql
-- Check for remaining conflicts
SELECT l.lemma, pv.primitive, pv.value, pv.source
FROM primitive_values pv
JOIN lexemes l ON pv.lexeme_id = l.id
WHERE pv.source LIKE 'stage5:%'
ORDER BY l.lemma, pv.primitive;

-- Count by confidence tier
SELECT
    (SELECT COUNT(DISTINCT lexeme_id) FROM primitive_values WHERE source = 'stage5:high') as high_conf,
    (SELECT COUNT(DISTINCT lexeme_id) FROM primitive_values WHERE source = 'stage5:medium') as med_conf;
```
