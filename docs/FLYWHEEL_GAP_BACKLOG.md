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

## Contemporary-text finding (2026-06-21)

Augmented the corpus with modern HF sources — `modern_news` (ag_news), `reviews_modern`
(imdb), `twitter` (tweet_eval). **No new STRUCTURAL shape surfaced.** On 36K sentences of
contemporary, messier text the collapse rate held at **0.444%** (the 1961-prose band), and
the messiest register barely collapsed (`social` 6, `review` 9). The new registers'
residual is purely **lexical coverage** — slang (`lol/oh/please`), names (`hepburn/ned`),
the known function words. Hashtags/@mentions/emoji never even reach the OOV worklist (the
tokenizer files them non-content). Minor curiosity: a stray `ly` token in social (an
orphaned `-ly` adverb suffix? worth a glance). Diachronic `news` vs `modern_news` (same
reportorial node) available for a later 1961-vs-2020s shape comparison.

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
| plural-definite → named-set coreference | `"Gnash wanted to eat the pigs"` (after `"Pip, Bram, and Hew are pigs"`) — `the pigs` grounds to the generic type, NOT the named trio. Anaphora resolution of a definite plural NP to a set of previously-named individuals; a resolution-layer (`resolve_references`) feature, not a parse fix. Surfaced by the Three-Pigs folk-tale run through the Genesis bridge (2026-06-21). Not wrong today (it resolves to the type), just under-specific. |

| ClauseCoordination event extraction (skeleton) | `"Bertran betrayed Aldric and murdered him"` → the narrative skeleton gets NEITHER event. `queries.predicates()` recurses into Causation/Control/RelativeRestriction/Event but **not** `ClauseCoordination`/`Conditional`/`Temporal`, so events nested under a top-level coordination are invisible to `NarrativeGraph.from_document`. (Compounded by the catalogued VP-coordination parse-tail: GSE also drops the 2nd conjunct's verb, `murdered`→bare entity.) Together they gut a coordination-heavy arc → 0 derivations even on a covered (violence) domain. Surfaced by the hand-written stress test 2026-06-22. The `predicates()` descent is a small fix — **mind the other callers (`inference.py`) that may rely on not descending**. |
| ~~"that" 3-way POS~~ **RESOLVED 2026-06-22** | `that` was dead-locked to **PRON** (the early `_PRON` branch pre-empted the `that` branch; `_that_is_clausal` was unreachable). Enumerate-and-score over a full clause decomposition was tried and **abandoned** — token-local circularity (a neighbour's POS depends on `that`'s own POS, since `that ∈ _DET`) + unreliable isolated content-word POS. **Shipped fix:** (1) exclude surface `that` from the determiner-context guards (`prev_det`) so a relativizer `that` no longer nominalizes the following verb ("the king that **fell**" keeps fell=VERB — the actual breakage); (2) resolve by the **governor** (reliable preceding token): noun→PRON relativizer, verb→SCONJ complementizer, clause-initial→DET-if-nominal-else-PRON. Reframe (user): `that` is droppable structural glue in 3 of 4 readings; only the demonstrative pronoun is a referent. 9/9 canonical cases. |
| ~~ClauseCoordination event extraction (skeleton)~~ **RESOLVED** (`dfe161f` descent + `186dbaf` VP-coord) | see history. |
| plural common noun + verb-sense in subject position | `"I know that dogs bark"` → the *outer* clause now parses (`know`→VERB, `that`→SCONJ), but the *inner* "dogs bark" garbles: `dogs`→VERB (the `-s`+verb-sense rule fires on a plural noun) and `bark`→NOUN (tree-bark sense wins). A bounded-register POS tail — a plural common noun with a verb sense in subject position, and a following content word with a competing noun sense. Not the `that`/predicate logic (those are fixed). Surfaced 2026-06-22. |
| possessive/apposition subject extraction | `"Aldric's son Cael swore revenge against Bertran"` → the subject mis-threads (skeleton gets `bertran —swear→ …`, not Cael). A complex subject NP (possessive + apposition, `Aldric's son Cael`) isn't reduced to its head referent (Cael). Compounds with proper-noun typing (Cael then never gets a person type for the guards). Surfaced by the stress test 2026-06-22. |
| token-coverage degradation signal (DETECTOR strand) | If a large fraction of a sentence's CONTENT tokens never reach the contract structure, the parse is degraded — a cheap, general "keep going" trigger that routes to the repair/heal *fixers*. Would have flagged the VP-coordination 2nd-conjunct drop (~half the clause lost) before it was found by eye. A detector strand in the multi-strand error correction (complements the fixers: parse-repair, subject-sharing, discourse/world heals). User idea 2026-06-22. |

---

## Evidence & instrumentation gaps (claim-validation — not a parse fix)

These don't fix a parse; they build the EVIDENCE that lets the capability be claimed out
loud. Added 2026-06-22, alongside the document-compression / native parse-repair / multi-
strand-healing work.

| item | what it is | why it matters |
|---|---|---|
| **spaCy head-to-head benchmark** | A *measured* comparison of the native front-end vs spaCy on a standard parsing / role-labelling task (and the project's own bounded register): accuracy + failure-mode coverage. Native already *replaced* spaCy (no runtime dependency) and parses its known failure seams clean (`Macbeth murders Duncan`) — but that is anecdotal. | Converts "functionally past spaCy" into a **defensible "we beat spaCy"** claim. The native parse-repair (now wired) is the last *capability* piece; the benchmark is the missing *measurement*. Without it, beat-spaCy stays an assertion, not a result. |
| **Telemetry / compute-cost instrument** | A timing + cost harness around the GSE→Genesis pipeline: per-stage wall-time, total latency, and an **LLM-equivalent cost** comparison (tokens × \$/token, latency) for the same task on the same input. | A **killer demonstration vs LLM approaches**: deterministic, laptop-hostable, ~ms and fractions-of-a-cent vs LLM tokens / dollars / seconds. The cost-and-latency asymmetry is one of the strongest arguments for the non-neural regime — but it must be *measured and shown*, not asserted. Pairs with the inverse-brittleness curve as headline evidence. |
