Reading the packet only, here is the second-reader check: five answers, then provable errors, then the three decisions.

**1. NOUN and evaluation.** The supplied Natural Semantic Metalanguage evidence, NSM below, does not establish that NOUN implies evaluation 0. It establishes scope distinctions. Goddard 2012 lists GOOD and BAD as evaluators with no part-of-speech restriction, and its THINK frames include "someone thinks something good or bad about someone." The Finnish noun viha, in the definition most analysts applied to most noun tokens, carries BAD at three scopes: the experiencer feels very bad, the experiencer thinks something very bad about the target, and many people think it is bad to think like this. Levisen's explication of the noun happiness carries GOOD at the same three scopes, and Levisen calls it a value word with an emotive component. The paper's own noun-versus-verb contrast is also a scope shift: the verb predicates badness on the target and wants bad things to happen to it, while the noun only thinks something bad about it. BAD moves; it does not vanish. None of this is a speaker-voice judgment on the noun's referent, which is what F057 denies. The founder's rule is therefore a GSE convention about one scope, the word's own evaluation cell. It is permitted under F144. The literature neither confirms nor refutes it, and the build should label it GSE's, not NSM's.

On English hatred the packet says nothing direct. The viha paper gives no explication of English hate or hatred. It reports that Wierzbicka's English anger lacks the Finnish "many people think it is bad" feature, and the authors say the cross-language differences may come from language, data, or method. Their inter-analyst agreement on the noun was poor. One Finnish word cannot ground a law about English nouns, and the packet forbids inferring law from association. What can be stated: by GSE convention hatred's own evaluation cell is explicit 0; by NSM practice its explication carries BAD under FEEL and THINK scope; that scoped content is the structured evidence the settled projection decision keeps out of the own cell. Whether an observer-judgment feature belongs to English hatred is unknown from this packet.

**2. What destash supplies.** The file is a target-versus-candidate similarity filter with vetoes. It supplies four reusable ideas:

- **A three-pole cell.** Affirm 1.0, silent 0.5, contradict 0.0, mapped through a cosine to +1, 0, −1. Silence is neutral by design and −1 fires only on a positive contradiction.
- **Contradiction as veto**, not a point on a spectrum. This matches the founder's inviolate true-rule tier.
- **Discrete and continuous axes scored separately** and never averaged. This matches keeping NUMBER out of sign-bank agreement.
- **A weighted agreement score** over independently scored dimensions.

It does not implement:

- **Cross-dimension inference.** Each dimension is scored alone against hand-set constant weights. Nothing relates one dimension to another within a vector or across a corpus, so there is no bank-to-bank rule discovery of the F101 kind.
- **Corpus-wide statistics.** The profile is self-contained per call by its own docstring.
- **Dynamics.** Despite the name there is no oscillator coupling or phase evolution, only a static weighted cosine of phase differences.
- **An explicit zero.** The target is always 1.0 on its own binary dims, so a target cannot be silent or zero. A candidate's 0.5 means "did not mention," which is GSE's empty, not GSE's 0. No code path means "asserted absent."
- **Exceptions.** The veto is absolute. The curated and sold bypasses are provenance bypasses, not conditionally-true rules.

The F101 coherence metric is not in this file, and the packet cannot show whether the harmonizing code has it.

Neutral versus explicit zero decides whether the build's statistic works at all. When counting how often NOUN co-occurs with evaluation 0, the 0 cells are the signal. Inheriting destash's "absence is neutral" and treating 0 as no-information discards that evidence. The opposite mistake, counting empty as 0, fabricates the law from coverage: a sentiment source that annotates only adjectives leaves every noun empty, and empty-as-zero turns that gap into perfect NOUN-implies-0 coherence. Any coherence count needs a four-valued input, with empty excluded as missing data and 0 counted as an observation. Destash has no template for this.

**3. Combinability.** Combinability does not entail an assignment in a word's own banks. Goddard's "substantives can combine with specifiers," with the examples "one place" and "many kinds," is a permission in the metalanguage's syntax. A permission says a cell is not forbidden. It does not say the cell is filled or zero. Only incompatibility collapses: if two categories cannot co-occur, presence in one forces explicit 0 in the other. Combinability only says that collapsing rule is false, and leaves the cell empty for other evidence.

Counterexample on the packet's own terms. Quantifiers combine with substantives in both Goddard's text and F067's flock example. If combinability entailed own-bank assignment, the prime word many would carry THING and the word bird would carry MANY. Under F088 a prime fills one bank, and under F057 a modifier has no objectness, so many has no THING value. Bird is as combinable with MANY as flock is, yet only flock's explication contains MANY. Combinability was the precondition that let flock's explication be well formed. It supplied no value.

One provenance note. The packet's Goddard text does not state that evaluators and descriptors are mutually exclusive; it lists them as separate categories. The "no big good" exclusion is a GSE law and should be recorded as GSE's. Words such as monstrous, which plausibly carry both BIG and BAD, are the test cases that fix its tier under question 5.

**4. Dog, cat, and NUMBER.** Both are resolved in intent. Point 5 and the repo's agent file say dog and cat may be near-identical in the lexical leg and are distinct objects. The dictionary words of 2026-10-26 fix identity as one entry per definition keyed by headword, with the world leg carrying the differences. F098, F126 and F148 fix NUMBER's purpose: an ordering among words with identical bank presence and sign, changing neither.

Remaining mathematical facts, stated without reopening intent:

- **The lexical map is not one-to-one.** Dog and cat can share a sign vector and a NUMBER. Inversion from vector to word is set-valued, and "same vector" is a synonym-candidate class, not a synonym class. Synonym collapse cannot be defined by vector equality alone; it needs the entry key or the world leg. F098's claim that NUMBER makes every non-synonym unique holds only for words separated by intensity, so uniqueness is a property of the whole entry, not of the lexical leg.
- **NUMBER is relative, so it needs a declared comparability domain and origin.** The only domain consistent with the founder's words is the class of entries with identical sign vector. Comparing exhausted with furious is undefined. F098's own scale puts neutral at the center. Under "NUMBER changes no sign," neutral is the bank's 0, each side of the scale is one sign of the bank, and NUMBER ranks magnitude within a side. If NUMBER were instead signed across the center, direction would be stored twice. The scale is ordinal unless a source supplies interval structure. NUMBER stays out of bank-coherence counts, as destash keeps continuous dims out of discrete ones.

## Provable errors

**Latent in destash.** The pairwise coherence function defaults a missing dimension to 0, while the decision function defaults to 0.5.

```
weights = {"d": 1.0}; target_vals = {"d": 1.0}; candidate_vals = {}
kuramoto_coherence_pairwise:  cos(pi * (1.0 - 0))   = -1   # read as contradiction
coherence_decision:           cos(pi * (1.0 - 0.5)) =  0   # read as silence
```

The comp filter never hits this because it materializes every extractor. A GSE reuse on sparse bank dictionaries would read every empty cell as a contradiction.

**GOOD and BAD as two cells.** F066 and F067 write them as two cells. F098 and F148 say definitional antonyms collapse into one signed bank. If the implementation keeps two cells, GOOD equal to minus BAD must be a true-tier constraint, or the cells must merge. F067 itself calls them perfectly anti-correlated.

**Prime counts.** Goddard 2012 says 64 primes. The counts 72, 58 and 73 are GSE's basis, fine under the closed-basis rule, but not NSM's counts.

## Three unresolved decisions

1. **Where scoped evaluation lives in an entry.** With own-cell evaluation at 0 and no automatic projection, love and hatred both have FEEL non-zero and evaluation 0. Their one definitional difference, a good feeling against a bad feeling, is expressed in NSM by primes, so it is lexical meaning under the closed-basis rule. If the entry has no typed place for it, the two words collapse in the lexical leg and a correct value is destroyed. The decision is the typed form of that structured evidence and whether it participates in distance and synonym collapse.

2. **Tier assignment and acceptance criterion.** F148 fixes the three-tier hierarchy but places only prime-to-prime relations in the true tier. The part-of-speech laws and the evaluator-descriptor exclusion are POS-to-bank and category-to-category rules from F057 and F067, which Rohan called sketches to be checked against the sources. Veto machinery applies to the true tier and significance weighting to the conditionally-true tier, so a rule's tier changes the lexicon on every conflicting word. The build needs the true-tier list declared, plus the acceptance rule for corpus-derived conditional rules, since "possibly Zipf-weighted" was left open and the weighting changes which rules survive.

3. **NUMBER's operational definition and scope.** Confirm the comparability domain, origin and ordinal scale above, and state whether NUMBER assignment is in this build or deferred. By F098 symbolic rules cannot derive intensity from prime structure, so the source must be named: gloss patterns such as "very X," an intensity lexicon, or the typed model stage.

One obligation settled in intent and easy to break: the typed model call targets only empty cells after symbolic exhaustion. A rule-derived explicit 0 is an assignment, not a gap, and is never re-queried. F078 lists empty as an allowed output, so the model may abstain, and an abstention leaves the cell empty rather than writing 0.

Recap: the NSM evidence supports scope distinctions, not a NOUN law. Destash offers a veto and a three-pole cell but no rule discovery and no explicit zero. Combinability entails nothing. Dog/cat and NUMBER are settled in intent, with two precise obligations on injectivity and on NUMBER's domain. The three decisions above gate the build.