# Source-backed symbolic construction and publication

This is the engineering contract for GSE-01, issue #168. The lexical design authority is
`docs/program/LEXICON_CONSTRUCTION_DESIGN.md` and Rohan's current instructions, followed by the
founder record it cites. This change began with the checkpoint documented in
`docs/verification/lexicon-rebuild/foundation-2026-10-25/REPORT.md`; that dated receipt is not the
current full-build result. Work now lives on main, without a feature branch or worktree.

The current acceptance index is planned at
`docs/verification/lexicon-rebuild/execution-2026-10-25/REPORT.md`. Its computed JSON, test, Detective,
replay, corpus and publication receipts determine acceptance. Their generation/verification remains
pending until the actual receipts exist; this document supplies no measured result counts.

## Protected representation

- The versioned basis has 72 lexical names, 14 signed alias pairs and 58 canonical coordinates.
  NUMBER is a separate sign/mask-preserving scale operation, not another lexical coordinate.
- Each located reading retains its own POS/source/sense, event and participant bindings. World
  affect, norms, associations and participant properties do not become target lexical content.
- Signed values, written zero, explicit silence, unresolved domains and conflict remain distinct in
  construction, JSONL, SQLite and the real consumer. A source-scoped collision remains quarantined
  even when its global coordinate domains are nonempty.
- Ordinary builds instantiate no model. Gold is evaluation-only. Neither the association catalog,
  a model answer nor the builder's own vector can validate a lexical rule or an exception.

## Shared construction graph

`NativeSources -> family ReadingSeed -> construct_reading/core.resolve -> sparse/structural artifacts
-> independent audit -> runtime.build_release -> lexical_evidence.lookup_lexeme`.

Profiles, adjective contracts, verb event/role projections and located noun heads use that same
constructor. The batch runs it over a declared source-union or explicit worklist and records every
input's outcome. A full sweep does not claim complete semantic coverage of every sense.

| Module | Ownership and boundary |
|---|---|
| `basis.py`, `foundation.json`/`foundation.py` | Fixed basis and authored whole-profile decisions; typed claims, reference/construction data, examined boundary and reconstruction. |
| `sources.py` | Pinned native records; FrameNet LU types/incorporation/DEN/frame elements; VerbNet origin frames, syntax and inherited restrictions. No prime projection. |
| `registry.py`, `bank_laws.json`, `core.py` | Validated rule admission, guarded relations, exact joint support, rooted attribution, conflicts and application-level retraction. |
| `nouns.py`, `native_constraints.py`, `build.py` | Own-target/source-bound applications, preserved native alternatives and shared construction orchestration. |
| `conditionals.py` | Native association diagnostics at word-alternative-union scope. It never writes lexical cells or admits a linked rule. |
| `reading.py`, `tail.py`, `model.py` | Recompute after every selection; exact source/domain-bound tasks, legal zero, abstention, call budget and task dispositions. |
| `artifact.py`, `runtime.py` | Validate and preserve the complete sparse state contract; deterministic atomic publication; audit-only conflicts. |
| `surprise.py`, `release_audit.py` | Evaluation-only published-explication ledger and independently reported corpus/evidence/completion coverage. |

## Prime reconstruction and proof

An examined authored definition partitions all 58 coordinates. Source claims and shared rules rebuild
its content and explicit absence; only the authored boundary compiles directly into scoped silence
laws. Draft boundaries, if present, close nothing. A permitted combination is not content. Ordinary
homographs never identify the prime lexical unit or inherit its boundary.

A cited relation must actually force each attributed decision. The rooted check existentially erases
the target columns from every active relation and asks the joint solver whether independently
supported outside assignments permit a wrong value. Equality cycles cannot prove themselves.
Unknown/inactive/noncovering/permissive/unrooted support, background conflict and solver limits have
separate named outcomes. Ablations remove their premises and reopen only unsupported consequences;
redundant independent support survives.

Prime-only one-hot and authored non-substantive head conventions remain scoped. Ordinary nouns do
not receive the other seven prime-head zeros. Reviewed target contracts can establish SOMETHING,
SOMEONE, PEOPLE, BODY, PART or KIND under their own sourced guards. Part targets keep the whole or
possessor in the relation; generic physical typing never supplies SOMETHING. Containers' Part/Type/
Contents and clothing's body location are arguments. Whole-body, collective-body, leadership and
anatomical readings remain separate. Unknown noun contracts remain explicit unresolved LU readings.

## Rule admission, diagnostics and correction

Authority, tier, lifecycle and validation are separate. Current validated registry records require
source references, a warrant, positive/MUST-NOT test node IDs and a receipt matching the exact rule
contract digest. The gate runs those tests. Legacy founder approval is restricted to recorded exact
digests; no new approval is created by a label. Withheld rules write no cells or enabling premises.
Reviewed source projectors retain their own tested code/application contracts and recipe hashes.

The association catalog preserves each candidate and its disposition, native evidence and lineage.
Corroborated, contradicted, missing, unavailable, retired and unsupported cases remain diagnostics.
A link to an independently admitted conditional lexical rule does not itself admit or apply it.

An exception names one reading/rule/application and independent evidence. Foundational, ambiguous,
duplicate, inapplicable or builder/model-derived corrections are refused by name. Resolution starts
again without that conditional application, preserving unrelated applications and independent support.
This local retraction neither demotes nor confirms a global rule. Marginal-resolution analysis and
source-backed guard refinement remain separate from raw association frequency.

CAUSE requires a bound lexical outcome in another participant. Generic agentive cause on speech,
construction-result placeholders, reflexive targets and unconfirmed body-part identities do not
supply that outcome. The rejected native predicate remains in the derivation, with its named reason.
BECAUSE remains distinct and does not acquire CAUSE merely from its connective meaning.

## Tail and gold isolation

Only projector-nominated unresolved coordinates with established source IDs can become automatic
`plan-tail` tasks. Explicit queues bind to the exact current domain, including surviving zero; an
emotion-specific constraint removes zero only within that emotion domain. Each selection is checked,
added as a MODEL_CANDIDATE constraint and propagated before another decision. Abstention, stale task,
already-resolved, symbolic-only, backend failure and budget exhaustion are separate ledger outcomes.
Legacy library fill/bank-review routes remain opt-in diagnostics and cannot certify silent closure.

Gold values never decide tasks, options, payloads or construction cells. Independent comparison
reports both additions and omissions, wrong poles, zero/silence disagreement, unresolved cells and
conflict. Explication absence does not establish lexical silence. DeepNSM remains silver evaluation
material rather than shipped construction content.

## Release and acceptance boundary

The JSONL artifacts retain every reading, construction home, domain and provenance record. Only
fully settled exportable candidates enter `vectors.jsonl`; a head-only partial reading is not complete.
SQLite publication stages and validates an artifact, rechecks input hashes and atomically replaces
the destination. Full payloads, structures, symbolic statuses and digests remain authoritative.
Compatibility rows expose settled written cells, including zero, while missing rows cannot distinguish
unknown from silence. `lexical_evidence.lookup_lexeme` validates and returns the full definition;
deterministic row choice is not sense resolution. Conflicts cannot supply selectable components.

The corpus audit streams the complete sparse artifact and measures Brown by native genre and
Gutenberg by text using local pinned files. Vocabulary/homing, signed evidence, head zeros, other
zeros and coordinate completion get separate token-mass thresholds and OOV ledgers. Conflicted
readings retain diagnostics but supply no evidence/completeness coverage. A 90% homing result does
not certify semantic completion or production readiness.

Known residuals include unsupported native predicates and nominal targets, unresolved alignment,
abstract/time/place/untyped collective heads, construction basis gaps, uncovered source families,
unhandled alternatives and scale calibration. Pending acceptance work is receipt generation,
frozen replay review, the declared sweep, independent corpus/reference audit, actual runtime checks,
Detective and repository gates, then scoped publication/commit. Historical reports stay unchanged.
