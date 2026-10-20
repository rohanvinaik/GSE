# Clean NSM lexicon rebuild

> The rebuild of the degenerate `data/lexicon.db` (1.36M lexemes, bag-of-words
> primitives → `dog≈murder`) into a clean, sparse, discriminative ternary lexicon
> at `data/lexicon_clean.db`. Built 2026-06-20; validated end-to-end. The DB is a
> reproducible artifact (gitignored) — the build scripts below are the source of truth.

## Result

**67,061 grounded words** over the closed 72-prime basis, ternary {−1,0,+1}:

| layer | count | source |
|---|---|---|
| tier-0 (prime axioms) | 68 | `external_sources/tier_0_dispatch` |
| Layer-1 (source-grounded) | 11,832 | the external-sources integrator pipeline |
| Layer-2 (decomposed) | 55,153 | genus-differentia decomposition |
| operators (clause/comparison) | 8 (+2 in place) | `primitives_v2.COMP_METADATA` |

**Validation:** discriminate 0.373 / collapse 0.602 (dual margin **+0.228**); sparsity
**1.87** primes/word; `tests/test_l1_ladder.py` **15/15** with the encoder pointed at the
clean DB (identical to the baseline).

## The build (all reuse the existing machinery — no new decomposition logic)

**Layer 0 — primes.** The 68 word-scale NSM primes as axioms (`canonical_decomposition`).
The 5 hierarchy primes + the sentence-scale operators are excluded from the word lexicon.

**Layer 1 — `gse/curation/build_clean_layer1.py`.** Grounds the frequency-ranked common
register through the existing `integrator` → `source_scope` → `weighted_voting` pipeline.
Policy:
- **WordNet IS-A is the category source, authoritative within its scope** (SUBSTANTIVES) —
  a scoped vote counts single-source, like tier-0 owns the primes.
- **`wiktionary_v2` is dropped** (the degenerate source this rebuild replaces).
- **Every other source needs ≥2-source agreement** (the A-filter; drops single-source noise).
- WordNet was fixed (`wordnet_hierarchy.to_primitives`) to use the **primary sense only** and
  **not** tag PART from meronyms (was union-over-senses + has-parts→PART noise).

**Layer 2 — `gse/curation/build_clean_layer2.py`.** Genus-differentia decomposition
(`definition_linker`, the genus chain bottoming on the grounded floor + differentia) for words
the sources didn't ground, over the **frequency register + WordNet's real-word lemmas** (WordNet
is the "is this a real word" filter that excludes the exotic junk in the raw definitions dump).
Grammatical words are **not decomposed**: function words and the quantity/intensity/modality
operators route to informational-zero (`definitional_decomposer`, grounded in
`gse/lexicon/function_words.py` + `docs/NSM_GRAMMAR_MAPPING.md`).

**Operators — `gse/curation/build_clean_operators.py`.** The clause/comparison operators
(`than→SET_DIFF`, `so→CONSEQUENCE`, `because→CAUSAL_SOURCE`…) carry no word content but MUST
exist in the lexicon with their `comp_*` metadata, because the **encoder reads the operator
from there** to build clause structure. Grounded in `primitives_v2.COMP_METADATA`.

**Closed class — `gse/curation/build_clean_closed_class.py`** (runs last, after the quantifier
rows). Puts each grammatical word in one of the three homes below and only there: a pronoun takes
its word-scale prime from `gse/lexicon/pronouns.py` (SOMEONE or SOMETHING); an inflected tier-0
word takes that word's prime (`am/are/being → BE`, `does/did → DO`, `has → HAVE`; `cannot → CAN,
NOT`); five words take the prime they realize (`like → LIKE`, `underneath → BELOW`,
`may/might/perhaps → MAYBE`); the periphrastic modals take the primes `NSM_GRAMMAR_MAPPING.md` routes
them through, one Bank 7 prime each (`could → CAN`, `should → MUST`, `would → MAYBE`; GSE #66); every other closed-class word is
informational zero (`shall`, like `will`, among them), its primes
cleared and its row kept (the spellchecker reads its vocabulary from `lexemes`). It overwrites the
layer-1 rows that took a WordNet noun homograph (`he` = helium, `at` = astatine) and the layer-2
connectives (`however`, `therefore`), GSE #8, and adds the pronouns that had no row, GSE #9. Held:
`this/that/these/those` (determiners as well; rows are keyed by lemma, not POS), `what` (an operator
row), `i`/`you` (the tier-0 primes I and YOU).

Definitions are queried from the indexed `data/definitions.db` (`source_index.py`) — never the
2.7 GB raw dump.

## Design invariants (see also `docs/NSM_GRAMMAR_MAPPING.md`)

- **Closed 72-prime basis.** If a component isn't a sign over the 72 primes, it isn't lexical
  meaning (world-salience is sparse-wiki's job).
- **WordNet is an audit/resolution voter, never a flat lookup or similarity score.** Category is
  set-theory inheritance over primitive sets, not a `word→primitive` fetch.
- **Grammatical words have three homes:** word-scale prime (tier-0), sentence-scale operator
  (`comp_*` / `SYN_*` / `INTENSITY` / `QUANTITY`), or informational zero — never decomposed as content.

## Known residuals

- Synonym-collapse gaps where the genus chain misses a prime (`large→SOMETHING`, not `BIG`).
- A minority of technical adjectives pick up a stray prime via the genus chain.
- The deep exotic tail of `definitions.db` (beyond WordNet's real-word set) is intentionally
  not covered.
