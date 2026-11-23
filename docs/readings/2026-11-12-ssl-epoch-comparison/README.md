# Replay the SSL epoch comparison

Run from the GSE repository with the pinned baseline and plan. The two arms share the typed model and source population. They differ in which eligible question they select. Zipf orders by SUBTLEX count. Closure ordering stages the present proposal and possible two-rule bridges, screens contradictions, and ranks marginal singleton gain. SUBTLEX breaks ties for closure ordering.

```sh
baseline=data/lexicon_builder/2026-11-01/constructed-corpus-monetary-want-zipf.db
plan=docs/readings/2026-11-12-ssl-epoch-comparison/plan.json
run=data/lexicon_builder/2026-11-12/ssl-epoch-comparison
model=qwen3.8:27b-q4_K_M
model_digest=25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e
owner=../SquishOS/ops/agents/bin/owned-run

"$owner" --label epoch-inventory -- .venv/bin/python -m scripts.run_lexicon_epochs init \
  --baseline "$baseline" --plan "$plan" --directory "$run"
"$owner" --label epoch-closure -- .venv/bin/python -m scripts.run_lexicon_epochs run \
  --baseline "$baseline" --plan "$plan" --directory "$run" \
  --policy closure --model "$model" --model-digest "$model_digest"
"$owner" --label epoch-zipf -- .venv/bin/python -m scripts.run_lexicon_epochs run \
  --baseline "$baseline" --plan "$plan" --directory "$run" \
  --policy zipf --model "$model" --model-digest "$model_digest"
.venv/bin/python -m scripts.run_lexicon_epochs compare \
  --baseline "$baseline" --plan "$plan" --directory "$run"
```

Either arm can resume with the same command and directory. Each intent consumes a typed-question slot before inference begins. Completed responses replay against the same request hash and schema. An interrupted request whose answer was never recorded remains a charged operational refusal. Separate arm locks prevent duplicate writers, and a shared model lock serializes inference.

Each epoch preserves the exact selection, model intent and result, reviewed observation, held-out audit, migration forecast, and replayed candidate. Scope contradictions and changes to previously established cells prevent automatic admission and remain inspectable in the staged report. Admission uses GSE's existing reviewed rule transition. The subsequent epoch reads the validated candidate it produced. The comparison checks whether removing an earlier admitted rule opens a later rule's teaching premise.

The benchmark uses a declared family language with exact WordNet scopes and one signed premise per candidate. It measures selection and composition within that language. Discovery still requires a reviewed typed result and audit evidence independent of the target rule. The source warrant and candidate-language boundaries are in [the scope review](SOURCE_SCOPE.md).
