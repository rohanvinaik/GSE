# Detective commands for the rule-contract scope

Working directory: `/Users/rohanvinaik/Projects/gse`. Each command used the target repository's `.venv`; no global interpreter was substituted. Commands are recorded in execution order. Outputs are read in full.

```sh
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/python -c 'import Detective, Wesker; print("Detective ->", Detective.__file__); print("Wesker ->", Wesker.__file__)'
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective --help
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective regime
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective converge gse/lexicon_builder/core.py::cli_law_contract > /private/tmp/gse-lexicon-cli-law-contract-detective.log 2>&1
```

The first convergence run requested uncovered-line calls. The complete report was read, and the prescribed rerun supplied these fifteen literal inputs:

```sh
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective converge gse/lexicon_builder/core.py::cli_law_contract --input '({},)' --input '({"law_contract":"ADMITTED_RULEBOOK","laws":[{}]},)' --input '({"law_contract":[]},)' --input '({"law_contract":"invalid"},)' --input '({"law_contract":"DIRECT_CONSTRAINTS"},)' --input '({"laws":None},)' --input '({"laws":[None,{}]},)' --input '({"laws":[{}]},)' --input '({"law_contract":"DIRECT_CONSTRAINTS","laws":[{}]},)' --input '({"law_contract":"DIRECT_CONSTRAINTS","laws":[{"review_state":"CANDIDATE"},{}]},)' --input '({"law_contract":"DIRECT_CONSTRAINTS","laws":[{"lifecycle":"ACTIVE"}]},)' --input '({"law_contract":"DIRECT_CONSTRAINTS","laws":[{"authority":{}}]},)' --input '({"law_contract":"DIRECT_CONSTRAINTS","laws":[{"validation":{}}]},)' --input '({"law_contract":"DIRECT_CONSTRAINTS","laws":[{"may_write_lexical_cells":False}]},)' --input '({"laws":[{"kind":"NATIVE_ASSOCIATION"}]},)' > /private/tmp/gse-lexicon-cli-law-contract-detective-inputs.log 2>&1
```

This run printed STOP / UNGATEABLE because the proof basis changed between measurements. Its output is retained in `detective-cli-inputs-stopped.log`, and its full report in `detective-cli-stopped-report.txt`. The exact prescribed repair was reported to the lead; further Detective work waited for a shared code/test freeze. No surviving mutant was manually flagged equivalent.

After the shared freeze, the same fifteen-input command was repeated with output `/private/tmp/gse-lexicon-cli-law-contract-detective-fixed.log`; its final result was COMPLETE, with the explicit bounds recorded in `RULE_CONTRACTS.md`.

The existing-target revalidation then ran:

```sh
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective audit gse/lexicon_builder/artifact.py::vector_status > /private/tmp/gse-lexicon-detective-artifact-vector-status.log 2>&1
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective audit --help
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective audit gse/lexicon_builder/model.py::selection_status --check > /private/tmp/gse-lexicon-detective-model-selection-status.log 2>&1
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective converge gse/lexicon_builder/model.py::selection_status > /private/tmp/gse-lexicon-detective-model-selection-status-converge.log 2>&1
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective converge gse/lexicon_builder/model.py::selection_status --input "({'_unread': 'x'}, {})" > /private/tmp/gse-lexicon-detective-model-selection-status-input.log 2>&1
```

The artifact audit's `--remove` prescription was explicitly stopped by the lead to preserve authored integration/must-not tests. The model retry prescribed writing an authored assertion rather than repeating the input command; that exact assertion was placed in the existing malformed-decoder-contract test. Before its next prescribed convergence, the lead revoked the shared freeze to fix a real full-source reading-identity defect. No further target was started against a moving basis.

After the corrected shared snapshot was frozen, the remaining commands were:

```sh
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective converge gse/lexicon_builder/model.py::selection_status > /private/tmp/gse-lexicon-detective-model-selection-status-authored.log 2>&1
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective audit gse/lexicon_builder/native_constraints.py::predicate_domain --check > /private/tmp/gse-lexicon-detective-native-predicate-domain.log 2>&1
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective audit gse/lexicon_builder/number.py::paired_order_status --check > /private/tmp/gse-lexicon-detective-number-paired-order.log 2>&1
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective audit gse/lexicon_builder/surprise.py::comparison_status --check > /private/tmp/gse-lexicon-detective-surprise-comparison.log 2>&1
PYTHONPATH=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker .venv/bin/detective audit gse/lexicon_builder/tail.py::tail_task_status --check > /private/tmp/gse-lexicon-detective-tail-task-status.log 2>&1
```

Model convergence printed reproducibility confirmed and DONE / COMPLETE. Each audit reported complete within its stated unproven-equivalent/crash-only bounds. All audit removal paths were stopped under the lead's explicit no-test-removal directive, and every printed bound remains in the receipt. No `flag` or `--remove` command was run.
