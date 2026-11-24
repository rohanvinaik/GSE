# GSE test-suite census (advisory)

Commit `8bfb980`, clean archive at `/tmp/gse-census/tree`, with `data/` symlinked to the live checkout. CPython 3.14.7, pytest 9.1.0. Flags: `-p no:randomly -o addopts=""`. Machine-readable results: `census-candidates.json` beside this file holds every candidate list (committed); the full `census.json` (10.7 MB, per-test timing and per-function data) is kept on disk here and listed in `.gitignore`. Raw run artifacts and the census scripts were in `/tmp/gse-census/` at the time.

**Boundary:** this is an advisory census. It points at things to inspect and certifies nothing as removable. A shared coverage set says nothing about inputs, assertions, side effects or intent, and a static smell carries no correctness authority. Removal goes through Detective and the named obligations.

## 1. Baseline (no plugins)

- Collected: **7707** tests in 293 files, with 0 collection errors. Detective-generated tests: 76.
- Run 1: `1 failed, 7639 passed, 55 skipped, 12 xfailed, 6 warnings in 457.37s (0:07:37)` (process wall 461.67 s).
- Run 2: `1 failed, 7639 passed, 55 skipped, 12 xfailed, 6 warnings in 430.51s (0:07:10)` (process wall 434.59 s).
- Expected failures: 45. Observed: **1** in run 1 and **1** in run 2. Not investigated. Failing test(s):
  - `tests/test_thatless_complement.py::test_guard_no_full_clause_opens_no_complement[I think about the door.-expected2]`: AssertionError: assert {'about': 'as...': 'asserted'} == {'think': 'asserted'} Omitting 1 identical 
- The live `data/lexicon_active.json` pointer (→ `sparse-release-021.db`) and its db's mtime and size were unchanged across every run. No file under the live `data/` changed after the census started.
- Load: run 1 overlapped two foreign full-suite pytest runs for about its second half. During run 2, the 1-minute load average on 10 cores was 10.81–28.92 (mean 15.3, 15 samples). Treat every time as wall-clock under contention.

### Skip / xfail reasons (run 1)

| outcome | count | reason |
|---|---:|---|
| skipped | 15 | spell_entities.db not built |
| skipped | 11 | HDC speller lexicon cache not built |
| skipped | 8 | genealogy.db not built (scripts/build_genealogy_db.py) |
| skipped | 7 | genealogy.db not built |
| skipped | 4 | could not import 'torch': No module named 'torch' |
| skipped | 2 | pre-existing failure since initial commit (9578764); code-only checkout — needs triage vs as-built to_primitives behavio |
| skipped | 1 | pre-existing failure since initial commit (9578764); code-only checkout — needs triage vs as-built build-index behavior |
| skipped | 1 | pre-existing failure since initial commit (9578764); code-only checkout — needs triage vs as-built definition-match beha |
| skipped | 1 | pre-existing failure since initial commit (9578764); code-only checkout — needs triage vs as-built progress-logging beha |
| skipped | 1 | pre-existing failure since initial commit (9578764); code-only checkout — needs triage vs as-built JSON-extract behavior |
| skipped | 1 | pre-existing failure since initial commit (9578764); code-only checkout — needs triage vs as-built parse behavior |
| skipped | 1 | pre-existing failure since initial commit (9578764); code-only checkout — needs triage vs as-built batch-parse behavior |
| skipped | 1 | Integration: run with Regenesis on PYTHONPATH |
| skipped | 1 | Wiktionary wordlist and frequency.db not both built |
| xfailed | 2 | #82 F-plural-verb: a base verb after a noun subject is tagged NOUN |
| xfailed | 1 | #76 F-passive: 's before a passive participle reads as has |
| xfailed | 1 | #85 F-tense: an irregular past carries no tense |
| xfailed | 1 | #103 E-tam: no future or question mark is ever emitted |
| xfailed | 1 | #103 E-tam: no imperative mark is ever emitted |
| xfailed | 1 | #76 F-passive: a passive carries no voice mark |
| xfailed | 1 | #84 F-oov-verb: an unknown word is never a verb |
| xfailed | 1 | #83 F-promote: a compound member is promoted to a verb |
| xfailed | 1 | #92 F-closed-gaps: degree 'so' is read as a consequence link |
| xfailed | 1 | #100 E-if-when: 'wonder if' is read as a conditional |
| xfailed | 1 | #101 E-fronted: a fronted 'if' without a comma gives a one-armed conditional |

## 2. Cost

| measure | run 1 | run 2 | per-test min |
|---|---:|---:|---:|
| Σ junit time (s) | 451.42 | 422.32 | 390.76 |
| Σ setup (s) | 45.49 | 44.47 | 39.93 |
| Σ call (s) | 400.61 | 372.54 | 345.9 |
| Σ teardown (s) | 0.06 | 0.03 | 0.03 |
| process wall (s) | 461.67 | 434.59 | – |

Per-test time buckets (min): <0.01s: 6086 tests / 4.04 s, 0.01-0.1s: 1068 tests / 37.81 s, 0.1-1s: 512 tests / 133.75 s, 1-10s: 33 tests / 89.19 s, >=10s: 8 tests / 125.97 s

### 30 slowest tests (per-test min of the two runs; setup/call/teardown from the run that was faster)

| # | total s | setup | call | teardown | run1 | run2 | test |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 37.34 | 0.00 | 37.34 | 0.00 | 46.97 | 37.34 | `tests/test_spellcheck.py::test_deterministic` |
| 2 | 15.72 | 0.00 | 15.72 | 0.00 | 15.72 | 18.32 | `tests/test_lexical_healing_contract.py::test_standalone_cli_shares_exact_source_and_ledger` |
| 3 | 12.67 | 0.00 | 12.67 | 0.00 | 16.58 | 12.67 | `tests/test_spellcheck.py::test_committed_word_always_grounds` |
| 4 | 12.67 | 0.00 | 12.67 | 0.00 | 15.40 | 12.67 | `tests/test_spellcheck.py::test_injected_candidate_must_ground` |
| 5 | 12.45 | 0.00 | 12.44 | 0.00 | 12.85 | 12.45 | `tests/test_lexicon_builder_runtime.py::test_negative_prefix_cannot_overwrite_an_explicit_zero[happy-unhappy]` |
| 6 | 12.37 | 0.00 | 12.37 | 0.00 | 14.91 | 12.37 | `tests/test_spellcheck.py::test_confusion_injects_beyond_edit2` |
| 7 | 12.37 | 0.33 | 12.04 | 0.00 | 12.37 | 14.19 | `tests/test_GSE_demiword.py::test_compound_proper_name_is_one_demiword` |
| 8 | 10.38 | 0.09 | 10.29 | 0.00 | 12.41 | 10.38 | `tests/test_runtime_native_composed_controls.py::test_spatial_opposites_reach_query_and_emitted_contract` |
| 9 | 8.87 | 0.00 | 8.87 | 0.00 | 9.77 | 8.87 | `tests/test_spellcheck.py::test_hyphenated_compound_never_mangled[set-theory]` |
| 10 | 6.84 | 0.14 | 6.70 | 0.00 | 9.13 | 6.84 | `tests/test_rohan_voice_v2.py::test_real_cli_uses_named_manifest_and_reports_refit_without_dense` |
| 11 | 6.80 | 2.11 | 4.68 | 0.00 | 8.25 | 6.80 | `tests/test_lexicon_021_prefetch.py::test_preview_is_identical_to_real_post_enrichment_question_and_never_writ…` |
| 12 | 6.63 | 0.00 | 6.63 | 0.00 | 7.92 | 6.63 | `tests/test_lexicon_builder_source_enrichment.py::test_real_wordnet_exception_context_is_verified_without_assi…` |
| 13 | 5.85 | 5.85 | 0.00 | 0.00 | 5.85 | 6.81 | `tests/test_GSE_curation_external_sources_wordnet_hierarchy.py::TestToPrimitives::test_unknown_empty` |
| 14 | 4.90 | 0.00 | 4.90 | 0.00 | 4.90 | 5.22 | `tests/test_lexicon_builder_defining_genus.py::test_real_enrichment_cli_rechecks_native_genus_and_preserves_al…` |
| 15 | 3.41 | 0.00 | 3.41 | 0.00 | 3.50 | 3.41 | `tests/test_audit_lexicon_runtime.py::test_audit_exercises_approved_degree_vectors_and_leaves_database_unchang…` |
| 16 | 3.40 | 0.00 | 3.40 | 0.00 | 3.40 | 3.41 | `tests/test_data_paths.py::test_decoder_default_lexicon_from_another_directory` |
| 17 | 3.37 | 0.00 | 3.37 | 0.00 | 3.60 | 3.37 | `tests/test_lexicon_builder_completion_cohorts.py::test_huge_call_budget_keeps_default_cohort_bounded_and_resu…` |
| 18 | 3.14 | 0.00 | 3.14 | 0.00 | 4.05 | 3.14 | `tests/test_spellcheck.py::test_no_grounded_candidate_abstains` |
| 19 | 2.88 | 0.00 | 2.88 | 0.00 | 3.23 | 2.88 | `tests/test_lexicon_builder_prime_linkage.py::test_all_foundation_links_build_and_replay_with_native_sources` |
| 20 | 2.88 | 0.00 | 2.88 | 0.00 | 3.76 | 2.88 | `tests/test_lexicon_epoch.py::test_two_generations_replay_and_resume_at_equal_budget` |
| 21 | 2.40 | 2.40 | 0.00 | 0.00 | 2.40 | 2.42 | `tests/test_lexicon_builder_defining_genus.py::test_complete_ancestry_is_context_only_and_legacy_packet_stays_…` |
| 22 | 2.37 | 0.00 | 2.37 | 0.00 | 2.54 | 2.37 | `tests/test_lexicon_epoch.py::test_equal_budget_comparison_consumes_discovered_inventory_and_actual_teaching_c…` |
| 23 | 2.03 | 0.00 | 2.03 | 0.00 | 2.03 | 2.21 | `tests/test_lexical_healing_contract.py::test_mcp_and_direct_healing_have_identical_text_and_ledgers` |
| 24 | 1.81 | 0.00 | 1.81 | 0.00 | 1.81 | 1.95 | `tests/test_GSE_benchmarks_datasets.py::TestGetAllDatasets::test_returns_dict_with_custom` |
| 25 | 1.70 | 0.10 | 1.60 | 0.00 | 1.70 | 1.82 | `tests/test_GSE_api_encoder.py::TestEncode::test_returns_operation_trace` |
| 26 | 1.65 | 0.00 | 1.65 | 0.00 | 1.65 | 9.80 | `tests/test_lexical_healing_contract.py::test_healing_preserves_every_unaffected_utf8_byte_and_guards` |
| 27 | 1.62 | 0.00 | 1.62 | 0.00 | 1.62 | 1.81 | `tests/test_GSE_benchmarks_datasets.py::TestLoadStsBenchmark::test_missing_returns_empty` |
| 28 | 1.48 | 0.00 | 1.48 | 0.00 | 1.84 | 1.48 | `tests/test_lexicon_epoch.py::test_open_bank_discovery_review_audit_and_replay_resume_under_the_same_plan` |
| 29 | 1.45 | 0.00 | 1.44 | 0.00 | 1.62 | 1.45 | `tests/test_lexicon_learning_questions.py::test_full_bank_questions_share_source_and_proof_records_and_restore…` |
| 30 | 1.42 | 0.00 | 1.42 | 0.00 | 1.54 | 1.42 | `tests/test_lexicon_epoch.py::test_constraint_only_rule_is_taught_audited_admitted_and_replayed` |

### 20 slowest files (Σ per-test min)

| # | total s | tests | setup | call | file |
|---:|---:|---:|---:|---:|---|
| 1 | 88.8 | 44 | 0.0 | 88.7 | `tests/test_spellcheck.py` |
| 2 | 19.6 | 18 | 0.0 | 19.6 | `tests/test_lexical_healing_contract.py` |
| 3 | 16.1 | 36 | 2.4 | 13.7 | `tests/test_lexicon_builder_runtime.py` |
| 4 | 14.6 | 143 | 0.0 | 14.5 | `tests/test_lexicon_epoch.py` |
| 5 | 12.5 | 7 | 0.3 | 12.2 | `tests/test_GSE_demiword.py` |
| 6 | 12.0 | 30 | 0.1 | 11.9 | `tests/test_runtime_native_composed_controls.py` |
| 7 | 11.2 | 31 | 0.0 | 11.2 | `tests/test_lexicon_builder_reconsideration.py` |
| 8 | 9.8 | 12 | 0.7 | 9.1 | `tests/test_rohan_voice_v2.py` |
| 9 | 7.4 | 22 | 0.0 | 7.3 | `tests/test_lexicon_builder_source_enrichment.py` |
| 10 | 7.3 | 9 | 2.4 | 4.9 | `tests/test_lexicon_builder_defining_genus.py` |
| 11 | 6.9 | 8 | 0.0 | 6.9 | `tests/test_lexicon_learning_recovery.py` |
| 12 | 6.8 | 1 | 2.1 | 4.7 | `tests/test_lexicon_021_prefetch.py` |
| 13 | 6.2 | 10 | 2.0 | 4.2 | `tests/test_lexicon_builder_publication.py` |
| 14 | 6.1 | 46 | 5.4 | 0.7 | `tests/test_lexicon_builder_degree_runtime.py` |
| 15 | 5.9 | 92 | 5.8 | 0.0 | `tests/test_GSE_curation_external_sources_wordnet_hierarchy.py` |
| 16 | 5.5 | 77 | 0.0 | 5.5 | `tests/test_copula_complement.py` |
| 17 | 5.5 | 39 | 3.3 | 2.1 | `tests/test_GSE_api_encoder.py` |
| 18 | 5.0 | 9 | 0.0 | 5.0 | `tests/test_lexicon_builder_delayed_questions.py` |
| 19 | 4.0 | 35 | 0.0 | 4.0 | `tests/test_complete_document_reading.py` |
| 20 | 3.9 | 8 | 0.0 | 3.9 | `tests/test_lexicon_builder_reviewed_history.py` |

## 3. Coverage per test

Instrument: pytest-cov 7.1.0 and coverage 7.17.5, with `--cov=GSE --cov-branch --cov-context=test` and **`COVERAGE_CORE=ctrace`**. On 3.14 the default `sys.monitoring` core recorded first-hit-only attribution in a pilot (mean 1.004 contexts per arc, 20 of 65 tests present). Under ctrace the mean was 4.15 per arc, up to 30, with every code-reaching test present.

- Measured 266 GSE files. 41763 distinct arcs and 29227 lines are attributed to tests.
- 16493 arc rows fall in the empty context (import and collection time, not credited to any test).
- Coverage-run outcome: `1 failed, 7635 passed, 55 skipped, 4 deselected, 12 xfailed, 1074 warnings in 1152.18s (0:19:12)`. Per-test outcomes match run 1 except the 4 deselected tests.
- **Instrument interaction:** 4 tests replace `sqlite3.connect` with a function that asserts `?mode=ro` or fails. Coverage's per-phase flush to its SQLite file hits the patch. The first attempt ended in INTERNALERROR with 5,959 cascading errors. These 4 were deselected for coverage only and are **UNMEASURED** for reach:
  - `tests/test_lexicon_builder_evaluation.py::test_readonly_connection_closes_on_success_and_error[False]`
  - `tests/test_lexicon_builder_evaluation.py::test_readonly_connection_closes_on_success_and_error[True]`
  - `tests/test_lexicon_builder_representation.py::test_superseded_modifier_writer_rejects_before_opening_database`
  - `tests/test_lexicon_builder_representation.py::test_modifier_dry_run_uses_a_read_only_connection`
- JSON export (`coverage json --show-contexts`, 879 MB): per-test line sets match the arc-derived lines from the db for all 7104 tests with lines (0 mismatches).
- Eligible for the lists below: 7635 tests that passed in both runs. Excluded: 13 failed or xfailed (truncated reach), 55 skipped (never ran), 4 unmeasured.
- Unit: **arcs** (file, from, to). A test's reach is the union of its setup, run and teardown contexts. Reach depends on order: module- and class-scoped fixtures and caches credit their code to the first test that triggers them.

### 3a. Identical reach across different test functions: 693 clusters, 2382 tests

Pointers for inspection, not duplicates. Clusters by arc count: {'1-5': 87, '6-20': 229, '21-100': 254, '101-1000': 97, '>1000': 26}. Clusters spanning more than one file: 65.

Top 15 by number of shared arcs:

| arcs | tests | files | members (first 3) |
|---:|---:|---:|---|
| 3101 | 2 | 1 | `tests/test_rohan_voice_v2.py::test_manifest_fit_grades_holdout_per_class_and_never_trains_on_it`<br>`tests/test_rohan_voice_v2.py::test_recognition_retains_per_class_grade_and_rejects_forged_overlap` |
| 2232 | 2 | 1 | `tests/test_lexicon_builder_validation.py::test_candidate_evidence_tampering_is_reported[missing]`<br>`tests/test_lexicon_builder_validation.py::test_candidate_summary_tampering_is_reported[counts]` |
| 2169 | 2 | 1 | `tests/test_reading_probes_ring2.py::test_a_negated_matrix_keeps_its_complement`<br>`tests/test_reading_probes_ring2.py::test_a_negation_negates_the_node_that_takes_its_sign[She doesn't know that the door…` |
| 2058 | 2 | 2 | `tests/test_reading_probes_ring2.py::test_a_negation_negates_the_node_that_takes_its_sign[Mike's dog isn't cuter than Re…`<br>`tests/test_sign_composition.py::test_one_sign_on_a_comparison_negates_it` |
| 1848 | 2 | 1 | `tests/test_symbolic_templating.py::TestStructurePreservation::test_substitution_preserves_logical_shape`<br>`tests/test_symbolic_templating.py::TestStructurePreservation::test_swap_produces_argument_swap_when_args_are_swapped` |
| 1846 | 2 | 1 | `tests/test_lexicon_builder_catalog_refresh.py::test_corrupt_dictionary_cannot_be_relabelled_by_catalog_upgrade`<br>`tests/test_lexicon_builder_catalog_refresh.py::test_stale_catalog_repair_never_bypasses_authoritative_state_failure[pub…` |
| 1814 | 2 | 1 | `tests/test_lexicon_builder_validation.py::test_assertion_exact_native_provenance_is_required[source-forged]`<br>`tests/test_lexicon_builder_validation.py::test_missing_native_record_is_not_self_authorizing` |
| 1813 | 3 | 1 | `tests/test_lexicon_builder_validation.py::test_conflict_hierarchy_is_not_published`<br>`tests/test_lexicon_builder_validation.py::test_hierarchy_requires_known_nonzero_base_and_integer_level[hierarchy0]`<br>`tests/test_lexicon_builder_validation.py::test_hierarchy_requires_known_nonzero_base_and_integer_level[hierarchy1]` |
| 1811 | 2 | 1 | `tests/test_lexicon_builder_validation.py::test_missing_explicit_zero_is_a_published_mismatch`<br>`tests/test_lexicon_builder_validation.py::test_unresolved_bank_cannot_be_materialized_as_zero` |
| 1792 | 4 | 1 | `tests/test_lexicon_builder_conventions.py::test_classified_unknown_size_blocks_absence_without_inventing_value`<br>`tests/test_lexicon_builder_conventions.py::test_known_size_is_preserved_without_default_fallback_exception[-1]`<br>`tests/test_lexicon_builder_conventions.py::test_known_size_is_preserved_without_default_fallback_exception[0]` |
| 1776 | 3 | 1 | `tests/test_lexicon_builder_catalog_refresh.py::test_cli_rejects_incompatible_catalog_flags[arguments0-CATALOG_APPLY_REQ…`<br>`tests/test_lexicon_builder_catalog_refresh.py::test_cli_rejects_incompatible_catalog_flags[arguments1-CATALOG_INVENTORY…`<br>`tests/test_lexicon_builder_catalog_refresh.py::test_real_cli_previews_applies_and_still_reads_saved_catalog` |
| 1719 | 2 | 1 | `tests/test_symbolic_templating.py::TestEdgeCases::test_empty_mapping_no_op`<br>`tests/test_symbolic_templating.py::TestEdgeCases::test_no_match_returns_equivalent_tree` |
| 1567 | 3 | 1 | `tests/test_symbolic_expression.py::TestFromTraceAllCompOperators::test_operator_lifts_with_correct_label[Mike is taller…`<br>`tests/test_symbolic_expression.py::TestFromTraceComparisonOperator::test_than_args_have_mike_and_rex`<br>`tests/test_symbolic_expression.py::TestFromTraceComparisonOperator::test_than_lifts_to_set_diff_op` |
| 1427 | 2 | 1 | `tests/test_comp_operator_trace.py::TestOperatorTracePerComp::test_trace_records_correct_arity[COMP_HOW]`<br>`tests/test_comp_operator_trace.py::TestOperatorTracePerComp::test_trace_records_correct_operation_label[COMP_HOW]` |
| 1416 | 2 | 1 | `tests/test_comp_operator_trace.py::TestOperatorTracePerComp::test_trace_records_correct_arity[COMP_THAN]`<br>`tests/test_comp_operator_trace.py::TestOperatorTracePerComp::test_trace_records_correct_operation_label[COMP_THAN]` |

Provenance: 17 cross-function clusters include Detective-generated tests (5 entirely generated; 35 generated tests in total). The rest are authored.


Separately, 289 clusters (1151 tests) are cases of a single parametrized function reaching identical arcs, i.e. the same code with different inputs.

### 3b. Reach strictly contained in another test of the same file: 2497 tests

For 2239 of these, at least one container is a different test function; for the rest, only a parametrize sibling contains them. A small unit test inside a large integration test's reach is the expected shape, and containment says nothing about what is asserted.

Setup-arc check: if only run-phase arcs are compared (dropping setup and teardown, where shared-fixture setup is credited to a module's first test), 2429 of the 2497 are still strictly contained, 2197 of them by a non-sibling. Generated (tests/detective) entries: 7.

Top 15 (largest contained reach with a non-sibling container):

| arcs | smallest container arcs | containers | test → smallest container |
|---:|---:|---:|---|
| 4864 | 7366 | 2 | `tests/test_lexicon_epoch.py::test_open_bank_curriculum_runs_through_the_public_epoch_entry_point`<br>→ `tests/test_lexicon_epoch.py::test_equal_budget_comparison_consumes_discovered_inventory_and_actual_…` |
| 4673 | 5057 | 1 | `tests/test_lexicon_builder_source_guard_migration.py::test_source_guard_end_to_end_archives_only_ex…`<br>→ `tests/test_lexicon_builder_source_guard_migration.py::test_new_receipts_and_reconsideration_replay_…` |
| 4651 | 4660 | 4 | `tests/test_lexicon_builder_source_guard_migration.py::test_historical_homograph_receipt_uses_origin…`<br>→ `tests/test_lexicon_builder_source_guard_migration.py::test_tampered_historical_request_context_is_r…` |
| 4524 | 4525 | 4 | `tests/test_lexicon_builder_rule_migration_integrity.py::test_report_symlink_created_after_preflight…`<br>→ `tests/test_lexicon_builder_rule_migration_integrity.py::test_new_unreviewed_model_context_is_archiv…` |
| 3712 | 3728 | 1 | `tests/test_lexicon_checkpoint_reference_migration.py::test_projection_refuses_model_prefix_and_chan…`<br>→ `tests/test_lexicon_checkpoint_reference_migration.py::test_real_retirement_then_source_projection_r…` |
| 3447 | 3451 | 1 | `tests/test_lexicon_builder_reconsideration.py::test_cli_repeated_roots_use_atomic_batch_path`<br>→ `tests/test_lexicon_builder_reconsideration.py::test_batch_uses_one_preflight_coalesces_same_entry_a…` |
| 3432 | 3436 | 2 | `tests/test_lexicon_builder_reconsideration.py::test_real_cli_defaults_to_dry_run_and_requires_expli…`<br>→ `tests/test_lexicon_builder_reconsideration.py::test_expected_snapshot_refuses_new_valid_suffix` |
| 3428 | 3432 | 4 | `tests/test_lexicon_builder_reconsideration.py::test_withdrawing_first_receipt_removes_entire_model_…`<br>→ `tests/test_lexicon_builder_reconsideration.py::test_real_cli_defaults_to_dry_run_and_requires_expli…` |
| 3420 | 3579 | 1 | `tests/test_lexicon_builder_publication_scope.py::test_incomplete_historical_reference_ruling_blocks…`<br>→ `tests/test_lexicon_builder_publication_scope.py::test_actual_cli_reports_scope_block_even_when_inco…` |
| 3101 | 3104 | 1 | `tests/test_rohan_voice_v2.py::test_manifest_fit_grades_holdout_per_class_and_never_trains_on_it`<br>→ `tests/test_rohan_voice_v2.py::test_legacy_and_resource_changed_models_require_refit` |
| 3101 | 3104 | 1 | `tests/test_rohan_voice_v2.py::test_recognition_retains_per_class_grade_and_rejects_forged_overlap`<br>→ `tests/test_rohan_voice_v2.py::test_legacy_and_resource_changed_models_require_refit` |
| 3037 | 3078 | 16 | `tests/test_lexicon_builder_reconsideration.py::test_cli_refuses_database_hardlink_report`<br>→ `tests/test_lexicon_builder_reconsideration.py::test_changed_preflight_snapshot_refused` |
| 3015 | 3017 | 1 | `tests/test_lexicon_builder_completion_zipf.py::test_new_known_value_moving_priority_before_cursor_d…`<br>→ `tests/test_lexicon_builder_completion_zipf.py::test_later_finished_batch_entry_cannot_hide_earlier_…` |
| 3011 | 3015 | 2 | `tests/test_lexicon_builder_completion_zipf.py::test_explicit_per_entry_cap_still_visits_partial_def…`<br>→ `tests/test_lexicon_builder_completion_zipf.py::test_new_known_value_moving_priority_before_cursor_d…` |
| 2934 | 2946 | 1 | `tests/test_lexicon_builder_completion_zipf.py::test_explicit_per_entry_cap_still_visits_partial_def…`<br>→ `tests/test_lexicon_builder_completion_zipf.py::test_new_known_value_moving_priority_before_cursor_d…` |

### 3c. Passing tests that reached no GSE line during their own phases: 545

This does **not** mean they test nothing in GSE. Import-time code is not credited to tests, and dataclass-generated methods have no measured source lines. Sampled untagged cases (e.g. `test_GSE_lexicon_function_words.py`, `test_symbolic_walker_parity.py`) read module-level tables or construct dataclasses. Tests that hit caches warmed by earlier tests, run child processes, or exercise `scripts/` also land here. The causes were not classified test by test. Tags:

- file_imports_scripts(outside --cov=GSE): 71
- file_has_no_GSE_import: 68
- requests_shared_scope_fixture(order-dependent attribution): 18
- file_imports_subprocess(child process unmeasured: UNMEASURED): 15
- test_body_uses_subprocess_or_sys.executable(child process unmeasured: UNMEASURED): 8
- no_assertion_static: 1
- untagged: 425
- generated (tests/detective): 0

Files with the most zero-reach tests: `tests/test_GSE_lexicon_function_words.py` (27), `tests/test_scale_definition.py` (27), `tests/test_GSE_curation_constraint_aggregation_types.py` (25), `tests/test_GSE_curation_schema.py` (25), `tests/test_serialization_field_completeness.py` (23), `tests/test_symbolic_walker_parity.py` (20), `tests/test_GSE_curation_llm_prompts.py` (18), `tests/test_GSE_lexicon_pronouns.py` (16), `tests/test_lexicon_coherence.py` (16), `tests/test_lexicon_evaluation_readiness.py` (16), `tests/test_GSE_composition_composer.py` (15), `tests/test_GSE_curation_external_sources_verbnet.py` (14)

Also, 20 tests reach GSE code only in setup or teardown, with an empty run phase.

## 4. Static checks (AST)

Scope: tests/**/*.py outside archive dirs (295 files: 273 in tests/, 22 in tests/detective [generated]); pytest default naming (test* functions, Test* classes). 5259 test functions, 40 of them generated.

### 4a. No assertion: 21 functions, all authored

Criterion: no `assert`, no `raises`/`warns`/`approx`, and no call to `assert*`/`check*` anywhere in the body. 15 of the 21 names contain safe/no_op/noop/no_crash/no_raise/continues/without, so they read as completes-without-raising checks.

- `tests/test_GSE_cli_main.py:329` TestCmdInteractive::test_empty_line_continues
- `tests/test_GSE_curation_cli_commands.py:71` TestPrintStatus::test_no_rate_for_zero_total
- `tests/test_GSE_curation_external_sources_conceptnet.py:554` TestClose::test_no_conn_safe
- `tests/test_GSE_curation_external_sources_integrator.py:405` TestClose::test_without_db
- `tests/test_GSE_curation_external_sources_wiktionary.py:116` TestCreateDatabase::test_creates_table
- `tests/test_GSE_curation_external_sources_wiktionary.py:452` TestClose::test_no_conn_safe
- `tests/test_GSE_curation_frequency_integration.py:236` TestGetDefaultPath::test_returns_existing_gse_data_path
- `tests/test_GSE_curation_lexicon_db.py:171` TestUpdateLexeme::test_no_op_when_all_none
- `tests/test_GSE_curation_llm_batch_processor.py:102` TestLogProgress::test_calculates_percentage
- `tests/test_GSE_curation_llm_batch_processor.py:111` TestLogProgress::test_zero_total_safe (marked skip)
- `tests/test_GSE_curation_llm_ollama_client.py:180` TestPullModel::test_zero_returncode_no_raise
- `tests/test_GSE_curation_llm_primitive_matcher.py:392` TestClose::test_without_conn_safe
- `tests/test_GSE_curation_llm_qwen_client.py:133` TestUnload::test_safe_when_already_none
- `tests/test_GSE_curation_llm_qwen_client.py:147` TestMockQwenClient::test_load_noop
- `tests/test_GSE_curation_llm_qwen_client.py:151` TestMockQwenClient::test_unload_noop
- `tests/test_GSE_curation_pipeline_staged_builder.py:123` TestInit::test_default_freq_db_uses_helper
- `tests/test_GSE_emit_contract.py:92` test_emit_is_total_over_all_demo_sentences
- `tests/test_GSE_entity_refs.py:123` test_v2_contract_is_json_safe
- `tests/test_GSE_merkle_learning_bridge.py:265` TestTrainFromTree::test_no_lexemes_no_crash
- `tests/test_GSE_profiles_profile_manager.py:208` TestSaveActiveProfile::test_no_active_no_op
- `tests/test_GSE_profiles_profile_manager.py:273` TestDeleteProfile::test_nonexistent_no_op

### 4b. Body only `pass`/docstring, or ending in bare `pass`: 0

### 4c. Identical bodies

- **Exact** (body AST without docstring; decorators excluded): 18 clusters, 39 functions. 7 of these clusters contain parametrized members, which run different inputs. 12 span files, where a module-local helper of the same name can differ.
  - size 3, 1 stmt(s): `tests/test_GSE_curation_constraint_aggregation_conflict_detector.py:53::TestBipolarPairs::test_good_bad_present`; `tests/test_GSE_curation_llm_primitive_matcher.py:64::TestConstants::test_good_bad_in_bipolar`; `tests/test_GSE_curation_schema.py:79::TestBipolarPairs::test_good_bad_pair`
  - size 3, 1 stmt(s): `tests/test_GSE_curation_llm_primitive_matcher.py:61::TestConstants::test_bipolar_pair_count`; `tests/test_GSE_curation_llm_primitive_sweep.py:56::TestConstants::test_bipolar_pair_count`; `tests/test_GSE_curation_schema.py:76::TestBipolarPairs::test_count_is_14`
  - size 3, 1 stmt(s) [parametrized]: `tests/test_spellcheck.py:129::test_acronym_never_mangled`; `tests/test_spellcheck.py:134::test_hyphenated_compound_never_mangled`; `tests/test_spellcheck.py:139::test_contraction_never_mangled`
  - size 2, 5 stmt(s): `tests/test_GSE_merkle_hash_chain.py:99::TestMembershipProof::test_valid_proof_verifies`; `tests/test_GSE_merkle_hash_chain.py:134::TestMembershipProof::test_right_sibling_position`
  - size 2, 4 stmt(s): `tests/test_GSE_curation_llm_gap_filler.py:101::TestGetSinglePrompt::test_includes_answer_options`; `tests/test_GSE_curation_llm_primitive_matcher.py:127::TestGetSinglePrompt::test_includes_answer_options`
  - size 2, 4 stmt(s): `tests/test_GSE_parsing_graph.py:361::TestPrettyPrint::test_negation_marker`; `tests/test_GSE_parsing_graph.py:480::TestPrettyPrintLiterals::test_negation_marker_exact`
  - size 2, 3 stmt(s): `tests/test_GSE_encoders_paragraph_structure_encoder.py:365::TestBindBundle::test_bundle_empty_returns_zeros`; `tests/test_GSE_encoders_text_structure_encoder.py:254::TestBundle::test_empty_returns_zeros`
  - size 2, 3 stmt(s): `tests/test_GSE_encoders_paragraph_structure_encoder.py:370::TestBindBundle::test_bundle_thresholding`; `tests/test_GSE_encoders_text_structure_encoder.py:259::TestBundle::test_threshold_applied`
  - size 2, 3 stmt(s) [parametrized]: `tests/test_lexicon_builder_grammatical_definitions.py:127::test_unattached_chemical_words_negation_and_questions_do_not_veto_pronoun`; `tests/test_runtime_native_identity_controls.py:30::test_broad_ancestor_or_unasserted_type_cannot_veto_person_reference`
  - size 2, 2 stmt(s): `tests/test_GSE_curation_validation_bipolar_validator.py:37::TestValidate::test_empty_decomposition_passes`; `tests/test_GSE_curation_validation_hierarchy_validator.py:28::TestValidate::test_empty_passes`
- **Normalized** (names and literals replaced): 337 clusters, 1123 functions. Functions in clusters by body length (statements): {'1': 464, '2': 289, '4': 110, '3': 187, '5': 47, '6+': 26}. These are shape similarities. 753 of the 1123 functions have 1–2-statement bodies. Top 5 by size × statements:
  - size 8, 4 stmts, 1 file(s): `tests/test_GSE_curation_llm_response_parser.py:407::TestDecompositionToVectorFormat::test_assigns_evaluation_role_for_bank_2`; `tests/test_GSE_curation_llm_response_parser.py:424::TestDecompositionToVectorFormat::test_bank_0_entity_role`; `tests/test_GSE_curation_llm_response_parser.py:431::TestDecompositionToVectorFormat::test_bank_1_quantity_role` …
  - size 7, 4 stmts, 1 file(s): `tests/test_GSE_curation_llm_hybrid_builder.py:106::TestFastMatchBipolar::test_response_a`; `tests/test_GSE_curation_llm_hybrid_builder.py:112::TestFastMatchBipolar::test_response_b`; `tests/test_GSE_curation_llm_hybrid_builder.py:118::TestFastMatchBipolar::test_response_neither` …
  - size 26, 1 stmts, 7 file(s): `tests/test_GSE_curation_external_sources_framenet.py:85::TestFrameToPrimitive::test_cognition`; `tests/test_GSE_curation_external_sources_framenet.py:102::TestFEToPrimitive::test_goal_toward`; `tests/test_GSE_curation_external_sources_lancaster_sensorimotor.py:77::TestDimensionToPrimitive::test_interoceptive_inside` …
  - size 25, 1 stmts, 7 file(s): `tests/test_GSE_curation_llm_response_parser.py:190::TestNormalizePrimitiveName::test_unknown_returns_none`; `tests/test_GSE_curation_schema.py:157::TestIsBipolarPrimitive::test_bipolar_true`; `tests/test_GSE_curation_schema.py:160::TestIsBipolarPrimitive::test_non_bipolar_false` …
  - size 5, 5 stmts, 3 file(s): `tests/test_GSE_curation_external_sources_lancaster_sensorimotor.py:208::TestLoad::test_lowercases_word`; `tests/test_GSE_curation_external_sources_nrc_emotion.py:130::TestLoad::test_skips_blank_lines`; `tests/test_GSE_curation_external_sources_nrc_emotion.py:153::TestLoad::test_lowercases_word` …

### 4d. Test files whose GSE imports are only the experiment stack: 29 files, 1054 tests, 4.79 s (per-test min)

| file | tests | s | GSE imports |
|---|---:|---:|---|
| `tests/test_GSE_benchmarks_datasets.py` | 34 | 3.44 | GSE.benchmarks.datasets |
| `tests/test_GSE_merkle_learning_bridge.py` | 29 | 0.29 | GSE.merkle.learning_bridge, GSE.merkle.nodes, GSE.merkle.tree |
| `tests/test_GSE_curation_pipeline_staged_builder.py` | 23 | 0.28 | GSE.curation.pipeline.staged_builder |
| `tests/test_GSE_teaching_teacher.py` | 38 | 0.12 | GSE.profiles.profile_manager, GSE.teaching.teacher |
| `tests/test_GSE_merkle_translator.py` | 20 | 0.12 | GSE.merkle.nodes, GSE.merkle.translator, GSE.merkle.tree |
| `tests/test_GSE_profiles_profile_manager.py` | 34 | 0.11 | GSE.profiles.profile_manager |
| `tests/test_GSE_curation_llm_gap_filler.py` | 48 | 0.10 | GSE.curation.llm.gap_filler |
| `tests/test_GSE_benchmarks_metrics.py` | 34 | 0.08 | GSE.benchmarks.metrics |
| `tests/test_GSE_curation_llm_primitive_sweep.py` | 48 | 0.08 | GSE.curation.llm.primitive_sweep |
| `tests/test_GSE_curation_llm_primitive_matcher.py` | 58 | 0.07 | GSE.curation.llm.primitive_matcher |
| `tests/test_benchmark_runner.py` | 10 | 0.03 | GSE.benchmarks.datasets, GSE.benchmarks.run |
| `tests/test_GSE_teaching_conversation_processor.py` | 47 | 0.02 | GSE.teaching.conversation_processor |
| `tests/test_GSE_curation_llm_batch_processor.py` | 37 | 0.01 | GSE.curation.llm.batch_processor |
| `tests/test_GSE_merkle_tree.py` | 67 | 0.01 | GSE.merkle.nodes, GSE.merkle.tree |
| `tests/test_orchestrator.py` | 12 | 0.01 | GSE.patterns |
| `tests/test_GSE_patterns_networks_v2.py` | 37 | 0.00 | GSE.patterns.networks_v2 |
| `tests/test_GSE_curation_constraint_aggregation_engine.py` | 45 | 0.00 | GSE.curation.constraint_aggregation.engine, GSE.curation.constraint_aggregation.types |
| `tests/test_GSE_patterns_klines.py` | 32 | 0.00 | GSE.patterns.klines |
| `tests/test_GSE_teaching_feature_extractor.py` | 48 | 0.00 | GSE.teaching.feature_extractor |
| `tests/test_GSE_curation_constraint_aggregation_types.py` | 60 | 0.00 | GSE.curation.constraint_aggregation.types |
| `tests/test_GSE_curation_validation_hierarchy_validator.py` | 15 | 0.00 | GSE.curation.validation.hierarchy_validator |
| `tests/test_GSE_curation_constraint_aggregation_conflict_detector.py` | 46 | 0.00 | GSE.curation.constraint_aggregation.conflict_detector, GSE.curation.constraint_aggregation.types |
| `tests/test_GSE_curation_constraint_aggregation_mapping_registry.py` | 44 | 0.00 | GSE.curation.constraint_aggregation.mapping_registry, GSE.curation.constraint_aggregation.types |
| `tests/test_GSE_curation_constraint_aggregation_scoring.py` | 34 | 0.00 | GSE.curation.constraint_aggregation.scoring, GSE.curation.constraint_aggregation.types |
| `tests/test_GSE_curation_llm_prompts.py` | 48 | 0.00 | GSE.curation.llm.prompts |
| `tests/test_GSE_curation_validation_bipolar_validator.py` | 15 | 0.00 | GSE.curation.validation.bipolar_validator |
| `tests/test_GSE_evaluation_world_model.py` | 31 | 0.00 | GSE.evaluation.world_model |
| `tests/test_GSE_merkle_hash_chain.py` | 35 | 0.00 | GSE.merkle.hash_chain |
| `tests/test_GSE_verb_templates.py` | 25 | 0.00 | GSE.verb_templates |

Files that mix experiment-stack imports with other GSE imports: 17 (listed in census.json).

## 5. Fixtures

- `pytest-deadfixtures` 4.0.0 on pytest 9.1.0 / Python 3.14.7: **0 unused fixtures** ("every declared fixture is being used"). The plugin was validated on a scratch probe with the same runtime, where it reported the planted unused fixture.
- Static cross-check: 143 fixtures defined ({'class': 6, 'function': 82, 'module': 55}), 5 autouse, 0 with no name reference.
- Setup-phase time (where fixture cost lands), Σ per-test min: 39.93 s. Fixture-level timing (pytest-durations) was not run.

## 6. Scoping by GSE area

Rule: a file is charged in full to every area it imports, so column sums exceed the suite total. *Exclusive* counts files whose GSE imports fall in exactly one area. Time is the per-test min.

| area | test files | tests | time s | exclusive files | exclusive tests | exclusive s |
|---|---:|---:|---:|---:|---:|---:|
| curation | 153 | 4307 | 210.2 | 121 | 3535 | 121.3 |
| api | 65 | 1747 | 134.7 | 3 | 117 | 0.0 |
| nlp | 22 | 380 | 132.2 | 11 | 98 | 0.0 |
| mcp | 4 | 95 | 108.4 | 0 | 0 | 0.0 |
| symbolic | 55 | 1309 | 77.8 | 13 | 198 | 0.0 |
| [scripts/ (non-GSE)] | 22 | 474 | 59.2 | 0 | 0 | 0.0 |
| lexical_evidence | 5 | 80 | 36.9 | 2 | 7 | 0.0 |
| vectors_v2 | 16 | 647 | 26.3 | 0 | 0 | 0.0 |
| lexicon_resource | 5 | 80 | 21.5 | 0 | 0 | 0.0 |
| frequency | 2 | 52 | 19.6 | 1 | 34 | 0.0 |
| discourse | 7 | 303 | 16.6 | 1 | 11 | 0.0 |
| primitives_v2 | 19 | 498 | 6.2 | 2 | 3 | 0.0 |
| namespace | 9 | 245 | 5.5 | 1 | 11 | 0.0 |
| cassettes | 1 | 35 | 4.0 | 0 | 0 | 0.0 |
| structure | 1 | 35 | 4.0 | 0 | 0 | 0.0 |
| benchmarks | 4 | 84 | 3.5 | 3 | 78 | 3.5 |
| [no GSE import] | 13 | 139 | 2.0 | 0 | 0 | 0.0 |
| verification | 2 | 60 | 1.9 | 1 | 35 | 0.1 |
| encoders | 5 | 187 | 1.3 | 3 | 131 | 0.2 |
| cli | 2 | 46 | 1.1 | 1 | 27 | 0.0 |
| merkle | 7 | 253 | 0.9 | 4 | 151 | 0.4 |
| lexicon | 12 | 490 | 0.9 | 4 | 152 | 0.0 |
| profiles | 2 | 72 | 0.2 | 1 | 34 | 0.1 |
| teaching | 3 | 133 | 0.1 | 2 | 95 | 0.0 |
| pipeline_v2 | 1 | 21 | 0.1 | 0 | 0 | 0.0 |
| scale_definition | 2 | 87 | 0.0 | 1 | 30 | 0.0 |
| scales | 1 | 28 | 0.0 | 1 | 28 | 0.0 |
| patterns | 4 | 99 | 0.0 | 3 | 81 | 0.0 |
| prime_projection | 2 | 27 | 0.0 | 1 | 2 | 0.0 |
| composition | 2 | 57 | 0.0 | 0 | 0 | 0.0 |
| parsing | 5 | 192 | 0.0 | 0 | 0 | 0.0 |
| evaluation | 1 | 31 | 0.0 | 1 | 31 | 0.0 |
| verb_templates | 1 | 25 | 0.0 | 1 | 25 | 0.0 |

### Second level under `curation` (GSE.curation.X), same rule

| curation sub-area | test files | tests | time s |
|---|---:|---:|---:|
| lexicon_builder | 97 | 2320 | 180.6 |
| external_sources | 45 | 1479 | 46.2 |
| cli | 14 | 267 | 22.2 |
| personal_dictionary | 5 | 45 | 19.6 |
| build_clean_closed_class | 2 | 19 | 1.5 |
| schema | 10 | 419 | 1.2 |
| lexicon_db | 3 | 94 | 1.0 |
| llm | 10 | 492 | 0.7 |
| pipeline | 1 | 23 | 0.3 |
| frequency_integration | 1 | 26 | 0.2 |
| build_wordlist | 1 | 6 | 0.0 |
| constraint_aggregation | 5 | 229 | 0.0 |
| validation | 3 | 45 | 0.0 |

## 7. UNMEASURED

- **coverage reach of 4 tests**: Each replaces sqlite3.connect via monkeypatch with a function that asserts '?mode=ro' or fails on any connection. pytest-cov switches coverage context at each phase and coverage flushes to its own SQLite file, which hits the patched connect while the patch is still active: attempt 1 raised INTERNALERROR and left the patch in place, so 5,959 later tests errored. These 4 were deselected for the coverage run only. Their cost and outcome come from the plugin-free runs.
- **code run in child processes**: No subprocess coverage was configured. Tests that launch `python`/scripts via subprocess or sys.executable have reach limited to the parent process. They are tagged in coverage.zero_reach.
- **code outside GSE/ (scripts/, tests/ helpers)**: --cov=GSE measures only the GSE package; tests that exercise scripts/ show only their GSE reach.
- **import-time / collection-time GSE code**: Module-level GSE code runs at import during collection and is recorded under the empty context, not under any test (16493 arc rows). Tests that only read module-level tables or call dataclass-generated methods therefore show zero reach.
- **order-independent reach**: Shared-scope fixtures (module/class), lru_cache and lazy singletons credit their code to the first test that triggers them, so reach sets depend on the fixed collection order. No stability rerun or reordering was done.
- **isolated (uncontended) timing**: Both plugin-free runs shared the machine with other sessions (other GSE pytest runs and voice tools). Timings are wall-clock under recorded load, not isolated measurements.
- **fixture-level timing (pytest-durations)**: Not run. Setup-phase time per test is reported instead.
- **duplicate-fixture analysis (--dup-fixtures)**: Not requested. It executes the whole suite, and it was stopped so it would not overlap the coverage run.
- **pytest_deduplicate, jscpd, PyNose, TestIQ**: Not run (not requested). Coverage clustering was computed directly from the Coverage.py db.
- **complete write check of the live data/**: The before/after check compared the pointer, its target db (mtime and size) and `find -L data -maxdepth 3 -newer marker`. Deeper paths were not scanned.
- **outcome stability across orders/reruns**: Not measured (no randomized or repeated runs beyond the two cost runs).
