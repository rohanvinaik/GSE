# Bounded checkpoint worker

`run_bounded_checkpoint.py` prepares no signs, warrants, reviews, or production rules. It executes existing completion machinery only when deliberately launched. The original worker preparation did not call a model or write a database. Subsequent authorized executions are recorded under `quantity-discovery-001/` and `body-zipf-005/`; the latter is followed by the separately recorded intrathecal receipt withdrawal. `final-cycle-verification.json` records the corrected candidate state.

The transport configuration matches `../2026-11-01-lexicon-next-stage/run_body_checkpoint.py`: `qwen3.8:27b-q4_K_M`, installed digest `25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e`, 65,536 context tokens, 1,024 output tokens, thinking disabled, 300-second timeout, temperature zero, and at most four independent word–bank questions per invocation. Model identity is pinned before completion and checked by the existing transport around inference. No source context is truncated.

The worker calls `complete_dictionary(candidate, transport, budget, ...)` with one selected bank, one question per entry, eight-entry cohorts, `priority="zipf"`, `cohort_policy="spelling"`, `bank_priority="evidence"`, and `continue_cohorts=True`. Explicit selection bounds the definition IDs; automatic Zipf selection uses the existing durable schedule. The budget counts bank questions, not transport invocations. Previous unchanged failed attempts are skipped unless `--retry` is explicitly supplied. A new report run ID does not reset request journals.

## Commands

Run from `/Users/rohanvinaik/Projects/gse`. Each command below executes work; none was launched while preparing this worker. Choose a new `--run-id` each time. Reports are created in a new directory beneath this document's directory, and existing run directories are never reused.

Exactly three QUANTITY questions, with a budget of three:

```bash
/Users/rohanvinaik/Projects/SquishOS/ops/agents/bin/owned-run --label gse-quantity-discovery -- uv run python docs/readings/2026-11-01-lexicon-you-body/run_bounded_checkpoint.py --candidate data/lexicon_builder/2026-11-01/constructed-corpus-linear-unit-want.db --run-id quantity-discovery-001 quantity-discovery
```

The definition IDs are `wordnet:in:inch.n.01`, `wordnet:are:are.n.01`, and `wordnet:at:at.n.02`. These are three independent bounded questions. They do not constitute evidence that the entire `unit_of_measurement.n.01` population shares any sign.

Resume up to sixteen QUANTITY questions in Zipf order:

```bash
/Users/rohanvinaik/Projects/SquishOS/ops/agents/bin/owned-run --label gse-quantity-zipf -- uv run python docs/readings/2026-11-01-lexicon-you-body/run_bounded_checkpoint.py --candidate data/lexicon_builder/2026-11-01/constructed-corpus-linear-unit-want.db --run-id quantity-zipf-001 zipf --bank QUANTITY --max-model-calls 16
```

For another selected bank, change `--bank` to an existing bank name after deciding that question scope. Zipf checkpoints accept a budget from one through sixteen; repeated bounded runs preserve the durable scheduling cursor. Spelling frequency is scheduling evidence, not sense frequency or sign authority.

For an explicit set of one through eight definitions, use `selected`; its budget is exactly the number of distinct IDs. For example, this is another way to express the three discovery questions:

```bash
/Users/rohanvinaik/Projects/SquishOS/ops/agents/bin/owned-run --label gse-quantity-selected -- uv run python docs/readings/2026-11-01-lexicon-you-body/run_bounded_checkpoint.py --candidate data/lexicon_builder/2026-11-01/constructed-corpus-linear-unit-want.db --run-id quantity-selected-001 selected --bank QUANTITY --entry-id wordnet:in:inch.n.01 --entry-id wordnet:are:are.n.01 --entry-id wordnet:at:at.n.02
```

Do not run both forms merely to repeat the same questions. `--retry` is a global option placed before the mode, and should be used only for an explicitly intended retry. An optional existing semantic-label file may be passed as `--gold /absolute/path/to/gold.json` for the readiness check; this does not authorize publication.

## Verification and artifacts

The worker reserves a new report directory before work. It saves `plan.json`, `before.json`, `execution.json`, `progress.jsonl`, `completion.json`, `after.json`, `receipts.json`, `assignment-audit.json`, `replay.json`, `publication.json`, `verification.json`, and a file-byte-hash `manifest.json`. Failures produce named error artifacts instead of a success claim. The manifest hashes all completed reports except itself. The plan also records the worker source hash, model configuration, exact selected scope, budget, and active-pointer hash.

Snapshots use query-only read transactions. Accepted receipt bodies are materialized while their database connection is open. The audit checks unchanged definition population, preservation of prior accepted receipts and known domains, exact new receipt-to-cell correspondence, selected-bank/entry scope, and an unchanged active pointer. It conservatively flags any other-bank change for review, including a possible legitimate symbolic consequence; it does not silently authorize broader edits.

`complete_dictionary` performs full preflight replay before model calls or database writes. After completion, the worker calls `validate_build(candidate)` again over the full candidate, then `publication_readiness(candidate, gold_path)`. It also attempts these checks after an ordinary completion exception because earlier valid cells may already have committed. A worker process killed by the owner can leave only partial reports; such a run must not be described as verified. Its durable database journal remains the resumption authority.

An unresolved cell is never assigned zero by this wrapper. A null answer, refusal, invalid response, or scope rejection stays in the underlying completion outcomes. `CHECKPOINT_VERIFIED` means the bounded run passed its mechanical checks; it does not mean the lexicon is complete or the new model receipts have received semantic review. A `PUBLICATION_BLOCKED` result is expected while the whole corpus remains incomplete. No code in this worker invokes `publish_complete` or changes the active pointer, even if readiness later succeeds.

## Separate reviewed-rule workflow

Completion receipts remain model evidence. A source-backed reviewer supplies a distinct hash-bound selection; no routine in this worker invents that review. Existing entry points are:

1. `export_reviewed_input(candidate, selection)` / `uv run python -m scripts.export_lexicon_patterns --candidate CANDIDATE --selection SELECTION.json --input INPUT.json --report EXPORT.json`.
2. `run_workflow(input_path, transport, max_calls=N)` / `uv run python -m scripts.audit_lexicon_patterns --input INPUT.json --report AUDIT.json --model qwen3.8:27b-q4_K_M --max-model-calls N --context-tokens 65536 --output-tokens 1024 --timeout 300 --no-thinking`.
3. After a separately supplied justified rule-admission review: `migrate_rule(candidate, new_output, input_path, audit_path, review)` / `uv run python -m scripts.migrate_lexicon_rule --candidate CANDIDATE --output NEW_CANDIDATE.db --input INPUT.json --audit AUDIT.json --review REVIEW.json --report MIGRATION.json`.

The uppercase file names and `N` in these interface examples are placeholders for actual reviewed artifacts and an explicit bounded budget. Launch these tools through `owned-run` as well. The audit command pins its selected installed model; the checkpoint worker additionally enforces the calibrated digest above. These are separate review/audit/migration entry points, not an automatic continuation of a completion checkpoint. A `selected` completion run is not a substitute for the reviewed rule workflow's independent held-out audit.

The broader measurement ancestor includes disk partitions, bit strings, scoring points, money, and other branch-specific meanings. This preparation admits no broad measurement rule and supplies no QUANTITY sign. Any narrower rule, such as a proposal limited to exact linear-unit senses, still needs its own source-backed warrant, distinct-synset held-out questions, review, and migration.
