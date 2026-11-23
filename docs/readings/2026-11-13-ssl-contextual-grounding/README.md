# Contextual grounding on sparse release 013

The sentence encoder still reads exact native WordNet definitions from the sparse lexicon. The existing noun-anchor and type-thread path runs first. When it abstains, the grounding code can use a bounded construction with a unique source-backed witness. Witnesses include a defining predicate repeated with other gloss content, a verified WordNet derivational pointer, or an explicit grammatical construction supported by the native type thread. The branch retains the competing candidate IDs when more than one exact sense qualifies. WordNet pointers are checked against the saved definition and native lemma set. The encoder still takes bank domains from the selected definition. A grammatical construction supplies identity evidence and leaves its bank values to the dictionary.

The parser's verb-promotion check also preserves a noun in a governed cardinal phrase such as *with one cut*. The corresponding clause-initial pronoun in *One cut the rope* remains a possible subject of the verb *cut*.

## The fourteen event and action abstentions

| Case | Grounding result | Required banks still open |
|---|---|---|
| Change of state | Identified by the transition between two attested states of matter and the transition sense's event thread and gloss | HAPPEN |
| Unexpected incident | Abstained. A train delay is compatible with either a distinct event or a public disturbance. | HAPPEN |
| Unplanned accident | Abstained. The complement identifies what happened. It supplies no exact WordNet witness distinguishing the general chance occurrence from a mishap. | HAPPEN |
| Night fire | Identified by event onset and the defining verb *burn* in the continuation | HAPPEN |
| Daily sunrise | Identified by *sun*, *rise*, and *horizon* in the linked temporal clause | |
| Roof collapse | Identified by *cause* and *fall* in the native event gloss and sentence | HAPPEN |
| Finish of a race | Identified by the temporal elaboration and the *race* gloss cue, which the place sense also has but whose thread is locative | HAPPEN |
| Motor repair | Identified by *put*, *work*, and *order* in the shared-subject construction | |
| Delivery kick | Identified by *deliver* and *foot* in the defining action | |
| Manual push | Identified by *apply*, *force*, and *move* in the native gloss | |
| Deliberate cut | Identified by the *divide* derivation to the native ancestry and the counted result *into two parts*. The grammar preserves the target noun. | |
| Cleaning action | Identified by the duration and the *scrub* derivation to a native subtype of cleaning | |
| Criminal arrest | Identified by the native derivation from *apprehend*, corroborated by the noun's defining predicate | DO, HAPPEN |
| Buying action | Identified by the exact native derivation from *purchase* | DO, HAPPEN |

The syringe sense of *injection* remained identified. The event/action cases went from one to thirteen correct sense selections out of fifteen, with two abstentions and no wrong selections. Thirteen of their 23 required signed banks were emitted in context, up from two. Eight required banks are open on identified senses and two are still blocked by sense selection. The participant reading of *arrival* adds a separate correct SOMEONE emission. Its DO and HAPPEN remain open. All three explicit ambiguity controls still abstained. The projectile, work product, wound, and arrest-state controls also abstained in context. [Benchmark replay](final-corrected-benchmark.json)

The wound control originally named `cut.n.01`, the share-of-profits sense. The corrected benchmark names `cut.n.05`, the wound. Both versions were run, with identical event/action counts. The original benchmark had been withheld from rule teaching and audit. Its cases informed this grounding change, so the before/after result is a diagnostic regression check. Independent transfer requires separate evaluation. [Original labels rerun](final-original-benchmark.json) · [Corrected baseline](013-baseline-sentences.json)

Full lexicon replay validated 401,596 records with complete support search and zero mismatches. Sparse runtime controls passed. The semantic audit returned 78 correct and ten abstentions with zero wrong, missing, or conflicted outcomes. Release 013 supplies the same bank domains throughout the comparison, with zero database changes. [Validation](final-validation.json)
