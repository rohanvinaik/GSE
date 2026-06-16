# Complex-Sentence Architecture — Build Design

> The agreed design for lifting GSE from single-clause to multi-clause sentences,
> on the **live spine** (`gse.api` + `gse.symbolic`). Companion to the spec
> `complex_sentence_architecture.md`. Authoritative source: Rohan, then the code.
>
> **Status.** Design agreed 2026-06-14. Implementation in progress.

---

## 0. The keystone (corrected)

The recursion machinery **already exists**. `evaluate_tree`
(`gse/symbolic/operators.py:215`) recurses into `Op.args`, evaluating nested
`Op`s into `Predicate`s before the parent dispatch — so `Op(args=[Op(...)])`
already yields nested predicates at runtime. The `Expression` union excluding
`Predicate` is a *type annotation that under-describes runtime behavior*, not a
structural barrier.

The real gaps for multi-clause are two **bugs**, both downstream of clause-blind
token handling:

1. **Clause-blind argument spans.** `_resolve_operator` (`encoder.py:403`) gathers
   *every* content token before the operator as `arg1` and every one after as
   `arg2`. In "The dog is cuter than the cat because the dog barks", `THAN`'s arg2
   swallows `the cat because the dog barks`.
2. **Positional nesting.** `from_trace`'s left-fold (`expression.py:273`) assumes
   *leftmost operator = innermost*. Correct for "X than Y because Z"; **inverted**
   for "Rex barks because the dog is cuter than the cat" → builds
   `THAN(BECAUSE(...), cat)` instead of `BECAUSE(rex-barks, THAN(dog, cat))`.

The fix for both: **segment into clauses first, compose clause-linking operators
over clause results by tier + surface order.**

---

## 1. Agreed decisions

- **(A) Segmentation runs in the encoder.** It owns spaCy's dependency labels
  (`mark`/`cc`/`relcl`) that mark boundaries. Clause spans are emitted into the
  trace (the serialized contract); `from_trace` consumes them.
- **(B) Clauses are implicit.** No `Clause` AST node. A clause is just the
  `Expression`/`Predicate` a span resolves to, discoverable via a `clauses()`
  query walk. (More faithful to fluid NLP; any Genesis-side reification is manual
  later.)
- **(C) Nesting comes from operator tier + surface order + the center-embedding
  cap.** spaCy stays the boundary/role tagger it already is; its parse tree is
  *not* imported as the nesting authority. Keeps the spaCy seam where
  `ARCHITECTURE.md` draws it.

---

## 2. The one new concept: operator tier

Every operation is `WITHIN_CLAUSE` or `CLAUSE_LINKING`.

| Tier | Operations |
|---|---|
| `WITHIN_CLAUSE` | `SET_DIFF`, `BIND_EQ`, `DEGREE_QUERY`, `TYPE_QUERY`, `TYPE_ASSERT`, `CARD_LOWER`, `SCALAR_EXTREME`, `CONTRAST` |
| `CLAUSE_LINKING` | `CAUSAL_SOURCE`, `CONSEQUENCE`, `COORDINATION`, `REL_RESTRICT`, `CONTROL` |

`SO`/`BECAUSE` (`CONSEQUENCE`/`CAUSAL_SOURCE`) are *already* clause-linking in
effect; tiering makes it explicit and drives segmentation + nesting.
`CONTRAST` (but) stays `WITHIN_CLAUSE` for now to preserve current behavior — a
documented candidate for promotion, out of this build's scope.

---

## 3. Surface-by-surface changes

1. **`gse/symbolic/tiers.py` (new).** `OperationTier` enum + `OPERATION_TIER`
   map + `is_clause_linking(operation)`. The single source of truth for §2.
2. **`gse/api/trace.py`.** Add `ClauseSpan(clause_id, token_start, token_end,
   operator_indices)` and `OperationTrace.clauses: List[ClauseSpan] = []`. Flat
   `operators` list stays. JSON round-trip extended; empty `clauses` ⇒
   byte-identical single-clause traces (back-compat).
3. **`gse/api/encoder.py`.** A segmentation pre-pass partitions tokens at
   `CLAUSE_LINKING` operator positions + clause punctuation into ordered spans.
   Within-clause arg resolution runs *inside each span*. Clause-linking operators
   record their left/right operands by clause-id. Connectives with no lexicon
   operator row (`and`/`who`/`which`/`that`/`to`) are recognized structurally
   from spaCy dep labels — same pattern as the copula `TYPE_ASSERT` synthesis.
4. **`gse/symbolic/expression.py`.** `Operand = Union[Atom, Phrase, Negation, Op,
   Predicate]`; annotate operand-bearing fields with it. Replace positional
   left-fold in `from_trace` with tier-aware build: within-clause `Op` per span,
   then clause-linking `Op`s folded over clause results by surface order.
5. **`gse/symbolic/predicates.py`.** Add `Coordination(members, conjunction)`,
   `RelativeRestriction(head, restriction)`, `Control(verb, controller, inner)`.
   `Causation`/`Contrast` unchanged.
6. **`gse/symbolic/operators.py`.** Dispatch entries for `COORDINATION`,
   `REL_RESTRICT`, `CONTROL`.
7. **`gse/symbolic/queries.py`.** Add `clauses(tree)` and clause-scoped
   `entities()`.
8. **`gse/verification/symbolic_proof_suite.py`.** Lift the argument-swap proof
   to clauses (`X because Y` ≠ `Y because X`, HDC-similar); add the
   nesting/inversion proof and novel-clause systematicity.

---

## 4. Build milestones

**M1 — Segmentation + correct nesting on existing operators.** Tier registry,
`ClauseSpan` in the trace, within-span arg resolution, tier-aware `from_trace`.
Proven on `SO`/`BECAUSE` × `THAN` nesting (the inversion case) — no new operators,
no DB changes. This is the keystone milestone; everything else layers on it.

**M2 — New connectives.** Refined during the build once spaCy structure was
inspected (the uniform "all clause-linking" assumption in §2 didn't survive
contact):

- **M2a — NP-coordination (`and`/`or`). DONE.** "Spot and Rex are dogs" is
  *set-union of subjects under one predicate*, not two clauses — so `COORDINATION`
  is retiered `WITHIN_CLAUSE` and handled in `resolution.py` as an entity
  grouping (`Coordination` node), keyed off the `and`/`or` lemma already visible
  in the Phrase. No encoder/trace change. Clause-level `and` ("Spot barks and Rex
  sleeps") deferred. Also closed two latent gaps: `entities()` and
  `_structural_signature` were missing `TypeAssertion`.
- **M2b — Relative clauses (`who`/`which`/`that`). TODO.** `relcl` subtree is
  *embedded* in the middle of the parent clause (attaches to an antecedent
  entity), not sequential. Needs **nested** `ClauseSpan` (a parent span containing
  a child span) + `from_trace` recursion → `RelativeRestriction(head, restriction)`.
- **M2c — Control (`to`). TODO.** `xcomp` clause is *embedded* as the object of
  the outer verb. Same nested-span machinery → `Control(verb, controller, inner)`.

Decision (2026-06-14): embedded clauses use **nested spans**; `and` is
**NP-coordination first**.

**M3 — Queries + proof-suite completion. DONE.** Added `clauses(tree)` (returns
the clause-level predicates: Causation, RelativeRestriction, Control;
clause-scoped entities is just `entities(subtree)`), and a `systematicity` proof.
Also closed serialization (the new predicates + the pre-existing `TypeAssertion`
gap now round-trip JSON) and extended `substitute()` to the new predicates.

The **systematicity** proof operates on the symbolic tree via `substitute`
rather than re-encoding nonsense words, because surface parsing of novel content
is bounded by spaCy: it mis-tags "The zorble that blibs …" (blibs → NOUN/nsubj,
no relcl), so the relative clause isn't detected. GSE's *symbolic* layer is
content-independent; the limiting factor is the spaCy front-end. **Abstention**
(the §5 weighted/abstain-under-ambiguity proof) is deferred with the sparse-wiki
track — it needs ambiguity scoring the deterministic parser doesn't have.

Determinism guarantee is preserved throughout: every operator is a typed set
operation; spaCy remains the only non-deterministic component.

## Showcase

`python -m gse.demo.showcase` (`gse/demo/showcase.py`) prints a self-evident,
at-a-glance demonstration of the whole scope: it renders the clause graph for a
"see Spot run" → Macbeth-grade climb of sentences, shows the argument-swap jewel
(HDC cosine ≈ 0.93 yet logically opposite), proves byte-identical determinism
across runs, and shows systematicity under novel content. It is the artifact to
run when someone asks "what does this actually do, and how is it not an LLM?"

## Final state (2026-06-14)

All milestones complete. **13/13 proofs, 345 tests pass.** New predicates:
`Coordination`, `RelativeRestriction`, `Control` (plus `Causation`/`Contrast`
reused). Single-clause traces stay byte-identical; multi-clause trees round-trip
JSON. Files touched: `gse/symbolic/{tiers,expression,predicates,operators,
resolution,queries,templating,serialization}.py`, `gse/api/{trace,encoder}.py`,
`gse/verification/symbolic_proof_suite.py`.

Out of scope for this build (unchanged): sparse-wiki OOV grounding + abstention
(separable later track), paragraph/cross-sentence (Genesis), clause-level `and`,
`CONTRAST` promotion, control-clause controller verb retention.
