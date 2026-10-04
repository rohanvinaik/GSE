# The Janus Module — Two-Faced Pragmatics (Irony, Humor, and the Subjective Tail)

> **Status: design, not result (2026-06-21).** A real design spec for the
> top-level (L3) pragmatics layer — irony, sarcasm, understatement, humor — modeled
> as the *disagreement between two faces* over GSE's existing deterministic
> substrate. Tier 0 is buildable now on parts already in the tree; Tiers 2–3 name
> their real dependencies (a commitment TMS, the world/value model) honestly. Per
> CLAUDE.md, docs are not ground truth; Rohan + the code are. File:line references
> were current at writing — verify before editing.
>
> Supersedes the irony sketch in `GSE_vision.md §IV½` and the L3 notes in
> `ROADMAP.md` by giving them a single mechanism. Reads the SoM/flywheel
> architecture in `project_l2_voice_modes_flywheel` as its host.

---

## 0. The one idea

Some semantic signals are **not properties of the text, nor of the world model, but
of the *relationship* between them.** Irony is the canonical case: the words say one
thing (`"Oh, wonderful"` — `wonderful`: GOOD +1), the situation expects the
opposite (a `doom`/`terrible` frame — BAD +1), and *the clash itself is the
meaning.* No single-face system can represent this, because **the signal is the
disagreement** — a bottom-up reader calls it positive (wrong), a top-down reader
calls the whole frame negative (wrong); only the *gap* is right.

So we model these signals from **two faces** — Janus, the god of doorways, who looks
both ways at once (and whose faces point in *opposite* directions, exactly as
literal and intended meaning do in irony):

- **Face A — structural / literal** (bottom-up, intrinsic): what the grounded words
  and the local clause structure actually say.
- **Face B — global / world** (top-down, extrinsic): what the register, frame, and
  world-grounding say *should* be here.

The module's output is **the relationship between the two faces**, including — and
this is the load-bearing part — a *calibrated uncertainty* when they are near-tied.
Irony is the signal where even humans disagree; a two-faced model can report
disagreement *by a measured amount* where a one-faced model must fabricate a label.
That honesty is the same epistemics GSE already ships in the IV-E abstention layer,
turned on a new axis.

---

## 1. Why two faces is *correct*, not convenient

The double-dissociation argument the vision doc uses for the four criteria applies
here too — each single face fails in a direction the other catches:

| reading | `"Oh, wonderful,"` in a disaster | a genuine compliment inside a rant |
|---|---|---|
| **Face A alone** (literal affect) | ✗ calls it positive | ✓ positive |
| **Face B alone** (register expectation) | ✓ negative frame | ✗ calls the aside negative too |
| **Janus (A vs B)** | ✓ A:+ vs B:− → **sarcasm** | ✓ A:+, B:+ → **sincere** |

Neither face is sufficient and neither is wrong — they measure different things. The
*relationship* is the only place the answer lives, and it is also the only place the
**uncertainty** lives: a single face must commit; two faces can be close, and their
closeness *is* the "nobody's sure" regime, measured rather than guessed.

---

## 2. The substrate is already built

The Janus module is a **comparator over two existing layers** — almost no new
representation, by design (the roadmap's "irony falls out of the coherence engine —
no new module," made concrete).

### Face A — structural / literal (intrinsic)

Already produced by `gse/discourse/profile.py` and the symbolic core:

- **valence** — per-word `GOOD − BAD` from `encoder._lookup_lexeme` (profile.py:134),
  aggregated as `affect.valence_mean / valence_spread / valence_arc` (profile.py:163).
  The **sarcasm channel.**
- **intensity** — the gradable/hierarchy magnitude from the quantifier-intensifier
  work (`vectors_v2.encode_hierarchy`, `HIER_PLUS/MINUS`; `mild` vs `extreme`). The
  **understatement / hyperbole channel.**
- **local structure** — the typed operator the clause resolved to, plus
  `KLineStore.complete_pattern` (klines.py:164) voting the *expected* primitive
  completion from the local pattern. The **garden-path / commitment channel**
  (Tier 2).
- **confidence** — clean coherence (`coherence_report` returns no degraded clause)
  ⇒ Face A is confident in its literal reading.

Face A *is* the `GSE_vision.md §IV½` PoC, promoted to one face of a pair.

### Face B — global / world (extrinsic)

Already produced by the trained Society-of-Mind dispatcher:

- **register path** — `NestedRouter.predict_paths` (nested_router.py:120) descends
  `all-text → super-register → genre`, with a confidence per step. This is the
  compressed world-model: "this is a eulogy / a rant / a wire report."
- **expected contour** — for the resolved register node, the *normal* affective and
  operator profile (Tier 1: a learned per-node k-line; Tier 0: a static prior). The
  same `text_profile` banks, aggregated per register instead of per document.
- **world intensity & benignity** (Tier 3) — the referent's potency from
  `sparse-wiki` (the *gravity* of `death`, not in the word) and the cost/safe split
  from the Genesis value model.
- **confidence** — the dispatcher's descent confidence (a document the SoM can only
  resolve to a shallow node yields a *weak* Face B, which correctly widens the
  uncertainty band).

### The head — the coherence comparator

The **same propose→veto / coherence primitive** GSE runs at every other scale, now
run *between two k-line activations* (Face A's local completion vs Face B's
register-expected completion) instead of within one clause. Recognizing irony is
structurally identical to recognizing a degraded clause: *does this cohere with what
was expected; if not, what is the bounded reinterpretation?* — only the scope is the
whole span and the expectation is the world face.

---

## 3. K-lines over the whole SoM (the Janus framing)

Each face is a **k-line ensemble**, and they run over the *entire* trained SoM, not a
bolted-on classifier:

- **Face A k-lines** — the existing `KLineStore`: stored `(primitive, polarity)`
  co-activation patterns that complete the local affective/structural reading.
- **Face B k-lines** — a **new per-register expectation layer**: for each node in the
  `taxonomy_tree`, the learned "what affect/operator contour is normal here." This is
  the natural twin of the Genesis rule-ground-per-node idea — each register node
  already inherits a *repair-script* stack down its root-to-leaf path
  (`project_l2_voice_modes_flywheel`); it now *also* inherits an **expectation
  profile** down the same path. Recognition (the nested router) and expectation (the
  Face B k-line) are the two payloads at every node.

The Janus head compares the two activations. So the apex pragmatics reuse the exact
machinery — k-lines, nested routing, the coherence gate — that the comprehension
stack is already built from. **The module is ~200 lines of comparator over thousands
of lines of existing substrate.**

---

## 4. Naming the phenomenon from the *type* of disagreement

| disagreement | Face A | Face B | phenomenon |
|---|---|---|---|
| **valence sign-flip** | GOOD +1 | BAD expected | **sarcasm** |
| **intensity magnitude-clash** | mild (INTENSITY −1) | extreme expected | **understatement** (or **hyperbole**, sign reversed) |
| **structural garden-path** | committed to reading-1 | wider scope forces reading-2 | **verbal joke / pun** (Tier 2) |
| **agreement** | +/− | same | **sincere** (no irony) |

The output is not a label but a **graded relational reading**:

```
disagreement(axis) × confidence(Face A) × confidence(Face B)
```

- both faces confident **and** opposed → strong irony/sarcasm.
- one face weak (e.g. the SoM only reached a shallow register node) → wide
  uncertainty band → the module reports *"possible irony, low confidence"* rather
  than committing.
- faces near-tied → the genuinely-ambiguous regime → **graded abstention**, the same
  honest signal as `grounding_flags` in IV-E (`gse/symbolic/grounding.py`): GSE
  already separates *"I built the logic"* from *"I could ground the words"*; Janus
  adds *"the two faces agree / clash / are genuinely uncertain."*

---

## 5. Humor maps straight on

The roadmap's humor theory (*"the felt reward for safely catching that your own model
made a premature, locally-coherent commitment that wider scope invalidates"*) is a
Janus signal with one extra gate:

- **self-caught commitment-error (garden-path)** — Face A *commits* (high structural
  confidence on reading-1 via the local k-line completion); Face B's wider scope
  *invalidates* it; the resolution snap is the comparator flipping. The mirth =
  Dennett/Hurley's "reward for debugging your just-in-time model" = the magnitude of
  the *corrected* disagreement. This is why humor needs the **commitment record**
  (Tier 2): Face A must have *committed* for there to be an error to catch.
- **benignity (McGraw benign-violation)** — a **gate on Face B**: the *same* A/B clash
  routes to **fear** if the world/value model flags the caught error as costly, to
  **humor** if safe. Benignity is a Face-B (world) property — which is exactly why
  humor is frame-dependent (L2/L3), as the roadmap says.
- **the two tiers** — a *primitive* benign-violation tier (the clash is on the affect
  axes — funny faces/dogs, no committed model) vs a *cognitive* garden-path tier (the
  clash is on the structural/commitment axis — verbal jokes, irony). Same head;
  differ only on which Face-A channel the clash lands in.

Generation = *construct* a controlled A/B clash (a garden-path setup whose punchline
forces Face B's reinterpretation) — comprehension's own machinery run backward, the
vision doc's §VI reversal. Un-prompted joke generation is the apex, gated on the
WIN-oracle question.

---

## 6. Implications for physics-based & world-grounded AI

Generalize past language. A **Janus signal** is any quantity that is *constitutively
relational* — defined by the gap between an intrinsic/local measurement and a
contextual/global expectation:

- **Face A** = the intrinsic / local / structural invariant (the thing measured in
  isolation).
- **Face B** = the field / context / world-grounded expectation *at that point*.
- **observable** = the phase / disagreement between them, carrying an uncertainty
  from the *joint* confidence of the two faces.

This is the same shape as several deep patterns, and the resemblance is the argument
for the form, not decoration:

1. **Gauge / field structure** — a local quantity is only meaningful against a
   connection that says what "the same value" means elsewhere; the physics is in the
   *difference* (the curvature), not the local value. Face B is GSE's connection;
   irony is its curvature.
2. **Predictive coding / active inference** — perception is prediction-error =
   bottom-up sensory signal vs top-down prediction. Face A is the sensory signal,
   Face B the prediction, the comparator the error unit. **GSE gives a *computable,
   auditable, deterministic* instance of prediction-error-as-meaning** — and irony is
   its sharpest linguistic case (the place the error is the whole content).
3. **World-grounded model honesty** — the dominant failure mode of world-grounded /
   embodied models is *confident confabulation*: a single head forced to emit one
   label. The Janus form is a template for representing subjective / genuinely-
   uncertain properties **without fabricating certainty** — report the two faces and
   their disagreement; abstain in the graded middle. The one thing the architecture
   refuses to do (collapse a real two-faced ambiguity to a fake single answer) is
   exactly the thing fluency-first systems do *unreliably* anyway.

The honest claim: GSE's coherence primitive, applied between an intrinsic and a
world-grounded face, is a **general, inspectable mechanism for the
constitutively-relational tail** of understanding — of which irony/humor are the
linguistic proof-of-concept.

---

## 7. Build plan — honest tiers

Each tier is a real boundary; Tier 0 is genuinely a now-thing.

- **Tier 0 — the PoC, buildable now.** Face A (sarcasm = valence sign-clash;
  understatement = intensity magnitude-clash) over the `affect` bank + a **static**
  per-super-register expectation prior (the SoM already hands you the register; the
  contour is hand-set for the ~10 super-registers) + the coherence comparator +
  graded abstention. Sentence / short-context. **Demonstrates the *form*** — two
  faces, disagreement-as-signal, calibrated uncertainty — which is the proof-of-
  concept the vision doc §IV½ marks as "design, not result," now *running*. No L2
  TMS, no Genesis. Proposed home: `gse/pragmatics/janus.py` (reads `discourse` +
  `symbolic.coherence`); tests in `tests/test_janus.py`; a `gse.demo.irony` showcase.
- **Tier 1 — learned Face B.** Replace the static prior with **per-register
  expectation k-lines** mined from the *same flywheel corpus* (the contour is just
  another aggregate of `text_profile`, grouped per register node and inherited down
  the taxonomy). Face B becomes data-driven and self-extends with the flywheel.
- **Tier 2 — the commitment axis (humor proper).** Add the **TMS** — the engine
  recording its own just-in-time commitments — so a garden-path *error to catch*
  exists. This is the L2 truth-maintenance build the roadmap names (JTMS/ATMS); it is
  real work, not a wrap-up.
- **Tier 3 — benignity + world intensity (the apex).** Wire `sparse-wiki` potency into
  Face B's intensity channel and the Genesis value model into the benignity gate (the
  cost/safe split). Enables the fear-vs-humor routing and, run backward, un-prompted
  joke generation.

**Honest scope, unchanged:** Tier 0 proves the *mechanism* on a shallow Face B; full
irony/humor *coverage* is bounded by how rich Face B's world-expectation model is,
which is Tiers 1–3. The form runs at Tier 0; the coverage is the build-out — the same
"the boundary is the result, the build-out is the work" the vision doc closes on.

---

## 8. What this subsumes

One mechanism — *compare a literal face to a world face, make the disagreement the
signal, abstain in the graded middle* — covers: sarcasm, understatement, hyperbole,
verbal humor, the primitive benign-violation tier, and (generalized) the whole
constitutively-relational tail. It reuses the k-line store, the nested SoM, the
coherence gate, and the abstention epistemics already in the tree. It is the L3 apex
of the L1→L2→L3 stack, and it is **two faces over one head.**
```
                       ┌─────────────── Janus head ───────────────┐
   text ──► GSE core ──┤  Face A (literal): affect + k-lines        │
            (symbolic) │  Face B (world):   register + expectation  ├──► relation
                       └────────────── coherence comparator ────────┘     + uncertainty
```
