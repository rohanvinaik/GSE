# GSE — Geometric Semantic Encoding

GSE composes lexical primitive evidence and grammatical structure into deterministic geometric and symbolic representations. Its native reader uses rules and local lexical resources. The typed symbolic reading retains predicates, roles, operators, scopes and referent evidence for downstream reasoning.

A reading is evidence at a stated projection. Unknown words, ambiguous identities, failed analysis and unsupported inference remain explicit; a vector or an empty diagnostic is not a certificate of complete understanding.

## Run locally

The project requires Python 3.14 or later. `uv sync --locked` creates the locked environment. The native reader also needs the local WordNet corpus; resource acquisition is separate from reading:

```bash
uv run python -m nltk.downloader wordnet
uv run python -m gse.cli encode "The dog runs." --format json
uv run python -m gse.cli compare "big" "small" --format json
```

The encoder's default lexicon is `data/lexicon_clean.db`, resolved relative to the checkout. Optional spelling, frequency and rating resources have independent availability states and are never downloaded during reading.

## Public Python paths

```python
from gse.api import GSEEncoder
from gse.symbolic import from_trace, resolve, evaluate_tree, propositions, commitment

encoder = GSEEncoder()
try:
    trace = encoder.encode("The dog runs.")
    tree = evaluate_tree(resolve(from_trace(trace)))
    claims = [(p.kind, commitment(p)) for p in propositions(tree, source_text=trace.input_text)]
finally:
    encoder.close()
```

For a complete document, consume `encode_document_utterance_events` from `gse.discourse.speech`. It returns a manifest, an outcome for every expected utterance, and a termination record. `MultiScaleDoc` adds shared document resolution and unit views without re-grounding each paragraph. Legacy success-only wrappers and fixed classifier vectors remain explicit compatibility projections.

The shared claim API separates commitment, polarity, scope and identity. `KnowledgeBase` admits supported premises through that authority. Its legacy lexical queries and its resolved claim query have distinct documented limits. Default Genesis serialization is preserved; `emit_contract(..., include_semantics=True)` adds the versioned claim sidecar.

## Contracts and consumers

- [Complete document reading and structural evidence](docs/TYPED_READING_API.md)
- [Shared claim semantics and inference limits](docs/CLAIM_SEMANTICS.md)
- [Lexical evidence and the shared healing core](docs/LEXICAL_EVIDENCE_AND_HEALING.md)
- [GSE–voice boundary](openspec/changes/archive/2026-10-20-preserve-typed-prose-readings/contracts/gse-voice-boundary.md)
- [Implementation and consumer review](docs/TYPED_READING_CLOSEOUT.md)

The geometric stack remains available through `GSEPipeline` as a separate interface. Geometric similarity describes that encoding; referent-aware equivalence and contradiction require the supported symbolic evidence. No aggregate voice-quality score is defined here.

## Verification and theory status

Run `scripts/ci_local.sh` for the repository's lint, format, test and advisory type checks. The output of a fresh run is the current measurement; historical counts in research records are not live status. Expected failures name unresolved probes and do not certify those readings.

`CLAUDE.md` marks `docs/THEORY.md` invalid, while that document describes itself as reconciled. This unresolved authority conflict is recorded in the OpenSpec evidence matrix. This README does not promote either claim into a replacement theory. The current repair's scope and preserved outputs are specified in [the typed-reading change](openspec/changes/archive/2026-10-20-preserve-typed-prose-readings/proposal.md).

MIT — Rohan Vinaik.
