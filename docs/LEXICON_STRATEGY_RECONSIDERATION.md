# Lexicon Population Strategy — Reconsideration

> **HISTORICAL.** This document was the strategic fork that surfaced the
> need to stratify lexicon population. The path taken: a **tiered
> architecture** rather than any single one of options A–E listed in §6.
> Specifically the Tier 0 dispatch (§6 option A) was implemented; the
> sentence-architecture insight (word-scale ⊥ sentence-scale) then
> drove the word-scale boundary enforcement in `source_scope.py`.
> Tier 1 (NSM-analyzed manifest, hinted at in §6 option D) is deferred
> to a follow-up round. See `CONSTRUCTION_PLAN.md` §4.2 for the live
> tiered design.
>
> Kept for traceability — the diagnosis in §3–4 still grounds the
> shape of the solution that landed.

---

> **Status:** Retrospective + decision document. Written after the
> May 2026 attempt to fix antonym-cosine geometry via multi-source
> aggregation hit a bounded payoff. The four aggregation mechanisms
> built this session land cleanly tested in `gse/curation/external_sources/`,
> but the headline metric (per-bank cos(good, bad) ≈ −1) didn't move.
> This document is the honest accounting + the strategic fork.

---

## 1. The starting question

> Why does GSE encode "good" and "bad" as cos ≈ +0.66 globally, when
> the bipolar primitive system was supposed to put them at exact
> opposition?

Earlier in the May 2026 investigation:

- **Basis level** ✓: `cos(GOOD basis vec, BAD basis vec) = −1.0000`
  exactly. The math is correct.
- **Per-bank** at EVAL: `cos(good, bad) | EVALUATORS = +0.002` — *not* −1.
- Diagnosis: `good` and `bad` in the LLM-populated `data/lexicon.db`
  both have **BIG = −1** in their EVAL bank (alongside the correctly
  opposed GOOD axis). Their EVAL-bank vectors agree on the SIZE axis
  → opposition on the GOOD axis cancels exactly.

The user's request: rebuild from deterministic source materials,
discard the LLM lexicon, and get cos(good, bad) at EVAL bank to
approach −1.

---

## 2. What was built (mechanisms 1–4)

Per-session timeline, with rationale and outcome:

### 2.1 Confidence-weighted voting (`weighted_voting.py`)
Ported the formula from the legacy
`scripts/rebuild_lexicon_from_sources.py` (lines 240-255). Sums
confidences by sign, cross-source agreement boost, source-prior
override. **9 tests pass.** Sound on synthetic inputs.

### 2.2 Bipolar mutual-exclusion (`bipolar_exclusion.py`)
For each of the 14 BIPOLAR_PAIRS, if both poles arrive active, keep
the higher-confidence pole and record the suppression. **14 tests
pass.** Solves the within-word "both poles active" pattern (e.g.,
"near" having both NEAR=+1 AND AWAY=+1).

### 2.3 Wiktionary v2 loader (`wiktionary_v2.py`)
Reads the pre-built 886MB v2 DB (`word_primitives_v2` joining
`primitive_dictionary`). 1.35M words, source-grounded via
definition-keyword patterns, no LLM. Per-vote confidence available.
**13 tests pass.** Registered as primary lexeme source.

### 2.4 Per-source primitive scope (`source_scope.py`)
Each external source restricted to its semantically-appropriate
primitives. Empirically derived from a 50-word diagnostic showing
NRC VAD voting on LOGICAL primitives (a category error). **9 tests
pass.** Plus NRC VAD parser bug fix removing the Arousal → INTENSITY
and Dominance → CAN/MUST mappings.

### 2.5 Wiktionary scaffolding filter (`wiktionary_v2.py:_compute_scaffolding`)
Drops primitives Wiktionary votes for on > threshold of vocabulary
(default 80%). Logic is sound. **Default threshold finds zero
primitives to drop on the real DB** — see §3.

---

## 3. The empirical failure

After all four mechanisms are in place, the geometry on canonical
bipolar antonym pairs:

| Pair | Target bank | Bank-projected cosine | Should be |
|---|---|---|---|
| big / small | EVALUATORS | **−1.000** ✓ | −1 |
| beautiful / ugly | EVALUATORS | **−0.706** ✓ | −1 (some shared context OK) |
| good / bad | EVALUATORS | **+0.002** ✗ | −1 |
| happy / sad | EVALUATORS | **+0.002** ✗ | −1 |
| near / far | SPATIAL | **+0.286** ✗ | −1 |
| inside / outside | SPATIAL | **+0.333** ✗ | −1 |
| above / below | SPATIAL | **+0.009** ✗ | −1 |
| alive / dead | ACTION | **+0.941** ✗ | −1 |
| before / after | TEMPORAL | **+0.599** ✗ | −1 |
| true / false | LOGICAL | **+0.635** ✗ | −1 |

Two out of ten pairs work (big/small, beautiful/ugly). The rest
remain stuck because the EVAL/SPATIAL/ACTION/TEMPORAL/LOGICAL banks
have shared non-bipolar primitive activations across each pair.

Concretely, the `good` and `bad` decompositions after the full
pipeline (weighted vote + scope + exclusion + scaffolding filter at
default threshold):

```
good EVAL: {GOOD: +1, BIG: -1}
bad  EVAL: {GOOD: -1, BIG: -1}
```

The GOOD axis opposes correctly; the BIG=-1 component is identical;
they cancel. The fix is one BIG=-1 vote on each — confidence 0.595
exactly from Wiktionary, the signature of a default keyword pattern
firing too broadly.

---

## 4. Why aggregation hit a bounded payoff

### 4.1 Wiktionary's frequency distribution doesn't match a "scaffolding" model

I expected scaffolding primitives (BE, SOMETHING, etc.) to appear on
> 80% of words. Empirically they don't:

```
SOMETHING:  75.2%
SOME:       31.6%
MUCH:       30.6%
BE:         25.1%
DO:         22.8%
...
BIG:         4.8%  ← the polluting vote, well below any frequency threshold
SMALL:       0.0%
```

The 80% default does nothing. Lower thresholds (30% or 50%) would
drop SOMETHING/SOME/MUCH/BE but would still leave BIG=-1 in place
since it's only on 4.8% of words.

### 4.2 The pollution is confidence-driven, not frequency-driven

Every Wiktionary "BIG=-1" vote has confidence **exactly 0.595** —
that's one rule firing across 65,000+ semantically-diverse words.
A confidence threshold of e.g. 0.7 would drop these. But:

- That's a different filter than "frequency of vote."
- It targets the SYMPTOM (low-conf rule), not the underlying issue.
- It's a 5th mechanism on top of 4 that haven't moved the metric.

### 4.3 Cross-word agreement on non-bipolar primitives is structural

Even with all 4 mechanisms, the EVAL bank ends up with shared BIG=-1
on every evaluative antonym pair because one Wiktionary rule taps
into a definitional template common to "good", "bad", "happy",
"sad", etc. Aggregation across imperfect sources, no matter how
carefully filtered, will produce *some* cross-word agreement on
spurious dimensions. The mechanism count needed to reach
cos ≈ −1 keeps growing.

### 4.4 The anti-pattern of approach cycling

Four mechanisms added, headline metric unchanged. The texture is
"one more filter and we'll get there" — that's the pattern. The
premise (multi-source aggregation produces the geometry we need)
is what's wrong, not any individual mechanism.

---

## 5. What to keep from the work built

The four mechanisms are not wasted; they're useful for the **other
1.35M non-bipolar words**. The bipolar primitives are 28 words. The
rest of the lexicon needs *some* mechanism for assigning primitive
decompositions, and aggregation with these filters is a reasonable
approach for content words whose semantics don't have a clean
theory-grounded canonical form.

Concrete: any future strategy retains:

- `weighted_voting.py` — the formula is sound
- `bipolar_exclusion.py` — guard against the "both poles" violation
- `wiktionary_v2.py` (loader + scaffolding filter) — the spine source
- `source_scope.py` — domain restriction
- The NRC VAD parser bug fix — that's just correct now
- The `populate_with_voting_and_exclusion` orchestrator — connector

These remain in the codebase; they're tested. They're just not
sufficient on their own for the 14 bipolar dimensions.

---

## 6. Alternative strategies

### A. Canonical hand-authored bipolar decompositions

**Premise:** the 14 bipolar dimensions are theory-anchored. They
shouldn't be discovered via aggregation — they're definitional.
Hand-author 28 sparse decompositions (`good = {GOOD: +1}`,
`bad = {BAD: +1}`, etc.) and an override layer that says "if the
word matches a canonical bipolar primitive, use the canonical
decomposition; otherwise use aggregation output."

**Pros:** Guaranteed cos(good, bad) = −1 at EVAL bank. Concrete and
small (~30 LoC + 28-entry fixture file). The aggregation work
remains valid for non-canonical words.

**Cons:** Doesn't address the cross-word pollution problem for
near-bipolar conceptual antonyms (happy/sad, beautiful/ugly,
brave/cowardly) — those still go through aggregation and inherit
its noise. Could be extended with a "canonical antonym set" beyond
the 14 dimensions.

**Effort:** ~1 hour.

### B. Confidence-thresholded Wiktionary-only

**Premise:** Wiktionary v2 is the cleanest, most-grounded, broadest
source we have. Drop multi-source aggregation entirely; use
Wiktionary alone with a confidence floor (e.g., ≥ 0.7) to filter out
the "default rule firing" pattern.

**Pros:** Conceptual simplicity — one source, one filter. Removes
all the cross-source noise. The pre-built v2 DB already has
per-vote confidence.

**Cons:** Loses the multi-source validation signal. Some primitives
have genuine evidence from NRC/Lancaster/etc. that's discarded.
Confidence threshold of 0.7 is a guess; would need calibration.

**Effort:** ~2 hours (build the wrapper, validate against the
canonical bipolar pairs, tune threshold).

### C. Source-as-evidence, not source-as-decomposition

**Premise:** invert the strategy. Hypothesize the decomposition
from theory (or per category) and ASK sources to verify. A primitive
is committed only if at least one source provides direct evidence
for it.

**Pros:** Most rigorous. Avoids "vote for a primitive because some
rule fires" — the rule has to provide concrete support. Aligns with
the sparse-wiki-grounding pattern of using sources for verification.

**Cons:** Requires a hypothesis-generation step (where do candidate
decompositions come from?). The legacy LLM lexicon is one source
of hypotheses (after stripping the obvious noise), but that's
circular. Could use Wiktionary definitions as the hypothesis source
and other sources as verifiers.

**Effort:** Substantial — multi-day. Real research direction.

### D. Hybrid: A + Wiktionary-only for the 1.3M

**Premise:** Combine A (canonical override for bipolar primitives
and theory-anchored content words) with B (Wiktionary-only with
confidence threshold) for everything else. The other 4 sources are
retired.

**Pros:** Most defensible. Theory-anchored where theory exists;
empirically-grounded where it doesn't. Removes the aggregation
machinery once verified to be redundant.

**Cons:** Significant restructuring. The integrator changes role.
Need to define which content-word categories get canonical
treatment beyond the 14 bipolar dimensions.

**Effort:** ~3-5 hours.

### E. Step further back: redesign the lexicon model entirely

**Premise:** the (word, primitive, value) flat decomposition may be
the wrong representation. Words have senses, context, polysemy. A
single decomposition per lemma can't capture this. The right model
might be (word, sense, primitive, value) with sense disambiguation
done at encode time.

**Pros:** Could resolve much of the per-word noise (sense conflict).
Aligns with NSM theory (decompositions are per-sense).

**Cons:** Major architectural change. Most of the existing code
assumes lemma-keyed lexemes.

**Effort:** Research/redesign phase, not implementation.

---

## 7. Recommendation order to evaluate

Without prescribing the answer, here's the order I'd evaluate the
options in:

1. **A first.** It's small, it directly resolves the headline
   problem for the 28 canonical bipolars, and it doesn't preclude
   any of the others.
2. **A + run the existing aggregation for the rest.** See if
   non-canonical pairs (happy/sad, beautiful/ugly) come out
   acceptably with the current 4 mechanisms in place. They might
   — the EVAL bank pollution from Wiktionary affects bipolar
   primitives specifically because Wiktionary's keyword templates
   correlate evaluative-adjective definitions with BIG=-1.
3. If happy/sad still has EVAL ≈ 0, evaluate **B** vs **D**.
4. **C and E** are research directions; revisit after the
   immediate question is resolved.

---

## 8. What does NOT need a decision right now

- The existing four mechanisms stay in the codebase. They're tested
  and documented. None of the strategies above require removing them.
- The construction plan at `docs/CONSTRUCTION_PLAN.md` is still the
  authoritative source for the rebuild's *infrastructure* (archive
  step, schema, provenance). Only the §4.2.4-5 population strategy
  changes per the chosen path above.
- `data/lexicon.db` remains untouched. No archive, no rebuild, no
  irreversible action has run.

---

## 9. Open question for the user

Which of A–E (or a combination) should drive the next round?

The recommendation in §7 is A first as a small, reversible
experiment that directly addresses the headline metric and informs
whether further steps are needed. But this is your call.

---

*End of document.*
