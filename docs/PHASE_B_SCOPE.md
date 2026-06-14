# Phase B Scope: Symbolic Evaluator over OperationTrace

> **Status:** Live scope document. Tracks the sub-phases of the symbolic
> evaluator implementation, what's done, what's blocked.
>
> **Architecture anchor:** `sentence_architecture.md` line 164 — *"We
> shouldn't be doing direct vector math for the full sentence as part of
> the semantic wrapper. The API for engaging with the system should be
> pure python/order of operations/set theory."*
>
> **Phase A status:** Complete. `tests/test_comp_operator_trace.py`
> (32 passing) verifies the encoder produces correct `OperatorTrace`
> entries for all 10 COMP_* operators. Phase B builds on that contract.

---

## What Phase B is

Per the architecture document, the trace layer of `OperationTrace.operators`
is supposed to be consumed by a **pure-Python symbolic evaluator** that:

1. Lifts the trace into a typed AST.
2. Applies the set-theory semantics of each operator.
3. Exposes a query interface: entities, predicates, logical equality,
   structural similarity, argument-swap detection.
4. Round-trips through JSON for persistence and replay.
5. Supports templating (substitute entity X with Y, preserve structure).
6. Backs a proof suite that demonstrates the architecture's
   line 154 validation queries end-to-end.

HDC vector math is NOT part of Phase B. Vectors carry semantic content
(handled by the encoder + word/sentence bases); Phase B is the
logical/symbolic lens on top.

---

## Sub-phases

| Phase | Deliverable | LoC | Theory blocker | Status |
|---|---|---|---|---|
| **B1** | `gse/symbolic/expression.py` — AST (`Atom`, `Phrase`, `Negation`, `Op`) + `from_trace(trace)` builder | ~100 | None | Pending |
| **B5** | `gse/symbolic/resolution.py` — multi-word entity grouping, possessive resolution, single-sentence pronoun binding | ~150 | None | Pending |
| **B4** | `Expression.to_json()` / `from_json()` round-trip | ~50 | None | Pending |
| **B2** | `gse/symbolic/operators.py` — pure-Python semantic functions for each of 10 `OperatorTrace.operation` labels | ~300 | **6 specs needed** (see below) | Pending |
| **B3** | `gse/symbolic/queries.py` — `entities()`, `predicates()`, `is_logically_equal_to()`, `is_argument_swap_of()`, `axis_of_comparison()` | ~150 | None (uses B2) | Pending |
| **B6** | `gse/symbolic/templating.py` — `Expression.substitute(Atom, Atom) → Expression` for structural substitution | ~100 | None | Pending |
| **B7** | `gse/verification/symbolic_proof_suite.py` — the architecture's line 154 validation queries | ~150 | None | Pending |

**Total: ~1000 LoC + tests, gated on 6 operator specs.**

---

## Theory specification status (B2 unblocked)

User-authored specs landed for 6 of 7 operators that needed them. The 7th
(EVEN/SCALAR_EXTREME) is recorded as future work — see below.

**Authoritative specs for B2** (user-approved 2026-05-23):

| Operator | Operation | Semantics |
|---|---|---|
| COMP_AS | BIND_EQ | `X is as Y as Z` → bind X and Z as equivalent on the Y axis. Symmetric, non-directional. Distinguishes from THAN which is sign-aware. |
| COMP_WHAT | TYPE_QUERY | `What is X?` → query the SUBSTANTIVES-bank decomposition of X. Returns the KIND/SOMEONE/SOMETHING/PEOPLE/BODY primitive activations. |
| COMP_ONLY | SET_RESTRICT | `Only X [predicate]` → ∀Y: predicate(Y) → Y = X. Arg is the lone member; predicate is the surrounding sentence context. |
| COMP_BUT | CONTRAST | `X but Y` → both X and Y are asserted true; the contrast metadata records the pragmatic note that Y violates X's expectation. v1 simplification: don't model "Yoda" cases. |
| COMP_SO | CONSEQUENCE | `X so Y` → X is cause, Y is effect. Cause → effect directional. |
| COMP_BECAUSE | CAUSAL_SOURCE | `X because Y` → Y is cause, X is effect. Inverse of SO. Equivalent to `CONSEQUENCE` with args swapped. |

**Deferred to future work** (user decision 2026-05-23):

| Operator | Operation | Why deferred |
|---|---|---|
| COMP_EVEN | SCALAR_EXTREME | Not a 1st-order primitive. Requires hierarchical network traversal coherence math (the "more expected on some scale" universal can't be resolved at the single-operator semantic layer). v1 implementation: inert `BoundaryCase` placeholder that records the operation; no scalar-extreme assertion. Tests skip the universal-quantification assertion. |

Specs explicit in the architecture document for the other 3 operators:

| Operator | Operation label | Spec source |
|---|---|---|
| COMP_THAN | SET_DIFF | Line 141: `[MIKE'S DOG]*[-1]set_diff{[CUTE]*[REX]}>0` |
| COMP_HOW | DEGREE_QUERY | Line 145: conditional on following clause to clause-terminating punct |
| COMP_JUST | CARD_LOWER | Line 146: cartesian-product cardinality example for "just enough mustard" |
| (NOT explicit, but) any negation | sign flip | Lines 22-46: `[-1]` is a directional argument, not an operator |

The 6 operators **without explicit semantics** in the architecture doc:

* `COMP_AS` → `BIND_EQ`
* `COMP_WHAT` → `TYPE_QUERY`
* `COMP_ONLY` → `SET_RESTRICT`
* `COMP_EVEN` → `SCALAR_EXTREME`
* `COMP_BUT` → `CONTRAST`
* `COMP_SO` → `CONSEQUENCE`
* `COMP_BECAUSE` → `CAUSAL_SOURCE`

What "spec" means for each: 1–3 sentences plus an example, like:

> *COMP_AS / BIND_EQ:* "X is as Y as Z" binds X and Z as having
> equivalent value on the Y axis. Output: `Predicate(X.Y_axis ≈ Z.Y_axis)`.
> Example: "Mike is as tall as Rex" → `tall(Mike) ≈ tall(Rex)`.

Drafted by the user, with possible iteration via strawman proposals.

---

## Recommended execution order

1. **B1 + B5 + B4** (foundation, no theory blocker) — buildable now.
2. **Theory specification** for the 6 operators — user-authored.
3. **B2** (semantics) — implements step 2's specs.
4. **B3** (queries) — consumer interface over B1+B2.
5. **B6** (templating) — structural manipulation.
6. **B7** (proof suite) — end-to-end validation per architecture line 154.

---

## Resolved limitations

* **Axis recovery post-resolution.** *(Resolved 2026-06-14)* `Entity`
  now carries an optional ``modifier: Optional[Atom]`` field. During
  ``_collapse_phrase_to_entity``, the first ADJ/ADV atom in the
  source phrase is attached as the modifier; ``axis_of_comparison``
  consults ``Entity.modifier`` first. Serialization and templating
  round-trip the field. ``Comparison`` predicates on resolved trees
  now return the axis lemma (e.g., ``"tall"`` for "Mike is taller
  than Rex") instead of ``None``.

## What Phase B explicitly defers

Per the architecture document:

* **Knowledge-base truth evaluation** — recovering "what animals are
  we talking about" works structurally; *answering* "is this true about
  the world" needs a KB integration that's its own project.
* **Natural-language generation** — line 152's "reconstructed into any
  arbitrary output (e.g., a natural-language response)" is Phase C.
* **Paragraph/full-text systems** — line 152: "I'm ok leaving the
  paragraph/full-text systems for later."
* **Bank activation count-informed normalization** — line 157, separate
  concern.
* **Multi-sentence coreference** — B5's pronoun binding is bounded to
  within-sentence. Cross-sentence coref is a separate research direction.
