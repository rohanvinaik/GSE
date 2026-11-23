# Read-only release hygiene

Commands and exits are recorded in [commands.json](commands.json). Initial sandbox cache failures
are preserved beside the completed escalated outputs. Tool availability is in [availability.json](availability.json).

- Offline zizmor: exit 0, no workflow findings; [full output](zizmor.log).
- Scientific Python repository review: exit 3; 7 rubric leads
  (PY003, PY006, PY007, PP309, RF002, RF101, SEC001); [full output](sp-repo-review.log) and
  [per-check dispositions](sp-repo-review-findings.json). Its persistent-check/task-runner/lint
  preferences are reported without changing project policy.
- detect-secrets 1.5.0, via uvx because neither scanner was on PATH: exit 0 in baseline
  mode, which does **not** mean no candidates. Network verification was disabled. The tracked
  working-tree scan found 25,859 candidates in 87 files,
  all from Hex High Entropy String. No raw matched values were printed. The complete baseline stores
  hashed candidates and locations in [detect-secrets-tracked.json](detect-secrets-tracked.json).

The structural review read complete JSON/JSONL records and the complete named Python approval-digest
assignment, without displaying candidate values. Its [computed outcomes](detect-secrets-summary.json)
identify digest/signature-field and opaque-hex-identifier metadata; the [full provenance
classification](detect-secrets-provenance.json) retains locations and field context. This establishes
substantial digest-metadata noise, not a credential-verification or blanket clean-secret claim.
Remaining structural-context review leads are kept explicit. No history scan was performed; root
separately owns the staged-tree export and publication identity.
