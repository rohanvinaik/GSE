# Exact native WordNet equivalence — factual census

**Scope:** ASSIGNMENT C — READ-ONLY FACT CENSUS; bounded native-equivalence second-reader probe. No transfers, admissions, model calls, DB writes, snapshots, activation, or source edits. Original coverage reports preserved.

## Opportunity, not actual gain

Verified all **155,111** original observations against local **WordNet 3.0**: exact canonical synset, full gloss/POS, native lemma list, and complete paths, plus production identity checks. Retained **114,316 native-attested definition IDs** across **76,411 synsets**; excluded **40,795** non-native-attested spelling expansions. Every definition/sense identity remains separate.

**2,508** distinct unknown candidate cells across **982 definitions**, **837 spellings**, and **546 exact synsets**:

- **2,489 source-backed:** 1,701 direct native VerbNet components; 788 existing MOVE→HAPPEN / CAUSE→HAPPEN founder-law consequences.
- **19 accepted-model-only**, separately recorded and not independent reusable-law evidence.
- **Zero existing singleton-sign contradiction groups** within the eligible exact-synset population.
- **517** cells have multiple donors; **3,384** donor→target edges deduplicate to 2,508 target cells.
- **Six INTENSITY candidates excluded** conservatively; no hierarchy or ordinal values transferred.
- **1,161** candidate cells concern forms in the runtime Brown common-form artifact. This is not a sense-frequency estimate.

| Bank | Candidate cells | Source-backed | Model-only |
|---|---:|---:|---:|
| HAPPEN | 790 | 788 | 2 |
| CAUSE | 661 | 661 | 0 |
| DO | 612 | 612 | 0 |
| MOVE | 349 | 349 | 0 |
| FEEL | 78 | 78 | 0 |
| BODY | 10 | 0 | 10 |
| WANT | 8 | 1 | 7 |

Existing frequency policy ranks **all distinct foundation spellings** using the fixed SUBTLEX CSV, not senses. All sense identities retained.

| Spelling band | Eligible native definitions | Existing open nonordinal cells | Candidate cells | Source-backed | Model-only |
|---|---:|---:|---:|---:|---:|
| 1-500 | 4,164 | 223,658 | 203 | 202 | 1 |
| 501-1500 | 6,957 | 372,352 | 280 | 279 | 1 |
| 1501-5000 | 15,121 | 806,848 | 548 | 546 | 2 |
| 5001+ | 40,526 | 2,160,817 | 852 | 848 | 4 |
| unranked | 47,548 | 2,522,418 | 625 | 614 | 11 |

Top forms by spelling rank: **have (6 cells), do (6), can (3), get (14), go (4)**. Only the exact listed readings are implicated—not every sense of these words.

## Existing source and guard support

`evidence._verbnet_links` resolves exact native sense keys but selects `by_synset[(word, synset)]`, so assertions reach one lemma definition rather than all native synonyms. WordNet’s projector is already exact-synset-specific and supplies **none** of these missing signs. `engine.propagate` constrains one definition, not multiple identities. These gaps are not claimed to be failed applications of already-matched WordNet root rules.

All **772** involved native VerbNet packets were reprojected with the pinned current adapter: **zero changed projections**. Their per-entry native sense links independently match. The existing solver retained every donor sign. This is a bounded donor check, **not a full dictionary replay or new semantic approval**.

Current guards can express exact native scope without a word lookup: `wordnet_native_lemma=true` AND `wordnet_ancestor:EXACT_SYNSET=true` AND `wordnet_outside_ancestor:CHILD=true` for **every** immediate native hyponym and instance-hyponym. Ancestry includes self; excluding child branches leaves the exact sense. No dedicated positive equality predicate is exposed.

Recorded conjunctions have **zero leaked/missed IDs** against the complete eligible cohort for all **548** relevant synsets, including excluded ordinal examples. Ancestry is used only as an identity filter, never to transfer signs down the hierarchy. No guard/rule was introduced or admitted.

## Complete source examples

- **accept.v.02** (v): “receive willingly something given or offered”
  Native lemmas: accept, take, have. Donor `wordnet:accept:accept.v.02` → separate target `wordnet:have:accept.v.02`: DO=1, HAPPEN=1, CAUSE=1; target cells remain unknown.
- **arrive.v.01** (v): “reach a destination; arrive by movement or progress”
  Native lemmas: arrive, get, come. Donor `wordnet:arrive:arrive.v.01` → separate target `wordnet:get:arrive.v.01`: HAPPEN=1, MOVE=1; target cells remain unknown.
- **do.v.08** (v): “create or design, often in a certain way”
  Native lemmas: do, make. Donor `wordnet:make:do.v.08` → separate target `wordnet:do:do.v.08`: DO=1, HAPPEN=1, CAUSE=1; target cells remain unknown.
- **abhor.v.01** (v): “find repugnant”
  Native lemmas: abhor, loathe, abominate, execrate. Donor `wordnet:abhor:abhor.v.01` → separate target `wordnet:abominate:abhor.v.01`: FEEL=1; target cells remain unknown.

JSON retains all candidate IDs, complete example root/VerbNet observations, source/assertion/request IDs, narrowing proofs, exact relation tables, native guard conjunctions, frequency denominators, and code/corpus pins.

## Verification and limits

**22 census checks passed.** An initial audit compared member-wide sense links against a per-entry subset; the failed receipt is retained and the corrected exact grouping check is documented. No membership, gloss or POS requirement was relaxed.

Foundation SHA256 before/after: `0a1ddba83ccca919a810305fa609199e6aa0b1d0f3431e9a50fb039ea979cc47`. All eight inspected source pins stable. Frequency CSV SHA256: `fa636292ba0b1b5cf4d6d335690ddcf3a162e4a8204124d95c64e795eb336226`; native WordNet ZIP hash in JSON.

**Actual semantic/corpus change: zero. Measured H gain: zero.** Candidate counts are not jointly validated assignments or entropy forecasts. A known singleton is not a newly adjudicated equivalence-transfer warrant. No CI/publication gate or CP completion claimed. Active pointer observed at `sparse-release-021.db`; this worker performed no activation.

**Completion receipt:** coverage scope has stopped editing after final report verification; controller/runtime work was not blocked.
