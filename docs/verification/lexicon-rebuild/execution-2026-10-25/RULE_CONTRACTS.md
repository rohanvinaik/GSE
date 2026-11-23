# Rule admission, rooted provenance and native diagnostics

This record covers the rule/provenance implementation in the shared main checkout. It does not certify the entire repository or the release artifact.

## Contracts

`core.rule_admission_reason` reports a named reason. `law_admission_status` remains the compatibility admission verdict. `registry.admission_report` exposes the same policy used by `split_by_admission`, across all four cell-writing rule families.

Seventeen historical approvals retain the frozen contracts in [legacy-approval-contracts.json](legacy-approval-contracts.json). Editing one of those records requires v2 validation. An arbitrary `FOUNDER_APPROVED` stamp cannot create a historical approval.

The thirteen migrated records have an ACTIVE lifecycle, a sourced authority, a warrant, and a validation receipt naming positive and must-not pytest nodes. `rule_contract_digest` hashes every record field except `validation` itself. Guard, relation, authority, lifecycle or other metadata changes invalidate that receipt. `NATIVE_ASSOCIATION` and explicitly nonlexical records remain inadmissible regardless of their stamps. Empirical mechanisms must be conditional. The release gate executes the referenced tests; the receipt is not inferred from the builder's answers.

[rule-admission.json](rule-admission.json) is the computed admission snapshot. The unsupported happiness/sadness prototype remains withheld.

## Reconstruction proof

`foundation.decision_check` preserves its six-argument interface. A cited law must be active, cover the decision, and force its value. The rooted check then existentially erases the decision's target columns independently from every active relation before solving the outside premises. A target cannot travel around a cycle and return as its own independent support. Redundant independent roots remain usable.

`CITED_LAW_NOT_ROOTED`, `PROVENANCE_BACKGROUND_CONFLICT` and `PROVENANCE_SOLVER_LIMIT` distinguish the residuals. A solver limit never supplies a proof. This is a deliberately conservative proof policy: it may refuse attribution that would require the removed target correlations. Reconstruction records declare `INDEPENDENT_TARGET_ERASURE_V1`. Ablation uses the actually retained claims/laws and removes withheld claim IDs from the premises.

## Local corrections

`Law.application_id` and `RuleException.application_id` are optional explicit application identities. `law_application_id(law)` supplies a stable relation-contract identity otherwise. Retraction is exact for reading, rule and application. A correction omitting the application identity is refused when multiple distinct applications match. The resolver starts over from retained support, preserving independent warrants and reopening downstream cells.

`Resolution.to_json` emits `rule_applications` with each retained rule ID, application ID, tier and coordinate scope. The real CLI witness uses those emitted IDs to retract FEEL while preserving KNOW from another application of the same rule, and refuses an ID that was not emitted. Callers need not reconstruct the hash implementation.

`RuleExceptionError.code` distinguishes malformed, nonindependent, inapplicable, ambiguous, duplicate and foundational-rule corrections. Model/builder-derived kinds and known derived origins are refused even if labelled `SOURCE_RECORD`. Source adapters are still responsible for authenticating the independent source record; arbitrary source strings are not cryptographic evidence. No correction confirms or globally promotes a law.

The native adapter's retraction granularity is a coordinate projection of a located frame, not an individual source predicate. An adapter that aggregates several event/binding supports into one relation must preserve those application supports separately before offering event-specific retraction. The core cannot recover supports an adapter has discarded. No adapter split was made in this scope.

The resolver CLI separates admission from an explicit scratch problem. Supplied reviewed records pass through admission. Raw equations require `law_contract: DIRECT_CONSTRAINTS`, are labelled `constraint_mode: DIRECT_CONSTRAINTS`, and cannot carry review metadata. An unreviewed builder record cannot use scratch mode to acquire lexical authority.

## Diagnostic catalog

The production interface is:

```python
catalog = conditionals.load_catalog(path)
manifest = conditionals.catalog_report(catalog, rulebook)
diagnostic = conditionals.evaluate_catalog(native, catalog)
```

The existing path is `docs/verification/lexicon-rebuild/rule-registry-2026-10-24/coherence_candidates.jsonl`. [conditional-catalog.json](conditional-catalog.json) records every disposition. All 648 native relations have a diagnostic disposition; none receives lexical authority from discovery.

Evaluation uses `WORD_ALTERNATIVE_UNION`, matching discovery rather than pretending to identify a word sense. Results distinguish corroboration, contradiction, an unmet premise, missing source/record/field, malformed input and unavailable observations. Each atom retains native source record IDs. Native zero association is observed data, not lexical zero. Native alternative participants, restriction mentions and rating signs never write prime cells. No gold or model answer enters the interface. An explicit link to an already admitted conditional is provenance for investigation and grants nothing further.

VerbNet ancestor-class absence stays unobserved if the source adapter does not carry complete class ancestry. A matched native class remains a positive witness. This prevents a missing adapter field from becoming a counterexample.

## Verification record

The authored and existing lexicon selection ran through the target interpreter:

```text
.venv/bin/python -m pytest tests/test_lexicon_*.py
392 passed, 1 warning in 14.32s
```

The warning is the repository's existing Hypothesis directory-collection warning. Pinned `.venv/bin/ruff` 0.16.10 formatting/checks and `uvx ty check` passed on the owned production/test scope. The computed reconstruction call returned `RECONSTRUCTED_PRIME_FOUNDATION` with 72 reconstructed profiles. The scoped source-rule tests include positive and must-not witnesses for the migrated admission receipts and the real constructor/CLI paths.

## Detective record and remaining revalidation

Resolution was proved through the target environment with `PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker`. `detective --help` directed `detective regime`; regime printed DONE, clean, nothing to migrate.

The first `detective converge gse/lexicon_builder/core.py::cli_law_contract` requested authored calls for its uncovered lines. The next run supplied fifteen explicit literal calls as prescribed, and Detective wrote sixteen tests. The isolated reproducibility step printed:

> STOP: the function or test basis changed between the two measurements

Its prescribed repair was to keep the proof basis fixed and rerun only once the cause is resolved. Its final result was `UNGATEABLE`; its mutation counts are diagnostic, not a certificate. No generated test or certificate was hand-edited. The shared tree was still receiving parallel test additions, and a shared freeze was requested before retrying.

The full outputs are retained in [detective-cli-initial.log](detective-cli-initial.log) and [detective-cli-inputs-stopped.log](detective-cli-inputs-stopped.log).

On the subsequent shared freeze, the prescribed retry printed reproducibility confirmed and DONE: `cli_law_contract` COMPLETE over its operator universe, modulo 2 unproven equivalents and 13 crash-only value gaps; 73/75 killed, 16 generated tests. No equivalent was manually flagged. [detective-cli-fixed.log](detective-cli-fixed.log) retains that receipt. This is a bounded operator-universe result, not a proof of semantic correctness.

The existing `artifact.vector_status` audit reported complete within its bounds: 15 unproven equivalents, 3 crash-only value gaps. It prescribed `audit --remove` for three authored tests, including broader entry-point coverage. The lead explicitly stopped that removal path and preserved the tests. That workflow override does not erase the survivor bounds. [detective-artifact-audit.log](detective-artifact-audit.log) retains the complete prescription.

`model.selection_status` reported 2 killable gaps and prescribed convergence. Following convergence and its exact supplied-input retry, Detective still reported those gaps and explicitly prescribed writing `selection_status({'_unread': 'x'}, {}) == 'MALFORMED_OPTIONS'` as an authored assertion. The assertion was added to `test_lexicon_bounded_tail.py::test_malformed_decoder_contracts_have_named_refusals`, as the lead directed. No generated test was edited. The next prescribed convergence waits for the next shared freeze because a full-source validation found a reading-identity defect requiring source changes. [detective-model-audit.log](detective-model-audit.log), [detective-model-converge.log](detective-model-converge.log) and [detective-model-input.log](detective-model-input.log) retain the full sequence.

After the next shared freeze, the prescribed model convergence confirmed reproducibility and printed DONE / COMPLETE. Its two killable gaps were closed by the authored assertion. The four remaining existing targets were then audited independently. The complete current-round bounds reported by Detective are:

| Target | Method | Value-pinned | Unproven equivalents | Crash-only value gaps |
|---|---|---:|---:|---:|
| `core.cli_law_contract` | Converge, reproducibility confirmed | 60/75 | 2 | 13 |
| `artifact.vector_status` | Audit | 61/79 | 15 | 3 |
| `model.selection_status` | Converge, reproducibility confirmed | 47/63 | 7 | 9 |
| `native_constraints.predicate_domain` | Audit | 34/38 | 4 | 0 |
| `number.paired_order_status` | Audit | 21/22 | 0 | 1 |
| `surprise.comparison_status` | Audit | 74/80 | 4 | 2 |
| `tail.tail_task_status` | Audit | 74/117 | 36 | 7 |

Each reported COMPLETE/complete within those stated bounds. The audit commands prescribed test removals; those paths were stopped under the lead's explicit instruction to preserve authored integration and must-not tests. No survivor was manually flagged, no generated file was hand-edited, and the bounds were not waived. These measurements characterize the operator/test basis; they do not prove the linguistic authority of a rule.

Final outputs: [model convergence](detective-model-authored.log), [native predicate audit](detective-native-predicate-audit.log), [NUMBER audit](detective-number-audit.log), [surprise audit](detective-surprise-audit.log), [tail-task audit](detective-tail-audit.log). The persisted lexicon and seven generated decision suites ran together in [rule-scope-tests.log](rule-scope-tests.log): 430 passed, one existing Hypothesis warning, in 13.46 seconds. The final owned-scope pinned Ruff check and production-module ty check also passed. These are scoped results; the lead owns the full repository and full-source artifact gates.
