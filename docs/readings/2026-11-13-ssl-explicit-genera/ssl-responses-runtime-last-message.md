**Runtime scope: CODE_FREEZE_READY; CP-07 remains OPEN.** No commits made.

Implemented:
- `GSE/api/encoder.py`
- `GSE/symbolic/{lexical_grounding,grounding}.py`
- `scripts/audit_lexicon_{runtime,sentences}.py`
- Three focused test files and the retained workload-census helper.

Verified:
- **316 tests passed**
- Pinned Ruff passed
- Public active sparse runtime audit: **SPARSE_RUNTIME_VALIDATED**
- Active and foundation checkpoint CLIs: **CHECKPOINT_BLOCKED**
- Ty: one pre-existing advisory; not certified clean

**New release-blocking findings from actual composed tools:**
1. Above/below collapse to identical `TYPE_ASSERT(bird, tree)`.
2. “Before dawn” loses its temporal relation.
3. Inert-gas **He** selects helium correctly, but the sentence incorrectly composes **gas** as a verb.

Further runtime repairs require **coordinated unfreeze**. Femur/teacher/chemical-symbol identity abstentions, open HAPPEN/SAY requirements, and complete workload acceptance also remain unresolved.

Receipts saved under the existing readings directory:
- `ssl-api-runtime-result.md`
- `ssl-api-runtime-result.json`
- `ssl-api-runtime-blockers.json`
- `ssl-api-runtime-checkpoint-demand.json`
- `ssl-api-runtime-postfreeze-findings.json`

Exact source pins, commands and test/report paths are retained there. Runtime source edits are finished and pins remain unchanged. **Zero corpus writes or admitted rules; H not remeasured; active pointer unchanged.** CP-07 acceptance and CP-08 publication gates remain open; controller-owned CP-03–06 obligations are not certified by this handoff.