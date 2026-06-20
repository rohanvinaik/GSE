# GSE Roadmap — Parser, Sentence Scale, and Beyond

> Captured 2026-06-19 from a long working session. This is a *forward plan*, not a
> spec — it records the reasoning behind each direction so we can resume without
> re-deriving. (Per CLAUDE.md, docs are not ground truth; Rohan + the code are.)

## Where we are (snapshot)

Branch `feat/resolved-structure`. Done and committed this session:
- **Parse-repair** (`gse/api/parse_repair.py`): promote spaCy-mistagged buried
  verbs to `VERB` via WordNet verb-sense + entity-flanking → recovers dropped subjects.
- **Coherence gate** (`gse/symbolic/coherence.py`): post-build collapse detector;
  surfaces degraded clauses so Genesis can *abstain*. Wrapper pattern, zero core edits.
- **Typed variables** (`gse/symbolic/variables.py`) + the variables↔coherence compose.
- **A-theme (embedded predication) complete:** A1 relative-clause gap-binding,
  A2 clausal-complement embedding, A3 control. All bind correctly.
- **L1 compositionality ladder** (`tests/test_l1_ladder.py`): the spine that forces
  each feature to be additive; frontier rungs = the roadmap.
- **Clean NSM lexicon rebuild** (`docs/LEXICON_REBUILD.md`, commit 66c4a4c): the
  degenerate `lexicon.db` (bag-of-words primitives, `dog≈murder`) replaced by a clean
  **67K-word** ternary lexicon at `data/lexicon_clean.db` — sparse (~1.9 primes/word),
  discriminative + synonym-collapsing (dual margin +0.228), `test_l1_ladder` 15/15.
  Directly addresses the leaf-grounding bottleneck below. Not yet the encoder default
  (vector-path test tolerances assume the dense lexicon — a deliberate recalibration,
  plus one resolution coupling `np_coordination` to fix).

Suite green at 2225.

---

## Workstream 1 — Replace spaCy with a deterministic, GSE-native parser ✅ DONE

**"Launch spaCy into space."** **Landed.** The runtime encoder path no longer
uses spaCy. Delivered in arc-free-first order (each step parity-gated against
spaCy on an 87-sentence golden register, suite green at every commit):

1. **`verbs_to_promote`** (`253b780`) — the verb-POS-mistag repair derives its
   flanking-entity signal from linear position, not `children`/`head`.
2. **`_detect_embedded_clauses`** (`1a515c7`) — relative/control/complement
   clauses bounded from the connective inventory + verb-inventory + position,
   not `relcl`/`xcomp`/`ccomp` arcs. *Trace-byte-identical* to the arc version.
3. **`_syn_roles`** (`31d557a`) — core syntactic roles (SUBJ/PRED/OBJ/COMPL)
   assigned positionally, not from `dep_`. 0 struct divergence; vector
   recalibration only (the deliberate one flagged below).
4. **GSE-native token engine** (`86398cd`, `gse/nlp/native.py`) — deterministic
   tokenizer + WordNet-morphy lemmatizer + coarse-UPOS tagger replace
   `spacy.load`. `GSEEncoder(engine="native")` is the default; `"spacy"` remains
   for the parity harness (`scripts/ws1_parity.py`, `ws1_characterize.py`).

Full suite after the swap: 3941 passed; the 9 failures are pre-existing
curation-env issues (none touch the encoder). spaCy is retired from the encoder;
it remains only the **bootstrap definition-parser** for the lexicon build
(`gse/curation/decomposition/definition_structure.py`) — explicitly in-scope to
keep. Remaining tidiness (non-blocking): the legacy `*_arcs` reference functions
in `parse_repair`/`encoder` are dead in production, kept only for the parity A/B.

**Original rationale (retained for the record):**

**Why.** (a) Determinism — spaCy (`en_core_web_sm`) is the *only* non-deterministic
component, and the source of every parse bug we've patched. (b) Positioning — spaCy
invites the persistent misread "GSE is just a neural-net wrapper." (c) It's the
project's actual thesis: structure recovery *from meaning*, which a syntax-only
statistical model fundamentally cannot do.

**Key finding — GSE is ~70% there already.**
- `expression._try_event` already parses base clauses **arc-free**: predicate by POS,
  subject = tokens-before, object = tokens-after. Positional, not `nsubj`/`dobj`.
- `parse_repair` already **overrides** spaCy's POS using WordNet + semantics.
- The *entire* remaining spaCy dependency is **attachment** — clause structure
  (embedding/coordination/linking via `dep_`/`head`/`subtree`).

**Approach.** Derive clause structure from **connectives** (lexically known:
that/who/whom/to/because/so/and/if) + **verb-inventory** (N predicates ≈ N clauses) +
**position** + **selectional constraints** (primitives / WordNet animacy + transitivity).
All GSE tooling. This is "finish the parser GSE is 70% of," not "build one from scratch."

**Payoff.** Dissolves B/C/D (below) into *uniform* connective-driven cases instead of
three bespoke spaCy-mis-parse patches — the compositionality we want. Where spaCy
mis-parsed `Macbeth murders Duncan` and `…and Macduff killed…`, GSE's semantics get
them *right*.

**Risk.** New failure modes on the genuinely complex tail that spaCy's training trees
currently absorb. Mitigations: the coherence gate flags them; "bounded register,
semantically-guided" is the thesis, not a compromise.

**Grammar spec = the NSM grammar of primes** (see WS2 research). The two threads merge.

**Decisive first step (PoC):** GSE-native parse of the B/C cases with *zero* spaCy
arcs. If it gets spaCy's failures right, that validates the yank empirically.

**Dependency surface to retire** (the grep): `tok.dep_` (~23), `tok.head`/`children`/
`subtree` (clause structure — the real work), `tok.pos_` (already overridden),
`tok.lemma_`, `tok.morph` (TAM), `is_alpha/title/stop`.

---

## Workstream 2 — Complete the single-sentence (L1) scale ✅ DONE

**All gaps closed** — and exactly as predicted, B/C/D fell out of the *one* arc-free
clause mechanism rather than three bespoke spaCy patches:
- **B — fronted subordinator** `Because X, Y` ✅ (`dc3a37a`). `_segment_clauses` now
  detects a fronted connective (no predicate before it) and splits at the following
  comma / `then`, decoupling connective-position from split-boundary.
- **C — clause coordination** `X verbed Y and Z verbed W` ✅ (`0a0a5ff`, earlier) —
  the arc-free verb-inventory signal (a predicate on both sides of `and`).
- **D — conditionals** `if/then` ✅ (`dc3a37a`). New `IMPLIES` clause-linking op +
  `Conditional` predicate via the 5-touchpoint pattern; `if` detected arc-free.
  Fronted *and* medial agree (`If X then Y` ≡ `Y if X`).

The **L1 compositionality ladder is fully green — 18 rungs, 0 xfailed.** The whole
single-sentence operator set (EVENT, TYPE_ASSERT, SET_DIFF, CONTRAST, COORDINATION,
REL_RESTRICT, CONTROL, complement-embedding, CAUSAL_SOURCE, CONSEQUENCE,
CLAUSE_COORD, IMPLIES) is recovered deterministically. See the vision doc §IV-G/§IV-H
(full-architecture trace) for the end-to-end demonstration.

**NSM / grammar research (shared prerequisite for WS1 and WS2).**
- **Wierzbicka / Goddard — NSM** (Natural Semantic Metalanguage). GSE's primitive basis
  (`SOMEONE`/`SOMETHING`/`CAUSE`/`DO`…) is essentially NSM primes. NSM has a *grammar of
  the primes* — valencies, complementation, the "universal grammar of meaning" — which is
  **the design spec for the deterministic parser** and the completeness check for L1.
- **Grammar as set theory**; survey of grammar formalisms/tools we may have missed
  (CCG, dependency grammar, construction grammar, valency theory) for useful machinery.

**Possible rework.** Sentence processing may need adjusting for deterministic-parser
compatibility — OR to *exploit new capabilities* the GSE-native parser unlocks
(e.g., meaning-based attachment disambiguation spaCy can't do; using selectional
constraints to resolve PP-attachment / instrument-vs-co-agent).

**The L1 ladder is the contract:** every feature flips a frontier rung green and keeps
all prior rungs passing. B/C/D rungs are waiting (`test_frontier_*`).

---

## Workstream 3 — Beyond the sentence (PRESERVED; delayed to later today)

The whole post-sentence architecture. Do not lose this.

**Unifying principle (Rohan's sparse-wiki insight): scope expansion *collapses*
uncertainty, it doesn't expand it.** A clause is under-determined in isolation; each
added clause/paragraph is a *constraint* that eliminates incoherent readings, so the
solution space contracts as scope grows. The naive ML intuition (more context = more
ambiguity) has the sign backwards. This is *why* comprehension is bounded-solvable.

**The coherence engine is the one recurring operation at every scale:** *"does this
cohere; if not, what's the bounded repair?"* — from verb-POS mistags up to irony. The
coherence gate we built is its kernel.

**The scale-up (Rohan's intentional ordering; deps L1→L2→L3):**

- **L1 — maximal local.** Intra-sentence multi-clause / subordinate depth (= WS2).
  Collapser: the matrix clause binding its subordinates. LSAT = *additive* composition
  of solved single sentences, not a new mechanism.
- **L2 — paragraph.** Classical-AI home: **frames / k-lines / negative learning /
  content-inference**. Collapser: **genre/frame selection** — "movie review" vs "biochem
  paper" vs "elevated opinion" prunes the interpretation space; the *same signal means
  different things in different contexts*. Tooling: truth-maintenance / belief-revision
  (JTMS/ATMS), abduction (best-explanation = max coherence), CSP.
- **L3 — top-level.** Irony + humor, **frame-conditioned** (parasitic on L2). The class:
  **coherence-violation → bounded reinterpretation.** Irony = locally-coherent but
  globally-clashing literal meaning → invert/shift to restore coherence.

**Humor theory (Rohan's, refined together).** *Humor = the felt reward for **safely**
catching that your own model made a premature, locally-coherent commitment that wider
scope invalidates.* Sub-category of joy; externally-sourced (needs a model to violate +
external input). Rohan's 4 traits = the phenomenology:
1. feels good = satisfaction of the mind's modeling goal (the keystone — turns
   description into explanation);
2. grounded in something real/external;
3. surprise = a core expectation/heuristic violated;
4. resolved = placed into the framework (the relief *is* the pleasure).

Two added **differentia** (what makes resolved-surprise *funny* vs mere insight/relief):
- **self-caught commitment-error** (garden-path): the setup leads you to commit to
  reading A, the punchline reveals B — you catch your *own* confident-but-wrong inference.
  Dennett/Hurley "Inside Jokes": mirth is the reward for **debugging your just-in-time
  model**, evolved to incentivize re-checking commitments. ⇒ humor is
  *error-correction-as-pleasure* — the "cheat code to communication."
- **benignity** (McGraw benign-violation): the SAME violation → **fear** if the caught
  error is costly, **humor** if safe. Benignity is frame-dependent (L2).

**Two tiers** (handles Rohan's funny-face/dog examples): a *primitive* benign-violation
tier (perceptual surprise, safe, resolved — animals, joy-adjacent, no model-commitment)
and a *cognitive* garden-path tier (language/model-rich — verbal jokes, irony). Same
core, differ on whether a *committed model* was caught.

**Architecture payoff:** humor/irony **fall out** as derived signals of the coherence
engine — *no new module*. Detection needs (a) the engine recording its own commitments
(a TMS — L2) + (b) a benignity check against a world/value model (the apex commonsense
layer, Genesis's domain). Generation = construct a garden-path = SSH-adjacent apex.
Comprehension's own machinery *is* the taste/humor evaluator. This is how the "messy
tail" of NLP resolves **without inference**.

**Shared bottleneck across L1–L3:** leaf-grounding quality (the primitive lexicon) +
a *computable* coherence metric + the world/commonsense model. One investment, three payoffs.

---

## Cross-cutting

- **Coherence gate** = measurement instrument + safety net throughout (incl. WS1's tail).
- **L1 ladder** = the compositionality contract; no feature ships baroque/parallel.
- **Genesis handoff:** GSE feeds the typed clause graph; bridge consumes the emit
  contract; coherence flags = the abstain signal.

## Open decisions (resume here)

1. ~~WS1 PoC before committing to yank spaCy?~~ **Resolved** — PoC done (`24b8fd5`),
   then the full yank landed (WS1 ✅).
2. ~~NSM research before/after the PoC?~~ **Resolved** — research done
   (`docs/NSM_GRAMMAR_MAPPING.md`); it grounded the connective inventory the
   arc-free derivers use.
3. ~~WS1 vs WS2 ordering~~ **Resolved** — WS1 first, as predicted: the arc-free
   clause layer dissolved B/C into uniform connective cases (C coordination green;
   B fronted-causal + D conditional remain as ladder rungs, now buildable on the
   arc-free `_detect_embedded_clauses`/`_segment_clauses` rather than spaCy patches).

**Next up:** finish the L1 ladder — **D conditional** (`IMPLIES`, still `xfail`)
and **B fronted-causal** (the comma-boundary segmentation). Both are now isolated
additions on the arc-free parser. Then WS3 (paragraph/L2, irony/humor) per below.
