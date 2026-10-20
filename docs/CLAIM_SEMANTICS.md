# Shared claim semantics, version 1

`gse.symbolic.propositions.propositions` is the extraction authority. The
atomic decisions in `gse.symbolic.claims` consume its `Proposition.node` and
ordered `Scope` records; they do not parse a second tree. The decisions are
also re-exported from `gse.symbolic.propositions`.

## Commitment and signs

`commitment(proposition)` returns `committed`, `non_committed`, `abstained`,
`in_question`, or `unresolved`. `commitment_modes` is its flat scope decision.
The entire ordered scope sequence participates. Possibility, obligation,
belief, conditions and irrealis block categorical admission. A denied
knowing/believing abstains on its content. Unnegated knowing/realizing commits
its complement under the existing knowability ruling.

`Proposition.status` remains the historical lossy outermost-scope projection.
In particular, both a possible negative and a committed negative can have
`status == "negated"`; consumers must use `commitment` instead. Negation over
a compound proposition is not distributed into separate negative facts.

`polarity` returns a `Polarity` record with `state`, `clause_sign`,
`lexical_sign`, composed `sign`, normalized type `base`, and `reason`.
Syntactic NOT and verified adjective-prefix negation multiply. A lexical
primitive such as `GOOD=-1` does not itself denote a denied clause. Reversal
is distinct from negation and does not flip a clause sign. Unavailable or
unresolved morphology produces an unresolved result, rather than a guessed
prefix operation.

`propositions(tree, source_text=original_utterance)` retains a terminal source
question mark even when the tree has no question node. Independent source
interrogative evidence can be supplied with `interrogative=True`. Query nodes
also carry question scope. An unevidenced declarative tree alone cannot tell
whether its original source was a question.

## Comparison and identity boundary

`identity(operand, namespace=None)` returns a resolved referent key, an
explicit unresolved local candidate, or an unsupported result. A lemma and
token position do not certify identity. Supply the resolution document as
`namespace` when comparing across resolution domains; a bare entity ID is
only meaningful in the caller's existing resolution domain.

`claim_key(proposition, relation_primitives=None, namespace=None)` returns a
`ClaimKey` record. Successful `key` values are tagged `gse.claim/1` tuples;
polarity is carried separately in the returned record. The key's projection
is `resolved_roles_signed_primitives_context/1`:

- Events retain signed primitive values and ordered resolved agent, patient
  and every represented theme slot. The selected lexical record's primitive
  map, or a callable returning that map for the verb, must be supplied.
- Type assertions retain resolved entity identity and verified normalized
  base-kind wording. Generic `thing/something/someone/entity/kind` is refused.
- Comparisons retain axis, direction and ordered operands. A unique
  represented modifier can supply an absent stored axis; competing axes are
  unresolved.
- Ordered non-negation scopes retain their owner/context. Temporal context
  and explicit modal qualifiers do not equal missing qualifiers. The modal
  owner's own wording is not duplicated into the key's primitive projection.

Empty or generic event decompositions, unknown/malformed primitive evidence,
unresolved argument/context identities and unsupported predicate kinds never
produce a certified key. A failed lexical callback returns `unread` with a
named reason. Equal supported keys establish equality at this projection,
not complete worldly or pragmatic meaning equivalence. Original wording and
the complete predicate remain on the `Proposition` beside the result.

## Bounded inference and consumers

`KnowledgeBase.from_trees` consumes this shared authority. Its optional
`source_texts` and `source_ids` must align one-to-one with trees; mismatches
raise `ValueError`. `admissions` records every predicate's named admission or
withholding decision. Positive and negative events, types and comparisons
are kept apart; negative facts never become positive premises.

For located multi-proposition trees, pass `source_claim_ids` as one sequence
per tree, aligned with **every** result from the shared `propositions`
extractor, including structural containers and scoped children. Each ID must
be a nonempty string. A coordination's second atomic premise then keeps its
own claim ID instead of inheriting the coordination container's ID. Exact
lookup and bounded derivations return those actual admitted premise IDs.
Without this optional mapping, the original per-tree source ID behavior is
retained.

The existing `event`, `is_a` and `greater` queries retain their documented
lexical type/order/single-antecedent projection for compatibility. They are
not referent-aware equivalence or contradiction certificates. Temporal
clauses remain asserted under this existing projection. Secondary event
arguments cannot be silently dropped into this interface. The exact
`claim(Proposition)` query instead uses certified resolved keys and the
supplied relation evidence; it returns a named `entailed`, `not_entailed`,
`unresolved`, `unsupported`, or `unread` result. It first looks up admitted
signed claims. A positive context-free query can additionally use the existing
bounded fragment when each referent has a unique, resolved alias in the prior
trees; same-lemma identity collisions and unresolved aliases cannot supply
that bridge. Secondary roles and qualified contexts cannot be dropped to make
a rule fire. Negative closure beyond exact signed lookup remains unsupported;
no negative-as-failure or new referent-aware rule system is introduced.

Rules require a whole single Event/TypeAssertion/Comparison antecedent and
a whole single Event consequent, with supported positive scope and arguments.
Compound arms, nested rules, modal/negative arms and secondary argument roles
are withheld. Supported rules still derive through the existing type/order
closure and retain actual source IDs together with their rule/premise chain.
No negation-as-failure, general quantifier logic or conjunctive antecedent
reasoning is added.

The narrative spine uses the shared committed projection. Conditional,
possible, required and abstained content remains available in the complete
reading but does not become a categorical event edge. Its serialization
compaction key is explicitly an emitted-structure projection: it preserves
ordered argument slots, nested NOT, themes and modal/context features, and
does not independently decide truth.

`emit_contract(..., include_semantics=True)` adds a `gse.claim-semantics/1`
sidecar containing these same decisions. The default Genesis-facing gold
payload remains unchanged. Pass source text and selected relation evidence
when those channels are available.

The proof packet's contradiction, reduction and fingerprint demonstrations
resolve each complete demonstration document before comparing shared keys.
They now print versioned resolved keys and explicitly abstain on unsupported
readings. The former private modal/prefix walker and primitive-only reduction
keys have been removed. These transcript changes are deliberate; the
demonstrations certify only their supported projection.
