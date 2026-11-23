# Executed commands

Run from `/Users/rohanvinaik/Projects/gse`. These are historical commands with frozen output identities; use a fresh directory or output filename for any new replay.

Both construction commands exited 0 and made zero model requests:

```sh
.venv/bin/python -m gse.lexicon_builder build --symbolic-only --words afraid fear nervous terrified scared frightened apprehension dread sad concerned sadness pity sorrow --output /private/tmp/gse-diagnosis-symbolic-pre-20261026
.venv/bin/python -m gse.lexicon_builder build --symbolic-only --words afraid fear nervous terrified scared frightened apprehension dread sad concerned sadness pity sorrow --output /private/tmp/gse-diagnosis-symbolic-post-20261026
```

Final evaluator diagnoses both exited 0:

```sh
.venv/bin/python -m gse.lexicon_builder.evaluation diagnose-symbolic --input /private/tmp/gse-diagnosis-symbolic-pre-20261026/sparse.jsonl --gold docs/verification/lexicon-rebuild/closeout-2026-10-25/evidence/template_fields.json --review docs/verification/lexicon-rebuild/diagnosis-2026-10-26/evaluation/evaluation-review-final.json --output docs/verification/lexicon-rebuild/diagnosis-2026-10-26/evaluation/symbolic-ledger-pre-change-final-evaluator.json
.venv/bin/python -m gse.lexicon_builder.evaluation diagnose-symbolic --input /private/tmp/gse-diagnosis-symbolic-post-20261026/sparse.jsonl --gold docs/verification/lexicon-rebuild/closeout-2026-10-25/evidence/template_fields.json --review docs/verification/lexicon-rebuild/diagnosis-2026-10-26/evaluation/evaluation-review-final.json --output docs/verification/lexicon-rebuild/diagnosis-2026-10-26/evaluation/symbolic-ledger-post-change.json
```

The baseline CLI **exited 1 as required by BASELINE_NOT_EXCEEDED**; that outcome is preserved:

```sh
.venv/bin/python -m gse.lexicon_builder.evaluation compare-baselines --input /private/tmp/gse-family-live-v4-20261025/sparse.jsonl --gold docs/verification/lexicon-rebuild/closeout-2026-10-25/evidence/template_fields.json --output docs/verification/lexicon-rebuild/diagnosis-2026-10-26/evaluation/tail-baselines-v4-final.json
```

Final code checks exited 0:

```sh
.venv/bin/python -m pytest tests/test_lexicon_evaluation.py
.venv/bin/ruff check gse/lexicon_builder/evaluation.py tests/test_lexicon_evaluation.py
uvx ty check gse/lexicon_builder/evaluation.py
```

The ty invocation inside a sandboxed subprocess first failed to access the existing uv cache. The direct approved escalated rerun passed; both outcomes are in verification-results.json. The module AST test verifies that the production construction modules do not import this evaluator. No model invocation, gold modification, runtime construction-policy update, commit or push was performed by this evaluation task.
