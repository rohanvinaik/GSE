# Native-source constructor: first bounded live proof

Run: `uv run python -m gse.lexicon_builder build --words excellent terrible enormous tiny delighted furious --output docs/verification/lexicon-rebuild/builder-live-2026-10-24`

This is a prototype construction receipt. Complete candidate vectors include explicitly provisional silence; they are not fully certified definitions. No production lexicon was written. The complete source records, premise IDs, before/after domains, JSON requests, decoder schemas, answers and model digests are in `words.jsonl`; the basis order, source and implementation hashes are in `manifest.json`.

| Word / reading | Before local selection | Selected fields | Calls | Outcome |
|---|---|---|---:|---|
| excellent:ADJ:A5.1+++:quality | GOOD:+1 | INTENSITY:+1 | 2 | CANDIDATE_COMPLETE |
| terrible:ADJ:A5.1-:quality | GOOD:-1 | INTENSITY:+1 | 2 | CANDIDATE_COMPLETE |
| enormous:ADJ:N3.2+++:size | BIG:+1 | INTENSITY:+1 | 2 | CANDIDATE_COMPLETE |
| tiny:ADJ:N3.2-:size | BIG:-1 | INTENSITY:+1 | 2 | CANDIDATE_COMPLETE |
| delighted:ADJ:E4.1+:feeling | GOOD:+1, FEEL:+1 | none | 0 | PARTIAL |
| furious | No applicable definitional rule | none | 0 | PARTIAL_NO_APPLICABLE_RULE |

Model: `qwen3.5:4b`, digest `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.

Quality/size readings used one binary degree selection and one omission challenge. The selected coordinate is reintroduced as a candidate constraint and the symbolic engine reruns before any next decision. The decoder receives its exact enum schema in the backend format parameter; no routine gloss text is sent. Source-approved and model-selected states remain separately traced.

The generic affective optional-field trial was rejected: it offered THINK/WANT/HAPPEN/BECAUSE without sufficient source warrants. Those options were removed; delighted now remains partial with GOOD:+1 and FEEL:+1 and uses no model call. The rejected run directory is diagnostic evidence only and is never loaded by the builder.

Furious has NRC anger and disgust associations but no applicable definition rule in this prototype. Neither association populated a vector. A source category or association is not an exhaustive component inventory.

Validation: 41 scoped pytest tests passed, including two Detective-generated tests; Ruff and ty passed on the new builder scope; the three-repository program reference/dependency checker passed. The ordinary pytest executable did not put the scripts namespace on the import path; the successful invocation used `uv run python -m pytest`.

Detective converge for gse/lexicon_builder/model.py::selection_status printed COMPLETE modulo 3 unproven-equivalent mutants and 1 crash-only value gap (21/24 killed). This is a bounded behavioral result, not proof of equivalence or lexical correctness. Its full report is .detective/reports/converge_selection_status.txt. The earlier discovery-script decision pin remains separately UNGATEABLE as recorded in the discovery receipt.

Remaining acceptance: complete the conditional bank laws and source coverage, all atomic combinatorial profiles, real lexical joint-constraint witnesses, random rank-2K–10K proof, then the 1,000-word / Zipf audit. The current prototype must not be launched as a full production lexicon build.
