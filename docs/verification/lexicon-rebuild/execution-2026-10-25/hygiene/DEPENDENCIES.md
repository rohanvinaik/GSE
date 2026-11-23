# Full-lockfile dependency hygiene

## Final audited lock after remediation

The implementation follow-up upgraded the locked packages and raised the direct security floors. The fresh [final audit snapshot](dependency-audit-final-snapshot.json) pins the current lock, project metadata and re-exported requirements. It retains **all extras and groups**, uses no suppression, and records export/audit exits of zero. The [final output](pip-audit-final.log) reports no known vulnerabilities among audited packages, with the explicit URL-sourced en-core-web-sm skip retained.

| Package | Final locked version |
|---|---|
| certifi | 2026.10.23 |
| nltk | 3.10.4 |
| mcp | 1.30.0 |
| setuptools | 84.1.0 |

The [NLTK source review](NLTK_ADVISORY.md) records the maintainer's later 3.10.4 release and checks its six named API repairs; the older advisory's missing fix column was not treated as proof that no newer repair existed. The original report below remains historical evidence. Dependency-declaration drift and repository rubric leads remain visible rather than being suppressed.

## Initial read-only audit (before remediation)

Read-only source/test audit. The authoritative hygiene instructions were read in full from `~/Projects/SquishOS/ops/agents/reference/repo-hygiene.md`. No dependency, lockfile, source, test, ignore or waiver was changed by this task.

## Scope and execution

The exported requirements include **all extras and all dependency groups**, with the required frozen/no-project/no-hashes flags. The export was not narrowed to obtain a clean result. The requirements remain in the private temporary file; their contents are not printed in this packet. Exact commands, exit codes and SHA256 fingerprints of `uv.lock`, `pyproject.toml` and the exported requirements are retained in [dependency-audit-snapshot.json](dependency-audit-snapshot.json).

```sh
uv export --frozen --no-hashes --no-emit-project --all-extras --all-groups --format requirements-txt > /private/tmp/gse-lexicon-hygiene-all-requirements-20261025.txt
uvx pip-audit -r /private/tmp/gse-lexicon-hygiene-all-requirements-20261025.txt --no-deps --disable-pip
uvx deptry .
```

Initial sandbox runs were refused access to uv's existing cache (`Operation not permitted`, exit 2). Those full messages are preserved in [uv-export.log](uv-export.log), [pip-audit.log](pip-audit.log) and [deptry.log](deptry.log). Required escalated reruns used the same scopes and flags. Export completed with exit 0; its stderr is [uv-export-escalated.log](uv-export-escalated.log).

## Vulnerability audit: findings, not a clean audit

`pip-audit` completed with **exit 1**, reporting four known vulnerabilities in four packages:

| Package | Locked version | Advisory reported | Fix versions reported |
|---|---|---|---|
| certifi | 2026.5.20 | PYSEC-2026-4320 | 2026.10.19 |
| mcp | 1.28.1 | CVE-2026-59951 | 1.30.0, 2.2.0 |
| nltk | 3.10.3 | PYSEC-2026-3740 | None listed |
| setuptools | 84.0.0 | GHSA-xmj3-9gf7-h52w | 84.1.0 |

The tool explicitly skipped **en-core-web-sm**, because URL requirements cannot be pinned to a specific package version. Its `--no-deps`/hash warnings are preserved. These are the tool's reported advisories and fix versions; no compatibility assessment, remediation or waiver is implied.

Complete output: [pip-audit-escalated.log](pip-audit-escalated.log).

## Dependency drift audit

`uvx deptry .` completed with **exit 1**, scanning 432 files and reporting **46 dependency issues** under DEP001, DEP002 and DEP004. Its full output includes every finding and all assumed package-to-module mappings. Paths include archived code, scripts and active modules. Reported examples include `psutil`, `torch`, `amrlib` and `sklearn` import findings; declared-unused findings for `scikit-learn` and `en-core-web-sm`; and an archive test importing the dev dependency `pytest`.

No finding was automatically classified as false positive, exempted or fixed. Package-module mapping assumptions, including `scikit-learn → scikit_learn`, remain visible for source-grounded triage.

Complete output: [deptry-escalated.log](deptry-escalated.log).
