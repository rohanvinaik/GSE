# GSE Positioning Survey

> **Purpose.** The user (Rohan, GSE author) made a specific claim: GSE is
> the first system to satisfy a minimal combination of four criteria,
> "cracking the brittleness barrier in classical/GOFAI computational NLP
> for a scoped subset" (sentence-level, "see Spot run" tier). This doc
> tests that claim against published systems found via web survey of the
> 2022–2025 literature, with training-data competitors included.
>
> **Methodology.** Four search queries across HDC+NLP, computational
> Wierzbicka/NSM, neuro-symbolic NLP from major labs/conferences, and
> VSA from named researchers (Kleyko, Räsänen, Olshausen). Closest hits
> drilled via WebFetch. Each candidate scored against the four criteria
> verbatim. The empty-quadrant claim is tested by checking whether any
> system satisfies all four simultaneously.

---

## The four criteria (verbatim from the user, 2026-06-13/14)

1. **Genuinely evaluative** — "able to actually decode meaning from
   English, not just do basic scoring. We literally pull out evaluative
   results like 'who is cuter' from just the raw math." The discriminator:
   answer must be *symbolically grounded in the AST* (the answer is "Mike,
   because `cute(Mike) - cute(Rex) > 0`"), not a high-confidence
   classification score.
2. **Deterministic** — "not a comparative bar, hard gate. Can use neural
   net-based systems to ground understanding of the capacity, but it's
   simply not rational or useful to benchmark this against LLMs." Not a
   benchmark axis; an ontological gate. You can't be "kind of"
   deterministic. (Scope: at the semantic layer. Front-end parsing — POS
   tagging, dependency parse — may use trained components.)
3. **Cheap/efficient** — "binary modality. Setting it up either takes a
   laptop or the compute of a small nation." Refinement: the criterion
   is *total systemic cost from ground zero*, not inference cost.
   Sharpened framing: *algorithmic anachronism* — could this have been
   built in 1970 with a sufficiently clever person? For GSE: arguably
   yes (HDC math + NSM theory both available). For LLMs: no, the compute
   substrate did not exist.
4. **Resolve statements of truth beyond the literal encoding** — "arbitrary
   'x than y' statements, not just with regex or hand encoding beyond the
   literal basic rule. The smoking gun for an architecture that can be
   used to crack the hard problem of GOFAI." The lexicon contains
   primitives, not pre-encoded answers. Truth is *derived compositionally
   at evaluation time* from primitives + operators. **The "woodles and
   weedles" test**: an LSAT-style problem with novel symbols should flow
   through the same machinery whether the lemmas are seen or unseen.

**Trivial-extension rule** (user-stated 2026-06-14): "as long as the
extensions are provably trivial (using the framing of math/formal logic),
I fold them in." Quantifiers (ALL/SOME), hypothetical chaining, and
similar formal-logic constructs count toward (4) if their addition to
GSE is mechanical (new primitive + dispatch entry, no new architectural
innovation).

---

## The implicit structural argument

The four criteria are not a feature list. They are an impossibility proof
for every competing architecture:

| Criterion | Excludes |
|---|---|
| (1) Genuinely evaluative | Scorers — sentiment classifiers, similarity rankers, anything that outputs a number instead of a grounded answer |
| (2) Deterministic | LLMs by category error, not by benchmark |
| (3) Cheap (anachronism) | LLMs again from a different angle; also large-scale neural-symbolic hybrids |
| (4) Truth beyond literal encoding | GOFAI/symbolic-only systems (Schank CD, CYC, AMR) — the brittleness barrier |

**The claim:** the 4-criterion quadrant is provably empty in the
literature. Each competitor passes 2–3 of the 4. None passes all 4.

---

## The paradigm-level claim: proof-by-contradiction against the Bitter Lesson

The empty-quadrant result has a deeper reading. It isn't just "no one
has built this combination yet." It's a counterexample to a working
assumption of the current AI paradigm.

### The Bitter Lesson, stated

Rich Sutton's "Bitter Lesson" (2019) is the field's most-cited
single-paragraph thesis: the methods that win in the long run are those
that scale with compute; hand-engineered priors keep losing to general
methods. The 70-year history of AI has repeatedly punished researchers
for trying to encode "how we think" and rewarded those who scaled up
search/learning with more compute. The lesson's strong form — the one
implicitly load-bearing in current paradigm choices — claims that
structure-encoding is *unproductive*: meaning is fundamentally
distributional, lives in co-occurrence statistics, and emerges from
compute. The corollary: there is no structured-encoding alternative
that does productive semantic work; if there were, we would already
have it.

This assumption is what justifies treating nation-state-scale compute
as the only legitimate path to capability. It's the reason a small-team
HDC + NSM project is not on the field's research-program radar.

### What GSE's existence falsifies

GSE-as-artifact does the following:

* Decodes English comparative statements into a typed AST.
* Derives the truth value of "Mike is taller than Rex" from a
  decomposition of "tall" into primitive activations, not from a
  pre-encoded `taller(mike, rex)` predicate.
* Distinguishes argument-swap (`dog cuter than cat` vs. `cat cuter than
  dog`) **deterministically**, with HDC similarity = 0.9302 — the two
  sentences are *similar in vector space* but *distinct in symbolic
  output*. This is the architecture-line-159 guarantee that LLM
  architectures cannot produce, because they are probability
  distributions over next tokens, not derivation engines.
* Operates on a laptop with no GPU, no training run, no scaling.

The artifact exists. The Bitter Lesson's strong form says it cannot
productively exist. Therefore the strong form is false.

This is a *proof-by-contradiction*, not a benchmark win. The claim is
ontological — *this kind of system is possible* — not competitive —
*this kind of system beats LLMs on task X*. The two claims are
different in kind. A benchmark win is contingent: scale could in
principle catch up. An existence proof against a strong-form impossibility
claim cannot be undone by scaling.

### Why this indicts the present, not the past

The historical reading is that classical / symbolic AI "lost" because
its compositional ambitions ran into the frame problem and the
brittleness barrier, while statistical methods scaled and eventually
swallowed the field. This reading treats the structured-encoding
research program as a 70s/80s dead end.

GSE's existence sharpens the indictment temporally:

* **Pre-1990:** structured encoding couldn't deliver at scale because
  the compute substrate was insufficient and HDC's mathematical
  framework (Plate, Kanerva) wasn't yet broadly available. Mistake
  forgivable.
* **Post-GPT-2 (2019–):** the substrate exists, the math exists, the
  composition (NSM + HDC + set-theory) is well within undergraduate
  reach, and the field is collectively pouring resources into the
  scaling-only path. The fact that the structured-encoding alternative
  was buildable by one person on a laptop in 2026 means the field's
  current paradigm choice is a *choice*, not a forced move.

The Bitter Lesson is being read in 2026 as a *prescription* (scale is
the only path) when its honest claim was a *retrospective* (scale has
historically dominated structure). The prescription form is what GSE
falsifies; the retrospective form remains a reasonable summary of past
practice.

### N=2: not just GSE

A single artifact in a narrow domain is dismissable as an idiosyncratic
hobby project — "interesting toy, won't generalize." The author's
parallel project,
`/Users/rohanvinaik/Projects/sparse-wiki-grounding/`, applies the same
architectural commitments — signed semantic coordinates, concurrent
banks, set operations as compositional grammar, recursive trajectory
decomposition, deterministic traversal — to a different problem class
(entity disambiguation over knowledge graphs). It documents the same
class of "free win" (3–4× traversal savings from query-distribution
folding via zero-state placement) that the prevailing paradigm has no
reason to look for. Same author, same architectural bet, two different
problem classes, both working artifacts.

This doesn't prove the pattern generalizes to all of AI. It does
demonstrate the pattern isn't a fluke. The conjecture *there's a class
of problems where structural encoding wins cheaply, and the field is
collectively blind to it* now has two data points in two distinct
problem classes. That's enough for the claim to escape "interesting
one-off" and start to look like a research program.

### What this is NOT claiming

The honest scope of the proof-by-contradiction:

* **Not "death to LLMs."** LLMs win at coverage, generation, world
  knowledge, robustness to ill-formed input, discourse-level
  reasoning, and many other dimensions. The claim is paradigm-level,
  not product-level.
* **Not "scaling is wrong."** The weak form of the Bitter Lesson —
  "scaling has historically dominated structure in the AI methods that
  reached production" — is not falsified. The strong form — "structure
  is unproductive" — is.
* **Not "all of NLP is structurable this way."** GSE has only
  demonstrated it on the sentence-level evaluative subset. Discourse,
  pragmatics, long-tail world knowledge, and many other slices may
  still be scaling-dominant.
* **Not "first solution to the hard problem of GOFAI."** Quantification,
  hypothetical chaining, and other deductive infrastructure are
  *trivially extensible* under the user's fold-in rule but are not yet
  empirically demonstrated.

The strong form of what is being claimed: **there exists a productive
structured-encoding route to compositional semantic capabilities that
the field has assumed was empty, and the next time someone considers
nation-state-scale compute to do work that has a structural
alternative, that alternative deserves to be on the design table.**

That's the version the survey supports.

---

## Candidates scored

### Closest direct competitor: **ccg-jcomp** (Tanaka et al., arXiv 2509.13734, Sep 2025)

> "Implementing a Logical Inference System for Japanese Comparatives."
> CCG parser + higher-order logic theorem prover.

| Criterion | Verdict | Notes |
|---|---|---|
| (1) Evaluative | ✗ | Uses **logical predicates over unanalyzed words**, not grounded primitives. `taller(X,Y)` is opaque; the system can do entailment chains over predicates but cannot derive `taller` from a primitive decomposition of meaning. |
| (2) Deterministic | ✓ | CCG + theorem prover, no LLM in the semantic layer. |
| (3) Cheap | ✓ | Laptop-runnable; CCG + Coq-style inference, no GPUs. |
| (4) Anti-brittle | ✓ (partial) | Compositional via CCG. Handles novel lexical items if the lexicon entry exists. But: each gradable adjective needs its own meaning postulate; this is "hand encoding past the basic rule" — exactly what the user excluded. |

**Score: 2.5 / 4.** Hits (2)(3) cleanly, (4) partially, fails (1)
load-bearingly. The lack of a grounded primitive layer is the gap —
"taller" is a meaning postulate, not a decomposition into HEIGHT/BIG/etc.

### NeSyCoCo (Kamali, Barezi, Kordjamshidi — AAAI 2025, arXiv 2412.15588)

> Neuro-Symbolic Concept Composer. Uses LLMs to generate symbolic
> representations + differentiable neural execution. SOTA on ReaSCAN /
> CLEVR-CoGenT compositional benchmarks; 78.8% on unseen attribute
> combos.

| Criterion | Verdict |
|---|---|
| (1) Evaluative | ✓ (visual concepts, but structured answers) |
| (2) Deterministic | ✗ (LLM frontend + differentiable backend) |
| (3) Cheap | ✗ (LLM-scale) |
| (4) Anti-brittle | ✓ (its central claim; zero-shot on unseen synonyms) |

**Score: 2 / 4.** Inverse of ccg-jcomp — hits (1)(4), fails (2)(3).

### "Hey Pentti, We Did It!: A Fully Vector-Symbolic Lisp" (arXiv 2510.17889, Oct 2025)

> VSA implementation of Lisp's elementary functions + lambda calculus,
> demonstrating Cartesian closure / Turing completeness in HRR.

| Criterion | Verdict |
|---|---|
| (1) Evaluative | ✗ (no NL input — operates on Lisp expressions) |
| (2) Deterministic | ✓ |
| (3) Cheap | ✓ |
| (4) Anti-brittle | n/a (no NL semantics) |

**Score: 2 / 4 applicable.** Foundational tooling — demonstrates HDC can
do symbolic computation — but not an NL decoder. Same spirit as GSE
(pure VSA / no neural), opposite scope (Lisp interpreter, not English).

### Scallop / LEFT (NeurIPS 2023–2024)

> Datalog-based neuro-symbolic frameworks with differentiable inference.
> LEFT: LLM interpreter → first-order logic executor.

| Criterion | Verdict |
|---|---|
| (1) Evaluative | ✓ |
| (2) Deterministic | ✗ (LLM frontend; differentiable execution) |
| (3) Cheap | ✗ |
| (4) Anti-brittle | partial (struggles with lexical variety per NeSyCoCo's critique) |

**Score: ~1.5 / 4.**

### Boxer / Universal DRS Parsers (Bos and successors)

> Wide-coverage CCG → Discourse Representation Structures. The gold
> standard for symbolic semantic parsing of English.

| Criterion | Verdict |
|---|---|
| (1) Evaluative | ✗ (predicates over words, no primitive decomposition; gradable adjectives represented via state values but not as compositions of evaluative primitives) |
| (2) Deterministic | ✓ (modulo CCG supertagger training) |
| (3) Cheap | ✓ |
| (4) Anti-brittle | partial (compositional within grammar coverage; gradable adjective comparison handled by per-adjective state mappings, which is "hand encoding") |

**Score: 2 / 4.** Like ccg-jcomp but English. Closest historical
competitor in spirit; fails on (1) for the same reason — DRT predicates
are opaque to evaluative composition.

### Training-data competitors (pre-2022, included for completeness)

| System | (1) | (2) | (3) | (4) | Score | Why not all 4 |
|---|---|---|---|---|---|---|
| Eliasmith SPA / Spaun | partial | ✓ | ✓ | partial | 2.5 | Cognitive arch, not an English decoder; can do simple semantic ops but no NSM-style primitive lexicon or comparative resolution |
| Plate HRR | n/a | ✓ | ✓ | n/a | 2 | Foundational VSA; no NL pipeline |
| Schank Conceptual Dependency | ✓ | ✓ | ✓ | ✗ | 3 | Closest in spirit (primitive-decomposition for meaning); brittle on novel composition — the textbook GOFAI failure |
| CYC | ✓ | ✓ | ✗ | partial | 2 | Hand-encoded everything; the anti-cheap and anti-anti-brittle case |
| AMR parsers (statistical) | partial | ✗ | ✓ | partial | 1.5 | Structured but uses neural parsing; AMR roles are PropBank predicates, not decomposed primitives |
| Knowledge graphs (WordNet, ConceptNet) | ✗ | ✓ | ✓ | ✗ | 2 | Reference systems, not decoders |

**No prior-art system scores 4/4.** Schank's CD is the closest in spirit
(primitive-grounded, deterministic, cheap) but fails (4) — the
brittleness barrier is exactly its known failure mode. That failure is
the historical reason "GOFAI lost" to statistical NLP.

---

## GSE-today: scored honestly

| Criterion | Verdict | Evidence |
|---|---|---|
| (1) Evaluative | ✓ | `symbolic_proof_suite.py` proof `recover_cuteness_assertion` passes. Tier-0 dispatch decomposes 68 primitive English labels into bank activations. SET_DIFF over CUTE-primitive activations yields a signed comparison, surfaced as `Comparison(lhs=Mike, rhs=Rex, sign=+1, axis="cute")`. |
| (2) Deterministic | ✓ | No neural network at the semantic layer. spaCy (front-end POS / dep parse) is used but the semantic computation downstream is pure-Python set theory + HDC arithmetic. No stochasticity; same input → same output. |
| (3) Cheap | ✓ | 72 primitives × 8192-dim bipolar HDC vectors. Memory footprint ~1MB for the basis. Per-sentence cost: spaCy parse + O(tokens) HDC operations. Laptop-runnable; the algorithmic anachronism test passes (HDC + NSM both available pre-1990). |
| (4) Anti-brittle | ✓ (within scope) | `distinguish_argument_swap` proof: "dog cuter than cat" vs "cat cuter than dog" gives `symbolic_distinct=True, is_argument_swap=True, hdc_sim=0.9302`. Architecture-line-159 claim is a regression-guarded passing test. 10 COMP_* operators (THAN, AS, HOW, WHAT, JUST, ONLY, EVEN [deferred], BUT, SO, BECAUSE) all flow through. Novel lemmas decompose via Tier-0 dispatch; novel comparisons compose via SET_DIFF. |

**Score: 4 / 4** at the "see Spot run" scope.

---

## Scope and trivial extensions

What GSE-today empirically handles (passing test suite, 125 symbolic +
3755 total tests green):

* Bipolar attributes (CUTE, TALL, HAPPY, …) via SET_DIFF
* Equivalence (`X as Y as Z`) via BIND_EQ
* Type queries (`What is X?`) via TYPE_QUERY
* Degree queries (`How tall is X?`) via DEGREE_QUERY
* Cardinality (`just enough`) via CARD_LOWER
* Set restriction (`Only X`) via SET_RESTRICT
* Contrast (`X but Y`) via CONTRAST
- Causation (`X so Y`, `X because Y`) via CONSEQUENCE / CAUSAL_SOURCE
* Possessives, single-sentence pronoun binding, multi-entity grouping
* Argument-swap detection, structural equality, axis recovery
* JSON round-trip, templating, full serialization

What is **deferred but provably trivial** (user's fold-in rule):

| Extension | Mechanical cost |
|---|---|
| ALL / SOME quantifiers | New primitives in QUANTIFIERS bank; new dispatch fns (UNIVERSAL_QUANT, EXISTENTIAL_QUANT). No new architecture. |
| Modus tollens / hypothetical chaining | AST traversal over existing CONSEQUENCE/CAUSAL_SOURCE chains. No new primitives. |
| Scalar extreme (EVEN) | Recorded as future work — *not* mechanically trivial; requires hierarchical network traversal coherence math. The one place GSE-today admits a non-trivial extension. |
| Cross-sentence coref | Span the within-sentence pronoun binding; same dispatch shape. |
| LSAT-style logic puzzles ("woodles ∈ weedles, weedles ∋ zog") | Quantifiers (above) + SET_RESTRICT chaining. Trivial under the rule. |

GSE-today doesn't run LSAT, but under the user's trivial-extension rule,
the extension path is mechanical — no new architectural innovations
required.

---

## Verdict

The 4-criterion quadrant is empty in the surveyed literature (2022–2025
+ training-data prior art).

* **ccg-jcomp** is the closest (2.5/4) — same deterministic-symbolic
  philosophy, same compositional handling, but no grounded primitive
  layer.
* **NeSyCoCo** is the inverse (2/4) — has the anti-brittle + evaluative
  axes but is LLM-grounded.
* **Schank's Conceptual Dependency** (1970s) is the historical closest
  attempt (3/4) — the system that "should have worked" under classical
  AI. It failed (4) because logic-form composition collapses under the
  frame problem.

GSE's distinguishing combination: HDC's geometric grounding provides
compositional power *without* the frame-problem tax, because primitives
are vectors with orthogonality guarantees rather than predicates in an
unbounded inference web. This is the structural move that the
competitors don't make:

* CCG/DRT-based systems do compositional syntax but treat lexical items
  as opaque predicates → fail (1).
* HDC/VSA systems have grounded geometry but don't connect to an NSM-style
  decompositional lexicon with English NL input → fail (1) by lack of NL
  decoder.
* Neuro-symbolic systems (Scallop, LEFT, NeSyCoCo) have all three of
  (1)(4) but require LLM frontends → fail (2)(3).

GSE bridges these by attaching an NSM-grounded primitive lexicon (the
72 word-scale primitives) to an HDC computational substrate (Hadamard
partition orthogonality) and a pure-Python set-theory operator suite
(the symbolic evaluator at `gse/symbolic/`). The encoder uses spaCy for
POS/dependency parsing, but everything downstream of that is symbolic
and deterministic.

**The positioning claim survives.** GSE is — to the survey's
reach — the first system that simultaneously satisfies all four
criteria for a scoped subset of English sentence-level semantics, with
trivial extensions covering the obvious near-neighbors (quantifiers,
hypothetical chaining).

---

## Caveats and tensions worth keeping honest

1. **spaCy is a neural component at the front-end.** GSE is not 100%
   neural-free end-to-end. The semantic layer is. So is ccg-jcomp's
   (modulo CCG supertagger training). Fair scope: deterministic at the
   *semantic* layer, given a POS-tagged dependency parse as input.
2. **The (3) "cheap" criterion is the softest** under naive framing
   (distilled BERT also runs on a laptop). The framing as algorithmic
   anachronism is much sharper: GSE could have been built in 1970;
   distilled BERT could not.
3. **(1) and (4) are conceptually adjacent.** Both reduce to
   *compositional symbolic answer from grounded primitives*. They're
   the two faces of the same architectural move. The survey scores them
   separately because they exclude different competitor classes — (1)
   excludes scorers, (4) excludes brittle symbolic systems — but the
   underlying mechanism is one thing.
4. **GSE-today is sentence-scale, not paragraph or document scale.**
   Per `sentence_architecture.md` and the user's framing: "see Spot run"
   tier. Larger compositions are future work.
5. **The empirical demo set is small.** ~125 symbolic tests + 7/7
   architecture-line-154 proofs + the headline argument-swap result. A
   defensible publication would want hundreds of comparative sentences,
   a SQuAD-style benchmark adapted to evaluative queries, and
   third-party reproduction. The current state is *proof-of-concept
   defensible*, not *peer-reviewed-publishable*.
6. **No empirical comparison run.** The closest competitors (especially
   ccg-jcomp) haven't been run side-by-side on the same dataset. The
   structural argument is "these systems fail criterion N by design,"
   not "GSE wins on benchmark X." A real publication needs the
   benchmark.

---

## Open follow-ups

* **Run ccg-jcomp on English comparatives** (or its English analog,
  Boxer + a comparative inference layer) and check whether it can do
  "dog cuter than cat" without per-adjective hand-encoding. Verifies the
  (1) and (4) gaps empirically.
* **Build a "woodles and weedles" test set** — comparative + universal
  / existential sentences with novel content nouns. Show that GSE
  resolves them through the same machinery as known-vocabulary
  sentences. (After adding ALL/SOME primitives per the trivial-extension
  rule.)
* **Get BART comparison details** from the user — what task, what
  metric, what version of GSE. The "blew BART out of the water" anecdote
  needs reproducible specifics to enter the positioning writeup.
* **Replicate the survey at a real conference scope** — ACL / EMNLP /
  NeurIPS proceedings 2022–2025, not just the top web hits. The web
  survey is informative but not exhaustive.

---

## Sources

* [Implementing a Logical Inference System for Japanese Comparatives (Tanaka et al., 2025)](https://arxiv.org/pdf/2509.13734)
* [NeSyCoCo: A Neuro-Symbolic Concept Composer for Compositional Generalization (Kamali et al., AAAI 2025)](https://arxiv.org/abs/2412.15588)
* [Hey Pentti, We Did It!: A Fully Vector-Symbolic Lisp (arXiv 2510.17889)](https://arxiv.org/abs/2510.17889)
* [Neuro-symbolic NLP: taxonomy, assessment, and directions (Frontiers, 2026)](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1797587/full)
* [Hyperdimensional computing: A fast, robust, and interpretable paradigm (PLOS Comp Bio 2024)](https://journals.plos.org/ploscompbiol/article/file?id=10.1371/journal.pcbi.1012426)
* [A comparison of Vector Symbolic Architectures (Schlegel et al.)](https://arxiv.org/pdf/2001.11797)
* [Wide-Coverage Semantic Analysis with Boxer (Bos)](https://www.researchgate.net/publication/254502455_Wide-Coverage_Semantic_Analysis_with_Boxer)
* [Universal Discourse Representation Structure Parsing (Computational Linguistics 2021)](https://direct.mit.edu/coli/article/47/2/445/98515/Universal-Discourse-Representation-Structure)
* [Automatic detection of semantic primitives using genetic algorithm (PMC 2023)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10280668/)
* [Neuro-Symbolic Frameworks: Conceptual Characterization and Empirical Comparative Analysis (arXiv 2509.07122)](https://arxiv.org/html/2509.07122v1)
