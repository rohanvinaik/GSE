# Resolved-Structure Architecture — Build Design

> The agreed design for the next GSE lift: **emit resolved structure, not just
> parsed structure**, on the live spine (`gse.api` + `gse.symbolic`). Companion
> to `COMPLEX_SENTENCE_DESIGN.md` (which built the clause graph this resolves
> over). Authoritative source: Rohan, then the code.
>
> **Status.** Design agreed 2026-06-16. Implementation staged below.

---

## 0. The one-line reduction

Everything collapses to a single shift: GSE should **emit resolved structure,
not just parsed structure.** "Resolved" deepens in three stages:

```
   predicates  ──▶  entities  ──▶  context
   (Stage 1)        (Stage 2)      (Stage 3)
   emit the         resolve refs   resolve scope:
   clause graph     globally:      document span,
   as a stable      coreference,   genre signature,
   {op,args,        roles, type    confidence/
   features}        threads        coherence
   contract
```

The clause graph already exists (`COMPLEX_SENTENCE_DESIGN.md` — 13/13 proofs,
345 tests). This effort makes its *output* resolved: an arg stops being a bare
string and becomes an **entity reference** with stable identity and a type
genealogy; the encode unit stops being one sentence and becomes a document; and
every assignment carries a **confidence / coherence** signal.

---

## 1. The GSE ⟂ Genesis boundary (refinement, 2026-06-16)

GSE is a **standalone NLP system**. Genesis cross-enhancements live in the
Genesis project; the two are *interoperable but distinct*. The boundary:

- **In GSE:** the determinism discipline (global resolution + the coherence /
  confidence signal), document-scope encoding, and the HDC genre **signature**
  (recognition *as emission*). GSE never imports a narrative concept.
- **In Genesis:** the predicate-tree → Innerese **walker**, the archetype
  **rule-inheritance**, k-line narrative-role retrieval, the narrative-WIN
  oracle. These consume GSE's output across the §3 contract; they are not GSE's
  concern.

The seam between them is the predicate-tree contract (Stage 1). GSE emits it;
Genesis's bridge walks it.

---

## 2. The headline insight: resolve globally, not per-token (the ARC-3 transfer)

Today GSE resolves **locally** — `resolution.py` collapses a phrase to an
`Entity` within its clause; role assignment is the arc-free `_syn_roles` →
`SYN_ROLE` derivation in the encoder (from connectives + verb-inventory +
position). There is no coreference, no stable identity across mentions, no
type genealogy.

Stage 2 replaces local guessing with **global constraint satisfaction over the
contained problem** (the sentence, later the document) — the direct transfer of
ARC-3's "global resolution of specific roles in a contained problem" to
language. The resolver stays **deterministic**: a fixed-order / exact CSP with
deterministic tiebreaks, never stochastic search. Determinism is preserved by
construction, exactly as it is for every typed operator.

---

## 3. The emit contract (Stage 1) — mirror adapter-spec §5

Per `Genesis/docs/gse_innerese_adapter_spec.md` §5, a node is
`{op, args[], features{}}`:

- `op` ∈ the operator set (`TYPE_ASSERT`, `COMPARISON`, `CAUSATION`,
  `REL_RESTRICT`, `CONTROL`, `COORD`, …);
- `args[]` are **entity references or nested predicate nodes** (recursion);
- `features{}` carry `sign`, `axis`, `conjunction`, `tense`, …

This is **flatter than GSE's internal `_kind` serialization** (which stays for
GSE-internal round-trip). The emit surface is a *new, versioned entrypoint* that
walks the evaluated predicate tree into the op-keyed envelope — the gold format
Genesis's walker deserializes 1:1 over its proven `RoleFrames` constructors. The
output contract mirrors the gold shape, not GSE's richer internal ontology.

**Sequencing note.** Stage 1's *full* contract wants `args` as entity-refs
(`{entity_id, lemma, type_thread[]}`), which are a Stage-2 product. So Stage 1
ships the `{op, features{}}` envelope with bare nested structure; **args upgrade
from strings to entity-refs when Stage 2 lands.** The contract is versioned so
this is an explicit `v1 → v2` step, not a silent change.

---

## 4. Global entity & role resolution (Stage 2 — the real new engineering)

The headline. Three resolution products, emitted as the upgraded `args`:

- **(a) Coreference / stable identity.** Mentions of one referent → one stable
  `entity_id`. A proper name keeps identity even when typed — fixes
  `TypeAssertion` masking "Macbeth" as "thane" and `Control`'s untyped entity.
  *Within-sentence first (string/lemma + role-compatibility); cross-sentence in
  Stage 3.*
- **(b) Role assignment.** Which resolved entity fills subject / object /
  controller / antecedent, decided by **global** consistency over the clause
  graph, not per-token.
- **(c) Type genealogy (threads).** The entity's path (`thing → person →
  thane`), because Genesis commonsense keys off threads. **Source: WordNet
  hypernym chains** (with domain DBs — law, medicine, expanded dictionaries
  incl. proper nouns — swapped in as needed). Sense-selection is the noisy step;
  it is itself a coherence-scored assignment (§5), so a wrong sense is a
  *flagged* thread, not a silent one.

Emit shape per arg: `{entity_id, lemma, type_thread[]}`.

---

## 5. The coherence / confidence signal (Stage 3c) — the DNA-sharpened L2

The old "front-end proposes, core vetoes" becomes a **fidelity-tiered mismatch-repair
engine**, repositioned as the *confidence output of the resolver* rather than a
free-standing stack. Primitives are ported from destash `coherence.py` (weighted
composite, hard gates, jaccard, `spearman`, variance-aware confidence) — those
transfer; the two-strand wiring and the tier detectors are new GSE code.

**The flag is the pairing, not a smarter read.** Two independent reads of each
token/clause — Strand A = the GSE-native front-end's `(coarse-POS, arc-free role,
clause head)`; Strand B = GSE's own grounding (lexicon primitives + the
structural expectation the operator grammar imposes). The deterministic flag is
the *structural non-pairing* of A and B; neither strand "knows" the right answer
(mismatch repair: a flagged residual surfaced from two deterministic reads —
both strands are now deterministic, so the residual is bounded-coverage
disagreement, not stochastic noise).

**Fidelity tiers = the DNA stack, literally:**

| Tier | DNA analogue | In GSE |
|---|---|---|
| 1 — self-contradiction (~10⁻⁷, rarest, no cross-ref) | molecule disagrees with itself | predicate tree disagrees with itself: an operator whose arity can't be filled from its own clause; a `Comparison` whose args ground non-comparable; a type thread incompatible with the role. Tree-only — front-end not consulted. |
| 2 — cross-strand (proofreading) | strand mispair | Strand A vs Strand B disagree; coherence composite < threshold → flag. |
| 3 — persist | needs the next enzyme | a second independent read (alt segmentation / alt sense) still won't resolve → abstain or route. |

**Eigen's error threshold is the stopping rule.** We do **not** drive flags to
zero — a zero-contradiction encoding is fully predicted, therefore inert. The
residual is the mutation load (genuine ambiguity, novel usage, garden-path).
L2's output is **clean structure + a catalogued residual of flagged sites**, not
"cleaned text."

**Persist triage = coherence one level up.** `spearman` the flags against
covariates: correlated ⇒ a *systematic* mechanism fault (distrust a native
front-end tag-class or a lexicon row); uncorrelated ⇒ a SNP, catalog and move on.

This closes the abstention proof `COMPLEX_SENTENCE_DESIGN.md` M3 deferred — the
coherence composite *is* the ambiguity scorer the parser lacked — and the same
signal doubles as the archetype coherence-veto Genesis needs.

---

## 6. Resolved context (Stage 3a/3b — gated on Stage 2)

- **(a) Document / contextual scope.** Extend resolution from sentence to
  paragraph/document — the clause-graph recursion lifted one level (completion
  is recursion, not addition). Prereq for cross-sentence coreference (4a).
- **(b) Genre signature.** An HDC document-genre signature (GSE already lives in
  8192-dim HDC) emitted for Genesis's hierarchical archetype retrieval. GSE
  *emits the signature*; Genesis owns the archetype rules that consume it.
- sparse-wiki world-grounding (sibling project) is the connected-but-separable
  world-salience track (`word-affect ⟂ world-salience`); integrated here, not
  rebuilt here.

---

## 7. Determinism invariants (hold throughout)

1. **The global resolver is a deterministic CSP** — fixed-order / exact, with
   deterministic tiebreaks. No stochastic search.
2. **The coherence flag is deterministic** — both strands are now deterministic
   (the GSE-native front-end carries no statistical model), and the flag is a
   structural mismatch computed by integer/set ops. The residual it surfaces is
   bounded-coverage disagreement, not stochastic noise.
3. **The whole pipeline, including the parse, is deterministic** — spaCy is gone
   from the encoder/runtime, so there is no non-deterministic component left to
   quarantine. Stage 3c's mismatch-repair now catalogues the native front-end's
   *bounded-coverage* limits (inspectable, reproducible) rather than veto-gating a
   stochastic proposer. (spaCy survives only in the offline lexicon-bootstrap
   definition-parser, `gse/curation/decomposition/definition_structure.py`, which
   never runs at encode time.)
4. **Single-clause / single-sentence traces stay byte-identical** when nothing
   new fires — same back-compat discipline as `ClauseSpan` (emit new fields only
   when non-empty).

---

## 8. Milestones

- **M0 — Baseline commit. ✅** Complex-sentence build landed clean (`43b632b`).
- **M1 — Emit contract (Stage 1). ✅** Versioned `{op, args[], features{}}` emit
  mirroring adapter-spec §5; v1 bare-string args, inferred v1/v2 (`bf334bc`).
- **M2 — Global resolution (Stage 2, the headline). ✅**
  - **M2.1 ✅** stable `entity_id` (coreference by id) + entity-ref contract v2,
    DB-free via an injectable `GenealogyProvider` (`0a0647d`).
  - **M2.2a ✅** the two-strand DB-backed `GenealogyStore` — WordNet word-threads
    + the (now-fixed) sparse-wiki world-threads, Option-B GSE-local ingest
    (`5e81b86`).
  - **M2.2b ✅** coherence-scored sense selection — the sense that coheres wins,
    margin-protected against noisy neighbours (`37fae98`).
- **M3 — Coherence / confidence (Stage 3c).**
  - **M3a ✅** `grounding_flags` — the abstention signal (Tier-2 ungrounded,
    Tier-1 incomparable); closes the deferred abstention proof (`6988a14`).
  - **M3b ✅** persist / Tier-3 triage (`triage_flags`, `spearman` over the flag
    corpus — systematic fault vs SNP) (`d16c553`). *The literal
    POS-vs-lexicon cross-strand was dropped: `lexemes.pos` is empty and the NSM
    decomposition describes meaning not category, so it has no sound Strand B —
    M3a's ungrounded/incomparable ARE the sound cross-strand vetoes.*
- **M4 — Context.**
  - **M4-3a ✅** document-scope resolution — cross-sentence coreference +
    document-global ids + document-wide coherence (`resolve_document`) (`89da152`).
  - **M4-3b — TODO** the HDC genre signature (emitter-ready; consumer is Genesis).
- **M5 — Faithful Innerese (the Genesis-walker must-haves). ✅**
  - **Event roleframe** — the base-case predicate a plain verb clause was missing;
    `EVENT(verb; agent, patient)`. Fixes Causation: cause/effect carry nested
    Events, not flattened entities (`c73b2d0`).
  - **Control restructure** — `CONTROL(verb, subject, controller, inner)`; "to"
    dropped, inner agent = controller (`1840bfa`).
  - **Proper-name identity** — proper nouns ground via the world strand only; a
    PROPN absent from it flags rather than taking a bogus common-noun thread
    (`786a6ce`).
- **M6 — Demi-words. ✅** A multi-token nominal slot is one unit; the *structure*
  does the segmentation (the slot is the boundary), identity keys off the whole
  span ("Lady Macbeth" ≠ "Macbeth"), and a matched span grounds against the
  dictionaries by its joined key (WordNet MWE / sparse-wiki label), ambiguity
  resolved by the existing coherence selector (`0fb3afb`, `7b353df`).
- **Inference ✅** transitive-closure logical reasoning over the clause graph
  (`KnowledgeBase`: is-a syllogism + ordering, with derivation chains) — the
  LSAT-style "zorble/florp" demo, real (`045ab61`, `gse/demo/reasoning.py`).

---

## 9. Honest open risks

- **WordNet sense-selection** is the noisy step in type threads. Mitigated by
  making the sense a coherence-scored assignment (a wrong sense flags, not
  silently mis-threads), but it is the load-bearing unknown in M2.
- **Global CSP determinism under scale.** Exact CSP is deterministic but can be
  costly; the fixed-order tiebreak must be specified so determinism never trades
  against tractability silently.
- **Error-threshold calibration.** "The right error rate, not zero" needs a
  concrete threshold; picked empirically and logged, not hidden.

---

*Out of scope (Genesis-side, by §1): the Innerese walker, archetype
rule-inheritance, k-line narrative-role retrieval, the narrative-WIN oracle.
Out of scope (separable track): sparse-wiki rebuild; Layer-3 deterministic
parser (the research tail — named in Genesis ARCHITECTURE.md, downstream of all
of the above).*
