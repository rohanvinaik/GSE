# GSE Theory

> **Purpose.** The theoretical foundation of Geometric Semantic Encoding
> (GSE) — what it claims about meaning and language, and the mathematical
> structure that lets it work.
>
> **Status (reconciled June 2026).** This document was previously marked
> invalid because it mixed claims that match the system with older,
> unscoped material presented as if it were live. It has been reconciled
> against [`ARCHITECTURE.md`](ARCHITECTURE.md) and the code: every claim in
> the body describes the **functional system** (the `gse.api` +
> `gse.symbolic` core on the `vectors_v2` / `primitives_v2` substrate and
> the `data/lexicon.db` lexicon). Theory that the code does not yet realize
> is confined to a single clearly-fenced section, [§11 Not yet
> implemented](#11-not-yet-implemented). Machinery that the functional core
> does not use (runtime pattern-network "learning," the lexeme-graph search,
> collision-confidence dynamics) has been removed — it belongs to the older
> `patterns/` and `merkle/` stack, which `ARCHITECTURE.md` documents as
> drift.
>
> For *system design* see [ARCHITECTURE.md](ARCHITECTURE.md). For the
> *paradigm-level claim* against the Bitter Lesson see
> [POSITIONING_SURVEY.md](POSITIONING_SURVEY.md).

---

## 1. The central thesis

**Meaning in natural language is fundamentally geometric.** Semantic
content corresponds to positions and orientations in a high-dimensional
vector space where relationships between concepts are encoded as
distances, angles, and projections.

This is a precise mathematical claim, not a metaphor. There exists a
finite-dimensional vector space and an encoding function such that:

1. Every meaningful linguistic unit maps to a vector in this space.
2. Semantic similarity corresponds to geometric proximity.
3. **Semantic opposition corresponds to geometric opposition** (negative
   cosine).
4. Semantic orthogonality corresponds to geometric orthogonality (zero
   cosine).
5. Compositional meaning follows algebraic operations on vectors.
6. The structure admits verification through hash-like properties.

The constructive part of the thesis: this space is *finite-basis*, the
basis is a small set of universal semantic primitives, and meaning
composition follows algebraic rules over that basis.

---

## 2. Intellectual lineage

GSE synthesizes five traditions:

| Tradition | Key insight | Contribution |
|---|---|---|
| **Natural Semantic Metalanguage** (Wierzbicka, 1972–) | Universal semantic primitives exist across all languages | Finite basis vocabulary (~62 NSM primes; ~74 word-scale primitives in the lexicon) |
| **Montague grammar** (Montague, 1970) | Natural language has formal compositional semantics | Algebra over a vector space; set-theoretic operator semantics |
| **Hyperdimensional Computing** (Kanerva 1988/2009; Plate 1995) | High-dim vectors enable symbolic operations | Bind / bundle / permute |
| **Orthogonal Ternary Projection** (Vinaik, 2025) | Zeros carry information; opposites are distinct from unrelated | Ternary {−1, 0, +1} encoding |
| **Society of Mind** (Minsky, Winston) | Intelligence emerges from interaction of simple agents | Frame-over-compute design stance |

Each tradition contributed a load-bearing piece; none on its own produces
a working English decoder with deterministic compositional truth. The
composition is where the work happens — none of the individual ideas are
new.

The historical reading: classical/symbolic NLP (1950s–1980s) had the
ambition but not the substrate. HDC's mathematical framework wasn't
broadly available; the ternary insight came later; the compute to explore
high-D vector spaces was insufficient. The shift to statistical methods
was rational given the available tools — but the field carried that shift
forward as a *prescription* (scale wins) rather than a *retrospective*
(scale historically dominated structure). GSE is an existence proof that
the prescription is wrong; see
[POSITIONING_SURVEY.md](POSITIONING_SURVEY.md) for the
proof-by-contradiction against the strong form of the Bitter Lesson.

---

## 3. Core principles

### Principle 1: Geometric grounding

Meaning is constituted by geometric relationships in a high-dimensional
vector space. Similarity is proximity; opposition is negative proximity;
unrelatedness is orthogonality. The encoding does not *describe* meaning —
it *is* the meaning.

### Principle 2: Primitive basis

The semantic vector space has a finite basis corresponding to universal
semantic primitives. All lexical meanings are constructed from this basis.
GSE uses ~74 word-scale primitives across 8 semantic banks (NSM's ~62
primes plus sentence-relevant atoms), and 24 sentence-scale primitives
(syntactic roles + compositional operators) in a separate basis.

### Principle 3: Ternary polarity

Primitive activation uses three values: **+1** (presence), **−1**
(opposition), **0** (orthogonality / non-applicability). This is the
load-bearing innovation that distinguishes synonymy, antonymy, and
unrelatedness in the same geometry:

| Relation | Cosine | Mechanism |
|---|---|---|
| Synonyms (`happy`, `joyful`) | ≈ +0.9 | Shared dimensions, same signs |
| Antonyms (`happy`, `sad`) | ≈ −0.7 | Shared dimensions, opposite signs |
| Unrelated (`happy`, `rectangular`) | ≈ 0.0 | No shared dimensions |

Standard binary or continuous encodings collapse antonymy into either
orthogonality (loses the shared dimension) or distinct clusters (loses the
opposition structure). The {−1, 0, +1} ternary preserves both. (Cosine
values above are illustrative of the regime, not fixed constants.)

### Principle 4: Compositional algebra

Meaning composition follows algebraic operations over the substrate
(`gse/vectors_v2.py`):

* **Binding (⊗, `bind`)**: element-wise ternary multiplication; creates
  compounds dissimilar to inputs. Used to attach roles to fillers
  (`ROLE_subj ⊗ ⟦dog⟧`).
* **Bundling (⊕, `bundle`)**: majority-vote superposition; creates
  mixtures *similar* to inputs. Used to assemble a token's full
  representation from its word-scale and sentence-scale vectors, and to
  assemble the sentence vector from its tokens.
* **Permutation (ρ, `permute`)**: circular shift; encodes token position.

A correctness note that matters: the per-token composition of word-scale
and sentence-scale uses **bundle, not bind** —
`full = bundle([word_vec, sent_vec])`. Binding two near-orthogonal sparse
vectors would destroy the signal (their element-wise product is nearly
empty); bundling preserves both the semantic content and the syntactic
role so each survives into the sentence vector. Binding is reserved for
role–filler attachment, where dissimilarity to the inputs is the desired
property.

### Principle 5: Constructed, not trained

A critical distinction, and the basis of the determinism claim:

* **Training** (rejected for the semantic layer): gradient descent on
  labeled pairs, producing opaque weights that encode *answers*.
* **Construction** (adopted): the primitive basis is built once from
  Hadamard matrices (no weights to learn — see §5), and the lexicon — the
  map from words to primitive decompositions — is **assembled offline** by
  the curation pipeline (lexical resources + LLM-assisted decomposition;
  see `ARCHITECTURE.md` §6). The decompositions are interpretable
  `(primitive, polarity)` assignments, not learned embeddings.

At **runtime** there is no learning and no adaptation. Encoding is a
deterministic static lookup against `data/lexicon.db` followed by fixed
HDC arithmetic. The same input always yields the same vector and the same
symbolic predicates. (The only trained component anywhere in the pipeline
is spaCy, used for the front-end parse *before* the semantic layer.)

### Principle 6: Multi-scale separation

Distinct linguistic scales have **distinct primitive vocabularies that
compose rather than conflate**. The functional system implements two:

| Scale | Scope | Primitives | Count |
|---|---|---|---|
| **Word** | Lexical meaning | NSM-derived semantic primes | ~74 |
| **Sentence** | Syntactic + compositional | `SYN_*` roles, `COMP_*` operators | 24 |

The two live in separate bank partitions of the *same* 8192-dim space,
each with its own partition-Hadamard basis, so that word-scale and
sentence-scale signals are near-orthogonal. A token's full representation
*bundles* both (Principle 4): `⟦w⟧ = bundle(⟦w⟧_word, ⟦w⟧_sentence)`.

This is why `ran` and `run` have word-scale similarity ≈ 1.0 (same
meaning) while their tense difference lives in sentence-scale, orthogonal
to word-scale operations; and why `than` carries ≈ 0 word-scale signal but
a strong sentence-scale `COMP_THAN` signal.

(Paragraph- and text-scale vocabularies are sketched in the broader vision
but are **not** part of the functional system — see [§11](#11-not-yet-implemented).)

### Principle 7: Frame over compute

The dominant paradigm assumes more computation yields better results. GSE
adopts the inverse stance: **add frame, not compute.** When the
representation's structure matches the problem's structure, the answer
falls out of cheap deterministic operations rather than search or
optimization.

Concretely: the interpretation work is done by *structure* — the primitive
decomposition, the bank partitioning, the operator dispatch — not by a
compute-heavy inference loop. The only arithmetic is O(tokens) sparse HDC
operations after lexicon lookup. This is the architectural reason GSE runs
on a laptop, and the basis for the survey's "algorithmic anachronism"
framing (the design could have been built in 1970, given the math).

---

## 4. The ternary insight in detail

### 4.1 Why binary fails

Standard semantic encoding treats antonyms as either **orthogonal**
(cosine ≈ 0 — conflates opposition with unrelatedness) or **distinct
clusters** (loses the shared semantic dimension). Both discard structure
human speakers obviously possess: `happy` and `sad` are not *unrelated*,
they are *opposites on the evaluative dimension*. A system that can't
represent this can't distinguish "the opposite of X" from "something
unrelated to X."

### 4.2 The informational zero

Crucial to the ternary scheme: **0 is informational, not absent.** A 0 in
dimension `d` asserts that primitive `d` is orthogonal / non-applicable to
this concept — not "unknown." This distinguishes:

* `(GOOD = 0)` — "no evaluative dimension" (e.g., "rectangle")
* `(GOOD = +1)` — "evaluatively positive" (e.g., "happy")
* `(GOOD = −1)` — "evaluatively negative" (e.g., "sad")

The 0 carries semantic weight: it asserts a structural relationship to the
dimension.

### 4.3 Bipolar dimensions

Antonym pairs are encoded on **bipolar dimensions** — a single dimension
where the two poles share the partition with opposite signs, so the
negative pole is the exact negation of the positive pole and
`cosine(pole₊, pole₋) = −1.0` exactly. The system defines 14 such
dimensions (`BIPOLAR_DIMENSIONS` in `gse/primitives_v2.py`):

| Dimension | Positive pole | Negative pole | Bank |
|---|---|---|---|
| IDENTITY | SAME | OTHER | SUBSTANTIVES |
| EVALUATION | GOOD | BAD | EVALUATORS |
| SIZE | BIG | SMALL | EVALUATORS |
| VITALITY | ALIVE | DEAD | ACTION |
| DURATION | LONG_TIME | SHORT_TIME | TEMPORAL |
| TEMPORAL_ORDER | BEFORE | AFTER | TEMPORAL |
| TEMPORAL_REF | THEN | NOW | TEMPORAL |
| TEMPORAL_BOUND | START | END | TEMPORAL |
| VERTICAL | ABOVE | BELOW | SPATIAL |
| DISTANCE | FAR | NEAR | SPATIAL |
| CONTAINMENT | OUTSIDE | INSIDE | SPATIAL |
| DIRECTION | TOWARD | AWAY | SPATIAL |
| ACCOMPANIMENT | WITH | WITHOUT | SPATIAL |
| TRUTH | TRUE | FALSE | LOGICAL |

This canonicalization is what produces `cosine(happy, sad) ≈ −0.7` (they
share the GOOD/BAD dimension with opposite polarity) instead of ≈ 0.

### 4.4 Polarity-aware similarity

Beyond raw cosine, the substrate exposes a polarity-decomposed similarity
(`polarity_aware_similarity` in `gse/vectors_v2.py`):

```python
{
    "cosine":        standard_cosine(v1, v2),
    "alignment":     same_sign_overlap / |union|,     # synonymy signal
    "opposition":    opposite_sign_overlap / |union|, # antonymy signal
    "orthogonality": 1 - |shared| / |union|,          # unrelatedness signal
}
```

This lets downstream code distinguish "synonyms" from "opposites" — both
have high shared-dimension counts but opposite sign-agreement profiles.
The decoder's `SimilarityResult` surfaces exactly this breakdown.

---

## 5. Hadamard partition orthogonality

### 5.1 The problem

Random high-dimensional vectors are only *nearly* orthogonal
(concentration of measure): for the 8192-dim space, random pairs give
`|cosine|` small-but-nonzero. GSE needs **exact** orthogonality between
basis primitives — if `GOOD` and `BIG` occupy orthogonal banks, the cosine
must be exactly 0, so the system can distinguish "deliberately orthogonal"
from "noisy near-orthogonal." The informational-zero semantics demand it.

### 5.2 The Hadamard solution

Hadamard matrices have exactly orthogonal rows (`H·Hᵀ = n·I`). GSE uses a
**partition-based** scheme (`generate_hadamard_pattern`):

1. Each of the 8 banks owns a 1024-dim partition of the 8192-dim space.
2. Within a bank, each primitive is assigned a **non-overlapping** slice of
   indices, with signs taken from a Hadamard row.
3. Roles get disjoint slices spanning all banks, with Hadamard signs.

Because distinct primitives occupy disjoint index sets, `cosine(pᵢ, pⱼ) = 0`
*exactly* for `i ≠ j` (both within and across banks); role–role cosine is
exactly 0 as well. These orthogonality and antonym (`cosine = −1`)
properties are regression-guarded invariants in
`tests/test_basis_theory_invariants.py` and `tests/test_primitives_v2.py`.

### 5.3 Sparsity and balance

Each primitive's basis vector `b_p ∈ {−1, 0, +1}^d` satisfies:

* **Sparsity**: `‖b_p‖₀ = k ≪ d` — concentrated in one bank's partition.
* **Sign balance**: Hadamard rows are sign-balanced (equal +1/−1), so each
  primitive's pattern is balanced — with the single exception of the
  all-ones Hadamard row, which the first primitive in a bank may draw.
* **Exact orthogonality**: `⟨b_p, b_q⟩ = 0` for `p ≠ q`.

The basis is constructed once from the Hadamard matrix; there are no
learned weights, which is what makes the encoding deterministic and
verifiable.

---

## 6. The multi-scale architecture

### 6.1 Two orthogonal HDC subspaces

The core architectural commitment: **word-scale and sentence-scale occupy
separate, near-orthogonal partitions** of the 8192-dim space.

* `word_vec` (8192-dim sparse): *what the word means* (semantic primitives).
* `sent_vec` (8192-dim sparse): *what role the word plays* (syntactic
  primitives + `COMP_*` operators).
* Their bases use disjoint bank partitions, so `cosine(word, sentence) ≈ 0`.

A token's full vector **bundles** the two so both signals survive:

```python
full = bundle([word_vec, sent_vec])  # gse/api/encoder.py
```

(Earlier theory drafts wrote `bind` here; the live encoder uses `bundle`
for the reason given in Principle 4 — binding near-orthogonal vectors
destroys the signal.)

### 6.2 Word scale: 8 banks × 1024 dims

| Bank | Category | Example primitives |
|---|---|---|
| 0 | SUBSTANTIVES | I, YOU, SOMEONE, SOMETHING, PEOPLE, BODY, SAME, OTHER |
| 1 | QUANTITY | ONE, TWO, SOME, ALL, MUCH, FEW |
| 2 | EVALUATORS | GOOD, BAD, BIG, SMALL, VERY, MORE |
| 3 | MENTAL | THINK, KNOW, WANT, FEEL, SEE, HEAR |
| 4 | ACTION | SAY, DO, HAPPEN, MOVE, BE, HAVE, ALIVE, DEAD |
| 5 | TEMPORAL | WHEN, NOW, BEFORE, AFTER, LONG_TIME, SHORT_TIME |
| 6 | SPATIAL | WHERE, ABOVE, BELOW, NEAR, FAR, INSIDE |
| 7 | LOGICAL | NOT, MAYBE, CAN, BECAUSE, IF, TRUE, FALSE |

(Bank identities are the `SemanticBank` enum in `gse/primitives_v2.py`.
Example primitives are illustrative of each bank's category.)

### 6.3 Sentence scale: 8 banks × 1024 dims

| Bank | Category | Primitives |
|---|---|---|
| 0 | CORE_STRUCTURE | SYN_SUBJ, SYN_PRED, SYN_OBJ, SYN_COMPL |
| 1 | MODIFICATION | SYN_ADJ_MOD, SYN_ADV_MOD, SYN_DET |
| 2 | TAM | SYN_TENSE_{PAST,PRES,FUT}, SYN_ASPECT_{PERF,PROG}, SYN_MOOD_{IMPER,INTER} |
| 3 | COMPARISON | COMP_THAN (SET_DIFF), COMP_AS (BIND_EQ) |
| 4 | QUANTIFICATION | COMP_HOW (DEGREE_QUERY), COMP_WHAT (TYPE_QUERY) |
| 5 | CONSTRAINT | COMP_JUST (CARD_LOWER), COMP_ONLY (SET_RESTRICT), COMP_EVEN (SCALAR_EXTREME) |
| 6 | DISCOURSE | COMP_BUT (CONTRAST), COMP_SO (CONSEQUENCE), COMP_BECAUSE (CAUSAL_SOURCE) |
| 7 | RESERVED | (unused) |

(This table matches `SENTENCE_PRIMITIVE_REGISTRY` exactly.)

### 6.4 Why scale separation matters

The word "did" can be a main verb ("she did her hair") or an auxiliary
("she did not run"). With separated scales:

* Word-scale `⟦did⟧` carries the bare content (DO).
* Sentence-scale `⟦did⟧` activates the syntactic role from the parse —
  orthogonal to word-scale.
* The two bundle at composition time, so the disambiguated reading
  propagates without polluting the word-scale lookup.

Ambiguity that lives on one scale doesn't contaminate the others.

---

## 7. Compositional operators as set theory

### 7.1 The architectural commitment

From `sentence_architecture.md` line 164:

> The API for engaging with the system should be pure Python / order of
> operations / set theory — not direct vector math for the full sentence.

The HDC layer carries semantic *content*; the composition layer is
*symbolic*. This split is what makes the architecture's signature guarantee
work: "dog cuter than cat" and "cat cuter than dog" are *similar in HDC
space* (cosine ≈ 0.93) yet *distinct symbolically* (argument-swap detected;
comparison signs opposite).

### 7.2 The 10 compositional operators

Each `COMP_*` primitive carries an operation label and a pure-Python
dispatch function (`gse/symbolic/operators.py`, `OPERATION_DISPATCH`):

| Operator | Operation | Semantics | Predicate |
|---|---|---|---|
| COMP_THAN | SET_DIFF | `X taller than Y` → signed difference | `Comparison(lhs, rhs, sign=+1)` |
| COMP_AS | BIND_EQ | `X as tall as Y` → symmetric equivalence | `Equality(lhs, rhs)` |
| COMP_HOW | DEGREE_QUERY | `How tall is X?` | `DegreeQuery(entity)` |
| COMP_WHAT | TYPE_QUERY | `What is X?` → SUBSTANTIVES decomposition | `TypeQuery(entity)` |
| COMP_JUST | CARD_LOWER | `just enough mustard for Ben` | `MinimalSufficiency(threshold, purpose)` |
| COMP_ONLY | SET_RESTRICT | `Only X sings` → ∀Y: sings(Y) → Y=X | `SetRestriction(member, predicate)` |
| COMP_EVEN | SCALAR_EXTREME | *(deferred — inert placeholder)* | `BoundaryCase` |
| COMP_BUT | CONTRAST | `X but Y` → both asserted | `Contrast(left, right)` |
| COMP_SO | CONSEQUENCE | `X so Y` → X cause, Y effect | `Causation(cause=X, effect=Y)` |
| COMP_BECAUSE | CAUSAL_SOURCE | `X because Y` → Y cause, X effect | `Causation(cause=Y, effect=X)` |

The set-theory semantics are *evaluated symbolically*, never via vector
operations. `COMP_EVEN` is the one acknowledged gap — it records the
operation without asserting its scalar-extreme universal (see
[§11](#11-not-yet-implemented)).

### 7.3 Why this layer exists

Without it, "Mike is taller than Rex" and "Rex is taller than Mike" encode
to *similar* vectors — both about Mike, Rex, and TALL — but they have
*different truth conditions*, and vector similarity has no answer for
"which is true." With the symbolic layer, the encoder's `OperationTrace`
lifts to an `Expression` AST that evaluates to a `Comparison` with
`sign = +1` for one and the swapped structure for the other. Truth
conditions are **derived** compositionally from primitives + operator
dispatch — the load-bearing piece of the survey's criterion (4).

---

## 8. The runtime pipeline: trace → AST → predicate

The theory above becomes a deterministic computation through a fixed
pipeline (full detail in `ARCHITECTURE.md` §2–4):

```
sentence
  → GSEEncoder.encode        spaCy parse + lexicon lookup + two-scale HDC encode
  → OperationTrace            HDC vector + token traces + operator traces
  → from_trace               lift to a typed AST (Atom / Phrase / Negation / Op)
  → resolve                  collapse phrases into Entities; bind pronouns
  → evaluate_tree            dispatch each Op to its set-theory predicate
  → queries / serialization  entities(), predicates(), axis_of_comparison(),
                             is_argument_swap_of(), to_json(), substitute()
```

Two theoretical points this pipeline makes concrete:

* **The lexicon is the meaning store.** All lexical content lives in
  `data/lexicon.db` (~1.36M lexemes, ~13.7M primitive assignments) as
  explicit `(primitive, polarity)` decompositions — *primitives, never
  pre-encoded answers*. "Taller(Mike, Rex)" is never stored; it is derived
  at evaluation time from the TALL-primitive activations and the SET_DIFF
  dispatch.

* **Two views, one trace.** The same `OperationTrace` feeds (a) the
  **symbolic path** above, which carries compositional truth, and (b) the
  **vector path** (`GSEDecoder`), which carries HDC geometry (similarity,
  nearest lexemes, bank profile). The architecture's central claim — *quite
  similar in HDC space, provably distinct symbolically* — is precisely the
  gap between these two views of one encoding.

---

## 9. Mathematical formalism (summary)

**Vector space.** `(V, ⟨·,·⟩, ⊗, ⊕, ρ)` where `V = ℝ^d`, `d = 8192`
(8 banks × 1024), realized as sparse ternary `{−1, 0, +1}` vectors;
`⊗` = binding (element-wise product), `⊕` = bundling (sum + sign
normalization), `ρ` = permutation (circular shift).

**Ternary encoding.** Each primitive `p` has basis `b_p ∈ {−1, 0, +1}^d`
with sparsity `‖b_p‖₀ = k ≪ d`, sign balance (per §5.3), and exact
orthogonality `⟨b_p, b_q⟩ = 0` for `p ≠ q`.

---

## 10. What GSE explicitly does *not* claim

1. **Not "general intelligence."** GSE is an encoding layer for
   compositional sentence-level semantics — not a planner, agent, or
   knowledge base.
2. **Not "death to LLMs."** LLMs win at coverage, generation, world
   knowledge, robustness to ill-formed input, and discourse-level
   reasoning. GSE occupies a different architectural quadrant.
3. **Not "the Bitter Lesson is universally false."** The weak form (scaling
   has historically dominated structure) stands. The strong/prescriptive
   form (structure-encoding is unproductive) is what GSE falsifies — see
   [POSITIONING_SURVEY.md](POSITIONING_SURVEY.md).
4. **Not "all of NLP is structurable this way."** Discourse, pragmatics,
   world knowledge, long-tail vocabulary may still be scaling-dominant. The
   current demonstration is sentence-level evaluative semantics.
5. **Not "first solution to the hard problem of GOFAI."** Quantification,
   hypothetical chaining, and other deductive infrastructure are
   *trivially extensible* under the fold-in rule but are not yet
   demonstrated ([§11](#11-not-yet-implemented)).

What GSE *does* claim:

> There exists a productive structured-encoding route to compositional
> semantic capabilities that the field assumed was empty. The route uses
> HDC's geometric grounding to escape the frame problem, NSM's primitive
> basis to give meaning a finite decomposition, ternary encoding to
> distinguish synonymy/antonymy/orthogonality, and a pure-Python
> set-theory layer for compositional truth — producing deterministic
> outputs from primitive activations at laptop scale.

---

## 11. Not yet implemented

These are intended directions consistent with the architecture but **not
present in the functional system.** They are recorded as the research
program, not as current capability. (The survey treats the first two as
"trivially extensible" under the fold-in rule.)

* **Quantifiers (ALL / SOME).** New primitives in a quantifier bank plus
  dispatch functions. Mechanical addition; no new architecture.
* **Quantifier scope via permutation.** The intended encoding uses
  permutation levels to mark scope, e.g. for "Every student read some book"
  (∀ > ∃): `ρ⁰(SCOPE)⊗⟦every student⟧ ⊕ ρ¹(SCOPE)⊗⟦some book⟧ ⊕ ⟦read⟧`.
  Sketched, not built.
* **Montague type bridge.** Mapping Montagovian types (e, t, ⟨e,t⟩) onto
  subspaces, with lambda abstraction as binding and β-reduction as
  unbinding. A theoretical correspondence, not implemented code.
* **Hypothetical chaining / modus tollens.** AST traversal over existing
  CONSEQUENCE / CAUSAL_SOURCE chains; no new primitives required.
* **COMP_EVEN / scalar extreme.** Requires hierarchical-network traversal
  coherence math beyond first-order operator dispatch. The live system
  records the operation as an inert `BoundaryCase`.
* **Paragraph- and text-scale.** Discourse and document scales are part of
  the multi-scale vision but have no functional operators; the system today
  is sentence-scale only.

---

## 12. Open theoretical problems

1. **Primitive completeness.** Are ~74 word-scale primitives sufficient for
   the structurable subset of English? NSM is the empirical anchor; whether
   the sentence-scale operators are complete for the "see Spot run" tier is
   open.
2. **Cross-linguistic validity.** Do the encodings transfer to other
   languages, given NSM's universality claim? Untested.
3. **Grounding.** GSE assumes primitives are pre-grounded; whether they
   could be grounded *from* perception/action via the same geometric
   machinery is open.
4. **Discourse and document scale.** Beyond the sentence tier, what are the
   right compositional operators? ([§11](#11-not-yet-implemented).)
5. **Where is gradient-based learning appropriate?** Current answer:
   front-end POS / dependency parsing only. Whether any other component
   benefits from differentiable parts is open.

---

## 13. The bottom line

GSE proposes that meaning has structure, that the structure has a finite
basis, and that the basis can be encoded geometrically with exact
orthogonality and compositional algebra. Out of this falls deterministic
compositional truth on sentence-level evaluative queries — at laptop scale,
with no neural network at the semantic layer.

This is one architectural quadrant of the AI design space, currently
believed to be unoccupied. GSE is a proof-by-existence that the quadrant is
not empty. Whether it generalizes to wider parts of language is the
research program, not the current claim.

For the structural argument about why the quadrant has been empty, see
[POSITIONING_SURVEY.md](POSITIONING_SURVEY.md). For the system design that
implements this theory, see [ARCHITECTURE.md](ARCHITECTURE.md).
</content>
