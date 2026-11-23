# Cross-dataset lexical bank coherence — measured run

These are native-source relations over shared English word keys. No old lexicon vector, gloss parser, model, or source-to-prime map enters the calculation.

Word key: NFC + casefold + strip; no stemming or synonym expansion. This run keeps single words: no whitespace or underscore, at least one alphabetic character; hyphens, apostrophes and Unicode letters are retained. One word has one vote, regardless of the number of source records. Missing sources are excluded. Space-delimited USAS tags are alternatives, slash components are joint membership. FrameNet/VerbNet features mean a native alternative exists, not that every use has it.

Discovery uses word-hash folds 0–2; held-out uses 3–4. Candidate gates: ≥40 antecedent words in EACH partition, conditional probability ≥0.85 in both, gain over the target base rate ≥0.10 in both, rate drift ≤0.10. A candidate is never automatically a definitional law. All counterexamples are in results.json.

C(A→B) = 2P(B|A)−1; information change = H₂(P(B))−H₂(P(B|A)). Positive or negative source-score signs are native score directions, not GSE ternary signs. Zero association, missing, written lexical zero and lexical silence remain distinct.

## Coverage

| Source | Distinct words |
|---|---:|
| concreteness | 37,057 |
| lancaster | 36,811 |
| vad | 44,728 |
| emotion | 14,154 |
| usas | 46,117 |
| framenet | 8,435 |
| verbnet | 3,585 |

Words present in at least two sources: **41,597**.

| Pair | Shared words |
|---|---:|
| concreteness ↔ emotion | 12,311 |
| concreteness ↔ framenet | 7,030 |
| concreteness ↔ lancaster | 36,809 |
| concreteness ↔ usas | 20,668 |
| concreteness ↔ vad | 33,843 |
| concreteness ↔ verbnet | 3,117 |
| emotion ↔ framenet | 5,157 |
| emotion ↔ lancaster | 12,275 |
| emotion ↔ usas | 12,270 |
| emotion ↔ vad | 14,117 |
| emotion ↔ verbnet | 2,335 |
| framenet ↔ lancaster | 7,022 |
| framenet ↔ usas | 7,137 |
| framenet ↔ vad | 7,442 |
| framenet ↔ verbnet | 2,322 |
| lancaster ↔ usas | 20,608 |
| lancaster ↔ vad | 33,635 |
| lancaster ↔ verbnet | 3,115 |
| usas ↔ vad | 22,675 |
| usas ↔ verbnet | 3,029 |
| vad ↔ verbnet | 3,334 |

## Continuous relations

All source-pair numeric tests are recorded, including weak relations. These are the strongest with distinct source channels.

| Fields | n | Spearman ρ | Five-fold range |
|---|---:|---:|---:|
| concreteness:mean ↔ lancaster:Visual | 36,809 | 0.573 | 0.568…0.577 |
| concreteness:mean ↔ lancaster:Haptic | 36,809 | 0.516 | 0.498…0.528 |
| concreteness:mean ↔ lancaster:Interoceptive | 36,809 | -0.475 | -0.492…-0.461 |
| concreteness:mean ↔ lancaster:Hand_arm | 36,809 | 0.429 | 0.408…0.443 |
| concreteness:mean ↔ lancaster:Mouth | 36,809 | -0.303 | -0.326…-0.289 |
| concreteness:mean ↔ lancaster:Auditory | 36,809 | -0.302 | -0.308…-0.297 |
| emotion:negative ↔ lancaster:Interoceptive | 12,275 | 0.270 | 0.250…0.289 |
| lancaster:Auditory ↔ vad:arousal | 33,635 | 0.248 | 0.238…0.264 |
| emotion:sadness ↔ lancaster:Interoceptive | 12,275 | 0.216 | 0.189…0.248 |
| concreteness:mean ↔ lancaster:Head | 36,809 | -0.206 | -0.215…-0.199 |
| emotion:fear ↔ lancaster:Interoceptive | 12,275 | 0.186 | 0.177…0.193 |
| emotion:anger ↔ lancaster:Auditory | 12,275 | 0.181 | 0.152…0.191 |
| emotion:anger ↔ lancaster:Interoceptive | 12,275 | 0.173 | 0.152…0.190 |
| concreteness:mean ↔ emotion:positive | 12,311 | -0.172 | -0.188…-0.141 |
| concreteness:mean ↔ lancaster:Olfactory | 36,809 | 0.161 | 0.146…0.180 |

## Stable directional candidates

458 candidates passed the declared discovery/held-out checks; no candidate is promoted to a hard bank law.

| Antecedent → consequent | Matched / support | Held-out rate | Base rate | Exceptions |
|---|---:|---:|---:|---|
| vad:valence_sign=positive → emotion:negative=0 | 7027/7326 | 0.956 | 0.767 | abundance, actionable, adjudicate, airs, alimony |
| emotion:negative=1 → vad:valence_sign=negative | 2983/3307 | 0.893 | 0.463 | abundance, actionable, adjudicate, airs, alimony |
| usas:field=M → lancaster:dominant_sense=Visual | 1924/2120 | 0.906 | 0.726 | abiding, about, admit, admitted, ahoy |
| lancaster:dominant_effector=Hand_arm → verbnet:argument_role=Agent | 915/965 | 0.936 | 0.821 | adjoin, aim, brawl, bud, cleave |
| usas:category=B2- → vad:valence_sign=negative | 536/597 | 0.888 | 0.423 | aids, analgesia, carrier, carries, carry |
| usas:field=H → emotion:negative=0 | 526/572 | 0.932 | 0.763 | asylum, barricade, bog, brothel, cage |
| verbnet:frame_predicate=motion → lancaster:dominant_sense=Visual | 576/665 | 0.855 | 0.690 | aromatize, bang, bed, blanket, bop |
| usas:field=O → verbnet:frame_predicate=cause | 610/691 | 0.884 | 0.760 | allure, bar, battle, blister, bluff |
| framenet:frame=Experiencer_obj → verbnet:frame_predicate=cause | 127/127 | 1.000 | 0.749 | none observed |
| framenet:frame=Experiencer_obj → usas:pos=VERB | 116/121 | 0.961 | 0.422 | nettle, shocker, solace, vexation, wow |
| verbnet:class=butter-9.9 → usas:pos=NOUN | 97/102 | 0.977 | 0.584 | chrome, lubricate, mulch, muzzle, whitewash |
| framenet:frame=Emotion_directed → lancaster:dominant_effector=Head | 132/140 | 0.944 | 0.640 | bitterness, cross, crushed, disquieted, livid |
| lancaster:dominant_sense=Gustatory → emotion:negative=0 | 204/226 | 0.925 | 0.762 | aftertaste, bitterness, bland, booze, brandy |
| verbnet:argument_restriction=Agent:+machine → emotion:negative=0 | 230/254 | 0.896 | 0.757 | belt, boil, confuse, copy, deform |

## Conjunction gains

Each conjunction uses three different datasets. Both single-premise rates are recomputed on the SAME triple-source population. The conjunction must improve on the stronger single premise by ≥0.03 in both partitions.

| Premises → consequent | Matched / support | Held-out rate | Held-out gain |
|---|---:|---:|---:|
| emotion:negative=1 AND usas:field=G → vad:arousal_sign=positive | 423/488 | 0.870 | +0.188 |
| usas:field=Q AND vad:arousal_sign=negative → emotion:negative=0 | 805/869 | 0.934 | +0.062 |
| usas:pos=NOUN AND vad:valence_sign=zero → lancaster:dominant_sense=Visual | 470/545 | 0.864 | +0.080 |
| lancaster:dominant_sense=Visual AND usas:field=Q → emotion:negative=0 | 656/722 | 0.919 | +0.069 |
| usas:field=Q AND vad:dominance_sign=positive → emotion:negative=0 | 729/801 | 0.915 | +0.048 |
| emotion:positive=1 AND usas:field=A → vad:dominance_sign=positive | 641/736 | 0.875 | +0.046 |
| emotion:positive=1 AND usas:field=X → vad:dominance_sign=positive | 362/402 | 0.920 | +0.091 |
| usas:field=W AND vad:dominance_sign=positive → lancaster:dominant_effector=Head | 220/251 | 0.881 | +0.116 |
| emotion:negative=1 AND lancaster:dominant_sense=Interoceptive → vad:valence_sign=negative | 459/474 | 0.963 | +0.070 |
| emotion:trust=1 AND lancaster:dominant_effector=Head → vad:dominance_sign=positive | 756/863 | 0.869 | +0.036 |
| emotion:negative=0 AND verbnet:argument_role=Predicate → vad:valence_sign=positive | 126/144 | 0.868 | +0.210 |
| emotion:joy=1 AND lancaster:dominant_effector=Head → vad:dominance_sign=positive | 433/492 | 0.892 | +0.055 |
| emotion:fear=1 AND usas:field=G → vad:arousal_sign=positive | 265/291 | 0.879 | +0.105 |
| lancaster:dominant_effector=Head AND usas:field=Q → emotion:negative=0 | 568/636 | 0.906 | +0.056 |
| usas:field=I AND vad:dominance_sign=positive → emotion:negative=0 | 433/472 | 0.921 | +0.054 |

Conjunctions with both singleton risk differences ≤0 in discovery: 0. The search does not require singleton lift; a separate parity witness tests that a purely complementary pair is discoverable.

Significance Weighting §§7b and 13 apply to the next rule stage: remeasure marginal resolution after each admitted relation; account for redundant coverage and complementary bridges. The entropy changes here describe native target-state frequencies. They are not an exact measurement of feasible GSE vector configurations or a proof of a greedy guarantee.

Native contracts: [USAS category guide](https://ucrel.lancs.ac.uk/usas/usas_guide.pdf) defines ranked alternatives and slash membership; [NRC VAD v2 paper](https://arxiv.org/html/2503.23547v1) defines the signed native rating scale. Source snapshot hashes, rather than assumed release names, identify this run.

## Interpretation boundary

A recurring native relation proposes the guard and allowed tuples of a GSE bank law. Definition versus association, participant versus denotatum, POS alternatives and the bank mask contract still determine its exact lexical consequence. Norm correlations alone cannot write FEEL, GOOD, BODY, MOVE or silence. The result is a ranked corpus of rule candidates, including counterexamples, for that symbolic review.

This run does not contain certified GSE bank states. Measuring relations between the old generated prime signs would reproduce its mistakes. It measures the independent source channels from which those signs and bank relations are to be derived.
