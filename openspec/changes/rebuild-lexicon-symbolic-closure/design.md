# Design: the lexicon as symbolic closure over orthogonal banks

## Authority

Rohan's words govern: `docs/program/LEXICON_FOUNDER_WORDS_2026-10-24.md` (October, F001-F160) and his prompts of
2026-11-23 to 26 (extracted verbatim from the session record). His framework is the same in every project he
pointed to. These are its instruments:

| Instrument | Where | What it fixes here |
|---|---|---|
| Data Geometry | `~/Projects/Kaggle_Killer/DATA_GEOMETRY_ARCHITECTURE.md` | Orthogonal ternary banks; the informational zero; symbolic healing; constraint clamping; hard rules first; discovery kept apart from evaluation |
| harmonizing (NCEMS) | `~/Projects/Kaggle_Killer/competitions/harmonizing/src/` | A column filled because other columns determine it; the shadow ledger; projection |
| TriageGeist | `~/Projects/Kaggle_Killer/competitions/triagegeist/` | Independent banks converging (Kuramoto); hard rules, then patterns, then a tiny certified tail |
| TrialLedger | `~/tools/TrialLedger/docs/THEORY_OF_THE_CASE.md` | Known / interpolated / proposed; defaults with applicability and defeaters; closure to an order-independent fixed point |
| Significance Weighting | `papers/Core Documents/SIGNIFICANCE_WEIGHTING.md` | kappa as the objective and the stop; population-latent rules (N_ind); the admission gate; oscillation narrowed by an imputed type |
| SSL | `papers/Core Documents/Semantic_Specification_Learning/01_PAPER_SKELETON.md` | H = sum log2 of surviving states; dH/dt = -(N + C(H)); hubs first |
| Negative Specification | `~/tools/Detective/docs/theory/NEGATIVE_SPECIFICATION.md` | Positive and negative channels are independent; censors come from population near-misses |
| sparse-wiki | `~/Projects/sparse-wiki-grounding/sparse_wiki_architecture.md` | Orthogonal faceted positions signed against a zero state |

The independent reading of this framework (GPT-6.2 Sol, recorded before this design was written) is in
`docs/readings/2026-11-26-rebuild-consult/`. Where it differs from Rohan, Rohan governs.

## The artifact this change delivers

Every one of the 401,596 readings has all 56 banks accounted for. Each cell is in exactly one of these states:

- **decided:** +1 or -1 (content, with a positive root), or 0 (explicit absence, F118);
- **proved silent:** the definition says nothing on that bank, and a warrant shows it (F140: "not uncertain or an
  unresolved degree of freedom");
- **typed residual:** a mask of two or more legal states, with the named reason it is still open (missing source,
  missing mapping, conflict, missing law, or a genuine bounded choice).

Every decided or silent cell carries its proof: the source observation, the authored prime, or the rule
application and its premises. Senses are built from these cells. The GSE runtime reads the artifact through its
existing consumer boundary. "A *full* lexicon, not one with 1-2 banks per word" (2026-11-25 07:15) is the
requirement. A fill quota is not.

## Elements

Each element answers the six questions of 2026-11-26 04:15: its source in his words, how it becomes code, its
information-theoretic principle, what it looks like running, its output in cells and bits, and its contribution.

### E1. Cell state and the shadow ledger

- **Source.** F118: "0 is explicit absence; empty is silence." F140: confirmed silence is decided. The harmonizing
  shadow ledger: evidence is append-only, typed, scoped and richer than the output, and a projector decides what is
  emitted. TrialLedger: "Every conclusion retains premises, source and rule versions and its weakest support."
- **Code.** `cells.py`: a `uint8` array of shape (readings, 56); bits are +1, -1, 0, SILENT. The bank registry holds
  the polarity aliases. Unpaired banks start at {+1, 0, SILENT}; bipolar banks start with all four states.
  `ledger.py`: an append-only table of observations (source, record, reading, scope, value or restriction,
  lineage) and a table of derivations (cell, removed states, rule application, premise ids).
- **Principle.** H = sum over cells of log2 |mask|. Every removal is a recorded cause. Zero and silence are
  distinct information (Negative Specification section 5: the negative channel is not redundant).
- **Running.** Masks for 22.5M cells fit in about 22 MB, or 11 MB packed. One pass over all masks takes well under
  a second.
- **Output.** The opening state: every cell at its legal starting mask. The opening H is the comparison point.
  The live lexicon measured 32,707,151 joint bits on its stored states.
- **Contribution.** One state for everything that follows. The meter and every rule read the same thing, so
  nothing lives in a side layer.

### E2. Source lenses

- **Source.** F056: "What semantic degrees of freedom are pinned by every typed, categorical assertion in them".
  F059: "a rigorous symbolic map of warranted meaning". TrialLedger: "Each source measures its own thing. Encodings
  of the same evidence are not independent corroboration." AGENTS.md: grounding goes through the existing parsers
  (`to_primitives`, `integrator.load_all_sources`, `SOURCE_PRIMITIVE_SCOPE`).
- **Code.** `projection.py` reads every parser once per pinned snapshot and writes typed observations into the
  ledger. Each source has a declared competence: the banks it may write, the banks it must not write, and the
  binding it needs (exact native id, declared mapping, or a typed alignment). Ratings, associations and classifier
  outputs are recorded but never write a cell (2026-11-26 17:01: "LLM slop"; F115).
- **Principle.** Each lens is an independent observation channel. An observation that a source is competent to
  make removes states. An observation it is not competent to make removes nothing.
- **Running.** Bulk loading into the ledger, then one vectorised pass that intersects each reading's masks with
  its competent observations.
- **Output.** Cells decided directly by sources, and multi-state narrowing. The previous projection stored 506,613
  cells (331,373 zeros). The new projection's count is measured in task 3.
- **Contribution.** The direct facts. These are the premises everything else propagates from, and the only
  material from which coherence is judged.

### E3. The prime foundation (hard rules)

- **Source.** F088: "The atomic words, those 72 primes, are definitionally written by hand, since they're
  essentially the equivalent to amino acids". 2026-11-24 23:42: "Just write it formally in code". Data Geometry:
  hard rules fire first.
- **Code.** `primes.py` reads the authored chart units (`external_sources/nsm_chart_data.py`) and the reviewed
  profiles (`prime_profiles.json`, `bank_laws.json`). Each prime and function word gets its content bank, its
  declared silences and absences, and its combinatorial frame (argument types, valency). The profile is not a
  one-cell vector by default (F148).
- **Principle.** Hard rules are Scale-0 ground truths. They are fully decided and short-circuit everything else.
- **Running.** A few hundred readings are fixed before any closure runs.
- **Output.** 72 primes x 56 = 4,032 cells fully decided, plus the function words (37 reconstructed records).
- **Contribution.** The basis every relation is written in. It also supplies the frames that E4 compiles into laws.

### E4. Relations between banks

- **Source.** F088: "the true atomic is a *sub*-prime symbolic rule of relation between banks ... 'presence of any
  non-zero and non-empty input in <bank A> forces <bank b> to be [typed 0/empty/also filled/etc]'". F067: some
  banks combine (a flock is many of bird), some are mutually exclusive (evaluators against descriptors). F073: the
  constraints are additive and conjunctive ("semantic sudoku": a value that must go somewhere and fits only one
  place is forced). Data Geometry pattern 10: symbolic healing is propagation through a constraint graph of domain
  physics, and constraint clamping is a condition on several banks that narrows the output.
- **Code.** `relations.py` represents a relation as a guarded table of permitted (or forbidden) tuples over two or
  more banks, with its warrant. `nsm_laws.py` compiles NSM's own material into relations: the chart's categories
  and frames, the reviewed head laws, valency (which primes need a someone as bearer), molecule decompositions and
  templates from the verified explications. A permission in the chart stays a permission unless a warrant says
  more.
- **Principle.** Joint configurations, not a Cartesian product of banks. Fixing one bank removes states in others.
  Entangled banks cost the product of their states and orthogonal ones the sum (SSL 2.4), so each relation turns a
  product into something smaller.
- **Running.** Each relation is applied to its whole eligible population at once as mask operations, and is
  re-woken only when one of its banks changes.
- **Output.** Cross-bank consequences. A predecessor measured 1,770,913 decided cells when the reviewed head laws
  and F088's reading were applied to the stored states. The count under the new state is measured in task 5.
- **Contribution.** This is how one decided bank fills others. It is the mechanism Rohan named as the whole point
  (2026-11-26 19:38: banks "implicitly decided and filled by other sources of information, like other banks").

### E5. Coherence across independent sources

- **Source.** F101: "if one bank, one dimension, has one value vs another value, or if a bank being filled with
  SOME non-empty value means another is definitionally silent every time, then we can impute a rule--validated by
  'common sense'/domain expertise/symbolic reasoning ... Not 'statistical similarity', but dynamic mechanism
  impute". F108: "relations between banks in single words, stable across the tens of thousands of words that exist
  in multiple datasets". 2026-11-25 01:53: "agreement and disagreement across orthogonal banks as the source of
  deterministic inference". TrialLedger: "Agreement alone does not assign a value; supported constraints eliminate
  alternatives."
- **Code.** `coherence.py` does two things.
  - **Per reading:** it intersects the independent lenses' constraints. Agreement settles a value. Disagreement
    becomes a conflict record naming the reading, the banks, the source roots and the candidate causes (wrong sense,
    wrong role, misfiling, overbroad rule). It never picks the bigger camp.
  - **Across the population:** postings index which readings each source puts in each bank state. For a candidate
    relation "A => B" within a typed scope, it retrieves the exact sets of readings where A holds, where an
    independent source states B, where an independent source states not-B, and where B is unknown. "Every time"
    means the contradicting set is empty. Unknowns are neither confirmations nor counterexamples. Candidates come
    from NSM templates, near-misses, and the endpoints of real derivation chains.
- **Principle.** N_ind (Significance Weighting section 11): a law no single reading states, which the population
  reveals. Independence is required: two encodings of one observation are one witness.
- **Running.** Over the postings, in one pass per candidate family. Nothing is computed over the 2.3% of cells
  already decided, where every relation looks unfalsifiable.
- **Output.** Settled cells where independent lenses agree. Conflict records. Candidate relations, each with its
  witness, counterexample and unknown sets.
- **Contribution.** The relations between banks that NSM's text does not state and the population does. These
  reach the 22 banks no relation touches today.

### E6. Admission

- **Source.** Significance Weighting section 14 and 16.3-16.7: promotion is computed, never thresholded. A rule is
  promoted if it is (i) confirmed by a stated fact, never by the engine's own output, (ii) still leaves lawful
  plurality (sigma_sem > 0), and (iii) has kappa > 0. Section 16.6: an oscillating rule is narrowed to the type that
  separates its confirmations from its contradictions; if no type does, the oscillation is the finding.
  2026-11-25 05:30: an input that breaks coherence is "an out-of-variance exception".
- **Code.** `admission.py`, written fresh from those sections. A verdict is one of ADMITTED, NARROWED (with the
  imputed guard), FINDING (with the exact readings), UNCONFIRMED, UNEXPOSED or NO_REACH. UNEXPOSED means no reading
  in the scope states the consequent's bank outside the consequent's states, so the population could not have
  refuted the rule (SSL 4.3, the falsifiability pivot; Significance Weighting 14 (ii)). An unexposed rule carries no
  information and is not admitted. A pair witness needs the two banks stated by distinct observations of the same
  reading (F108: relations "stable across the tens of thousands of words that exist in multiple datasets"). Typed
  scopes are strict kind-of ancestors; values carried by inheritance are derived and never confirm. Each admitted relation is versioned,
  with its warrant and its positive and must-not witnesses.
- **Principle.** The gate keeps N_ind well defined. A self-confirmed rule lowers H while carrying no information
  (Significance Weighting section 14).
- **Running.** Each candidate is staged over the whole population and its reach is measured against current
  closure. Admitted rules are compiled into E4's form and closure re-runs.
- **Output.** Admitted relations and their measured reach in cells and bits. Verdicts for everything else.
- **Contribution.** It turns coherence into rules without thresholds, and gives the build its own stopping rule.

### E7. Censors: confident zeros and proved silence

- **Source.** 2026-11-25 17:56: "the ones that are completely orthogonal to a valid definition of the word should be
  zeros. Others should NOT be automatically filled in with zeros." 18:06: confident zeros are "the CORE part".
  Negative Specification section 9: a censor is carved from observed near-misses across the population, and "An
  LLM- or a-priori-authored constraint is an unverified assertion and must not gate." 2026-11-25 08:06: "You can't
  define a thing only by what it's not."
- **Code.** `censors.py`. A censor is a relation that forbids states in a typed scope. It is admitted by E6 with a
  sourced near-miss as its witness, and it keeps the remaining lawful states. Zero is written when explicit absence
  is warranted. SILENT is marked when the definition is shown to be silent. A signed value always needs a positive
  root; a mask that elimination leaves at one sign without a root is reported as a missing content warrant.
- **Principle.** DOF- in Negative Specification's three regions. Forbidding is real information, and a valuable
  censor is often a bridge.
- **Running.** As E4 relations over their scopes.
- **Output.** Zeros and silences with proofs. The valency censor (persons-only predicates on non-living things,
  times and places) measured 79,780 zeros as a predecessor. It is re-derived under E6.
- **Contribution.** The confident zeros the information theory depends on, without mass zero-filling.

### E8. Inheritance across readings

- **Source.** 2026-11-26 19:38: sub-categories of meaning are "the *easiest* tier", and "I've told you repeatedly
  not to focus on WordNet as if its the gold standard". 19:42: "TrialLedger's constraint propogation ideas are how
  we allow sub-kind inheritance without introducing spurious and incorrect additions". TrialLedger: "Defaults have
  declared applicability and defeaters; conflicting defaults are suspended and reported, not selected by order."
  NSM molecules: "X [m] of one kind" means the category's components carry to its kinds.
- **Code.** `inheritance.py` builds typed, directed edges: kind-of, synonymy, adjective satellites, verb entailment
  and cause, Wiktionary form-of and alternative-of, and bindings of NSM molecule explications to their category.
  Each edge family declares which properties it carries. Defaults flow along edges as interpolated states. A
  default that conflicts with a known state, or with another default, is suspended and reported. Declared
  defeaters name the source misfilings. Hub silence never carries.
- **Principle.** kappa is coverage over the hub structure. One fact taught at a hub resolves its whole cover, which
  is C(H) in the completeness equation.
- **Running.** Sparse edge arrays. Defaults are pushed along edges, then E4's relations run, then defaults are
  checked again, until nothing changes.
- **Output.** Inherited cells, known and interpolated kept apart. The predecessor measured 63,638 cells on WordNet
  kind-of under an earlier gate.
- **Contribution.** It reaches the readings no source describes directly, including the Wiktionary readings bound
  by the links Wiktionary states.
- **Wiktionary readings (246,240).** F080: "I don't think we EVER need the raw gloss text". A Wiktionary sense is
  bound only through structured fields:
  - `form_of` and `alt_of` (an inflection or variant has the meaning of its target);
  - `synonyms`;
  - an alignment to a WordNet sense of the same lemma and part of speech. About 97% of senses carry `links`, the
    words their editors linked, and sparse-wiki uses exactly such editor links as semantic anchors. The sense
    aligns to a candidate only when exactly one candidate has the synset of a linked word among its kind-of
    ancestors (or as itself). With no such candidate, or two or more, it abstains and stays residual.
  This is exact set logic over editor links and the kind-of graph, with no score and no margin. GSE's runtime
  resolver (`grounding._select_by_coherence`) uses a margin and a frequency prior, so it is not used to decide
  anything in the build. An alignment is a proposed identity: content crosses it as an interpolated default,
  suspended on any conflict, and the senses of E10 confirm it or keep the readings apart. Topical categories and
  `topics` are domain facts for scoping and coherence, not kind-of edges.

### E9. Closure and measurement over the population

- **Source.** 2026-11-26 20:44: "There are several dozen million combinations of bank encodings and associations
  ... you're still stuck on the scale of hundreds or thousands". SSL 2.5: H and the completeness equation.
  TrialLedger: "Finite coordinate closure removes values with recorded causes and reaches an order-independent fixed
  point."
- **Code.** `closure.py` runs a worklist over changed cells and changed edges, waking only the relations and edges
  that read them, to a fixed point. `measure.py` computes H (marginal domain sum, plus the joint count in tractable
  components), the census, and per-rule reach and kappa.
- **Principle.** dH/dt = -(N_ext + N_ind + C(H)). Each round reports how much H fell, split into direct premises,
  structural consequences and admitted population laws.
- **Running.** A full round over 22.5M cells is a sequence of array operations; the target is seconds to minutes,
  not hours. Cold replay and incremental replay must agree.
- **Output.** A receipt each round: H, the census by state, bank, part of speech and source, the decided cells by
  warrant, conflicts, and wall time and memory.
- **Contribution.** The build works at the scale of the lexicon, and every claim about progress is a measurement.

### E10. Senses

- **Source.** 2026-11-25 03:28: "They're the same sense of the word if they resolve to the same bank encodings
  across the ones that are of high salience, that are definitional across the load-bearing banks". 20:20: no
  "arbitrary frequency-defined 'main sense'". 01:53: at least one sense for each part of speech present; the 44
  definitions of "lock" collapse to a few.
- **Code.** `senses.py` collapses readings within a lemma and part of speech when their resolved load-bearing
  encodings are equal. Missing evidence is never equality, and genuine homonyms stay apart.
- **Principle.** A sense is the coherent core over the noise of particular readings, the platonic ideal of 01:53.
- **Running.** Grouping by lemma and part of speech over the closed state.
- **Output.** Sense records with members, signature and residuals. The live runtime has 110,678 senses with about
  1.35 nonzero values each.
- **Contribution.** What the runtime reads.

### E11. The read: sentence selection and the consumer

- **Source.** 2026-11-25 20:56: "Sentence-side selection. You arbitrarily split it into a different step, when it
  isn't". 01:53: "Grammar is a constraint harness".
- **Code.** The existing grammatical harness and clause selection consume the sense records through
  `GSE.lexicon_resource`. Only their input changes. `store.py` writes the artifact in the form the runtime reads.
- **Principle.** The same constraints narrow the readings in context.
- **Running.** Per sentence, at runtime.
- **Output.** Readings selected in context. The acceptance witnesses are the florbles sentence, "lock",
  chemical "He" against the pronoun, and ordinary prose.
- **Contribution.** The lexicon working in GSE, which is the reason for building it.

### E12. The tail

- **Source.** F078 and F066: a small model selects among a few typed survivors after closure. F148: the tail is
  where a reading disagrees with NSM, by word, bank and rule. 2026-11-25 05:39: "Why is the *model* making
  decisions?" TriageGeist: 29 of 20,000 cases reached the model, under a typed, certified contract.
- **Code.** `tail.py`, enabled explicitly and only after the bulk has been measured. A request names the reading,
  the bank, the legal states and their warrants. The answer is one of those states or an abstention. It is checked
  against current closure, and it teaches: it is a premise for a rule candidate, never a lexical value on its own.
- **Principle.** I_ext, the information that structure and the population cannot supply.
- **Running.** Bounded batches over residuals whose reason is "genuine bounded choice".
- **Output.** Rule candidates and the cells their admitted rules decide.
- **Contribution.** The last, small part. If the tail is large, the structural gap is fixed instead.

## Scale

Readings get dense integer ids and banks get 0-55. Masks, postings and edges are arrays, and sparse records hold
proofs. Relations are compiled once and applied to sets. The old per-definition SQL path took about 3 hours per
pass. Nothing in this design runs per definition at build time.

## Settled by his words

- Feeling nouns carry their inherent valence (2026-11-25 05:30, ruling (c)), "very judicious".
- A model never decides a lexical value (05:39-05:46). Earlier manual calls he authorised keep their receipts.
- There is no main sense (20:20).
- Publication is setting the pointer once the new artifact is strictly better (2026-11-25 21:28).
- Statistical lexicons never write values (2026-11-26 17:01).
- At most three lexicon copies: the live one, the most complete one, and the one in progress (2026-11-26 19:38).

## Open points, to be decided by evidence or by Rohan

- Which banks are load-bearing for a family. The build starts with rule-grounded distinctions and keeps
  alternatives where equality is not shown.
- The exact boundary between zero and silence for each bank. It needs a per-bank warrant.
- The source manifest gives 401,593 readings (155,111 + 246,240 + 213 + 29), but the release counts 401,596. Task 1
  accounts for the difference.
