"""Score held-out exact senses and required banks through the sentence encoder."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from math import log2
from pathlib import Path
from typing import Any

from GSE.api.encoder import GSEEncoder
from GSE.curation.lexicon_builder.epoch import fingerprint, read, record
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.namespace import current_id

FORMAT = "GSE.lexicon-sentence-benchmark/1"


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _snapshot_pins(encoder):
    """Pin the full cohort, not only the senses with benchmark labels."""
    cohort = hashlib.sha256()
    definitions = 0
    for row in encoder.conn.execute(
        "SELECT d.entry_id,l.lemma,l.pos,l.gloss FROM definition_states d "
        "JOIN lexemes l ON d.lexeme_id=l.id ORDER BY d.entry_id"
    ):
        cohort.update(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode() + b"\n")
        definitions += 1
    metadata = dict(
        encoder.conn.execute(
            "SELECT key,value FROM builder_metadata WHERE key IN ('representation_contract','rule_version')"
        )
    )
    return {
        "definition_cohort_sha256": cohort.hexdigest(),
        "definitions": definitions,
        "representation_sha256": _digest(json.loads(metadata.get("representation_contract", "null"))),
        "rule_version": json.loads(metadata.get("rule_version", "null")),
    }


def _mass(counts, forms):
    """Token mass is a workload denominator, never semantic accuracy."""
    if (
        not isinstance(counts, dict)
        or not counts
        or any(
            not isinstance(word, str) or word != word.casefold() or type(n) is not int or n <= 0
            for word, n in counts.items()
        )
    ):
        raise ValueError("INVALID_CHECKPOINT_TOKEN_COUNTS")
    total = sum(counts.values())
    covered = sum(n for word, n in counts.items() if word in forms)
    return {"eligible": total, "in_cohort": covered, "meets_90_percent": 10 * covered >= 9 * total}


def checkpoint_result(report, runtime=None, workload=None):
    """Compute the formal checkpoint verdict, separately from nonregression.

    This consumes measured sentence/runtime results and a byte-pinned workload
    receipt. Missing evidence blocks acceptance; no singleton, homing count or
    sparse runtime success substitutes for the declared independent workload.
    The workload receipt records predeclared token denominators, operations,
    critical cases, lineage separation and full replay/repository receipts.
    It is evaluation-only and supplies no construction authority.
    """
    blockers, outcomes = [], defaultdict(Counter)
    good_banks = {"CORRECT", "OPEN_AS_EXPECTED"}
    rows = {row["id"]: row for row in report["cases"]}
    for row in rows.values():
        sense = row["sense_outcome"]
        cells = [cell["runtime"] for cell in row["banks"].values()]
        wrong = sense == "WRONG" or any(
            cell[field]
            in {"WRONG", "UNSUPPORTED_ASSIGNMENT", "UNSUPPORTED_EMISSION", "WRONG_EMISSION", "INVALID_DOMAIN"}
            for cell in row["banks"].values()
            for field in ("runtime", "exact_sense")
        )
        outcome = (
            "WRONG"
            if wrong
            else "ABSTAINED"
            if sense in {"ABSTAINED", "ABSTAINED_AS_EXPECTED"}
            else "IDENTIFIED"
            if sense == "CORRECT" and all(c in good_banks for c in cells)
            else "PARTIAL"
            if sense == "CORRECT"
            else "UNAVAILABLE"
        )
        outcomes[row["class"]][outcome] += 1
        if wrong:
            blockers.append({"code": "KNOWN_WRONG_ASSERTION", "case": row["id"]})
    if runtime is None or runtime.get("code") != "SPARSE_RUNTIME_VALIDATED":
        blockers.append({"code": "RUNTIME_NOT_VALIDATED"})
    elif runtime.get("lexicon_sha256") != report["lexicon_sha256"]:
        blockers.append({"code": "RUNTIME_RESOURCE_MISMATCH"})
    coverage = {}
    if workload is None:
        blockers.append({"code": "WORKLOAD_MANIFEST_NOT_FROZEN"})
    else:
        if current_id(workload.get("format")) != "GSE.checkpoint-workload/1":
            raise ValueError("INVALID_CHECKPOINT_WORKLOAD")
        expected_pins = {
            "lexicon_sha256": report["lexicon_sha256"],
            "benchmark_sha256": report["benchmark_sha256"],
            **report["snapshot_pins"],
        }
        if workload.get("pins") != expected_pins:
            blockers.append({"code": "WORKLOAD_PINS_MISMATCH"})
        split = workload.get("evaluation", {})
        if split.get("split") != "FINAL_UNEXPOSED":
            blockers.append({"code": "FINAL_HOLDOUT_NOT_UNEXPOSED"})
        for scale in ("senses", "families"):
            development, final = split.get(f"development_{scale}"), split.get(f"final_{scale}")
            if not isinstance(development, list) or not isinstance(final, list) or not final:
                blockers.append({"code": "HOLDOUT_LINEAGE_UNAVAILABLE", "scale": scale})
            elif set(development) & set(final):
                blockers.append({"code": "HOLDOUT_LINEAGE_OVERLAP", "scale": scale})
        if set(split.get("final_senses", [])) != {r["sense"] for r in rows.values() if r["sense"] is not None}:
            blockers.append({"code": "FINAL_SENSE_INVENTORY_MISMATCH"})
        critical = workload.get("critical_case_ids", [])
        if not critical or not set(critical) <= rows.keys():
            blockers.append({"code": "CRITICAL_CASE_INVENTORY_MISSING"})
        for case_id in critical:
            row = rows.get(case_id)
            if row is not None and (
                row["sense_outcome"] not in {"CORRECT", "ABSTAINED_AS_EXPECTED"}
                or any(c["runtime"] not in good_banks for c in row["banks"].values())
            ):
                blockers.append({"code": "CRITICAL_ANSWER_NOT_ESTABLISHED", "case": case_id})
        operations = workload.get("operations", [])
        claimed = set()
        if not operations:
            blockers.append({"code": "PROMISED_OPERATIONS_NOT_DECLARED"})
        runtime_classes = {row["class"]: row["outcome"] for row in (runtime or {}).get("records", [])}
        for operation in operations:
            cases = operation.get("case_ids", [])
            structures = operation.get("runtime_classes", [])
            claimed.update(cases)
            if not cases and not structures:
                blockers.append({"code": "OPERATION_WITHOUT_WITNESSES", "operation": operation.get("id")})
            if not set(cases) <= set(critical) or any(runtime_classes.get(c) != "IDENTIFIED" for c in structures):
                blockers.append({"code": "PROMISED_OPERATION_NOT_ESTABLISHED", "operation": operation.get("id")})
            for case_id, banks in operation.get("required_banks", {}).items():
                if case_id not in cases or not set(banks) <= rows.get(case_id, {}).get("banks", {}).keys():
                    blockers.append({"code": "REQUIRED_BANK_NOT_TESTED", "case": case_id})
        if not set(critical) <= claimed:
            blockers.append({"code": "CRITICAL_CASE_WITHOUT_OPERATION"})
        demand = workload.get("token_demand", {})
        forms = demand.get("common_forms", [])
        if (
            not forms
            or len(set(forms)) != len(forms)
            or any(not isinstance(f, str) or f != f.casefold() for f in forms)
        ):
            blockers.append({"code": "COMMON_FORM_COHORT_NOT_PINNED"})
        for key in ("frequency_source_sha256", "corpus_source_sha256", "denominator_rules", "exclusions"):
            if key not in demand or (key != "exclusions" and not demand[key]):
                blockers.append({"code": "TOKEN_DEMAND_PROVENANCE_MISSING", "field": key})
        if demand.get("frequency_source_sha256") == demand.get("corpus_source_sha256"):
            blockers.append({"code": "INDEPENDENT_CORPUS_REQUIRED"})
        try:
            coverage["frequency"] = _mass(demand.get("frequency_counts"), set(forms))
            genres = demand.get("corpus_genres", {})
            if not genres:
                raise ValueError("CORPUS_GENRES_MISSING")
            combined = Counter()
            coverage["genres"] = {}
            for genre, counts in genres.items():
                coverage["genres"][genre] = _mass(counts, set(forms))
                combined.update(counts)
            coverage["independent_corpus"] = _mass(dict(combined), set(forms))
            # The formal threshold applies to the two aggregate sources.
            # Genre slices remain reported, including below-threshold slices;
            # there is no independently authorized per-genre percentage gate.
            if not all(row["meets_90_percent"] for row in [coverage["frequency"], coverage["independent_corpus"]]):
                blockers.append({"code": "ELIGIBLE_TOKEN_MASS_BELOW_90_PERCENT"})
        except ValueError as error:
            blockers.append({"code": "TOKEN_DEMAND_UNAVAILABLE", "reason": str(error)})
        for name in ("full_replay", "repository_gate", "two_sided_semantic_audit"):
            gate = workload.get("gates", {}).get(name, {})
            if (
                gate.get("code") != "PASSED"
                or gate.get("lexicon_sha256") != report["lexicon_sha256"]
                or not gate.get("receipt_sha256")
            ):
                blockers.append({"code": "REQUIRED_GATE_NOT_ESTABLISHED", "gate": name})
    return {
        "format": "GSE.checkpoint-acceptance/1",
        "code": "CHECKPOINT_BLOCKED" if blockers else "CHECKPOINT_ACCEPTED_FOR_DECLARED_WORKLOAD",
        "lexicon_sha256": report["lexicon_sha256"],
        "benchmark_sha256": report["benchmark_sha256"],
        "workload_sha256": _digest(workload) if workload is not None else None,
        "by_class": {key: dict(value) for key, value in sorted(outcomes.items())},
        "token_mass": coverage,
        "blockers": blockers,
        "scope": "DECLARED_WORKLOAD_ONLY_NOT_FULL_LEXICON_COMPLETION",
    }


def load_workload(path):
    """Verify original resource/receipt bytes before consuming their claims.

    Relative paths are relative to the manifest. Every source and gate digest
    consumed by checkpoint_result must have a retained artifact, including the
    denominator/exclusion computation receipt. Merely declaring a hash is not
    a resource pin. This does not independently certify supplied semantic gold.
    """
    workload = read(path)
    artifacts = workload.get("artifacts", [])
    verified = set()
    paths = {}
    for artifact in artifacts:
        target = (Path(path).parent / artifact["path"]).resolve(strict=True)
        actual = fingerprint(target)
        if actual != artifact["sha256"]:
            raise ValueError("CHECKPOINT_ARTIFACT_CHANGED")
        verified.add(actual)
        paths[actual] = target
    demand = workload.get("token_demand", {})
    needed = {
        demand.get("frequency_source_sha256"),
        demand.get("corpus_source_sha256"),
        demand.get("counts_receipt_sha256"),
        workload.get("scope_freeze_sha256"),
    }
    needed.update(g.get("receipt_sha256") for g in workload.get("gates", {}).values())
    if None in needed or not needed <= verified:
        raise ValueError("CHECKPOINT_ARTIFACT_UNPINNED")
    counts = read(paths[demand["counts_receipt_sha256"]])
    fields = {
        "common_forms",
        "frequency_source_sha256",
        "corpus_source_sha256",
        "frequency_counts",
        "corpus_genres",
        "denominator_rules",
        "exclusions",
    }
    if counts != {key: demand.get(key) for key in fields}:
        raise ValueError("CHECKPOINT_COUNTS_RECEIPT_MISMATCH")
    scope = read(paths[workload["scope_freeze_sha256"]])
    if (
        current_id(scope.get("format")) != "GSE.checkpoint-workload-scope-freeze/1"
        or scope.get("token_demand_sha256") != demand["counts_receipt_sha256"]
        or not scope.get("operations")
        or {operation.get("id") for operation in workload.get("operations", [])} != set(scope["operations"])
        or len(workload["operations"]) != len(scope["operations"])
    ):
        raise ValueError("CHECKPOINT_FROZEN_SCOPE_CHANGED")
    for name, gate in workload.get("gates", {}).items():
        receipt = read(paths[gate["receipt_sha256"]])
        if any(receipt.get(key) != gate.get(key) for key in ("code", "lexicon_sha256")):
            raise ValueError("CHECKPOINT_GATE_RECEIPT_MISMATCH")
        if not receipt.get("command") or receipt.get("exit_code") != 0:
            raise ValueError("CHECKPOINT_GATE_EXECUTION_UNAVAILABLE")
        if name == "full_replay" and (
            receipt.get("definition_cohort_sha256") != workload["pins"]["definition_cohort_sha256"]
            or receipt.get("checked_definitions") != workload["pins"]["definitions"]
            or receipt.get("mismatches") != 0
            or receipt.get("solver_limits") != 0
        ):
            raise ValueError("CHECKPOINT_FULL_REPLAY_INCOMPLETE")
        # Semantic gold is a declared finite two-sided audit across the
        # promised operations/genres/tail, not a label for every spelling in
        # the token-mass cohort. These are separate kinds of evidence.
        if name == "two_sided_semantic_audit" and (
            not receipt.get("audited_forms")
            or not all(isinstance(form, str) and form for form in receipt["audited_forms"])
            or receipt.get("known_wrong") != 0
            or receipt.get("missing_required") != 0
            or any(
                receipt.get("checks", {}).get(key) != "PASSED"
                for key in (
                    "positive",
                    "must_not",
                    "missing_sign",
                    "source_warrants",
                    "morphology",
                    "pos_roles",
                    "tail_strata",
                    "genre_strata",
                )
            )
        ):
            raise ValueError("CHECKPOINT_TWO_SIDED_AUDIT_INCOMPLETE")
    return workload


def load_benchmark(path):
    benchmark = read(path)
    if (
        not isinstance(benchmark, dict)
        or set(benchmark) != {"format", "cases"}
        or current_id(benchmark["format"]) != FORMAT
    ):
        raise ValueError("INVALID_SENTENCE_BENCHMARK")
    cases = benchmark["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("EMPTY_SENTENCE_BENCHMARK")
    seen = set()
    fields = {"id", "class", "text", "token", "lemma", "sense", "banks", "basis"}
    for case in cases:
        if not isinstance(case, dict) or set(case) != fields:
            raise ValueError("INVALID_SENTENCE_BENCHMARK_CASE")
        if any(not isinstance(case[key], str) or not case[key].strip() for key in fields - {"sense", "banks"}):
            raise ValueError("INVALID_SENTENCE_BENCHMARK_TEXT")
        if case["id"] in seen:
            raise ValueError("DUPLICATE_SENTENCE_BENCHMARK_ID")
        seen.add(case["id"])
        banks = case["banks"]
        sense = case["sense"]
        if not isinstance(banks, dict) or any(
            bank not in BANKS or (value is not None and (type(value) is not int or value not in (-1, 0, 1)))
            for bank, value in banks.items()
        ):
            raise ValueError("INVALID_SENTENCE_BENCHMARK_BANK")
        if (sense is None and banks) or (sense is not None and (not isinstance(sense, str) or not sense or not banks)):
            raise ValueError("INVALID_SENTENCE_BENCHMARK_SENSE")
    return cases


def score_domain(domain, expected):
    if (
        not isinstance(domain, list)
        or not domain
        or any(type(value) is not int or value not in (-1, 0, 1) for value in domain)
        or len(set(domain)) != len(domain)
    ):
        return "INVALID_DOMAIN"
    if expected is None:
        return "OPEN_AS_EXPECTED" if len(domain) > 1 else "UNSUPPORTED_ASSIGNMENT"
    if expected not in domain:
        return "WRONG"
    return "CORRECT" if len(domain) == 1 else "OPEN"


def score_case(encoder, case):
    expected = case["sense"]
    if expected is not None:
        gold = encoder.lexical_lookup(case["lemma"], entry_id=expected)
        exact = gold.get("selected_record")
        if not exact or exact["entry_id"] != expected:
            raise ValueError(f"BENCHMARK_GOLD_SENSE_UNAVAILABLE {case['id']} {expected}")
    else:
        exact = None

    hits = [token for token in encoder.encode(case["text"]).tokens if token.token == case["token"]]
    token = hits[0] if len(hits) == 1 else None
    evidence = token.lexical_evidence if token else {}
    selected = evidence.get("selected_record") or {}
    identity = selected.get("entry_id")
    status = evidence.get("selection_status")
    if token is None:
        sense_outcome = "TOKEN_MISMATCH"
    elif identity is not None:
        sense_outcome = "CORRECT" if identity == expected else "WRONG"
    elif status in {"AMBIGUOUS", "CONFLICT"}:
        sense_outcome = "ABSTAINED_AS_EXPECTED" if expected is None else "ABSTAINED"
    else:
        sense_outcome = status or "NO_LEXICAL_EVIDENCE"

    banks = {}
    for bank, value in case["banks"].items():
        if exact is None:
            raise ValueError("BENCHMARK_BANKS_REQUIRE_EXACT_SENSE")
        domain = exact["domains"].get(bank)
        lexical = score_domain(domain, value)
        emitted = token.word_primitives.get(bank) if token else None
        if sense_outcome != "CORRECT":
            runtime = "BLOCKED_BY_SENSE"
        elif lexical in {"OPEN", "OPEN_AS_EXPECTED"} and emitted is not None:
            runtime = "UNSUPPORTED_EMISSION"
        elif lexical == "CORRECT" and emitted != (None if value == 0 else value):
            runtime = "WRONG_EMISSION"
        else:
            runtime = lexical
        banks[bank] = {
            "domain": domain,
            "expected": value,
            "exact_sense": lexical,
            "runtime": runtime,
            "emitted": emitted,
        }

    return {
        **case,
        "sense_outcome": sense_outcome,
        "observed_sense": identity,
        "selection_status": status,
        "parser_lemma": token.lemma if token else None,
        "parser_pos": token.pos if token else None,
        "grounding": evidence.get("contextual_grounding", {}).get("code"),
        "reading_eligibility": evidence.get("reading_eligibility"),
        "banks": banks,
    }


def audit(lexicon, benchmark):
    lexicon_sha256 = fingerprint(lexicon)
    benchmark_sha256 = fingerprint(benchmark)
    cases = load_benchmark(benchmark)
    with GSEEncoder(lexicon) as encoder:
        encoder.conn.execute("PRAGMA query_only=ON")
        pins = _snapshot_pins(encoder)
        rows: list[dict[str, Any]] = []
        for case in cases:
            try:
                rows.append(score_case(encoder, case))
            except (ValueError, RuntimeError) as error:
                rows.append(
                    {
                        **case,
                        "sense_outcome": "UNAVAILABLE",
                        "error": str(error),
                        "banks": {
                            bank: {
                                "expected": value,
                                "domain": None,
                                "emitted": None,
                                "exact_sense": "UNAVAILABLE",
                                "runtime": "BLOCKED_BY_SENSE",
                            }
                            for bank, value in case["banks"].items()
                        },
                    }
                )
    if fingerprint(lexicon) != lexicon_sha256 or fingerprint(benchmark) != benchmark_sha256:
        raise ValueError("SENTENCE_BENCHMARK_INPUT_CHANGED")
    counts = defaultdict(lambda: {"sense": Counter(), "runtime_bank": Counter(), "exact_sense_bank": Counter()})
    for row in rows:
        group = counts[row["class"]]
        group["sense"][row["sense_outcome"]] += 1
        for bank in row["banks"].values():
            group["runtime_bank"][bank["runtime"]] += 1
            group["exact_sense_bank"][bank["exact_sense"]] += 1
    report = {
        "format": "GSE.lexicon-sentence-benchmark-report/1",
        "lexicon_sha256": lexicon_sha256,
        "benchmark_sha256": benchmark_sha256,
        "snapshot_pins": pins,
        "by_class": dict(counts),
        "cases": rows,
    }
    report["checkpoint"] = checkpoint_result(report)
    return report


def compare_reports(baseline, candidate):
    if baseline["benchmark_sha256"] != candidate["benchmark_sha256"]:
        raise ValueError("SENTENCE_COMPARISON_BENCHMARK_CHANGED")
    previous = {case["id"]: case for case in baseline["cases"]}
    if previous.keys() != {case["id"] for case in candidate["cases"]}:
        raise ValueError("SENTENCE_COMPARISON_CASES_CHANGED")
    counts = defaultdict(Counter)
    failures = []
    good_senses = {"CORRECT", "ABSTAINED_AS_EXPECTED"}
    good_banks = {"CORRECT", "OPEN_AS_EXPECTED"}
    open_banks = {"OPEN", "BLOCKED_BY_SENSE"}
    for case in candidate["cases"]:
        old = previous[case["id"]]
        group = counts[case["class"]]
        sense = case["sense_outcome"]
        if sense not in good_senses | {"ABSTAINED"} or (
            old["sense_outcome"] in good_senses and sense not in good_senses
        ):
            failures.append({"case": case["id"], "outcome": sense, "prior": old["sense_outcome"]})
        for bank, cell in case["banks"].items():
            prior = old["banks"][bank]
            for field in ("exact_sense", "runtime"):
                outcome = cell[field]
                if outcome not in good_banks | open_banks or (prior[field] in good_banks and outcome not in good_banks):
                    failures.append(
                        {"case": case["id"], "bank": bank, "field": field, "outcome": outcome, "prior": prior[field]}
                    )
                if outcome == "CORRECT" and prior[field] != "CORRECT":
                    group[f"{field}_new_correct"] += 1
            if cell["expected"] is not None and prior["domain"] and cell["domain"]:
                group["exact_sense_bits_removed"] += log2(len(prior["domain"]) / len(cell["domain"]))
    return {
        "format": "GSE.lexicon-sentence-benchmark-comparison/1",
        "code": "SENTENCE_BENCHMARK_REGRESSION" if failures else "SENTENCE_BENCHMARK_VALIDATED",
        "baseline_sha256": baseline["lexicon_sha256"],
        "candidate_sha256": candidate["lexicon_sha256"],
        "benchmark_sha256": candidate["benchmark_sha256"],
        "by_class": dict(counts),
        "failures": failures,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lexicon", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--baseline-report", type=Path)
    parser.add_argument(
        "--checkpoint", action="store_true", help="Run runtime controls and require full checkpoint acceptance"
    )
    parser.add_argument("--checkpoint-manifest", type=Path, help="Frozen workload with retained byte-pinned artifacts")
    args = parser.parse_args(argv)
    inputs = [args.lexicon, args.benchmark, args.baseline_report, args.checkpoint_manifest]
    if any(
        p is not None
        and (args.report.resolve() == p.resolve() or (args.report.exists() and p.exists() and args.report.samefile(p)))
        for p in inputs
    ):
        parser.error("REPORT_MUST_NOT_REPLACE_INPUT")
    workload = load_workload(args.checkpoint_manifest) if args.checkpoint_manifest else None
    if workload is not None:
        for artifact in workload["artifacts"]:
            target = args.checkpoint_manifest.parent / artifact["path"]
            if args.report.resolve() == target.resolve() or (args.report.exists() and args.report.samefile(target)):
                parser.error("REPORT_MUST_NOT_REPLACE_INPUT")
    report = audit(args.lexicon.resolve(strict=True), args.benchmark)
    if args.checkpoint or workload is not None:
        from scripts.audit_lexicon_runtime import audit_sparse_runtime

        runtime = audit_sparse_runtime(args.lexicon)
        report["runtime"] = runtime
        report["checkpoint"] = checkpoint_result(report, runtime, workload)
        report["checkpoint"]["manifest_file_sha256"] = fingerprint(args.checkpoint_manifest) if workload else None
    if args.baseline_report:
        report["comparison"] = compare_reports(read(args.baseline_report), report)
    record(args.report, report)
    if report.get("comparison", {}).get("failures") or (
        (args.checkpoint or workload is not None) and report["checkpoint"]["code"] == "CHECKPOINT_BLOCKED"
    ):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
