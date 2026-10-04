# The Janus Figure System — Specialty SoM for Rhetorical-Figure Recognition

> **Status: build spec (2026-06-21).** The concrete implementation of the Janus
> two-faced architecture (`JANUS_MODULE_DESIGN.md`) as a specialty Society-of-Mind:
> a closed set of constitutively-relational rhetorical figures, recognized by
> comparing a *deductive* symbolic face against an *inductive* learned face — both
> grounded to the same GSE relational profile. This doc is the backbone: the closed
> figure enum, the data contract, and the build order. Per CLAUDE.md, docs are not
> ground truth; Rohan + the code are.
>
> **Corrects** `JANUS_MODULE_DESIGN.md` §2/§4 and `papers/.../janus_two_faced_meaning.md`
> §4, which describe Face B as a *symbolic aggregate* (per-register contour). That is
> the collapse case. Face B is a **learned network over the GSE profile** — induction,
> not averaging. A correction pass to those two documents is pending.

---

## 1. The architecture, corrected

Everything — every input span — is first ground through the GSE pipeline to a fixed
relational profile (`gse/discourse/profile.py::text_profile` → `TextProfile.vector()`:
operator mix, complexity, coherence, affect, register, 72-prime signature). That
profile is the **bounded, finite-VC hypothesis space** in which both faces live. The
two faces differ by *epistemic method*, not by input:

- **Face A — deductive (symbolic).** What GSE's resolution rules directly conclude the
  span means: its typed operator, its valence sign, its intensity magnitude, whether a
  `TypeAssertion` coheres, whether a comparison marker is present. The literal,
  definitional, *imperfect* reading. The version-space **S-boundary** (most specific).
- **Face B — inductive (learned).** A network trained on figure-labeled examples that
  recognizes the *distributional shape* of each figure **in GSE-profile space**. Not a
  rule; a learned generalization. The version-space **G-boundary** (most general). The
  PAC learner proper.
- **The comparator (the head).** Compares A and B. Agreement → the literal reading
  stands. A *characteristic* disagreement → the figure named by its signature. Output
  is a PAC-shaped `(ε, δ)` object: ε = the A-vs-B divergence magnitude, δ = the joint
  confidence; the genuine-ambiguity zone (low δ) is reported, not forced.

**Why grounding Face B to the GSE profile (not raw text) is load-bearing:** it forces
the learner into the bounded space, which is the PAC precondition for sound
generalization. A raw-text learner is unbounded — both faces distributional — the
collapse the thesis indicts in LLMs. One bounded grounding, two methods over it.

---

## 2. The closed figure set (the enum / anchor vocabulary)

A **closed basis**, disciplined like the lexicon and **grounded in two research passes**
(2026-06-21) against the linguistics, not improvised. The single source of truth is
`gse/pragmatics/figures.py`; this table mirrors it.

**The admission criterion** (Silva Rhetoricae, traceable to Quintilian) is a four-way
cut. A figure is a **trope** — and so IN the set — iff it turns word *meaning*
(literal ≠ intended). It is OUT if it is a **scheme** (rearranges words), **wordplay /
metaplasm** (alters form/sound), or a **pragmatic** phenomenon (implicature / speech
act). So `apostrophe` (an address-act), `pun`/`paronomasia` (form), `zeugma`
(arrangement), and `innuendo` (implicature) are deliberately excluded; `allegory` is
deferred (its merge-into-metaphor status did not survive verification).

The set has **two kinds**: **tropes** (constitutively relational) and an **appeals /
reasoning** sub-group (`is_trope=False`) — modes of persuasion (Aristotle's pisteis)
and figures of reasoning, kept because the goal is to resolve *all sensible modes of
communication*, not only tropes.

**Banks ARE the relation families** that license each trope (Jakobson's
similarity/contiguity; Radden & Kövecses' metonymy-as-access with synecdoche =
part-for-whole; irony as **echoic/attributive**, not "say the opposite"; metaphor ≠
hyperbole). The bank is also *Face A's tell*. The `refines` column is the subsumption
lattice the resolution voting propagates over (§5).

| bank (licensing relation) | figures (`refines →`) | Face A's tell |
|---|---|---|
| **similarity** | metaphor · simile · personification→metaphor · catachresis→metaphor | a `TypeAssertion` that fails coherence; a cross-domain mapping |
| **contiguity** (whole-part / part-part) | metonymy · synecdoche→metonymy · antonomasia→metonymy · metalepsis→metonymy | grounded referent ≠ selectional fit; an *associate* fits |
| **attribution** (echoic) | verbal_irony · sarcasm→verbal_irony | literal reading clashes with the *attributed/expected* reading (Face A vs Face B) |
| **magnitude** | hyperbole · understatement · litotes→understatement · meiosis→understatement · auxesis→hyperbole | intensity inflation / damping vs. situation |
| **valence** | euphemism · dysphemism | word-valence ⟂ world-salience (sparse-wiki) |
| **inversion** (Semantic Inversions) | oxymoron · paradox · humor_gardenpath · rhetorical_question | self-contradiction, commitment reversal, or form↔function flip |
| **appeal** *(non-trope)* | logos · pathos · ethos · postulation | operator/affect/source mix (not a meaning clash) |
| **baseline** | literal | A and B agree — the null class + matched negative set |

**26 classes = 21 tropes + 4 appeals + `literal`, across 8 relation-family banks.**
`humor_gardenpath` and `euphemism`/`dysphemism` are gated (TMS, sparse-wiki) — Face B
learns their shape now, the deductive tell completes when the capability lands.

**Two honesty reframes (from the research) that the comparator and the paper carry:**
1. **The discrete set is an engineering ontology of *resolution targets*, not a claim
   about psychological natural kinds.** Relevance theory's continuum (literal → loose →
   hyperbole → metaphor via one ad-hoc-concept mechanism) is real but *orthogonal* to an
   operational taxonomy; the defense (Romero & Soria; Carston & Wearing's distinct
   metaphor/hyperbole processing) holds for resolution. Burke: tropes "shade into one
   another" → overlap is expected → **multi-label**.
2. **The Gricean coherence-violation→repair is operational, not consensus cognition.**
   Grice classes irony/metaphor/hyperbole as Quality-flouting implicatures, but
   *flouting under-determines which figure is in play* — so the relational poles are the
   load-bearing disambiguator. And the Janus **parallel** two faces (deductive ∥
   inductive) sidestep RT's "no literal-first" objection: there is no serial literal-
   then-repair step, both faces run at once.

---

## 3. The data contract (bootstrap → hand-curate)

Method is the two workflow docs (`STRUCTURED_WEB_KNOWLEDGE_EXTRACTION.md`,
`PERSISTENT_KNOWLEDGE_GROUNDED_DATABASES.md`), applied verbatim — not reinvented.

**Cardinal rule (inherited): the LLM is the parser, not the source.** We harvest
*attested* examples of each figure from sources that already label them; the LLM
extracts `(figure, example, definition, span)` — it does **not** generate irony. An
LLM generating its own irony would train Face B on the LLM's notion of the figure,
contaminating the exact thing under test. Synthetic / hand-authored is the documented
fallback, not the default.

**Bootstrap sources** (attested, labeled): Silva Rhetoricae (rhetoric.byu.edu),
literary-device glossaries, rhetoric / AP-Lang textbooks, annotated literature; plus
the clean academic corpora where they exist (VU Amsterdam Metaphor Corpus, TroFi for
metaphor; SemEval-2018 Task 3, SARC for irony/sarcasm; SemEval-2007 Task 8 for
metonymy; SemEval-2017 Task 7 for puns/humor). These are noisy, sentence-level, and
single-figure — so they are **candidate pools**, not the dataset.

**Then hand-curate** (the decision: quality over volume for the prototype):
- **Clean** — each example unambiguously *is* its figure(s); reject genuinely borderline
  cases, but **multi-label is expected** (pen/sword = metaphor ∧ metonymy) — record every
  figure that applies, each with its own confidence and clearance.
- **Balanced** — comparable counts per figure, and a matched `literal` set per figure
  (the minimal contrast — same topic/register, no figure — so Face B learns the figure,
  not the topic).
- **Paragraph-scale** — enough context that the figure is *recoverable* (irony needs its
  frame); trim to the minimal sufficient span.
- **Provenance** — every example carries source URL + span + a confidence, in a shadow
  ledger (workflow doc 1 §10). The figure *definitions* are Mode-1 canonical reference
  (workflow doc 2 §7–8: `patch_field`, audit log, required `reason`).

**Typed-skeleton enforcement** (workflow doc 1 §3a): the extraction schema's `figure`
field is an `enum` over §2 — the LLM can only *select* a known figure, never invent a
label. Bank-organized passes (one bank's figures presented at a time) prevent
cross-figure contamination during extraction.

**Store** (bi-modal, workflow doc 2 §2): `data/janus_figures.db` —
`figure` (canonical defs + bank), `figure_example` (the curated labeled spans + GSE
profile vector + provenance), `figure_shadow_ledger`. Same join discipline as the
other grounded DBs.

---

## 4. Face B — the learned inductive face

Extend the existing SoM, do not build a new model type (`gse/discourse/nested_router.py`
is the recognizer; `klines.py` the pattern store). Face B:

- **Input** = `TextProfile.vector()` of the span (the grounded profile — §1). No raw
  text. This is the bounded space.
- **Architecture** = the nested-SoM recognizer pattern, repurposed: a per-bank
  specialist over each bank's figures, dispatched by register, descending to the figure
  leaf — the same confidence-gated descent (`predict_paths`) already built. Figures are
  the new leaves; the banks are the internal nodes.
- **Training** = the curated `figure_example` vectors (§3), the three-stage curriculum
  already in `train_router`. Small models, the existing recipe — this is a
  diagnostic-scale prototype, not a production run (the flywheel discipline:
  `project_l2_voice_modes_flywheel` — do not chase accuracy; demonstrate the shape).
- **Output** = per-figure activation + confidence (the inductive read, with its δ).

---

## 5. The comparator + the specialty flywheel

- `gse/pragmatics/janus.py` — the comparator. **Multi-label, resolved by ternary
  set-theory voting** (the OTP interference the lexicon already runs — *reuse*
  `weighted_voting`/the integrator, do not build a new voter). Each face emits a ternary
  vote per figure: `+1` asserted, `−1` considered-and-excluded, `0` orthogonal/OOV. The
  combined score is the sum of the two faces' votes, **propagated up the subsumption
  lattice** (`figures.with_supertypes` — a `synecdoche` vote also credits `metonymy`):
    - `+2` (both assert) → **confirmed** figure;
    - `+1, −1` (faces conflict) → `0`, **cancels** — not asserted;
    - `0, 0` → orthogonal; `−2` → confidently absent.
  So two faces both → `{X, Y}` confirms both (`[+2, +2]`); faces sharing one and
  differing on the rest resolve to the shared label by clean cancellation (`[0, +2, 0]`);
  no overlap → all cancel → **abstain** (the honest-uncertainty zone). The paper's
  `(ε, δ)` is this vote vector read two ways: ε = peak score magnitude, δ = how cleanly
  it peaks. The output is the confirmed label *set*, not a single figure.
- `scripts/janus_flywheel.py` — the specialty flywheel, mirroring `scripts/flywheel.py`:
  rebuild the figure corpus → train Face B → **audit the A-vs-B separation per figure**
  (does ε pull each figure away from its matched `literal` set?) + the failure shapes
  (figures A-vs-B can't separate → the worklist). The deliverable is the separation
  *shape*, not an F1.
- `tests/test_janus.py` — the comparator contract + one curated example per figure as a
  regression anchor.

---

## 6. Build order

1. **This spec** + the figure enum as code (`gse/pragmatics/figures.py`: the closed set
   + bank map + per-figure Face-A tell). Unblocks everything.
2. **Data**: bootstrap-gather → hand-curate → `data/janus_figures.db` with provenance.
   *(The next heavy step; parameters open — see below.)*
3. **Face B**: extend the nested SoM; train on the curated vectors.
4. **Comparator** + **flywheel** + **tests**.
5. **Correction pass** on `JANUS_MODULE_DESIGN.md` + the paper (Face B = learned, not
   aggregate).

## 7. Open parameters (confirm before the data marathon)

- **Per-figure target count** for "quality over volume" — e.g. ~30–50 curated examples
  per figure + a matched `literal` set? (Sets the size of the curation effort.)
- **Source whitelist** — start the bootstrap from which sources, and do we run the live
  extraction pipeline (SearXNG/Tavily + local Ollama, per workflow doc 1) or curate from
  known-attested examples first and add the pipeline once the schema is proven?
- **Curation gate** — who is final-checker on "this example cleanly is figure X"
  (human-final-check, per the workflow docs' propose-only discipline).
