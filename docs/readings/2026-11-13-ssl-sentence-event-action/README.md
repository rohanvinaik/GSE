# Reproduce the sentence-guided event and action round

Run from the GSE repository. This round uses a frozen release 012 snapshot and the pinned local model. The active pointer must name that baseline for the epoch command. [Source warrants and exclusions](SOURCE_SCOPE.md)

```sh
notes=docs/readings/2026-11-13-ssl-sentence-event-action
run=data/lexicon_builder/2026-11-12/ssl-sentence-event-action
baseline=data/lexicon_builder/2026-11-12/sparse-release-012.db
owner=../SquishOS/ops/agents/bin/owned-run
model=qwen3.8:27b-q4_K_M
model_digest=25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e

.venv/bin/python -m scripts.audit_lexicon_sentences --lexicon "$baseline" \
  --benchmark "$notes/sentences.json" --report "$notes/baseline-sentences.json"
"$owner" --label ssl-event-action-inventory -- .venv/bin/python -m scripts.run_lexicon_epochs init \
  --baseline "$baseline" --plan "$notes/plan.json" --directory "$run"
for policy in closure zipf; do
  "$owner" --label "ssl-event-action-$policy" -- .venv/bin/python -m scripts.run_lexicon_epochs run \
    --baseline "$baseline" --plan "$notes/plan.json" --directory "$run" \
    --policy "$policy" --model "$model" --model-digest "$model_digest"
done
```

In the recorded run the closure arm's WordNet audit exceeded the configured context. Its request and schema were replayed at a larger context with the same model digest. The Wiktionary answer was replayed locally. The refused dispatch and the recovered audit are retained separately. Run `scripts.audit_lexicon_sentences` with `--baseline-report "$notes/baseline-sentences.json"` against each replayed candidate. The verified closure path is `closure/epoch-01/candidate-recovered.db`; the Zipf path is `zipf/epoch-01/candidate.db`. The [comparison receipt](comparison-verification.json) records the exact model budgets, transport recovery, candidate digests, corpus deltas, and sentence outcomes. This one-epoch trial measures selection and propagation through the existing DO→HAPPEN convention.
