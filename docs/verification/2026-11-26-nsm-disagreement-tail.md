# The lexicon's disagreements with NSM: causes, fixes, measurement (2026-11-26)

Task: `openspec/changes/lexicon-symbolic-foundation/nsm-disagreement-tail.md` (F148). Rohan approved it on 2026-11-26.

**Result.** Every one of the 381 disagreements has a computed cause. No fix is admitted:

- The one candidate fix that a source could carry was measured and refuted by NSM counterexamples.
- Every other cause is either measurement structure or a decision that belongs to Rohan.

The lexicon is unchanged: 0 cells filled, 0 changed, 0 removed. What this run adds:

- the classifier (`word_sense_nsm_tail.py`);
- its receipts;
- the questions for Rohan in tasks.md.

## How the classes are computed

- Command: `.venv/bin/python scripts/word_sense_nsm_tail.py --receipt docs/verification/2026-11-26-nsm-tail-classes.json --db <lexicon>`
- Code: `GSE/curation/lexicon_builder/word_sense_nsm_tail.py`
- Tests: `tests/test_lexicon_nsm_tail.py`

Explications are matched to words exactly as `scripts/lexicon_measure_vs_nsm.py` matches them: 35 explications. A
disagreement is a prime the explication's own clauses use that the word's reading does not hold at +1. These are the
same 12 contradictions and 369 open primes the measurement reports.

Each disagreement's cause is computed in this order:

1. **CONVENTION_ZERO.** The reading holds 0, and every sense that holds it took the value from a release convention
   rule named in the definitions' traces (`founder:noun-own-evaluation`, `founder:adjective-not-object`).
2. **SENSE_SPLIT.** A sense of the word holds +1. The reading, which is what the senses agree on, does not.
3. Otherwise the class comes from the explication tokens that produce the bank. Tokens are matched through the same
   catalog exponents and WordNet morphology as `banks_in`. Each token is one of:
   - **frame**: inside NSM's own template structure and not a substantive. That means the category formula "of one
     kind", a referent anaphor (`template_types.REFERENT`), or the component introducer "like this". The introducer is
     derived from NSM's template records: the words before ":" that recur across them.
   - **deictic**: the exponent THIS, which the catalog files under SOMETHING as "a grammatical/contextual binding".
   - **collision**: a word that matches an exponent only after the catalog drops a final "s". This is the article
     "a" read as AS, and so as LIKE. Neither the word nor its WordNet base is the exponent.
   - **copula**: a form of "be". The catalog shares BE between BE (SOMEWHERE) and BE (SOMEONE/SOMETHING).
   - **content**: anything else.
4. A bank with any content token is classed by its chart category:
   - **LOGICAL_OPERATOR** if the category is logical concepts (CAN, NOT);
   - **CONTENT** otherwise.

   A bank with no content token takes its token class.

For each CONTENT disagreement, the receipt also records what the word's sources say about that bank
(`source_agreement`):

- **NO_VOTE**: no family votes on it.
- **UNMEASURED**: only families that do not measure the bank vote on it. These are association signals, which Rohan's
  ruling excludes as evidence.
- **SINGLE_FAMILY**: one measuring family votes on it. Committing needs two.

## The classes

| Class | Count | Banks | Cause | Fix |
|---|---:|---|---|---|
| CONVENTION_ZERO | 12 | GOOD 11, SOMETHING 1 | The release's F057 noun-evaluation zero, under D-1. It covers children (×2), snake, animals, dogs, kangaroo, happiness, disease, trauma, parricide and violence. Childlike's SOMETHING 0 comes from the adjective convention. NSM's own sign is −1 for children, snake, disease and violence, and +1 for happiness; the other five explications carry both signs. Childlike's SOMETHING tokens are 5 deictic THIS, 1 collision and 1 content: the feeling's object, a participant. | None. GOOD on nouns is FC-7, Rohan's open question. |
| SENSE_SPLIT | 33 | ALIVE 7, SOMEONE 7, BODY 3, PART 3, PEOPLE 3, SOMETHING 3, DO 2, WHEN 2, BE 1, MOVE 1, WHERE 1 | Polysemy. The explicated sense holds the prime, but another sense does not. Examples: dog.n.01 against andiron, frank and pawl; woman.n.01 against womanhood.n.02. | None. Rohan's ruling (2026-11-25) is that there is no main or default sense. |
| TEMPLATE_FRAME | 27 | KIND 14, ONE 12, LIKE 1 | The category formula, the referent anaphor ("of this kind") and the introducer "like this". | None. This is not the word's content. |
| DEICTIC_THIS | 1 | SOMETHING 1 (depressed) | THIS read as SOMETHING. | None. |
| EXPONENT_COLLISION | 22 | LIKE 22 | The article "a" read as AS. | None in the lexicon. It is an instrument fault (question 4). |
| COPULA_BE | 28 | BE 28 | Every "is" and "are" is read as the prime BE. | None. The instrument cannot separate the copula from BE. |
| LOGICAL_OPERATOR | 41 | CAN 26, NOT 15 | NSM's propositional operators: CAN or NOT scoping a clause about the referent. | None. Whether a noun's bank should carry these is a question for Rohan. |
| CONTENT | 217 | BODY 17, THINK 16, WHEN 15, PEOPLE 14, LIKE 12, SOMEONE 12, PART 11, WANT 10, ONE 9, TWO 9, BEFORE 8, FEEL 8, DO 7, KIND 7, OUTSIDE 7, KNOW 6, SAME 6, BIG 5, LONG_TIME 5, MOVE 5, WHERE 5, HAPPEN 4, FAR 3, SAY 3, TOUCH 3, ABOVE 2, GOOD 2, SEE 2, ALIVE 1, HEAR 1, THEN 1, WORDS 1 | Sources: NO_VOTE 166, UNMEASURED 45, SINGLE_FAMILY 6. See the analysis below the table. | None admitted. The source-backed candidates lie inside reviewed scopes (below). |

How the CONTENT disagreements break down:

- In 28, NSM's tokens are negative poles only. For example, "inside" is OUTSIDE −1, "other" is SAME −1 and "small" is
  BIG −1. NSM's value there is −1, not the +1 the measurement expects.
- In 2, a sense holds 0: hands WANT 0 and depression GOOD 0.
- Many are not the referent's own identity but its relations:
  - PART, ONE and TWO name the referent's parts and count them.
  - PEOPLE comes from the category line of a plural human noun whose sense holds SOMEONE+.
  - THINK, FEEL and WANT often sit in clauses whose subject is a participant that `own_lines` does not exclude, and
    so counts as the referent's own.

Agreements (41) under the same token kinds:

- 28 rest on content tokens.
- 11 rest only on THIS read as SOMETHING (the noun explications' SOMETHING "agreement").
- 2 rest only on the collision.

## Fixes considered

| Fix | Warrant | NSM counterexamples | Stored-value clashes | Coverage | Verdict |
|---|---|---:|---:|---|---|
| Synset carry: a derived-spelling WordNet definition (e.g. dogs:dog.n.01) takes its synset's native-spelling values | WordNet synset identity plus replay-validated native values | **5** (hands and legs: WANT 0, BODY 0) | 0 | 20,762 cells on 9,365 definitions (4,320 lemmas) | **Refuted**: `2026-11-26-tail-synset-carry-refuted.md`. The native-lemma guard is also a deliberate identity abstention (design), so its scope is Rohan's decision. |
| Widen the vertebrate BODY rule to animal.n.01 (BODY on animals and creatures) | The reviewed rule `reviewed-guarded-pattern:65152c2f…` is scoped by `wordnet_ancestor:vertebrate.n.01` | — | — | — | Not built. It widens a reviewed rule's scope, which is Rohan's decision. |
| GOOD on nouns where NSM uses GOOD/BAD in the word's own content | none (the noun-evaluation zero is the release's rule; D-1 is Rohan's) | — | — | — | Not built. This is FC-7. |
| Commit association-only or single-family source signs | refused by Rohan's rulings (statistical lexicons only corroborate; MIN_FAMILIES = 2) | — | — | — | Not built. |

No fix met admission, so cells changed by fixes: 0.

## Before and after

The candidate is `data/lexicon_builder/2026-11-12/sparse-release-022-senses3-tail.db`. It is a copy of the live
`sparse-release-022-senses3.db` with every word sense rebuilt at this commit's code.

| | Live (senses3) | Tail candidate |
|---|---|---|
| NSM measurement (agree / contradict / missing) | 41 / 12 / 369 | 41 / 12 / 369 (`2026-11-26-lexicon-vs-nsm-tail-candidate.json`) |
| Tail classes | as above | identical |
| Word senses | 110,678 senses; 264,317 assigned (135,417 nonzero); 5,933,651 unassigned cells of 56 banks | identical |
| `compare_word_senses.py` (93,396 readings) | — | 0 filled, 0 changed, 0 removed |
| `build_word_senses.py --verify 300` | — | 300/300, 0 mismatches |

Checks at this commit:

- **Word-sense tests**: source agreement, senses reader, acceptance, no new model values, every value warranted, and the
  new `test_lexicon_nsm_tail.py`. 65 passed on the tail candidate and 65 on the launcher's candidate.
- **Encoder test files** (66, `grep -rl GSEEncoder tests`, without `_archive`): 1,691 passed, 12 xfailed, 1 failed. The
  failure is the accepted `test_GSE_genealogy_store.py::test_world_strand_returns_thing_rooted_lineage`.
- **ruff**: check and format pass on the changed files.
- **`lint-imports`**: one contract is broken, and it was broken before this run. `GSE.symbolic.clause_selection`
  imports `lexicon_builder.valency_absence`. `git log -1 -- GSE/symbolic/clause_selection.py` gives 1585115 (Rohan's
  other session), and `git diff --stat 8722ef2..HEAD` shows that this run changed no file under `GSE/symbolic/`.
- **The launcher's candidate** (`sparse-release-022-word-senses.db`, built 2026-11-25): it was stale before this run,
  with 47 of 300 lemmas mismatching the committed code. The build code is unchanged since 5d018f0. It was rebuilt with
  `--all` and now verifies 300/300.
  - Its definitions come from a copy of bare release-022 made before the identity revisions (SP-1). Compared with the
    live senses3 it therefore shows 4,388 filled, 5 changed and 16,439 removed.
  - The 5 changed values are the identity revision's own BIG changes (gargantuan, grand, heroic, …), reversed. The
    removals are mostly SP-1 identity values (HAPPEN, DO, MOVE, CAUSE, WHEN).
  - None of this comes from this run. The comparison of this run's result is the tail candidate's 0 / 0 / 0.

## Files outside the brief's list

The task requires the `docs/verification/` receipts:

- this file;
- `2026-11-26-nsm-tail-classes.json`;
- `2026-11-26-tail-synset-carry-measured.json`;
- `2026-11-26-tail-synset-carry-refuted.md`;
- `2026-11-26-lexicon-vs-nsm-tail-candidate.json`.

They hold source keys, line ranges, lemmas, banks, classes and counts, and no explication text.
