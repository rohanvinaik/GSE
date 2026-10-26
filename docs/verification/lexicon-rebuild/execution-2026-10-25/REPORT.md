# Lexicon symbolic build execution

[CODE_OBSERVED] The symbolic builder and mask-aware SQLite publication run end to end. This is a verified **partial** lexical artifact. Ordinary-definition completeness and production replacement remain unestablished.

The computed [summary](summary.json) and [full audit](release-audit.json) are the measured state. The [basis contract](../../../program/LEXICON_BASIS_CONTRACT.md) states the authored senses and limits; [rule contracts](RULE_CONTRACTS.md) records admission, provenance, corrections and bounded Detective results.

## Foundation and source sweep

- Prime reconstruction: 72 examined profiles over 58 signed coordinates.
- Declared source surfaces: 82,681; emitted readings: 59,410.
- Complete coordinate profiles: 78 (prime surfaces); ordinary definitions remain partial.
- Actual model requests: 0.
- Native source files verified against their pins: 6,846.

Profile classifications, computed independently of token frequency:

- NO_WRITTEN_DEFINITIONAL_EVIDENCE: 25,476
- PARTIAL_HEAD_ZEROS_ONLY: 19,948
- PARTIAL_DEFINITIONAL_EVIDENCE: 13,181
- PARTIAL_HEAD_EVIDENCE_ONLY: 727
- FULLY_SETTLED_COORDINATE_PROFILE: 78

## Corpus coverage

Each metric has its own denominator and threshold. Native vocabulary presence, a located home and signed lexical content measure different properties. Brown is grouped by its native genres; Gutenberg by text, with no inferred genre labels. Exact normalized surface matching gives no lemmatization credit.

| Corpus | Declared vocabulary mass | Any lexical or structural home | Any signed lexical evidence |
|---|---:|---:|---:|
| brown | 93.62% | 84.78% | 18.30% |
| gutenberg | 94.31% | 82.52% | 23.04% |

The declared vocabulary clears the 90% mass threshold. Homing and signed evidence do not. Neither metric establishes that a definition is complete. The audit preserves all genre/text results, unhomed surfaces, source availability, per-coordinate states and the two-sided published-explication ledger. Published references enter evaluation only; they do not select construction tasks or legal answers.

## Replay and gates

The [complete historical replay](replay/README.md) compares every old/shared cell and retains the ledgers. The baseline refresh is justified by reviewed foundation, noun, source-adapter, CAUSE and admission contract changes, rather than by treating changed output as correct. A fresh comparison after the refresh reports IDENTICAL.

- [Repository gate](repository-gate.log): pinned lint, format, tests and advisory types.
- [Lexicon rebaseline gate](lexicon-rebaseline.log): scoped checks and regenerated frozen build.
- [Detective receipts and residual bounds](RULE_CONTRACTS.md): actual tool revalidation, with authored integration tests preserved.
- The distributable includes the rulebook and foundation JSON; the installed-wheel prime-proof smoke reconstructs the foundation. Final staged-source smoke is recorded separately.

## Artifact and use

The local published artifact is `/Users/rohanvinaik/Projects/gse/data/lexicon_symbolic.db`, SHA-256 `174ded50fc77285638c611a48212fec6f7d9372e8f8a83144e7fa0d9548c7fed`. Full build output is `/private/tmp/gse-lexicon-release-build-20261025`. These rebuildable data files stay outside Git, as required by the repository's data policy. [Publication receipt](published-release.json) pins the inputs and SQLite digest.

```bash
uv sync --locked
uv run gse-lexicon build --symbolic-only --all-source-words --output data/symbolic-build
uv run gse-lexicon release --input data/symbolic-build --output data/lexicon_symbolic.db
uv run gse-lexicon release-audit --build-dir data/symbolic-build --output data/symbolic-audit
```

Use `GSEEncoder(db_path="data/lexicon_symbolic.db")` to inspect the partial artifact explicitly. Lexical evidence preserves the full 58-cell payload; the compatibility vector uses settled components only, with sense alternatives still unresolved. Construction homes have separate readers and never acquire fabricated lexical cells. The default production database has not been replaced.

## Remaining work

[UNRESOLVED] Broad ordinary-word coverage requires additional reviewed source-to-definition projectors and conditional rules. Norms and native associations do not by themselves establish lexical content. No unexamined silence is imputed. THIS remains an explicit basis gap; shifted deixis requires a downstream binding consumer; numerical NUMBER calibration remains separate. Native conditional retraction currently addresses a located frame's coordinate projection, not an individual source predicate.

[AUTHORED] Fear DO/IF/KNOW are nominated per-word choices under F151/F152, without a claim that every member contains them. An explicit tail queue retains all rule-surviving states (including zero), offers abstention, enforces the call budget and records every disposition. Ordinary builds remain symbolic.
