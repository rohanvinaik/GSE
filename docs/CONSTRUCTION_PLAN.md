# GSE Construction Plan (May 2026 Rebuild)

> **Status:** Living plan; supersedes January `FINAL_INTEGRATION_PLAN.md`
> and `OPTIMIZATION_PLAN.md` where they conflict.
>
> **Last revision (May 2026):** §4.2 rewritten after the tiered-architecture
> finding from the sentence_architecture document. The original §4.2.4
> "vote per-primitive per-word" applied aggregation uniformly to every
> word, which empirically polluted the canonical bipolar primitives'
> definitional decompositions. The current §4.2 stratifies population
> into Tier 0 (definitional, 68 words), Tier 1 (NSM-analyzed, deferred),
> and Tier 2 (aggregation, ~1.3M words) with a word-scale boundary that
> drops sentence-scale primitives from word-scale lexicon rows.
>
> **Trigger for this rebuild:** The May 2026 antonym-cosine investigation
> showed the encoder is mathematically correct but the LLM-populated
> `data/lexicon.db` introduces systematic constraint violations that
> propagate into every encoder output. A badly-encoded data layer adds
> permanent noise to everything downstream; the rational move is to
> archive it and re-encode from source materials with the workflow
> informed by what we now know.

---

## 0. Reading guide

This document is organized so a reader can pick up cold:

- **§1 The theory anchor**: what GSE *is*, irreducibly, before any code.
- **§2 The encoding architecture (already correct, don't rebuild)**: what
  exists in `gse/` today that works and should be preserved.
- **§3 What this session's investigation discovered**: four findings that
  reshape how we use and verify the system.
- **§4 The lexicon population workflow (the rebuild)**: the concrete
  source-to-database pipeline, with the new constraints baked in.
- **§5 Verification workflow**: how we know each step is correct, with
  architecture-aligned metrics.
- **§6 Sparse-wiki-grounding mechanisms to incorporate (now or later)**:
  what to port from `~/Projects/sparse-wiki-grounding/` per
  `ARCHITECTURE_DEEP_DIVE.md`.
- **§7 Deliberately deferred**: what is *not* part of the rebuild.
- **§8 Risks and open questions**.

The plan favors small, verifiable steps with measurable invariants over
big-bang rewrites. The basis math is correct and tested — preserving it
is more important than rebuilding it.

---

## 1. Theory anchor

GSE is an instantiation of Wierzbicka's Natural Semantic Metalanguage
(NSM) in hyperdimensional sparse-ternary computing. The irreducible
commitments are:

### 1.1 The 72-primitive vocabulary across 8 banks

| Bank | # | Examples |
|---|---|---|
| SUBSTANTIVES (0) | 10 | I, YOU, SOMEONE, SOMETHING, PEOPLE, BODY, KIND, PART, SAME, OTHER |
| QUANTITY (1) | 3 | ONE, TWO, QUANTITY |
| EVALUATORS (2) | 4 | GOOD, BAD, BIG, SMALL |
| MENTAL (3) | 7 | THINK, KNOW, WANT, FEEL, SEE, HEAR, INFER |
| ACTION (4) | 10 | SAY, WORDS, DO, HAPPEN, MOVE, BE, HAVE, EXIST, ALIVE, DEAD |
| TEMPORAL (5) | 10 | MOMENT, WHEN, LONG_TIME/SHORT_TIME, BEFORE/AFTER, THEN/NOW, START/END |
| SPATIAL (6) | 14 | WHERE, HERE, SIDE, TOUCH, ABOVE/BELOW, FAR/NEAR, OUTSIDE/INSIDE, TOWARD/AWAY, WITH/WITHOUT |
| LOGICAL (7) | 14 | NOT, MAYBE, CAN, MUST, BECAUSE, CAUSE, IF, LIKE, TRUE/FALSE, HIER_PLUS, HIER_MINUS, INTENSITY, CERTAINTY |

Source of truth: `gse/curation/schema.py:14-78` (`ALL_PRIMITIVES`).

### 1.2 14 bipolar dimensions with mutual exclusion

Bipolar primitives encode antonymy as **±1 in the same orthogonal
direction**: cos(GOOD, BAD) = −1 at the basis level, by construction.
This is the foundational geometric property of GSE.

| Dimension | Pos / Neg | Bank |
|---|---|---|
| IDENTITY | SAME / OTHER | SUBSTANTIVES |
| EVALUATION | GOOD / BAD | EVALUATORS |
| SIZE | BIG / SMALL | EVALUATORS |
| VITALITY | ALIVE / DEAD | ACTION |
| DURATION | LONG_TIME / SHORT_TIME | TEMPORAL |
| TEMPORAL_ORDER | BEFORE / AFTER | TEMPORAL |
| TEMPORAL_REF | THEN / NOW | TEMPORAL |
| TEMPORAL_BOUND | START / END | TEMPORAL |
| VERTICAL | ABOVE / BELOW | SPATIAL |
| DISTANCE | FAR / NEAR | SPATIAL |
| CONTAINMENT | OUTSIDE / INSIDE | SPATIAL |
| DIRECTION | TOWARD / AWAY | SPATIAL |
| ACCOMPANIMENT | WITH / WITHOUT | SPATIAL |
| TRUTH | TRUE / FALSE | LOGICAL |

**The mutual exclusion rule (new policy, the central rebuild constraint):**

> For any word and any bipolar dimension, **at most one pole may be
> active**. A word that activates both NEAR and AWAY, or both BIG and
> SMALL, violates NSM. The canonical decomposition picks the
> stronger-evidence pole and zeroes the other.

This rule does not exist in the current lexicon; enforcing it is the
core of the rebuild.

### 1.3 Three ordinal hierarchies

QUANTITY (NONE → FEW → SOME → MIDDLE → MORE → MANY → ALL), INTENSITY
(BARELY → … → EXTREMELY), CERTAINTY (IMPOSSIBLE → … → CERTAIN). Encoded
as base primitive + N hierarchical markers (HIER_PLUS / HIER_MINUS). See
`gse/primitives_v2.py:179-217`.

### 1.4 Sub-context-conditioned similarity

Similarity between two words is **not** a single number. It is a vector
of per-bank cosines. "good" and "bad" share most of their semantic
context (both evaluative judgments, invoking FEEL/THINK/affect) — they
should be **highly similar globally** and **diametrically opposed in the
EVALUATORS bank specifically**.

The architecture-aligned similarity metric is **per-bank cosine**, not
global cosine. This was the central misunderstanding the May 2026
investigation corrected.

---

## 2. Encoding architecture (already correct — preserve)

### 2.1 Hadamard partition basis (`gse/vectors_v2.py`)

* 8192-dim sparse-ternary vectors, 1024 dims per bank, 8 banks.
* `generate_hadamard_pattern` assigns each primitive a disjoint local
  slice within its bank; signs come from a Hadamard row.
* **Guarantees**: cos(primitive_i, primitive_j) = 0 for distinct
  primitives in the same bank (verified by `test_primitives_v2.py`).
* `generate_bipolar_patterns` produces negation pairs with exact cos =
  −1 (also tested).
* `generate_role_pattern` was rewritten in May 2026 to be
  partition-based; exact role-role orthogonality is verified by
  `test_role_pairs_exactly_orthogonal`.

### 2.2 SparseVector with bank projection (`vectors_v2.py:165-237`)

`SparseVector.with_bank_only(bank_index, dims_per_bank)` returns the
projection onto a single bank's index range. This is the operation
that lets us compute architecture-aligned similarity.

### 2.3 Polarity propagation (`vectors_v2.py:1065-…`)

`POLARITY_PROPAGATION_RULES`: EVALUATORS → MENTAL, EVALUATORS → ACTION.
A negated EVALUATOR colors MENTAL/ACTION primitives in the same
decomposition so that "hate" and "love" are geometrically distinct
even though both contain FEEL/SOMEONE. 13 tests in
`test_polarity_propagation.py`.

### 2.4 Multi-scale ScaleDefinition

`gse/scale_definition.py`. TEXT, PARAGRAPH, SENTENCE scales use the
generic `ScaleDefinition` pattern (Genesis Atom). WORD-scale
deliberately retains its richer legacy `PrimitiveInfo` because the
semantic richness (is_bipolar, hierarchy markers, bipolar dim) doesn't
fit the generic schema.

### 2.5 OperationTrace (`gse/api/trace.py`)

Every encode produces a trace with per-token primitives, operators,
sparsity stats, and a vector hash. Bridges the HDC layer with logical
auditability — answers "what operators were applied, in what order, to
what tokens" without inspecting the bundle.

### 2.6 Orchestrator (`gse/patterns/orchestrator.py`)

Top-down cascade: text → paragraph → sentence → word. Each scale's
output becomes a `prior_*` feature for the next. `cascade=True` runs
all four scales; `process_hierarchical` does segmentation + cascade.

### 2.7 What none of these depend on

The encoding pipeline takes a `Dict[primitive_name, +1/-1]` and turns
it into a vector. **It does not care where the dict comes from**. The
rebuild changes only the source — *what produces the dict* — not the
math.

---

## 3. What this session's investigation discovered

### 3.1 Finding 1 — Per-bank cosine is the architecture-aligned metric

Global cosine for antonym pairs (good/bad, near/far) is positive
(+0.55-0.66) because the two words share massive non-evaluative context.
This is **correct geometry**. Bank-projected cosine, targeting the
bipolar dimension's home bank, is what should oppose.

Verified empirically on 8 pairs:

| Pair | Global | EVAL bank | SPATIAL bank | Notes |
|---|---|---|---|---|
| big/small | +0.55 | **−1.000** | +0.89 | clean |
| alive/dead | +0.40 | **−1.000** | +0.33 | clean |
| happy/sad | +0.42 | **−1.000** | +0.29 | NSM-decomposed via GOOD/BAD |
| above/below | +0.09 | −1.000 | +0.00 | anomaly: SPATIAL bipolar didn't oppose in SPATIAL |
| good/bad | +0.66 | **+0.000** | +0.75 | anomaly: EVAL=0 |
| near/far | +0.63 | +0.00 | +0.365 | anomaly: SPATIAL=+0.365 |

**Action**: `gse/benchmarks/metrics.py` now provides
`bank_cosine_signature` and `min_bank_cosine`. The benchmark runner
reports both global and bank-projected for antonym tasks.

### 3.2 Finding 2 — The anomalies are a single LLM policy violation

Diagnosis: both the good/bad EVAL=0 anomaly and the near/far
SPATIAL=+0.365 anomaly come from the **same structural error in the LLM
that populated `data/lexicon.db`**: it activated both poles of bipolar
pairs on the same word.

* good EVAL: `{GOOD: +1, BAD: -1, BIG: -1, SMALL: +1}` — the SIZE axis
  shouldn't be touched, but the LLM hallucinated a SIZE component
  shared between good and bad, neutralizing the EVAL opposition.
* near SPATIAL: `{NEAR: +1, FAR: -1, AWAY: +1, OUTSIDE: +1, …}` — "near"
  with `AWAY=+1` is a semantic contradiction; six SPATIAL primitives are
  shared between near/far with matching signs.

The constraint that should have been enforced during curation:
**within a bipolar pair, at most one pole can activate per word.**

### 3.3 Finding 3 — sparse-wiki-grounding doesn't solve this either

`~/Projects/sparse-wiki-grounding/` (per its `ARCHITECTURE_DEEP_DIVE.md`
and `epa.py`) uses **linear sum + post-hoc ternary quantization** for
opposing concepts. It does not implement mutual exclusion. We can't
solve the GSE issue by porting; we have to add the constraint
ourselves.

What sparse-wiki-grounding *does* offer that GSE lacks:

| Mechanism | Effort | Why it would help |
|---|---|---|
| Trajectory disambiguation (multi-layer Jaccard) | LARGE | Disambiguation by recursive context convergence |
| Anchor-layer Layer 2 connectivity | MEDIUM | Emergent similarity without direct edges |
| Bank-routed activation accumulation | MEDIUM | Per-bank float tracking through spreading |
| Zero-state signed distance | SMALL | Directional geometry for hierarchy |
| Calibration values (decay 0.7, threshold 0.15, max_depth 2) | — | Validated parameters |

### 3.4 Finding 4 — The encoder is correct; the lexicon is wrong

Together, findings 1-3 mean: the math, the basis, the propagation, the
roles, the trace — all working. The remaining gap is one rule
(mutual exclusion) that should have been enforced when the LLM
populated `data/lexicon.db`. Because that rule wasn't applied to
1.35M lexemes, the database has structural noise we can't filter
without rebuilding.

**Hence the rebuild.**

---

## 4. Lexicon population workflow (the rebuild)

### 4.1 Source materials (already on disk)

| Source | Path | Coverage |
|---|---|---|
| ConceptNet 5.7 | `data/external/conceptnet-assertions-5.7.0.csv` (9.7 GB) + `conceptnet-en.sqlite` | Relational assertions |
| Wiktionary | `data/external/wiktionary/` | Definitions, glosses |
| NRC Emotion | `data/external/nrc_emotion.txt` (2.6 MB) | 8 emotion + 2 sentiment dimensions |
| NRC VAD | `data/external/nrc_vad.txt` (1.5 MB) | Valence/arousal/dominance |
| Lancaster Sensorimotor | `data/external/lancaster_sensorimotor.csv` (2.7 M rows) | Modality-specific embodied semantics |
| Concreteness | `data/external/concreteness.csv` (1.5 MB) | Concreteness ratings |
| Sensorimotor norms | `data/external/Sensorimotor_norms_*.csv` | 3 variants |
| Scalar adjectives | `data/external/scalar-adj/` | Adjective orderings |
| Custom intensity GT | `data/external/intensity_ground_truth.json` | Gold intensity scores |

Parsers: `gse/curation/external_sources/{conceptnet,wiktionary,nrc_emotion,nrc_vad,lancaster_sensorimotor,concreteness,verbnet,framenet,propbank,usas,sentiwordnet,wordnet_hierarchy}.py` — 18 parsers, each implementing `BaseExternalParser.to_primitives(word) → Dict[str, int]`.

### 4.2 Population steps (the rebuild proper)

> Every step except the final write is a dry run. The actual
> `data/lexicon.db` is not touched until §4.2.7 is approved.

**Tiered architecture (May 2026 revision).** Word-scale population is
stratified per `sentence_architecture.md`. Per-tier handling:

| Tier | Words | Method | Module |
|---|---|---|---|
| 0 | 68 — English labels for the GSE primitives (good, bad, big, small, someone, think, ...) | Definitional: `{LABEL: +1}` identity decomposition. No aggregation. | `gse/curation/external_sources/tier_0_dispatch.py` |
| 1 | ~200-500 NSM-analyzed core lemmas (happy, sad, know, want, see, ...) | Published Wierzbicka analyses or hand-authored sparse decompositions. **Deferred to a follow-up round; not part of this rebuild.** | Not yet built |
| 2 | ~1.3M Wiktionary lemmas (long tail) | Confidence-weighted voting + bipolar mutual exclusion + per-source scope + Wiktionary scaffolding filter | `populate.populate_with_voting_and_exclusion` |

**Word-scale boundary (May 2026 revision).** Sentence-scale primitives
must not appear in word-scale lexicon rows. Tier 2 aggregation drops
votes for the 29 primitives in
`source_scope.WORD_SCALE_EXCLUDED_PRIMITIVES`:

* 24 sentence-scale primitives (SYN_SUBJ/PRED/OBJ/COMPL, SYN_ADJ_MOD,
  SYN_ADV_MOD, SYN_DET, SYN_TENSE_*, SYN_ASPECT_*, SYN_MOOD_*,
  COMP_THAN/AS/HOW/WHAT/JUST/ONLY/EVEN/BUT/SO/BECAUSE).
* 5 hierarchy operators (HIER_PLUS, HIER_MINUS, INTENSITY, CERTAINTY,
  QUANTITY).

These are populated by sentence-scale activations at encode time, not
by word-scale lexicon rows. Per `sentence_architecture.md`: word-scale
stores informational zeros for these dimensions.

#### 4.2.1 Archive the existing database

```
mv data/lexicon.db data/lexicon.db.legacy-2026-05-23
```

Preserve, don't delete. The legacy DB still has 1.35 M LLM-generated
lexemes — useful as a reference set for which lemmas to keep coverage
of.

#### 4.2.2 Recreate schema

Fresh `data/lexicon.db` with the existing schema in
`gse/curation/schema.py` (`LexiconDatabase()._initialize_schema()`).
No changes to schema in this rebuild; the constraint policy lives in
the *population code*, not the table definitions.

#### 4.2.3 Build candidate word list from external sources

```
integrator = ExternalSourcesIntegrator("data/lexicon.db")
integrator.load_all_sources()
external_words = integrator.get_all_words()
```

Expect ~50-80 k words across all sources. (Per-source coverage already
audited; see §6 of the May 22 audit report.)

#### 4.2.4 Per-word tier dispatch + vote

For each word, the integrator's `aggregate_primitives_weighted`:

1. **Tier 0 short-circuit.** If the word is one of the 68 English
   labels for a GSE primitive (good, bad, big, small, ...,
   `canonical_decomposition` in `tier_0_dispatch.py`), return the
   definitional decomposition `{LABEL: +1}` directly. No aggregation.
   Source recorded as `tier_0_definitional`.
2. **Tier 2 aggregation.** Otherwise, each parser proposes a dict of
   primitive activations + confidences. The integrator applies:
   * Word-scale boundary (drop votes for `WORD_SCALE_EXCLUDED_PRIMITIVES`),
   * Per-source scope (drop votes outside the source's domain),
   * Confidence-weighted voting (ported formula),
   * Bipolar mutual exclusion (suppress weaker pole on conflicts).
3. **Tier 1** (NSM-analyzed) is reserved for a follow-up; if a Tier 1
   word manifest is later added, it would short-circuit here between
   steps 1 and 2.

This produces an `ExternalWordData` with `primitives`, `confidence_scores`,
`sources`, and (for Tier 2) `suppressions`.

#### 4.2.5 **NEW: Apply the bipolar mutual-exclusion constraint**

This is the central rebuild constraint. Pseudocode:

```python
def enforce_bipolar_exclusion(
    primitives: Dict[str, int],
    confidences: Dict[str, float],
) -> Tuple[Dict[str, int], Dict[str, float], List[Dict]]:
    """
    For each of the 14 BIPOLAR_PAIRS, if both poles are active, keep
    the one with higher confidence and zero out the other. Record the
    suppressed pole in the provenance trail.
    """
    suppressions = []
    for pos, neg in BIPOLAR_PAIRS:
        if pos in primitives and neg in primitives:
            # Both active — pick the stronger one
            conf_pos = confidences.get(pos, 0.0)
            conf_neg = confidences.get(neg, 0.0)
            if conf_pos >= conf_neg:
                drop = neg
                keep = pos
            else:
                drop = pos
                keep = neg
            suppressions.append(
                {
                    "kept": keep,
                    "dropped": drop,
                    "kept_conf": confidences.get(keep, 0.0),
                    "dropped_conf": confidences.get(drop, 0.0),
                }
            )
            del primitives[drop]
            confidences.pop(drop, None)
    return primitives, confidences, suppressions
```

This module lives at `gse/curation/external_sources/bipolar_exclusion.py`
(new). The suppression records flow into
`decomposition_provenance.source_detail` so the audit trail captures
both the kept pole's evidence AND the suppressed-pole evidence.

#### 4.2.6 Write to `data/lexicon.db` via populate_from_external.py

The existing `populate_from_external.py` Store connector
(`gse/curation/external_sources/populate.py`, written in this session,
10 tests passing) writes:

* a `lexemes` row (source='external_sources_voting', avg conf)
* 72 `primitive_values` rows (the full decomposition, with non-active
  primitives at value=0)
* a `decomposition_provenance` row (source_type='external',
  source_detail = sorted source list + suppressed-pole records)

CLI: `python -m gse.curation.external_sources.populate --db data/lexicon.db --min-sources 2 --min-confidence 0.5`

This step is **irreversible in practice** (writes 50-80k rows). Gate on
explicit user authorization. The dry-run produces a CSV/JSON of what
would be written; the apply step writes it.

### 4.3 Verification gates between steps

| Gate | Check | Tool |
|---|---|---|
| After §4.2.5 dry-run | No `ExternalWordData` has both poles of any bipolar pair active | new `test_bipolar_exclusion_invariant` |
| After §4.2.6 | For each of the 28 bipolar primitive words (good, bad, big, small, …), the lexicon row contains the matching primitive with +1 and the opposing pole with 0 (not -1) | new `test_bipolar_primitives_have_canonical_decomp` |
| After §4.2.6 | `cos(good, bad) on EVALUATORS bank < -0.7` (theory predicts -1; allow noise from secondary primitives) | new `test_bipolar_eval_bank_opposes` |
| After §4.2.6 | Antonym benchmark min-bank cos negative-rate ≥ 0.8 | `python -m gse.benchmarks.run --task antonyms` |

---

## 5. Verification workflow

### 5.1 Existing test surface (preserve)

* `test_primitives_v2.py` — basis-level orthogonality, bipolar cos = −1
* `test_polarity_propagation.py` — emergent antonymy
* `test_orchestrator.py` — cascade, hierarchical segmentation
* `test_gse_verification_proof_suite.py` — reproducibility, similarity,
  entity recovery, operator antisymmetry, compositional operator
  resolution, structural similarity (35 tests)
* `test_klines.py` — pattern completion
* `test_marker_detection.py` — text/paragraph keyword detectors
* `test_benchmark_runner.py` — runner plumbing
* `test_bank_cosine_metrics.py` — bank projection
* `test_populate_from_external.py` — Store connector

### 5.2 New tests this rebuild requires

| Test | What it verifies |
|---|---|
| `test_bipolar_exclusion_constraint` | The new `enforce_bipolar_exclusion()` function keeps the higher-confidence pole, drops the other, records the suppression |
| `test_lexicon_bipolar_invariant` | After population, no lexeme has both poles of any bipolar pair active |
| `test_bipolar_eval_bank_opposition` | For each of the 14 bipolar dimensions, encoded primitive-word pairs have bank-projected cos < −0.7 in the dimension's home bank |
| `test_antonym_benchmark_baseline` | The custom antonyms dataset's min-bank cosine negative-rate ≥ 0.8 |

### 5.3 Architecture-aligned metrics in the runner

The benchmark runner now reports both global and bank-projected
results. For antonym/synonym tasks, the architecture-aligned metric is
the min-bank cosine. For correlation tasks (SimLex, STS), global
cosine remains correct (humans rate global similarity, not bank-
specific opposition).

---

## 6. Sparse-wiki-grounding mechanisms (incorporate, in waves)

### 6.1 Wave 1 — at rebuild time (SMALL)

* **Ternary quantization helper** for confidence-weighted aggregations
  (`>0.3 → +1`, `<-0.3 → -1`, else 0). Useful when source votes
  produce floats that need to land on the ternary grid.

### 6.2 Wave 2 — after rebuild (MEDIUM)

* **Bank-routed activation accumulation**: extend `OperationTrace` to
  carry `Dict[bank_name, float]` for each operator, so per-bank
  evidence flows through the entire pipeline (not just the final
  vector's bank projection).
* **Anchor-layer Layer 2 connectivity**: introduce an "anchor"
  intermediate vocabulary (categories like KNOWN_FOR, GENRE, etc.)
  that connects entities/words sharing semantic position without
  direct edges. Maps onto GSE's `PRIMITIVE_FAMILIES`.

### 6.3 Wave 3 — research investment (LARGE)

* **Trajectory disambiguation**: recursive multi-layer Jaccard
  similarity at increasing decomposition depths. For ambiguous words,
  the correct sense's anchor trajectory converges with the context's
  trajectory; wrong senses diverge.

Calibration values from sparse-wiki-grounding to consider as defaults:

```
decay = 0.7              # link layer per-hop decay
anchor_decay = 0.4       # anchor layer decay (softer)
threshold = 0.15         # min activation to continue
max_depth = 2
anchor_limit = 5         # max entities per anchor
anchors_per_layer = 15   # decomposition layer cap
```

---

## 7. Deliberately deferred

* **Empty banks (5 text + 3 paragraph)**: STRUCTURE, AUDIENCE, PURPOSE,
  STYLE, RESERVED_TEXT, COHERENCE, GESTALT, RESERVED_PARA — these
  require theory derivation work (a `sentence_architecture.md` doc
  that doesn't yet exist). NOT part of the rebuild.
* **POSTagger spaCy → heuristic-fallback abstraction**: already done
  this session (`HeuristicParser` + `make_parser`); not affected by
  the rebuild.
* **Anomaly + round-trip benchmarks** (the missing 2 of 4 from the
  original plan): can be added after the rebuild lands.
* **Trajectory disambiguation (Wave 3)**: research investment; defer
  until lexicon quality is high enough that disambiguation becomes the
  bottleneck.
* **Promote validated curation entries into the canonical Merkle
  store** (`gse/merkle/translator.py`): bridge between the curation DB
  and the canonical store; do after the curation DB has clean content.

---

## 8. Risks and open questions

### 8.1 Coverage loss

The current `data/lexicon.db` has 1.35 M LLM-generated lexemes.
External sources cover ~50-80 k words. Rebuild will lose ~95% of the
lexicon's surface lemma coverage. Mitigation: most NLP usage hits the
top ~20 k frequent words; the legacy DB's long tail of rare words is
mostly synthetic LLM noise of dubious value.

**Decision needed**: do we want a hybrid where the legacy DB serves as
fallback for words not in external sources, with a clear `source` tag
distinguishing high-quality external-grounded entries from
LLM-generated legacy entries? Or is the bipolar violation in the legacy
DB sufficient grounds to drop it entirely?

### 8.2 Bipolar exclusion may be too strict

Some words are polysemous and might legitimately activate "both poles"
in different senses. "Sharp" can mean BIG-positive (a sharp increase)
or sensory (a sharp pain) — but neither sense activates both poles of
any GSE bipolar dimension on the *same* sense. Per NSM, each sense
gets its own decomposition. Open question: does the lexicon need
per-sense rows, or is "lemma + dominant sense" sufficient for now?

Pragmatic answer: the existing schema has `sense_id` (default '01').
For words with strong polysemy, we can populate multiple sense rows
later. The rebuild treats one-sense-per-lemma as the default.

### 8.3 Source disagreement is information

Some words will have sources that *contradict* on a primitive. The
existing voting logic resolves by majority + confidence. The
`external_disagreements` table is designed to record these. We should
make sure disagreement records flow through during the rebuild and are
queryable — useful diagnostic data for later analysis.

### 8.4 Re-population compute cost

Loading all 18 sources from disk is on the order of 30-60 seconds
(measured in this session for the sample run). Voting + writing
50-80 k lexemes is on the order of 5-10 minutes. Not prohibitive.

### 8.5 Backwards compatibility

Any module currently consuming `PRIMITIVE_REGISTRY` indirectly via
`GSEEncoder._lookup_lexeme` will see different vectors after the
rebuild. We expect:

* Test suite breakages where tests pin specific cosine values from the
  LLM-generated decomposition.
* Improvements where tests check theoretical properties (antonym
  opposition, role binding).

The plan is to fix breaking tests *case by case*, treating each as
either (a) a test that was inadvertently testing LLM noise, or (b) a
genuine regression to investigate.

---

## 9. Execution order (the actual rebuild sequence)

1. **Land this document.** No code runs until approved.
2. **Add the bipolar-exclusion module + tests** without touching the
   lexicon. Verify on synthetic `ExternalWordData` fixtures.
3. **Add the new verification tests (§5.2) as expected-failure** so they
   document the target without blocking the existing suite.
4. **Dry-run the population pipeline** (§4.2.3-4.2.5) and write a JSON
   report of what would be written: lexeme count, mean primitives per
   word, bipolar-suppression counts per dimension.
5. **Surface the dry-run report** to the user. Approval gate.
6. **Archive `data/lexicon.db`** to `data/lexicon.db.legacy-YYYY-MM-DD`.
7. **Run the live population** via `populate_lexicon_from_external`.
   Time-box: 10 minutes.
8. **Run the new verification tests**. They should now pass.
9. **Run the full benchmark runner** with bank-projected metrics. Expect
   antonym min-bank negative-rate ≥ 0.8.
10. **Run the broader regression suite**. Investigate any breakages
    case-by-case (§8.5).
11. **Update `~/.claude/plans/lively-drifting-koala.md`** with the
    realized state.

Steps 1-5 are reversible. Step 6 is reversible (we kept the .legacy
file). Steps 7+ are not (re-running is cheap, but the legacy DB stays
preserved either way).

---

*End of document. Treat the construction sequence in §9 as the
authoritative checklist. If any step's invariant fails, halt and
surface — do not patch the symptom.*
