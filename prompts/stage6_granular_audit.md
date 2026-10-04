# Stage 6: Granular Traversal Audit

**Executors:** smollm:1.7b, granite3-moe:1b, gemma2:2b
**Focus:** Deeper layers, less-common entries (frequency rank > 5000)
**Mode:** Slow, entry-by-entry common-sense validation

---

## Purpose

Perform thorough common-sense traversal of the lexicon to identify glaring issues in less-common entries that may have been missed by higher-level audits or have insufficient coverage in NLP databases.

## New Primitives (v2.0)

This stage now validates:
- **SING/PLUR/ZERO**: Number encoding with mutual transparency constraint
- **gram_feature_values**: Grammatical features for pronouns and function words
- **hierarchy_levels**: Modifier scale positions

### Mutual Transparency Rule (CRITICAL)
If ZERO=1, then SING≠1 AND PLUR≠1

---

## Target Words

```sql
-- Words for Stage 6 audit
SELECT l.id, l.lemma, l.pos, l.frequency_rank, l.component_type
FROM lexemes l
WHERE l.frequency_rank > 5000  -- Less common words
  AND l.frequency_rank <= 25000  -- But still in vocabulary
ORDER BY l.frequency_rank;
```

Estimated: ~20,000 words

---

## Batch Strategy

### Batch Size
- 50 words per batch per model
- 3 models run in parallel
- ~400 batches total

### Batch Selection

Prioritize words with:
1. No NLP database coverage (no external validation)
2. Few active primitives (potentially incomplete)
3. LLM-only source (no cross-reference)

```sql
-- Priority 1: No external source
SELECT l.lemma FROM lexemes l
WHERE l.frequency_rank > 5000
AND NOT EXISTS (
    SELECT 1 FROM primitive_values pv
    WHERE pv.lexeme_id = l.id AND pv.source NOT LIKE 'llm:%'
)
LIMIT 50;

-- Priority 2: Sparse entries
SELECT l.lemma, COUNT(pv.id) as prim_count FROM lexemes l
LEFT JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.value != 0
WHERE l.frequency_rank > 5000 AND l.component_type = 'ATOMIC'
GROUP BY l.id
HAVING prim_count < 3
LIMIT 50;
```

---

## Model Prompts

### Common Template (All 3 Models)

```
You are auditing a lexicon database. For each word, check if its semantic primitives make sense.

## Word Entry
Word: {LEMMA}
POS: {POS}
Component Type: {COMPONENT_TYPE}

Current Primitives:
{PRIMITIVE_LIST}

## Check These Rules

1. **Experiencer Rule**: If FEEL=1, should SOMEONE=1 (or I/YOU)?
2. **Speech Rule**: If SAY=1, should WORDS=1?
3. **Action Rule**: If ATOMIC verb, should have DO=1 or HAPPEN=1?
4. **Bipolar Rule**: Should NOT have both GOOD=1 AND BAD=1 (unless truly ambivalent)
5. **Body Rule**: If physical body part, should BODY=1?
6. **Living Rule**: If living thing, should ALIVE=1?
7. **Empty Check**: ATOMIC content words should have at least 2-3 active primitives
8. **SING/PLUR/ZERO Rule (NEW)**: If ZERO=1, should SING=0 AND PLUR=0
9. **Pronoun Rule (NEW)**: Pronouns should have SOMEONE=1 (or SOMETHING=1 for "it") plus SING or PLUR
10. **Numeral Rule (NEW)**: Numbers should have SING=1 (for non-zero) or ZERO=1 (for zero/none)

## Response Format

If CORRECT:
{word}: OK

If ISSUE FOUND:
{word}: ISSUE - {description}
  Current: {primitive}={value}
  Expected: {primitive}={value}
  Reason: {explanation}
```

### Example Prompt Instance

```
Word: melancholy
POS: NOUN
Component Type: ATOMIC

Current Primitives:
FEEL=1, BAD=1, SOMEONE=0, THINK=1

---

Response:
melancholy: ISSUE - Missing experiencer
  Current: SOMEONE=0
  Expected: SOMEONE=1
  Reason: Melancholy is a feeling experienced by someone
```

---

## Execution Protocol

### Step 1: Generate Batches

```python
import sqlite3
import json

conn = sqlite3.connect('data/lexicon.db')

def generate_batch(offset, limit=50):
    words = conn.execute('''
        SELECT l.id, l.lemma, l.pos, l.component_type,
               GROUP_CONCAT(pv.primitive || '=' || pv.value) as primitives
        FROM lexemes l
        LEFT JOIN primitive_values pv ON l.id = pv.lexeme_id AND pv.value != 0
        WHERE l.frequency_rank > 5000 AND l.frequency_rank <= 25000
        GROUP BY l.id
        ORDER BY l.frequency_rank
        LIMIT ? OFFSET ?
    ''', (limit, offset)).fetchall()

    return [
        {
            'id': w[0],
            'lemma': w[1],
            'pos': w[2],
            'component_type': w[3],
            'primitives': w[4] or ''
        }
        for w in words
    ]

# Generate all batches
batch_num = 0
offset = 0
while True:
    batch = generate_batch(offset)
    if not batch:
        break
    with open(f'data/batches/batch_{batch_num:04d}.json', 'w') as f:
        json.dump(batch, f)
    batch_num += 1
    offset += 50
```

### Step 2: Run Models in Parallel

```bash
#!/bin/bash
# run_granular_audit.sh

BATCH_DIR="data/batches"
OUTPUT_DIR="data/granular_outputs"

for batch_file in $BATCH_DIR/batch_*.json; do
    batch_name=$(basename $batch_file .json)

    # Format prompt for this batch
    python scripts/format_granular_prompt.py $batch_file > /tmp/prompt.txt

    # Run all 3 models in parallel
    ollama run smollm:1.7b < /tmp/prompt.txt > $OUTPUT_DIR/${batch_name}_smollm.txt &
    ollama run granite3-moe:1b < /tmp/prompt.txt > $OUTPUT_DIR/${batch_name}_granite.txt &
    ollama run gemma2:2b < /tmp/prompt.txt > $OUTPUT_DIR/${batch_name}_gemma.txt &
    wait

    echo "Completed: $batch_name"
done
```

### Step 3: Parse Outputs

```python
import re
import json
from pathlib import Path

def parse_granular_output(output_path):
    issues = []
    with open(output_path) as f:
        content = f.read()

    # Parse ISSUE entries
    issue_pattern = r'(\w+): ISSUE - (.+?)\n\s+Current: (.+?)\n\s+Expected: (.+?)\n\s+Reason: (.+?)(?=\n\w+:|$)'

    for match in re.finditer(issue_pattern, content, re.DOTALL):
        issues.append({
            'word': match.group(1),
            'description': match.group(2).strip(),
            'current': match.group(3).strip(),
            'expected': match.group(4).strip(),
            'reason': match.group(5).strip()
        })

    return issues

def aggregate_model_issues(batch_name):
    smollm = parse_granular_output(f'data/granular_outputs/{batch_name}_smollm.txt')
    granite = parse_granular_output(f'data/granular_outputs/{batch_name}_granite.txt')
    gemma = parse_granular_output(f'data/granular_outputs/{batch_name}_gemma.txt')

    # Group by word
    all_issues = {}
    for source, issues in [('smollm', smollm), ('granite', granite), ('gemma', gemma)]:
        for issue in issues:
            word = issue['word']
            if word not in all_issues:
                all_issues[word] = {'models': [], 'issues': []}
            all_issues[word]['models'].append(source)
            all_issues[word]['issues'].append(issue)

    return all_issues
```

---

## Agreement Protocol

### Issue Confirmation

| Agreement | Confidence | Action |
|-----------|------------|--------|
| 3/3 models flag same issue | HIGH | Flag for immediate fix |
| 2/3 models flag same issue | MEDIUM | Flag for review |
| 1/3 models flags issue | LOW | Log but don't prioritize |
| 0/3 models flag issue | NONE | Entry is likely correct |

### Aggregation Logic

```python
def compute_issue_priority(word_issues):
    """
    word_issues: {'models': [...], 'issues': [...]}
    """
    model_count = len(set(word_issues['models']))

    # Check if issues are the same type
    issue_types = set(i['description'].split()[0] for i in word_issues['issues'])

    if model_count == 3 and len(issue_types) == 1:
        return 'HIGH'
    elif model_count >= 2:
        return 'MEDIUM'
    else:
        return 'LOW'
```

---

## Output Format

### Issue Log

```
=== Stage 6 Granular Audit Log ===
Batch Range: 5001 - 25000
Total Words Checked: {N}
Issues Found: {N}

--- HIGH Priority (3/3 agree) ---
melancholy: Missing SOMEONE=1 (FEEL requires experiencer)
  smollm: ISSUE - Missing experiencer
  granite: ISSUE - No SOMEONE for emotion
  gemma: ISSUE - FEEL=1 needs SOMEONE=1

eloquence: Missing WORDS=1 (SAY implies words)
  smollm: ISSUE - SAY without WORDS
  granite: ISSUE - Speech concept needs WORDS
  gemma: ISSUE - Missing WORDS primitive

--- MEDIUM Priority (2/3 agree) ---
ethereal: Possible missing THINK=1
  smollm: ISSUE - Abstract concept
  granite: OK
  gemma: ISSUE - Conceptual word needs THINK

--- LOW Priority (1/3 flags) ---
quintessential: Possible excessive primitives
  smollm: OK
  granite: OK
  gemma: ISSUE - Too many active primitives

--- Statistics ---
HIGH: {N} words
MEDIUM: {N} words
LOW: {N} words
OK: {N} words
```

### Fix Queue

```json
{
  "high_priority": [
    {
      "word": "melancholy",
      "lexeme_id": 12345,
      "issue": "Missing SOMEONE=1",
      "fix": "INSERT INTO primitive_values (lexeme_id, primitive, value, source) VALUES (12345, 'SOMEONE', 1, 'fix:stage6')",
      "agreement": "3/3"
    }
  ],
  "medium_priority": [...],
  "low_priority": [...]
}
```

---

## Verification Queries

After applying Stage 6 fixes:

```sql
-- Count fixes by priority
SELECT
    (SELECT COUNT(*) FROM primitive_values WHERE source = 'fix:stage6_high') as high,
    (SELECT COUNT(*) FROM primitive_values WHERE source = 'fix:stage6_medium') as medium;

-- Verify no new issues introduced
SELECT l.lemma FROM lexemes l
JOIN primitive_values g ON l.id = g.lexeme_id AND g.primitive = 'GOOD'
JOIN primitive_values b ON l.id = b.lexeme_id AND b.primitive = 'BAD'
WHERE g.value = 1 AND b.value = 1;  -- Bipolar violation

-- Check experiencer rule
SELECT l.lemma FROM lexemes l
JOIN primitive_values feel ON l.id = feel.lexeme_id AND feel.primitive = 'FEEL'
LEFT JOIN primitive_values someone ON l.id = someone.lexeme_id AND someone.primitive = 'SOMEONE'
WHERE feel.value = 1 AND (someone.value IS NULL OR someone.value != 1)
AND l.frequency_rank > 5000;  -- Stage 6 range
```

---

## Resource Estimates

| Metric | Value |
|--------|-------|
| Words to audit | ~20,000 |
| Batches | ~400 |
| Time per batch (3 models parallel) | ~30 seconds |
| Total time | ~3-4 hours |
| Expected HIGH issues | ~1-2% (~200-400 words) |
| Expected MEDIUM issues | ~3-5% (~600-1000 words) |

---

## Continuous Mode

For ongoing audits:

```bash
# Run Stage 6 on new words only
python scripts/run_stage6.py --new-only --since-timestamp "2024-01-01"

# Run Stage 6 on words with recent fixes (re-verify)
python scripts/run_stage6.py --recently-fixed --days 7
```
