# Detective family baseline discrepancy — independent diagnosis

## Finding

The prior frozen retry is strongly explained by a stale **Detective verdict-cache replay**, rather than three tests newly failing during that retry. The current real six-test baseline passes cold under the original pytest regime. I found no evidence of fixture contamination.

This distinguishes three questions:

1. **Initial historical failure:** the archived caches record three failed baseline IDs, but neither stores the exception traceback. The original exception cannot be recovered from these receipts. Root reported a missing `projection_scope` in library `_payload` and a subsequent fix; that is session evidence, not a traceback independently recovered here.
2. **Historical frozen retry:** target/suite ledger hashes and invocation parameters match the initial run; the cached verdict contains those same three failures; cache read returns before target loading or baseline execution. Its duration was 11,019 ms, compared with the initial 162,966 ms, and the retry log contains no tracing/mutation phase. Confidence in stale replay as the retry explanation: high. There was no cache-read event instrumentation on that historical invocation, so this remains a code-and-receipt reconstruction rather than a contemporaneous hit log.
3. **Current baseline:** after backed-up supported purge, the unmodified CLI freshly traced six tests in 3.9 seconds and persisted `passed` for all six, with `failing=[]` and `inert_names=[]`. This is a current execution result, not an interpretation of old prose.

## Exact persisted basis

Archived Detective key:

```text
gse/lexicon_builder/families.py::family_contract_status:d1.2.2+w1.2.2+p9.261d14e34119:c55b7ae6cdbf1c25:ba54985d8e878392:0:0:50,1800:defer_shaped:9697199b44cbba08
```

`c55b7ae6cdbf1c25` is the validator AST hash, still identical in the current source. `ba54985d8e878392` is the archived exercising-test fingerprint. `9697199b44cbba08` is the original pytest regime; the unmodified cold run reproduced that exact regime.

The two historical ledger records both contain:

```json
{"target_src":"sha256:a4d21971ec6176b6368af0cfaeafe886","suite":"sha256:ca97b1e19a8783a3c0870111a564f76a"}
```

The target file and source-aligned test/fixture/config fingerprints are keyed. Other production functions used by the integration tests are **not** included in the verdict key. A change to builder `_payload` can change whether these tests pass while leaving the target AST and test-file fingerprints identical. Changed test bytes do invalidate their fingerprint; this investigation does not claim otherwise.

Rehydrating the archived row through the actual `Detective.verdict_cache.get` returned `served_from_cache=True`, `trace_provenance=["replayed"]`, and all three historical failure IDs:

- `test_native_family_boundary_reaches_the_real_builder_and_export`
- `test_boundary_cannot_supply_a_deleted_content_warrant`
- `test_removing_one_silence_support_reopens_only_its_coordinate`

The uninstrumented historical retry nevertheless printed **FAILING NOW** and told the user to fix a test. That wording did not distinguish a replayed failure from an executed failure.

## Both caches, and the actual consumer path

- **Detective:** `Detective/engine.py::profile` (line 992), `verdict_cache.py::cache_key`, `get`, and `put`. `profile` checks the verdict cache before `_load_original`, target-first routing, or the session baseline. A hit returns the stored `failing_tests`. The cache key contains the target AST and tests, not their imported production dependency closure. `put` permits a completed profile with baseline failures; there is no separate dependency check for these failures.
- **Wesker:** `Wesker/trace_cache.py::test_fingerprint` (line 89), `targets_fingerprint` (163), and `load_outcomes` (373); `engine.py::build_session_baseline` (4427). The archived trace cache separately holds the same three failures, keyed to the target file and each test context. Its own comments explicitly acknowledge that imported-helper closure is absent from the fingerprint.
- **Important difference:** the ordinary target-first miss path calls `LazySessionBaseline.seed` (4226), which builds with `fresh=True`. `build_session_baseline` then re-observes both reach and outcomes rather than reusing those cached failures. Thus the presence of stale Wesker failure rows does **not** prove that this path consumed them. The Detective early return is the path that bypasses this fresh protection. Purging only Wesker would leave the stale Detective verdict available.
- **Traceback lifetime:** `pytest_runner.py::_ExcCapture` (69) temporarily preserves the actual exception; `_make_item_callable` (253) re-raises it. `_cheap_failure_repr` (170) deliberately omits traceback formatting. `engine.py::_run_test_with_timeout` (7961) reduces that exception to a named outcome; the persisted profile and baseline rows retain no traceback. Therefore the archived initial failure cannot now be assigned a precise exception site from those files.

## Actual runs and their bounds

Interpreter was GSE `.venv/bin/python` / `.venv/bin/python3`, Python 3.14.6. Detective and Wesker resolved to `/Users/rohanvinaik/tools/Detective/Detective/__init__.py` and `/Users/rohanvinaik/tools/Wesker/Wesker/__init__.py`, respectively. The historical ledger records the same tool roots and target interpreter. Fresh traced target paths point into `/Users/rohanvinaik/Projects/gse/gse/lexicon_builder/families.py`.

1. Read current CLI help and `regime`: **DONE**, clean flat layout, no migration.
2. Instrumented logging-only CLI run: six-test `fresh=True` baseline passed, no baseline exception. Its capture subclass changes the pytest regime to `c16189e242befe3a`, and the current tests also changed their fingerprint. Its cache misses therefore cannot establish a controlled unmodified warm/cold comparison. It was safely interrupted (exit 130) before a full mutation result, after the baseline evidence had been obtained. No certificate is claimed.
3. Supported `detective purge`: 100 regeneratable cache/report files removed, 18,196 KB reclaimed. Both complete cache directories were backed up beforehand. Inputs, pins, equivalents, judgments, and the existing ledger were preserved; preservation was checked byte-for-byte (ledger as a prefix after new invocations appended).
4. Unmodified CLI:

```sh
env PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective converge gse/lexicon_builder/families.py::family_contract_status --deadline 20 --write-dir /private/tmp/gse-detective-diagnosis-20261026/generated
```

Fresh baseline: all six passed, original regime `9697199b44cbba08`, original target-file fingerprint `7a885bbf017d5d2e`. Final printed result:

```text
INCOMPLETE:  property_render_timeout: the remaining execution deadline is exhausted
```

Exit 3. The deliberately bounded run establishes the baseline result, not complete mutation convergence. No authored or generated test was manually changed or removed, and no certificate was manually created or altered. No lexicon model was called. All seven frozen source/test/rulebook hashes matched at the cold-baseline checkpoint; the parent was then told the freeze was released. Later formatting changed two hashes, which is recorded separately and is not represented as frozen-run drift.

**Causal limit:** the current tests and surrounding builder changed since the original failure. The cold pass is not a one-variable experiment proving that purge alone fixed historical code. The cache-key omission, retained row, control flow, historical ledger identity, and explicit cache rehydration independently support the historical retry explanation. A controlled historical failure traceback is unavailable.

## Concrete correction proposal

Immediate operational correction is complete: preserve the evidence and use the supported purge of both regeneratable cache layers after relevant builder changes, then read a fresh baseline rather than revising tests to satisfy a replay.

For Detective/Wesker, propose a separate tool change, not a lexicon change:

1. Bind verdict reuse to the executed production dependency/content basis, or conservatively invalidate on relevant project-source changes. A target/test-only key cannot certify integration-test outcomes. If the complete basis is unavailable, a replayed row may order work but must not assert present failure or completeness.
2. At minimum, re-screen baseline outcomes fresh before reporting a cached failure, and label its provenance. This prevents the specific stale **FAILING NOW** instruction; by itself it does not make every old mutant result safe after arbitrary helper changes.
3. Preserve an initial-baseline exception receipt (test ID, phase, raw exception type/message, traceback, interpreter and imported origins). It should run once for baseline failures, not format every killed-mutant traceback. That would make the next such discrepancy diagnosable from exact evidence.
4. Add a tool-level regression where an integration test remains byte-identical while an imported helper is fixed. The warm run must reopen/re-measure instead of replaying the old failure. Also verify that changes to test bytes invalidate the row, and that clearing only the trace cache cannot mask a still-cached verdict.

No lexicon-source correction, authored-test weakening, equivalence judgment, or fixture-contamination claim follows from this diagnosis.

## Receipts

Complete backups are private, not repository artifacts:

- `/private/tmp/gse-detective-diagnosis-20261026/cache-before-042759/`
- `/private/tmp/gse-detective-diagnosis-20261026/cache-before-supported-purge/`

Targeted receipts in that same parent directory: `archived-cache-rehydration.json`, `family-ledger-records.json`, `cache-comparison.json`, `current-run-basis.json`, `cold-baseline-summary.json`, `cold-trace-cache.json`, `warm-current-events.jsonl`, `warm-current.log`, `cold-unmodified.log`, and `purge.log`. The `warm-current` filename denotes the instrumented run described above; it is not a claim of original-regime cache reuse.
