# Operating the three-repository program

This file is identical in Sparse Wiki, GSE and Regenesis. The design authority is Rohan's current instruction, then the whole cited theory/source and observed code. Git-tracked program files carry enduring intent. OpenSpec changes carry bounded engineering designs. GitHub issues and [Project #5](https://github.com/users/rohanvinaik/projects/5) carry scheduling and receipts. The older [GSE overhaul Project #4](https://github.com/users/rohanvinaik/projects/4) remains a GSE-specific historical/execution board; link related work without silently duplicating completion claims.

## Start a work session

1. Run `python3 scripts/check_program.py` from any of the three repos. It checks all pinned source hashes, required documents, the cross-repo dependency graph and issue maps. A changed or missing source stops re-grounding: read the complete changed document or coherent section, revise its dependent claims, then update the hash. A changed hash is never just a mechanical refresh.
2. Read `START_HERE.md`, `GLOSSARY.md`, `BUILD_GAPS.md`, `BUILD_SPEC.md` and `ASSURANCE.md` as complete units for the owning repo. Read the exact pinned sources and whole code producer/consumer units relevant to the chosen package. Keep USER_INTENT, CODE_OBSERVED, DATED_REPORT, INFERENCE and UNRESOLVED visibly separate.
3. Pick an unblocked stable ID in `WORK_INDEX.json`; `ISSUE_MAP.json` gives its GitHub issue URL. Resolve cross-repo dependencies from their actual acceptance receipts, not a status field alone. The issue title and Project fields are indexes into the specification, not specifications themselves.
4. Start or reconcile a local OpenSpec change. Put the stable ID in its proposal and link the issue. A change states the exact producer → artifact → consumer → named abstention contract, data/schema version, positive and MUST-NOT cases, and any compatibility/migration route. Regenesis already has an active correctness/performance change; reconcile overlapping tasks before adding another.
5. Trace actual production callers and any duplicate implementation before code edits. Prefer the repo that owns the information: Sparse Wiki for world identity/paths, GSE for language artifacts and bounded observations, Regenesis for story inference. Put integration adapters at the consumer seam and preserve provenance.

## Complete a package

1. Run hand-authored intent and negative specification through the real public entry point, including null, empty, malformed, ambiguity, missing resource and boundary cases. Follow Detective's installed next-action protocol, prove/fence survivors, and keep a per-class identified/abstained/wrong/unavailable/partial ledger.
2. Run the locked local/remote gate applicable to the package. For a performance claim, prove SAME-answer results and attach paired end-to-end measurements plus data-free kernel replay. A fast isolated helper does not close a package.
3. Put the completion receipt in the issue: exact source/data/code hashes, command and fixture, observed decision classes, consuming caller, negative witness, Detective state, and performance evidence if claimed. Update `BUILD_GAPS.md` and any specification only when the evidence changes their claims. Close the issue and mark Project Evidence State “Acceptance witnessed” only after that receipt exists.
4. Cross-repo integration closes only when the actual consumer reads the versioned artifact on a jointly pinned data/commit combination. Regenesis alone owns the eventual `stack.lock` of verified versions; never stamp a dirty checkout or bare HEAD as verified.

## Planning tool state

OpenSpec 1.14.1 is installed on this machine. GSE and Regenesis already had `openspec/config.yaml`; Sparse Wiki was initialized with `openspec init --tools none --no-animation --no-copilot-cloud`. `openspec doctor` passed in all three at setup. The Project is private and linked to all three GitHub repositories. It has Status, Work ID, Channel and Evidence State fields, and one GitHub issue per ID with blocking dependencies. The common issue form is `.github/ISSUE_TEMPLATE/program-work.yml`. GSE's `scripts/create_program_issues.py` can idempotently recreate missing issues from work indexes; `scripts/configure_program_board.py` can restore stable Work ID/Channel fields. Its `--initialize-evidence` option resets evidence state and is only for first setup.

If the GitHub board is unavailable, work remains reconstructible from the Git-tracked files and `ISSUE_MAP.json`. If a local source path is unavailable in another checkout, preserve `UNAVAILABLE_REFERENCE` until the source is deliberately relocated or repinned with its full reading; do not treat a missing path as assent.
