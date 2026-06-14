# GSE Architecture

> **Status.** This document describes the **functional core** of GSE as it
> actually runs in the code, verified by reading the source and tracing the
> import graph (June 2026). It is the architecture that backs the claims in
> [`POSITIONING_SURVEY.md`](POSITIONING_SURVEY.md).
>
> **Authoritative sources, in order:** Rohan, then the code. This doc follows
> the code. Where older planning docs or the root `README.md` disagree with
> what is written here, *they* are the drift — see [§7 Drift map](#7-drift-map).
> `docs/THEORY.md` is known-invalid and is not used as a source anywhere below.
>
> **Scope.** Sentence-level evaluative semantics — the "see Spot run" tier.
> Everything documented here is reachable from the public API and exercised by
> the test suite and proof suites.

---

## 1. The one-paragraph version

GSE turns an English sentence into (a) a sparse ternary **HDC vector** and (b) a
typed **symbolic AST** of predicates, deterministically and on a laptop. A
sentence is parsed by spaCy, each token is looked up in a precompiled lexicon of
primitive decompositions, those primitives are encoded into an 8192-dim
Hadamard-orthogonal vector space at two scales (word-scale meaning +
sentence-scale syntax), and compositional operators (`than`, `as`, `so`,
`because`, …) are resolved into an `OperationTrace`. The symbolic layer then
lifts that trace into an AST, resolves entities, and dispatches each operator to
a pure-Python set-theory function that yields predicates like
`Comparison(lhs=dog, rhs=cat, sign=+1)`. No neural network runs at the semantic
layer; the same input always produces the same output.

---

## 2. The functional pipeline (the spine)

```
  "The dog is cuter than the cat"
            │
            ▼
   ┌─────────────────────┐
   │  gse.api.GSEEncoder  │   spaCy parse + lexicon lookup + HDC ops
   │     .encode(text)    │
   └─────────────────────┘
            │   produces
            ▼
   ┌─────────────────────┐
   │   OperationTrace     │   HDC vector  +  token traces  +  operator traces
   │  (gse.api.trace)     │   ── JSON-serializable, deterministic ──
   └─────────────────────┘
            │
   ┌────────┴───────────────────────────┐
   │                                     │
   ▼ symbolic path                       ▼ vector path
 from_trace(trace)                  gse.api.GSEDecoder
   → Expression AST                   .decode(vector)  → DecodedSemantics
            │                          .similarity(v1,v2) → SimilarityResult
            ▼
 resolve(ast)                        (vector-space view: entities, attributes,
   → entities bound                   relations, nearest lexemes, bank profile)
            │
            ▼
 evaluate_tree(ast)
   → Predicates (Comparison, Causation, Equality, …)
            │
            ▼
 queries / serialization / templating
   entities(), predicates(), axis_of_comparison(),
   is_argument_swap_of(), is_logically_equal_to(),
   to_json()/from_json(), substitute()
```

The two paths share the encoder output. The **symbolic path** is the one that
carries the positioning claims (grounded, deterministic, compositional truth);
the **vector path** is the HDC geometry (similarity, decoding back to lexemes).
The architecture's guarantee — "two sentences quite similar in HDC space but
provably distinct symbolically" — is exactly the split between these two paths.

### Worked example (`gse/verification/symbolic_proof_suite.py:85`)

```python
from gse.api import GSEEncoder
from gse.symbolic import from_trace, resolve, evaluate_tree, predicates

enc   = GSEEncoder()                                  # opens data/lexicon.db, loads spaCy
trace = enc.encode("The dog is cuter than the cat")   # → OperationTrace
tree  = evaluate_tree(resolve(from_trace(trace)))      # → Comparison predicate
predicates(tree)        # [Comparison(lhs=Entity(dog), rhs=Entity(cat), sign=+1)]

# Argument-swap is symbolically distinct but HDC-similar:
v1 = enc.encode("The dog is cuter than the cat").vector
v2 = enc.encode("The cat is cuter than the dog").vector
v1.cosine(v2)           # ≈ 0.93  (similar geometry)
# is_logically_equal_to(tree1, tree2) → False  (distinct logic)
# is_argument_swap_of(tree1, tree2)   → True
```

---

## 3. Layers, bottom-up

### Layer 0 — HDC substrate · `gse/vectors_v2.py`, `gse/primitives_v2.py`

The mathematical floor. Pure NumPy/SciPy; no I/O, no neural anything.

**Dimensions and banks** (`primitives_v2.py:23`):

| Constant | Value | Meaning |
|---|---|---|
| `D` | `8192` (2¹³) | total vector dimension — power of two so Hadamard matrices exist |
| `N_BANKS` | `8` | semantic banks, each owning a disjoint 1024-dim slice |
| `DIMS_PER_BANK` | `1024` | `D // N_BANKS` |

The 8 banks (`SemanticBank`): `SUBSTANTIVES`, `QUANTITY`, `EVALUATORS`,
`MENTAL`, `ACTION`, `TEMPORAL`, `SPATIAL`, `LOGICAL`.

**`SparseVector`** — ternary `{-1, 0, +1}` stored as two `uint16` index arrays
(`positive_indices`, `negative_indices`); everything else is implicitly 0.
Operations: `dot`, `cosine`, `negate`, `with_bank_only` / `without_bank` (bank
masking), `serialize`/`deserialize` (msgpack), content `hash`.

**Hadamard-OTP basis** (`HadamardOTPBasis`, `create_basis()`): each primitive
gets a **non-overlapping partition** of its bank's dimensions, with signs taken
from a Hadamard row. Non-overlapping index sets ⇒ **exact** orthogonality
(`cosine = 0.0`) between distinct primitives, not the approximate orthogonality
of random HDC vectors. Antonyms are **bipolar**: the negative pole is the exact
negation of the positive pole, so `cosine(GOOD, BAD) = −1.0`. There are 14
bipolar dimensions (`BIPOLAR_DIMENSIONS`, e.g. `EVALUATION: GOOD/BAD`,
`SIZE: BIG/SMALL`, `VERTICAL: ABOVE/BELOW`).

**Sentence-scale basis** (`SentenceScaleBasis`, `create_sentence_basis()`): a
second basis over the *same* 8192-dim space using distinct bank partitions, for
the `SYN_*` syntactic roles and `COMP_*` compositional operators. Carries
`comp_metadata` (arity + operation) per operator.

**Core HDC ops** (module-level functions):
- `bind(a, b)` — element-wise ternary multiply; result dissimilar to both inputs (role/structure binding).
- `bundle(vectors)` — majority-vote superposition; result similar to all inputs (set membership).
- `permute(v, shift)` — circular shift; encodes token position.

### Layer 1 — Lexicon data · `data/lexicon.db` (SQLite)

The precompiled decompositions. **This is the live database the encoder opens by
default** (`GSEEncoder(db_path="data/lexicon.db")`). Run commands from the repo
root so the relative path resolves.

Live contents (June 2026):

| Table | Rows | Role |
|---|---:|---|
| `lexemes` | 1,355,619 | one row per (lemma, pos, sense); carries `comp_primitive`, `comp_arity`, `comp_operation` for operator words |
| `primitive_values` | 13,679,042 | word-scale primitive activations per lexeme (74 distinct primitives) |
| `sentence_primitive_values` | 30,619 | sentence-scale `SYN_*` / `COMP_*` activations (17 distinct) |

Supporting tables: `decomposition_provenance`, `validation_results`,
`llm_batches`, `processing_checkpoints` (build-time bookkeeping, not read at
encode time). All lexeme `source` values are `llm` — the lexicon was generated
by the curation pipeline (§6).

The encoder reads three queries only: lexeme row (for compositional metadata),
`primitive_values`, and `sentence_primitive_values`. The DB is otherwise opaque
to runtime.

> The root-level `lexicon.db` (123 KB, 0 rows) is a stale empty stub. Do not
> point the encoder at it. See [§7](#7-drift-map).

### Layer 2 — Encoder · `gse/api/encoder.py`

`GSEEncoder.encode(text) -> OperationTrace`. The steps:

1. **Parse** — spaCy `en_core_web_sm` tokenizes, lemmatizes, dependency-parses,
   and tags morphology. (spaCy is the one trained component, and it sits *in
   front of* the semantic layer — see the determinism caveat in the survey.)
2. **Per-token lookup** — `_lookup_lexeme(lemma)` pulls word-scale + sentence-scale
   primitives and any compositional metadata from `data/lexicon.db`.
3. **Dynamic syntactic roles** — `_extract_dynamic_primitives` overrides the
   static core-role primitives (`SYN_SUBJ`/`SYN_OBJ`/`SYN_PRED`/`SYN_COMPL`) using
   the spaCy dependency label (`DEP_TO_SYNTACTIC` map) and TAM from morphology.
   **This is what makes argument order matter** — "dog as subject" ≠ "dog as
   object."
4. **Two-scale encoding** — word-scale primitives → `word_vec`, sentence-scale →
   `sent_vec`, combined per token via `bundle` (preserves both signals).
5. **Operator resolution** — `_resolve_operator` finds each operator's left/right
   argument spans by position and applies the HDC operation named by
   `comp_operation` (`SET_DIFF`, `DEGREE_QUERY`, `CONTRAST`, …), recording an
   `OperatorTrace`.
6. **Sentence bundle** — position-permuted token vectors + operator results are
   bundled into the final sentence vector; primitive activations and a content
   hash are computed.

`strict=True` raises `OOVError`/`PrimitiveError`; the default `strict=False`
degrades gracefully (OOV words contribute nothing).

### Layer 3 — Trace · `gse/api/trace.py`

The JSON-serializable contract between encoder and everything downstream.

- **`TokenTrace`** — token, lemma, POS, position, word/sentence primitives, nnz
  stats, operator flags.
- **`OperatorTrace`** — `primitive` (`COMP_THAN`), `operation` (`SET_DIFF`),
  position, arity, `arg1_tokens`/`arg2_tokens` + lemmas. Carries the structural
  comparison helpers `structurally_equals`, `is_argument_swap_of`,
  `get_entity_args`.
- **`OperationTrace`** — the whole thing: input text, token traces, operator
  traces, final nnz/sparsity, primitive activations, vector hash, `deterministic`
  flag. `.vector` holds the live `SparseVector` (not serialized). `to_json()` /
  `from_dict()` round-trip everything except the vector.
- **`DecodedSemantics`, `SimilarityResult`** and their parts — the decoder's
  output types (§ decoder below).

### Layer 4 — Symbolic evaluator · `gse/symbolic/`

Pure Python, set theory, no HDC math (per `sentence_architecture.md` line 164).
Four stages, each a module:

- **`expression.py` — `from_trace(trace) -> Expression`.** Lifts an
  `OperationTrace` into a typed AST of four node kinds: `Atom` (one token),
  `Phrase` (unresolved multi-token span), `Negation` (a `-1` sign direction —
  NOT is treated as a directional argument, not an operator), and `Op` (a
  compositional operator with `operation` label + args). Multiple operators are
  left-folded by position.
- **`resolution.py` — `resolve(ast) -> ast'`.** Collapses `Phrase`s into
  `Entity` nodes: entity grouping ("the cat" → `Entity(head=cat)`), possessive
  structuring ("Mike's dog" → `Entity(head=dog, possessor=Entity(head=mike))`),
  and within-sentence pronoun binding (nearest preceding referent; no
  gender/number agreement; single-sentence only). `Entity` also preserves the
  ADJ/ADV `modifier` so the comparison axis is recoverable.
- **`operators.py` + `predicates.py` — `evaluate_tree(ast) -> predicates`.**
  Each `Op` is dispatched by its `operation` label through `OPERATION_DISPATCH`
  to a one-line set-theory function producing a frozen `Predicate` dataclass:

  | Operation | Operator word | Predicate produced |
  |---|---|---|
  | `SET_DIFF` | than | `Comparison(lhs, rhs, sign=+1)` |
  | `BIND_EQ` | as…as | `Equality(lhs, rhs)` |
  | `DEGREE_QUERY` | how | `DegreeQuery(entity)` |
  | `TYPE_QUERY` | what | `TypeQuery(entity)` |
  | `CARD_LOWER` | just (enough) | `MinimalSufficiency(threshold, purpose)` |
  | `SET_RESTRICT` | only | `SetRestriction(member, predicate)` |
  | `CONTRAST` | but | `Contrast(left, right)` |
  | `CONSEQUENCE` | so | `Causation(cause=left, effect=right)` |
  | `CAUSAL_SOURCE` | because | `Causation(cause=right, effect=left)` |
  | `SCALAR_EXTREME` | even | `BoundaryCase` — **inert placeholder, deferred** |

  `SCALAR_EXTREME`/EVEN is recorded but does not assert its universal — the one
  acknowledged non-trivial extension (needs hierarchical-network coherence math).

- **`queries.py` — the consumer interface.** Pure tree-walks over the evaluated
  tree: `entities()`, `entity_lemmas()`, `predicates()`, `axis_of_comparison()`,
  `is_logically_equal_to()` (structural signature equality), `is_argument_swap_of()`.
- **`serialization.py`** — `to_json`/`from_json`/`to_dict`/`from_dict` for the
  symbolic tree (structure-preserving round-trip).
- **`templating.py`** — `substitute(tree, {lemma: new_lemma})` for structural
  substitution ("dog→rabbit, cat→mouse" preserves the comparison structure).

### Decoder · `gse/api/decoder.py`

The reverse / geometric view. `GSEDecoder.decode(vector) -> DecodedSemantics`
reads entities, attributes, relations, nearest lexemes (DB-backed), and the bank
activity profile straight out of the HDC vector. `similarity(v1, v2, …) ->
SimilarityResult` reports cosine + alignment/opposition/orthogonality breakdown.

### Verification · `gse/verification/`

- **`symbolic_proof_suite.py`** — the line-154 validation: 7 end-to-end proofs
  (recover entities, recover the cuteness assertion, distinguish argument swap,
  templating preserves structure, causation directionality, JSON round-trip,
  bipolar-vs-relational). Run: `python -m gse.verification.symbolic_proof_suite`.
- **`proof_suite.py`** — `GSEProofSuite`, the HDC-level proof suite the CLI's
  `verify` command runs.

---

## 4. Interface surfaces

These are the surfaces you import or call when interfacing with GSE. Everything
else is internal.

### 4.1 `gse.api` — encode / decode (primary surface)

```python
from gse.api import GSEEncoder, GSEDecoder

enc   = GSEEncoder(db_path="data/lexicon.db", strict=False)
trace = enc.encode("The dog is cuter than the cat")   # OperationTrace
trace.to_json()                                        # JSON (no vector)
trace.vector                                           # SparseVector

dec  = GSEDecoder()
dec.decode(trace.vector)                               # DecodedSemantics
dec.similarity(v1, v2, s1, s2)                         # SimilarityResult
```

Errors (`gse.api.errors`): `GSEError` ⊃ `OOVError`, `EncodingError`,
`PrimitiveError`, `OperatorError`, `DecodingError`. Both classes are context
managers (`with GSEEncoder() as enc:`) and hold a SQLite connection — call
`.close()` or use `with`.

Trace types (`gse.api.trace`) are the stable data contract:
`OperationTrace`, `TokenTrace`, `OperatorTrace`, `DecodedSemantics`,
`SimilarityResult`, `EntityExtraction`, `AttributeExtraction`,
`RelationExtraction`.

### 4.2 `gse.symbolic` — symbolic reasoning surface

```python
from gse.symbolic import (
    from_trace, resolve, evaluate_tree,            # the pipeline
    entities, entity_lemmas, predicates,           # queries
    axis_of_comparison, is_argument_swap_of, is_logically_equal_to,
    to_json, from_json, substitute,                # serialize / template
    Comparison, Equality, Causation, Contrast,     # predicate types
    TypeQuery, DegreeQuery, MinimalSufficiency,
    SetRestriction, BoundaryCase,
    Atom, Phrase, Negation, Op, Entity,            # AST node types
    OPERATION_DISPATCH,                            # operator → semantics map
)
```

This is the "pure Python / order of operations / set theory" API the
architecture mandates. It never calls back into HDC.

### 4.3 `gse.cli` — command line

```bash
python -m gse.cli encode "The dog is cuter than the cat" [--format json|summary]
python -m gse.cli compare "I love you" "I hate you"
python -m gse.cli decode --text "The big dog" [--trace file.json]
python -m gse.cli verify
python -m gse.cli interactive
```

Backed entirely by `gse.api` + `gse.verification` — no separate logic.

### 4.4 The HDC substrate (advanced / extension surface)

`from gse.vectors_v2 import SparseVector, bind, bundle, permute, create_basis,
create_sentence_basis` and `from gse.primitives_v2 import D, N_BANKS,
DIMS_PER_BANK, SemanticBank, BIPOLAR_DIMENSIONS`. Only needed when extending the
primitive set or working below the trace level.

---

## 5. Determinism & cost (why the positioning claims hold here)

- **Determinism** — downstream of the spaCy parse there is no stochasticity: DB
  lookups, fixed Hadamard bases, integer set operations, dispatch on string
  labels. Same input → same vector hash → same predicates. The `deterministic`
  flag on `OperationTrace` is structural, not aspirational.
- **Cost** — the basis is ~1 MB of sparse vectors; per-sentence cost is a spaCy
  parse plus O(tokens) HDC ops. No GPU, no training run, no scaling. Laptop-class.
- **Grounding** — `Comparison(lhs=dog, rhs=cat, sign=+1)` is derived from the
  SET_DIFF over primitive activations, not retrieved from a `taller(dog,cat)`
  predicate. The lexicon stores *primitives*, never pre-encoded answers.

---

## 6. Offline: how `data/lexicon.db` is built

The lexicon is **generated offline**, not at runtime. This tooling is necessary
to *reproduce* the data but is not imported by the functional spine.

- **`gse/curation/`** — the lexicon-construction pipeline: `external_sources/`
  (WordNet, ConceptNet, FrameNet, VerbNet, PropBank, NRC-VAD/Emotion, Lancaster
  Sensorimotor, SentiWordNet, USAS, Wiktionary, concreteness), `llm/` (LLM-driven
  decomposition + gap filling), `constraint_aggregation/` (merging conflicting
  sources), `decomposition/`, `validation/`, `pipeline/`.
- **`scripts/`** — entry points and one-offs: `generate_lexicon.py`,
  `rebuild_lexicon_from_sources.py`, `populate_sentence_primitives.py`,
  `validate_lexicon.py`, `validate_architecture.py`, plus enrichment/audit
  scripts.

Treat this as a data-build subsystem: its output is `data/lexicon.db`; its
internals are out of scope for *using* GSE.

---

## 7. Drift map

Per the working agreement, sources that contradict the functional core are
drift. Confirmed drift / not on the functional path:

| Item | Status | Why |
|---|---|---|
| `docs/THEORY.md` | **invalid** | Declared known-invalid; not a source. |
| root `README.md` | **stale** | Claims 10,000-dim vectors, `gse.pipeline.load_pipeline`, `data/basis.msgpack`, a Merkle-coherence `process()` pipeline. None match the 8192-dim `gse.api` core. |
| root `lexicon.db` (123 KB) | **stale stub** | 0 rows. The live DB is `data/lexicon.db` (2.3 GB). |
| `gse/__init__.py` top-level exports | **misleading** | Re-exports `GSEPipeline`, `merkle`, `patterns`, etc. The functional `gse.api`/`gse.symbolic` core does **not** import these. Docstring says "~45 primitives / 8 banks" — banks correct, count understated (74 word-scale primitives live). |
| `gse/_archive/` | **archived** | Self-evidently old. Exclude. |
| `gse/pipeline_v2.py` (`GSEPipeline`) | **older stack** | A separate entry point built on the Merkle lexicon + learning networks; not the path the positioning claims run through. |
| `gse/merkle/` | **older stack** | Merkle-tree lexicon. The functional encoder reads a flat SQLite lexicon instead. |
| `gse/patterns/` | **contradicts core** | Hebbian "learning networks" — adaptation conflicts with the determinism guarantee at the semantic layer. |
| `gse/encoders/`, `gse/nlp/sentence_parser.py`, `gse/scales/`, `gse/composition/`, `gse/parsing/`, `gse/evaluation/`, `gse/teaching/`, `gse/profiles/`, `gse/orchestration/`, `gse/graph/` | **not on the spine** | None are imported by `gse.api`/`gse.symbolic`/`gse.cli`. Older or auxiliary; treat as drift unless wired back in. |

Other root docs (`UNIFIED_ARCHITECTURE.md`, `SYSTEM_SUMMARY.md`, `STATUS.md`,
`gse_implementation_spec.md`) predate the current core and are unverified — defer
to this document and the code.

> If any module in the bottom rows of that table is in fact live and I've
> mislabeled it, tell me which and I'll fold it into the spine — the
> classification is by import-reachability from the public API, not by judgment
> about its value.

---

## 8. Module reference (functional core only)

| Module | Responsibility |
|---|---|
| `gse/primitives_v2.py` | Banks, dimensions, bipolar definitions, primitive registries |
| `gse/vectors_v2.py` | `SparseVector`, Hadamard-OTP bases, `bind`/`bundle`/`permute` |
| `data/lexicon.db` | Precompiled lemma → primitive decompositions (live data) |
| `gse/api/encoder.py` | `GSEEncoder`: text → `OperationTrace` |
| `gse/api/decoder.py` | `GSEDecoder`: vector → `DecodedSemantics`, similarity |
| `gse/api/trace.py` | `OperationTrace`/`TokenTrace`/`OperatorTrace` + decoded types |
| `gse/api/errors.py` | Exception hierarchy |
| `gse/symbolic/expression.py` | AST + `from_trace` |
| `gse/symbolic/resolution.py` | `resolve`: phrases → entities, pronoun binding |
| `gse/symbolic/operators.py` | Operator dispatch + `evaluate_tree` |
| `gse/symbolic/predicates.py` | Predicate dataclasses |
| `gse/symbolic/queries.py` | `entities`/`predicates`/`axis_of_comparison`/swap checks |
| `gse/symbolic/serialization.py` | Symbolic-tree JSON round-trip |
| `gse/symbolic/templating.py` | `substitute` |
| `gse/cli/main.py` | CLI over the API |
| `gse/verification/symbolic_proof_suite.py` | Line-154 end-to-end proofs |
| `gse/verification/proof_suite.py` | HDC-level proof suite (`GSEProofSuite`) |
| `gse/curation/**`, `scripts/**` | Offline lexicon construction (build-time only) |
</content>
</invoke>
