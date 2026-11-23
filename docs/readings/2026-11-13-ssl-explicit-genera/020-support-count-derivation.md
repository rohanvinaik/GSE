# Exact support counting for the expression and reasoning stage

This is a finite combinatorial derivation for the pinned GSE constraint model. Semantic admission of the proposed expression and reasoning rules is a separate obligation. The [stage audit](020-joint-support-stage.json) records complete resolver witnesses and exact native identities; [the measurement tests](../../../tests/test_lexicon_coherence_support_counts.py) pin the counts and their failure conditions.

The existing event component contains DO, MOVE and CAUSE, each with an approved positive implication to HAPPEN. When all four coordinates are free, HAPPEN=+1 permits all `3^3 = 27` triples of the other coordinates. Each of HAPPEN=0 and HAPPEN=-1 permits only `2^3 = 8` triples, because none of the three positive antecedents can hold. The total is therefore `27 + 8 + 8 = 43` supported tuples.

For a definition with SAY already +1, adding SAY→DO forces DO=+1 and hence HAPPEN=+1. MOVE and CAUSE retain three alternatives each, giving nine supported event tuples. The support reduction is `43/9`. The staged corpus has 275 definitions in this case.

With SAY still free, the earlier component has `3 × 43 = 129` supported assignments. Under SAY→DO, each of SAY=0 and SAY=-1 still permits all 43 event tuples, while SAY=+1 permits nine. The new total is `43 + 43 + 9 = 95`. All individual coordinate domains can remain `{-1, 0, +1}` while joint support contracts by `129/95`. The stage has 54 definitions in this case. A justified SAY=0 is a different state: the implication adds no restriction and the event component retains 43 tuples.

For each of the 21 staged reasoning definitions, THINK is already +1 and INFER is free of earlier active constraints. The scoped THINK→INFER implication reduces three alternatives to one. It supplies a factor of three without a conclusion about truth or inferential correctness.

Multiplying the recorded per-definition factors gives:

`(43/9)^275 × (129/95)^54 × 3^21`

Its base-two log is 677.6117 bits. The stage's marginal-domain potential reduction is 905.0136 bits. These quantities differ because the event coordinates were already correlated, and the 54 joint-only changes are invisible to singleton counts.

The product is over the independent definition variables represented by the current implementation. Synonymous spellings, aliases and shared ancestry are not independent linguistic observations. The audit verifies component partitions, complete searches and absence of model-assertion retirement in this stage. Conflicts and search limits receive no exact count. Applying a future rule or changing the represented constraints requires counting again. This result is neither a model posterior-entropy estimate nor a measured convergence rate across learning epochs.
