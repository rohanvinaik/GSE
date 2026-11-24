# GSE — Geometric Semantic Encoding

GSE composes lexical primitive evidence and grammatical structure into deterministic geometric and symbolic representations. Its native reader uses rules and local lexical resources. The typed symbolic reading retains predicates, roles, operators, scopes and referent evidence for downstream reasoning.

A reading is evidence at a stated projection. Unknown words, ambiguous identities, failed analysis and unsupported inference remain explicit; a vector or an empty diagnostic is not a certificate of complete understanding.

## Run locally

The project requires Python 3.14 or later. `uv sync --locked` creates the locked environment. The native reader also needs the local WordNet corpus; resource acquisition is separate from reading:

```bash
uv run python -m nltk.downloader wordnet
uv run python -m GSE.cli encode "The dog runs." --format json
uv run python -m GSE.cli compare "big" "small" --format json
```

The encoder's default lexicon is the build named by `data/lexicon_active.json`, resolved relative to that pointer; `data/lexicon_clean.db` is read only when the pointer is absent. Optional spelling, frequency and rating resources have independent availability states and are never downloaded during reading.

## Lexicon builder

GSE has one lexicon builder, `GSE/curation/lexicon_builder/`. Its command line is `GSE-lexicon` (the same as `python -m GSE.curation.cli.commands`); continuing learning runs through `scripts/run_lexicon_epochs.py`. The encoder reads a build by default only after `publish --destination … --gold …` validates a snapshot of it and writes the active pointer; an explicit `db_path` bypasses activation.

```bash
uv run GSE-lexicon --help
uv run GSE-lexicon catalog --inventory    # the saved primary chart; no build needed
```

The construction contract is [`docs/program/LEXICON_CONSTRUCTION_DESIGN.md`](docs/program/LEXICON_CONSTRUCTION_DESIGN.md). The earlier upstream constructor is archived in `GSE/_archive/lexicon_builder/`; its contract is kept as Part II of that document. A successful build does not certify that ordinary word definitions are complete.

## Public Python paths

```python
from GSE.api import GSEEncoder
from GSE.symbolic import from_trace, resolve, evaluate_tree, propositions, commitment

encoder = GSEEncoder()
try:
    trace = encoder.encode("The dog runs.")
    tree = evaluate_tree(resolve(from_trace(trace)))
    claims = [(p.kind, commitment(p)) for p in propositions(tree, source_text=trace.input_text)]
finally:
    encoder.close()
```

For a complete document, consume `encode_document_utterance_events` from `GSE.discourse.speech`. It returns a manifest, an outcome for every expected utterance, and a termination record. `MultiScaleDoc` adds shared document resolution and unit views without re-grounding each paragraph. Legacy success-only wrappers and fixed classifier vectors remain explicit compatibility projections.

The shared claim API separates commitment, polarity, scope and identity. `KnowledgeBase` admits supported premises through that authority. Its legacy lexical queries and its resolved claim query have distinct documented limits. Default Genesis serialization is preserved; `emit_contract(..., include_semantics=True)` adds the versioned claim sidecar.

## Contracts and consumers

- [Complete document reading and structural evidence](docs/TYPED_READING_API.md)
- [Shared claim semantics and inference limits](docs/CLAIM_SEMANTICS.md)
- [Lexical evidence and the shared healing core](docs/LEXICAL_EVIDENCE_AND_HEALING.md)
- [GSE–voice boundary](openspec/changes/archive/2026-10-20-preserve-typed-prose-readings/contracts/gse-voice-boundary.md)
- [Implementation and consumer review](docs/TYPED_READING_CLOSEOUT.md)

The geometric stack remains available through `GSEPipeline` as a separate interface. Geometric similarity describes that encoding; referent-aware equivalence and contradiction require the supported symbolic evidence. No aggregate voice-quality score is defined here.

## Verification and theory status

Run `scripts/ci_local.sh` for the repository's lint, format, import-direction, test and advisory type checks. It is the full gate: before a push, and in CI. The import-direction contracts and their recorded exceptions are in `pyproject.toml` (`[tool.importlinter]`).

While working, run only what a change touches:

```bash
uv run pytest -m symbolic                                   # tests whose files import GSE.symbolic
uv run pytest -m "lexicon_builder or external_sources"      # every top-level area of GSE/ is a marker
uv run --with pytest-testmon pytest --testmon               # only tests affected by changed code
```

Area markers are derived from each test file's imports at collection (`tests/conftest.py`); `uv run pytest --markers` lists them. The impact selector records a baseline on its first run and keeps its state in `.testmondata`, which is not committed. The output of a fresh run is the current measurement; historical counts in research records are not live status. Expected failures name unresolved probes and do not certify those readings.

`CLAUDE.md` marks `docs/THEORY.md` invalid, while that document describes itself as reconciled. This unresolved authority conflict is recorded in the OpenSpec evidence matrix. This README does not promote either claim into a replacement theory. The current repair's scope and preserved outputs are specified in [the typed-reading change](openspec/changes/archive/2026-10-20-preserve-typed-prose-readings/proposal.md).

MIT — Rohan Vinaik.
