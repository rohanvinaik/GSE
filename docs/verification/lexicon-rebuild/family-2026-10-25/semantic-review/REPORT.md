# Independent semantic delta review

This began as a read-only second reading of the semantic deltas after the twelve-prime checkpoint. After the two probes, root explicitly authorized the narrow CAUSE fix described in the final section. Only native_constraints.py and test_lexicon_cause_bindings.py were edited; no reference corpus, configuration or Git operation was changed. Original source hashes are in source-snapshot.json.

## Scope and evidentiary boundary

Read in full: LEXICON_BASIS_CONTRACT.md; execution REPORT.md and RULE_CONTRACTS.md; nouns.py, native_constraints.py and sources.py; the NSM English chart v20 text; founder F098 and F148; complete KNOW, DO, NOT, CAN, IF, MUST, INFER, HIER_PLUS, HIER_MINUS and CERTAINTY profile records. Inspected the source research inventory and selected source records. The 72 intended-sense definitions in the basis contract were read, but this pass did not recheck every chart-line attribution in each of the other sixty profiles against the primary books. Some broad research JSON displays exceeded the tool output limit and do not count as complete readings. The older NSM_RESOLUTIONS §1 valence controls were read; unobserved sections are not treated as reviewed.

A fresh real CLI run returned RECONSTRUCTED_PRIME_FOUNDATION: all 72 profiles reconstruct over 58 coordinates, NUMBER is not a lexical coordinate. See prime-proof.json. That is behavioral consistency with the authored boundaries; it is not an independent proof that each boundary is semantically exhaustive.

## Finding 1: unsupported outcome polarity can still establish CAUSE

Status: reproduced adversarial boundary defect; high confidence. No current corpus error is established.

Location: gse/lexicon_builder/native_constraints.py::_bound_assertions (149), caused_change_status (87), and _REFUSED_JOINS (module constant).

Probe: use the authored cause-binding fixture (Agent causes E; Patient undergoes a change), substitute contact(end(E), Patient), and set that outcome predicate's bool to '?'. _bound_assertions correctly emits UNSUPPORTED_NATIVE_POLARITY for contact. Nevertheless, the produced constraints include CAUSE +1 and DO +1. caused_change_status sees the end phase as sufficient, and the outcome is not in its refused set because that set covers only three alignment/scope cases. Full data: cause-unsupported-polarity-probe.json.

Implication: an outcome refused as uninterpretable polarity must not become the affirmative witness for a lexical causing event. The repair belongs at the shared admissibility boundary or at caused_change_status's own polarity validation, with a positive terminal-negative-change control preserved. A negative terminal state can be a legitimate change; the issue is unsupported polarity, not generic negation.

## Finding 2: generic noun contracts do not invalidate when reviewed definitions change

Status: reproduced source-revision defense gap; high confidence in observed behavior, medium confidence on whether the current pipeline promises refusal at this precise layer. No current noun misclassification is established.

Location: gse/lexicon_builder/nouns.py::NounHeadContract (22), noun_head_claim (224); sources.py::NativeSources._framenet.

Probe: load the real box.n Containers record, then change both frame_definition and the Container FE definition to contradictory human-target definitions while retaining frame/FE IDs and the rest of the source envelope. noun_head_claim still returns LOCATED_NOUN_HEAD and SOMETHING. Full original and changed results are in noun-source-revision-probe.json.

The generic contract checks IDs and nonempty definitions; it carries no expected digest of the reviewed definitions. The LU-specific claims do check exact LU definition text and return NOUN_AUTHORED_CLAIM_SOURCE_CHANGED. NativeSources records current source hashes, which make the snapshot replayable, but a fresh snapshot alone does not prove that an older authored interpretation is still valid for changed source contents.

Implication: before relying on a generic frame boundary for completeness, pin its reviewed source contract (e.g. version/content digest of the frame and target FE), or explicitly require semantic revalidation after source revision. A forged in-memory record is only a boundary probe; the normal current adapter reads the actual pinned files and was not altered here.

## Finding 3: the proposed external-Fear words are already development controls

Status: verified documentary fact; high confidence.

Location: docs/verification/lexicon-rebuild/closeout-2026-10-25/NSM_RESOLUTIONS.md §1, subsection E5 and E6 controls.

worried, alarmed, horrified, petrified and anguish are all explicitly named with sourced felt-valence answers in this development record. W1999/W1990b references supplied their treatment. They can be valuable out-of-FrameNet-Fear transfer controls. They cannot be called untouched held-out references merely because their lexical readings fall outside the Fear frame. A posthoc split of the original eight also remains retrospective.

## Modal profiles and ordinary-family implications

The selected KNOW, DO, CAN, NOT and IF profiles correctly keep chart combinations as permissions rather than inherited content. KNOW's arguments do not create SOMETHING content; CAN's possible DO/HAPPEN constructions do not add DO or HAPPEN to CAN. No rule connecting ordinary Fear DO/IF/KNOW selections follows from these prime records alone. MUST is the explicit GSE exception with CAN +1 and NOT +1 plus a separate NOT(CAN(NOT(act))) construction. It does not assert the act.

The chart explicitly calls its displayed frames some combinatorial possibilities and permits more complex combinations. Consequently its absence of a coordinate cannot independently prove prime or ordinary-family silence. The authored boundary approach is accurately described in the current basis contract. For an ordinary family, fixed/optional/outside-family-scope decisions need their own explicit convention or sourced conditional contract; do not inherit a prime's boundary.

INFER and CERTAINTY do not imply KNOW/TRUE. HIER_PLUS and HIER_MINUS remain separate unpaired direction coordinates; their bound scale base is structural metadata and is not automatically written into the vector. These are clearly labelled authored GSE adaptations. This pass finds no contradiction between those selected records and their current written basis definitions. It does not turn them into NSM inventory claims.

## Noun and CAUSE semantic scope

The reviewed noun code keeps ordinary nouns outside the prime one-hot rule, writes target head plus KIND 0, and preserves unknown noun targets as unresolved. BODY/PART/whole bindings stay distinct. Located LU-specific definitions distinguish whole body, collective people and leadership head. These are explicit authored GSE projections, not universal consequences of noun POS. Frame/FE identity alone should not be advertised as a complete ordinary definition.

The tightened CAUSE contract deliberately requires a lexical outcome in another affected role and blocks typed reflexives, body-part ownership ambiguity, generic Pred placeholders, refused emotional joins and unrelated subevents. The authored tests demonstrate those named classes. There is no universal token-level distinctness theorem: declared source roles and the specified censors define the executable scope. Additional unencoded co-reference cases remain a source/contract limitation rather than evidence that the source proves arbitrary participants distinct.

The adapter still aggregates several supports into frame-coordinate laws. RULE_CONTRACTS.md correctly states that exceptions are not yet predicate-specific there. A family disagreement workflow must preserve the individual supports before retracting one source event while keeping another.

## NUMBER: operational agreement with a terminology tension

F098 explicitly says NUMBER has no intrinsic content or literal exponent in any bank and preserves every bank's presence/absence and sign. F148 calls it both a special meta-prime and, in the Roman V aside, a new 73rd prime. It also uses the 72-to-58 signed basis in the same prompt.

The current implementation's 72 lexical names / 58 signed coordinates plus separate scale operation is compatible with those explicit operations. Treating the 73rd label as a computational/meta-level entry is a reading, not a new founder quotation or proof that the words never conflict. Record both descriptions and the invariant; the wording alone supplies no warrant for a new lexical coordinate or for sign/mask changes. Confidence: high on the operational invariants, interpretive on the terminology reconciliation.

## Review disposition

The selected foundation/adaptation definitions support proceeding with a narrowly certified ordinary-family experiment. This is not a blanket independent semantic sign-off on all sixty additional profile attributions. Correct the reproduced CAUSE malformed-polarity path before claiming adversarial closure. The noun source-revision defense can be addressed in its shared contract, and its absence must remain explicit if deferred. Preserve the development/held-out distinction before freezing evaluation.

## Authorized narrow CAUSE repair

Root authorized implementing Finding 1 only. caused_change_status now refuses unsupported bool values on the cause itself and on any otherwise qualifying outcome. Because the support eligibility check lives inside this shared helper, direct callers and _bound_assertions/frame_constraints cannot use that unsupported outcome. Existing valid positive and negative terminal-state outcomes still establish the causing event. No change was made to bank_laws.json, noun contracts, generated tests or certificates.

Authored tests cover unsupported cause/outcome polarity directly, and frame_constraints verifies that refused outcome evidence writes neither CAUSE nor its DO companion while preserving positive and negative terminal-state controls. Commands run successfully:

- `.venv/bin/python -m pytest tests/test_lexicon_cause_bindings.py tests/test_lexicon_native_constraints.py`: 20 passed, one existing Hypothesis collection warning. Includes the actual source-backed build test for kill/wink/walk/say/tell.
- `.venv/bin/ruff check gse/lexicon_builder/native_constraints.py tests/test_lexicon_cause_bindings.py`: all checks passed.
- `.venv/bin/ruff format --check gse/lexicon_builder/native_constraints.py tests/test_lexicon_cause_bindings.py`: both files formatted.
- `uvx ty check gse/lexicon_builder/native_constraints.py`: all checks passed.

The pinned VerbNet XML inventory contains 2,946 origin predicates without bool and 207 with bool `!`, with zero unsupported symbols. The source hashes are compared against the prior full-build manifest in verbnet-polarity-inventory.json. This repair closes an adversarial/future-source boundary defect; it is not a claim that current corpus readings had changed polarity. Finding 2 remains recorded only and unmodified. No commit was created; root owns integration and the full repository gate.
