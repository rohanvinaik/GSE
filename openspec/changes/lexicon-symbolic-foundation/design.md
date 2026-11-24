# Engineering the existing lexicon path as one system

This bounded change implements GSE-01. Lexical authority and the dependency-ordered CP-01–CP-08
contract live in `docs/program/LEXICON_CONSTRUCTION_DESIGN.md` under “Engineering execution:
one checkpoint and a continuing learner”. Do not maintain an alternate acceptance plan here.

## Ownership and composition

| Responsibility | Existing owner / seam | Required consumer |
|---|---|---|
| Definition identity and source competence | `GSE/curation/lexicon_builder/evidence.py`, `definition_frames.py`, `wordnet_identity.py`, native adapters | Shared resolver context and exact reading eligibility |
| Joint legal state | `engine.py`, `resolution.py` | Teaching, forecasts, migration, replay and runtime domains |
| Discovery | `discovery.py`, `grounded_rules.py`, reviewed export and `epoch.mine_scope_chains` | Persistent candidate work ledger in the next cycle |
| Teaching and audit | `completion.py`, `residual.py`, `model_protocol.py`, `reviewed_patterns.py` | Reclosed exact decisions; independent admission evidence |
| Exception learning | Existing refinement command, `rule_revisions.py`, `rule_reservations.py` | Revised candidate, fresh boundary audit and joint migration |
| Revision and history | `rule_admission.py`, `rule_migration.py`, `rule_history.py` | Replayed working head and invalidation of dependent queued work |
| Scheduling | `epoch.py` and existing durable completion scheduling | Informative next question using current legal alternatives and candidate interactions |
| Measurement | `specification.py`, epoch phase reports | Equal-budget comparison, checkpoint gate and experiment notebook |
| Publication and consumption | `publication.py`, `lexicon_resource.py`, `GSEEncoder`, `publish_round` | One installed sparse successor and the next learning baseline |

Paths without a prefix in the table are within `GSE/curation/lexicon_builder/`. Split controller
responsibilities into focused modules there if needed; do not create a parallel construction stack.

## Representation boundary

The production basis is 56 ordinary lexical banks. Hierarchy and NUMBER remain separately scoped
metadata. The upstream constructor uses 58 coordinates and authored silence. Adapt only mechanisms
whose contracts match, with representation/mask/provenance tests. No prime-only one-hot import,
blanket remaining silence, silence-to-zero conversion or spelling-based definition identity is
permitted. The original sources and model request identities survive namespace normalization.

## Persistent control state

Version the new controller schema rather than silently changing fixed version-1 plans. Keep
historical replay and exact journals. The current working store owns the canonical run/head,
candidate mechanisms, typed surprise work and resumable tasks; compact reports are projections
of that state. Record basis/cohort/source/rule/curriculum/model versions, candidate warrants,
lineage-separated witnesses, audit outcomes, dependencies and next actions. Version candidate
contracts and invalidate only work whose dependencies changed.

A candidate can await evidence, warrant, audit or refinement; be challenged, reserved, rejected,
already entailed, admitted or retired; or be operationally unavailable. Distinct dispositions
receive distinct remedies. A visited bit cannot permanently hide a reopened question. Concurrent
writers, changed inputs or incomplete transitions receive a named refusal, not silent resumption.

The canonical design defines the learning-head, candidate-mechanism, surprise-work, next-work
and transition records and their consumers. Distinguish the published baseline from an unpublished
working head and preserve its migration lineage. The present active-baseline publication check
must be reconciled with this protocol; relabelling the current foundation candidate as active is
not an admissible shortcut.

## One cycle

1. Verify the working head and close admitted constraints using the existing resolver.
2. Measure legal joint space and regenerate eligible evidence/curriculum strata.
3. Consume discoveries and unresolved challenges, including newly grounded source-only candidates.
4. Stage candidate relations individually and together, preserving complementarity and limits.
5. Select a useful unresolved teaching or audit question from its legal alternatives and record it.
6. Validate the typed answer and closure; retain independent evidence and exact surprises.
7. Derive a warranted refinement or revision; independently audit the changed claim and boundary.
8. Apply reviewed additions, retirements, exceptions and reservations atomically; replay the full cohort.
9. Update the head, phase measurements and next work. Repeat or pin the passed checkpoint.

Each accepted residual answer can restart broad discovery. A rule already entailed by the admitted
closure is a shortcut, not newly acquired semantic information. A new candidate cannot approve
itself, supply its audit target, or become a premise before admission. Typed model calls remain
bounded word–bank rulings, not free-form rule authorship or whole-vector completion.

The generator's initial templates may be finite, but useful discoveries are no longer confined to
opening families. Extend tuple and guard vocabulary through the shared Relation/native-context
contracts with explicit warrants and tests. A bounded or exhausted search is reported relative to
that language, never as proof that no further symbolic structure exists.

## Refinement and retained plurality

Independent counterexamples retain the exact reading, context, conflicting values/combinations and
parent proof. Route wrong identity to existing grounding, unsupported projection to its adapter,
missing conditions to reviewed guard refinement, and genuine exceptions/reservations to the joint
revision path. A model disagreement alone is not the correction's authority. Do not suppress a
lawful alternative to make the rule pass. Unknown guards activate nothing. Review a semantic
boundary only when sources and the approved contract cannot settle it.

## Measurement and budgets

Use the exact joint H from `specification.py` with complete-count coverage, plus separate marginal
potential, filled/explicit-zero/unresolved/reopened counts and the pinned frequency buckets. Save
baseline, direct-teaching and post-revision results. Counterfactual replay distinguishes propagated
teaching effects from newly admitted rules and avoids double-counted overlaps. `compare` must
consume those measurements; it cannot retain a singleton-only success predicate.

Equal-budget arms share frozen initial evidence/cohort, discovery language, model/protocol and
accounting policy, while their learned trajectories may differ. Report actual teaching, audit,
review and execution costs separately. Unequal actual budgets or unavailable counts leave the
comparison incomplete. Exponential bulk learning is an observed H/amplification trajectory under
its stated conditions, not a conclusion from one large forecast or a log-count identity.

## Bounded storage and recovery

Keep the active release, its single rolling predecessor and one working head. Permit bounded
owned staging files during an atomic transition. Compact evidence/rule/model/transition records
must reproduce historical decisions without retaining every teaching.db/candidate.db. Resume
must validate event/head identities rather than require deleted intermediate database paths.
Protect source data, audit records and other sessions' files. Test interruption at each boundary
before enabling retention. Use the existing publication and retention mechanisms, not another
release tree or pointer.

## Checkpoint boundary

Freeze the workload manifest described in the canonical design: source/frequency/corpus pins,
90% eligible token-mass cohort in both sources, promised NLP operations and required banks,
independent two-sided labels, development/final split, explicit critical outcomes, and whole-build
replay/gates. Frequency is importance; current marginal coverage is leverage. Keep all senses and
all tail definitions in the dictionary accounting.

A final audit used to guide a correction becomes development evidence. A critical unresolved or
wrong result blocks its promised operation. Finite sparse-runtime probes do not establish general
usability. Repair closed-class contextual eligibility, including he/He, through the real encoder.
A passing sparse checkpoint preserves its unknowns and states its workload limitations. Continue
from that installed release using this same controller; whole-lexicon completion remains separate.

## Verification and current blockers

### Checkpoint-first execution update — 2026-11-24

The direct owner deadline defers generic controller completeness until after the
usable checkpoint; it does not defer its validity gates. Controller-owned code
now has exact request-context archival, a durable head CAS, owned-stage retirement
with native/unique-audit preservation, explicit model-prefix review, a reviewed
joint-revision intake and bounded explicit entry–bank work on the sustained
writer. Its 1,800-test scoped pass includes crash recovery after obsolete files
are removed and the actual Regenesis refinement integration. It is not the
integrated gate, a real linguistic admission, or a full CP-02–CP-06 receipt.

The catalogue repair and subsequent full replay are already recorded as valid;
the older failed catalogue/fixture observations below remain historical. The
active pointer still names 021. The v2 rebase preserves the original v1 plan and
water/I wire identity. Fresh reference audits are being supplied by the root's
pinned local transport; ordinary admission, full-corpus joint revision/replay,
usable-workload acceptance and the runtime peer's repaired code-freeze receipt
remain prerequisites to activation. Generic joint-tuple discovery and complete
source/identity/projector surprise correction remain deferred, not declared done.

Use the scenario requirements and checklist, then real corpus execution and full replay. CP-01
currently includes the failed catalogue refresh and reference-bank fixture failures. CP-02–CP-06
cover the controller feedback, comparison and retention gaps. CP-07 includes the reproduced wrong
pronoun selection in the chemical-symbol sentence. None is closed by this design edit.

Original upstream foundation, ordinary-family, native-role and independently rooted provenance
controls remain reusable regression obligations. Their historical counts or authored boundaries
are not evidence that the production current-basis checkpoint passes. Detective is explicitly
deferred; retain that status rather than claiming the prescribed mutation gate ran.
