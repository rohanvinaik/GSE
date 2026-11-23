# GSE assurance and performance contract

This is a target gate architecture for GSE-07, not a claim that all gates already exist. Inventory current scripts and CI before wiring. Sibling repositories apply the same principles to their entry points and kernels.

## Detective two-sign rigor

For each decision, write (1) intent tests showing what must happen and (2) negative specification showing what must never happen. Start Detective from the installed tool's `--help` in the repo, follow its reported next actions to DONE, and pair generated characterization tests with authored semantic witnesses. A surviving mutant requires an equivalence proof or explicit test fence; a high kill rate never proves intent. Use CrossHair/contracts where invariants are expressible. Test null, empty, malformed, ambiguity, collision, negation, quoted text, context boundaries, stale cache, and unavailable world resources through the real CLI/API. Report identified, abstained, wrong, unavailable and partial per class; no single committee score.

## Symmetric locked gates

Implement `scripts/ci_local.sh` and `.github/workflows/gate.yml` from the same locked `uv` environment and command list. Blocking checks: pinned `ruff check .` and `ruff format --check .`; import isolation so production code cannot import development/profiling/visualization libraries; full coverage-backed pytest; offline zizmor workflow scan; SonarQube unresolved bugs and vulnerabilities only (code smells, duplication and legacy coverage advisory, essential complexity rationale on any `NOSONAR`); detect-secrets on commit additions, with strict AST/hash verification for legitimate public digests. If a service is unavailable, emit an unavailable gate status rather than a pass. Pre-push `scripts/push_checks.py` hashes a clean working tree and stamps successful states in `.git/gate-passed/`, letting a hook check the exact pushed tree without redundant runs. Advisory leads, never targets: deptry, ty, Ruff PERF/FURB, two unmasked vulture scans, and pip-audit over exported lock extras/groups.

## Data-free continuous measurement

Instrument the real production entry point on a versioned proof study. For expensive kernels record the costliest invocation with scalar args and content-digested array buffers in `arrays.npz` and `manifest.json`; preserve exact dtype, shape, strides, writeability, and missing/fallback codes on replay. Lossless integer-float downcast is allowed only when byte-identical upon reconstruction. Assert input immutability. CodSpeed can track CPU instructions/allocations on PRs and main; local `pytest-memray --fail-on-increase` guards peak memory against the previous successful run. These are diagnostics, not substitutes for paired end-to-end timing under the real CLI.

## Efficiency epistemology

Resolve cheap structural constraints before heavy native/HDC work. Reuse early candidate sets and context maps to answer dependent questions; publish validated context immediately. Trace lineage with Hamilton/beartype/jaxtyping where suited, VizTracer/cProfile and Scalene/memray/py-spy/pyinstrument/line_profiler for attribution. Probe Numba/Cython/Ruff/Codeflash/pyperf/asv only after a real hotspot is measured. Vectorization, JIT twins, caches and batching must preserve the SAME answer: dtypes, shapes, sign/categorical codes, contractual ordering, zero and missing/fallback states across the full gate. Speed claims attach paired whole-entry measurements and a correctness receipt.
