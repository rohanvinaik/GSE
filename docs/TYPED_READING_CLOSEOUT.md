# Typed reading closeout review

This records the delivered boundary of `preserve-typed-prose-readings` and the
linked SquishOS `restore-voice-profile` implementation. The accepted proposal and
source manifest retain the original evidence; this document maps the resulting
behavior to its consumers. It does not certify arbitrary English understanding.

## Producer to consumer closure

| Producer and invariant | Production consumers | Executable review |
|---|---|---|
| Native lexical/morphological decisions preserve an actual lexical row; recognized negation is separate from admission of decomposition | Encoder token evidence, spelling core, shared claim polarity | `test_negation_admission.py`, `test_lexical_healing_contract.py`, `test_negation.py` |
| Clause core survives operator composition; phrase and clause tiers remain distinct; head linkers retain an open left relation | Evaluated trees, proposition extraction, grounding/fold/graph walkers, voice structure | `test_operator_core_preservation.py`, `test_head_linker_decision.py`, `test_symbolic_walker_parity.py` |
| Commitment, composed polarity, scopes and supported identity keys are separate decisions | KB premise/rule admission, narrative projection, optional emit sidecar, proof demonstrations, SquishOS passage evidence | `test_claim_semantics.py`, `test_kb_assertion_modality.py`, `test_sign_evidence.py` |
| One source manifest and one outcome per expected utterance; failed phases retain independent states | Legacy success-only wrappers, `MultiScaleDoc`, feature profiles, SquishOS probe | `test_complete_document_reading.py`, `test_discourse_speech.py` |
| Person eligibility has person/non-person/unknown outcomes | Coreference, entity and relational cassettes | `test_complete_document_reading.py` |
| Source-specific lexical, rank and raw-rating availability; structural EPA remains distinct | Healing rarity guard, word adapter, metric rows and their denominators | `test_lexical_healing_contract.py`, `test_rarity_evidence.py`, `test_healing_resource_provenance.py` |
| Typed dictionary protection and source-preserving healing use one core | MCP, REPL, standalone SquishOS spelling, default voice prepass | `test_lexical_healing_contract.py`, SquishOS `test_reading_probe_contract.py` |
| Complete source/word/utterance/claim/document joins and strict event decisions | SquishOS `read`, per-unit profiles, references and trades | SquishOS source, event, probe, metric and command tests |

The symbol/reference audit checked existing callers and duplicate paths before
edits. The retired profiler's bounded AST consumer inventory and migration
manifest are retained with the external application artifacts. The separate
register-router `.fit` calls belong to their own estimator receivers and were
left unchanged.

## Public changes and preserved projections

`gse.symbolic` exports shared claims and `negation_signs`; `gse.structure` exposes
operation counts, clause depth, verb-head and structural-loss evidence.
`encode_document_utterance_events` is the loss-preserving intake; older wrappers
remain explicitly success-only. `text_profile` has versioned failure accounting;
the fixed legacy classifier vector is an explicit projection.

`KnowledgeBase` keeps its legacy lexical query projection distinct from supported
resolved-claim queries. Modal, belief, question and unsupported generic claims do
not become committed positive premises. Supported rule receipts retain actual
atomic source-claim IDs. Default Genesis serialization is unchanged; callers opt
into the shared semantic sidecar.

SquishOS owns exact UTF-8 source reduction, line/paragraph/section/sentence
coordinates, bounded transport and strict runtime payload validation. Its probe
calls public GSE decisions under GSE's own interpreter. It streams successful
outcomes before document work, then joins final resolved evidence by identity.
Initial provenance survives interruption; final provenance follows document
analysis. Producer changes during a read are named rather than silently relabeled.

The metric registry contains independent rows with definitions, populations,
failures, support and located evidence. Line views include complete owned
sentences only, retaining crossing sentences as outside context. References keep
whole-source and whole-sentence pieces. Calibration requires declared disjoint
source groups and sufficient finite-sample support; descriptive references remain
`no_band`. Trades preserve original and draft observations when compatibility
cannot be certified, withholding incompatible arithmetic and placement.

## Consumer migration

The former `scripts/voice_profile.py` emits a named retirement record and its
Python API raises `RetiredProfileError`. The current commands live in SquishOS
`tools/voice/voice.py`: `identify`, `read`, `reference`, `compare`, `recognize` and
`corpus`. Default reading uses the shared healing core; `--raw` records a bypass.

RohanVoice v2 is an optional, independently versioned consumer. Fitting requires
explicit source hashes, labels, source groups, selection evidence and training /
holdout partitions. It uses no dense-cosine path or default private-corpus scan.
Missing or stale artifacts request a refit; per-class heldout identified, wrong
and abstained counts remain separate. The corpus selector reviews uncertain
sources before opening them and never fits automatically.

Paper callers and the global voice-profiler skill migrate to the same declared
SquishOS/GSE checkouts. Legacy in-memory rows and reference caches receive named
migration guidance. Historical accepted passages and their writing contract are
preserved. No private source text belongs in tracked verification artifacts.

## Verification and limits

Run `scripts/ci_local.sh` for GSE's blocking Ruff/format/test gate and advisory
type output. Use SquishOS's own locked Python environment for its tests, with
`GSE_REPO` explicitly naming the integration checkout. Local socket tests require
permission to bind their loopback sockets. OpenSpec validation checks package
structure separately from implementation acceptance.

Detective reports, generated tests and certificates identify their actual target
and source bytes. A timed-out run is non-gateable. Crash-only value gaps, unresolved
survivors and CrossHair `Not confirmed` results are not proofs. Full-project
advisory findings remain distinct from the scoped repair's intent tests.

The retained-source acceptance receipts preserve source/code/resource hashes,
complete located readings and ordered controls under ignored `data/voice`.
Unsupported/generic or unresolved keys remain open. The control passages examine
contradictions, argument swaps, modal contexts, synonymous refrains and strictly
earlier premises. They establish those represented relations; the writer still
judges whether a passage communicates its intended point.

No new theory authority is inferred: `CLAUDE.md`'s invalid-THEORY statement and
the document's reconciled label remain an explicit unresolved source conflict.
Remaining research probes retain their named expected failures. Resource
acquisition, a private recognizer refit and global agent-setup reconciliation are
separate prerequisites, rather than fabricated completed work.

## Application and evidence ledger

The guarded implementation application and installed entry-point checks are recorded in [the verification snapshots](verification/typed-reading-2026-10-20/README.md). They include the paper bridge's exact parsed-record equality, real MCP stdio parity, source-preserving separate-output healing, explicit temporary-store learning, reference compatibility, canonical expansion and complete-path profiling. Private retained texts and rebuilt references remain ignored in SquishOS; existing files have application backups.

The initial mutation inventory remains an initial snapshot. Expanded Detective walks found module-load refusals, a prescribed two-sign flag command that rejected its own reported mutant ID, and deadline-limited or incomplete assessments. Their exact artifact hashes and stopped-run states are recorded in `verification/typed-reading-2026-10-20/final-detective-limits.json`. A refusal is not a purity result, and a partial run is not a certificate. The user directed “Record limits and finish project”; these limits are accepted closeout exceptions, with ordinary intent tests retained. No full-project mutation certificate, LintGate pass or CrossHair proof is claimed. Detective repair is outside this implementation; reproducible tool failures are filed separately.

The full SquishOS JUnit receipt retains a setup-record failure: `read-whole.py` exists but is absent from the canonical hook record and both live client hook sections. Existing setup sync renders files and links; it does not wire hook JSON. Global setup reconciliation is separate from the voice implementation.

The canonical SymbolicSpellCheck interpreter was corrected and client configurations synchronized. That canonical sync also reconciled eight pre-existing Claude Desktop server registrations (ColabMCP, Genesis, Hamilton, Mneme, Regenesis, ShortcutForge, SparseWiki and Wayfinder); non-MCP settings were preserved and existing client configurations were backed up by the sync process. A subsequent sync dry-run reported every client unchanged. A fresh real MCP process matches the core's entire record. The existing session connection was left running because the user cannot reconnect it during this run; that connection still needs a later reconnect.

The final provenance regression reproduced stale compatibility after changes to imported calibration code and package initializers. The applied fix hashes those four dependencies as well as the original nine consumer files; four direct regression cases now require `rebuild_required/code_mismatch`. Derived Profiles and references are reprojected from immutable saved Readings under the current consumer identity. Earlier CLI, storage and performance receipts retain their historical measured identities.

Closeout receipt: `verification/typed-reading-2026-10-20/final-closeout.json`. Final SquishOS checks passed 2,601 tests with the single existing global hook-record failure; all 176 focused command/metric/dependency tests passed. The installed raw, healed and two-reference comparison commands completed with current 13-file identities and strict schemas. Both changes were archived on October 20, 2026; all ten promoted specs pass strict validation. Detective issues [#128](https://github.com/rohanvinaik/Detective/issues/128) and [#129](https://github.com/rohanvinaik/Detective/issues/129) retain the reproducible failures. This closeout snapshot predates the separately requested Git commit and push.
