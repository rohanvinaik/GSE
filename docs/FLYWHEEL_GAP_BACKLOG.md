# Flywheel gap backlog — the long tail

> **Purpose.** A persistent, **append-only** record of the gaps the L2 dogfooding
> flywheel surfaces and we deliberately DON'T fix immediately (genuine tail, lower
> value, or a bigger unit than the current pass). It is the mining target for a future
> long-tail cleanup sweep.
>
> **Not** `data/flywheel_worklist.txt` — that is the *latest* audit output, overwritten
> each run. This file is the curated, accumulating backlog. When a flywheel turn surfaces
> a gap we defer, add a row here. When one is fixed, mark it `RESOLVED` (don't delete —
> the history is the mining signal).
>
> Each entry: **shape · example · category · status/notes.** Categories below.
>
> Established this session (2026-06-20): the flywheel surfaced three *structural* parse
> gaps — coordination collapse, copula predicate-adjective, the `'s` clitic — and all
> three were **fixed**. Pressure-testing confirmed **nothing else is structurally off**;
> what remains underneath is this tail.

## Categories

1. **Lexical coverage** — an OOV word (no decomposition / not an operator). Sometimes
   masquerades as a parse collapse (an OOV *complement* drops the predication). The
   flywheel's ongoing job: voice-modes (spell-check / archaic / slang) + sources wired
   into the existing integrator pipeline (never a flat lookup).
2. **Bounded-register complexity** — long multi-clause sentences exceeding the
   deterministic parser's bounded depth. This is the vision doc's *stated* honest limit
   (claim 8), flagged by the coherence gate — not a hidden flaw.
3. **Rare construction** — a real but infrequent/complex syntactic form not yet handled.

---

## Lexical coverage

| word(s) | example | notes |
|---|---|---|
| `such` | "such a big dog" | Biggest single remaining OOV (≈240–280 across prose). Degree/identifier — its own category (not a QUANTITY/INTENSITY level). Candidate: a degree operator or hierarchy-adjacent handling. |
| archaic forms | `unto/thy/shalt/ye/thereof/spake/hath/alway` | The **archaic voice-mode** (KJV / Shakespeare register). Register-conditioned repair, not base lexicon. |
| archaic orthography | `haue/vpon/selfe` (u↔v, long-s) | The archaic u↔v spell-check error model (already noted in the flywheel memory). |
| abbreviation cluster | `af`(327), `mln`(132), `dlr`(77), `per` (reportorial) | OCR / domain abbreviations (mln=million, dlr=dollar). Investigate `af` specifically. Domain-glossary source or a pre-clean. |
| discourse/temporal adverbs | `also/ever/within/often` | Additive / temporal adverbs. |
| modal | `would` | The modal track (with CERTAINTY — see deferred). |
| gradable adjectives | `long`, `oily`, … | OOV adjectives. `oily` OOV is what makes "Brenner's voice was oily" collapse (NOT a possessive-copula structural bug — `The dog's owner was happy` → TypeAssertion works). |

## Bounded-register complexity (the stated honest limit)

| shape | example |
|---|---|
| deeply-embedded coordination | `"increase, decrease, add or eliminate budget items"` → `Mayor veto`; `"screen and endorse candidates"` → `then strive`. Coordination buried in a long subordinate clause; the simple/top-level cases ARE fixed (#1). |
| possessive in a complex clause | `"you always did Wright's dirty work"` → `Wright work`; `"Pike's honor would now come under attack"` → `Pike attack`. The `'s` resolves correctly (possessive); the *clause* exceeds depth. |

## Rare constructions

| shape | example | notes |
|---|---|---|
| gapping / elided copula | `"The Prince's perceptions were quick and his energy [was] monstrous"` → collapse | Coordination with a gapped verb in the 2nd conjunct. |
| partitive | `"the closest of [them]"` → `closest fellows` | Partitive `X of Y`. |
| infinitival quantity | `"so much to give"` → `much give` | `so much to V`. |
| tokenization artifact | `"...brings together"` → `centrally centrally Mann work` | A duplicated `centrally` — an encoding/tokenization artifact, worth a direct look. |

---

## Deferred build units (bigger than tail — scoped out of a specific pass)

| item | why deferred |
|---|---|
| QUANTITY→noun binding (quantifier case 2) | `"many dogs"` — gated on a noun POS mistag (`dogs`→VERB→EVENT). Binding + a tagging fix, its own pass. (Intensifier→adjective binding, case 1, IS done.) |
| CERTAINTY modal track | `possible/likely/probable/would` — the CERTAINTY hierarchy + modals. The quantifier build did QUANTITY+INTENSITY only. |
| REVERSAL semantics | `unlock` ≠ `negate(lock)` — action-reversal is not a sign flip; recognition-only in v1 (see [[negation-operation-spec]]). |
| possessive-subject coherence flag | A possessive-subject NP with an OOV complement collapses to a multi-token Entity the gate flags; a single-token subject does not. A coherence-gate refinement (treat a clean possessive Entity as non-degraded), not a parse fix. |
