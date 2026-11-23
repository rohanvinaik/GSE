"""Score held-out exact senses and required banks through the sentence encoder."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from math import log2
from pathlib import Path

from GSE.api.encoder import GSEEncoder
from GSE.curation.lexicon_builder.epoch import fingerprint, read, record
from GSE.curation.lexicon_builder.foundation import BANKS
from GSE.namespace import current_id

FORMAT = "GSE.lexicon-sentence-benchmark/1"


def load_benchmark(path):
    benchmark = read(path)
    if not isinstance(benchmark, dict) or set(benchmark) != {"format", "cases"} or current_id(benchmark["format"]) != FORMAT:
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
    elif status == "AMBIGUOUS":
        sense_outcome = "ABSTAINED_AS_EXPECTED" if expected is None else "ABSTAINED"
    else:
        sense_outcome = status or "NO_LEXICAL_EVIDENCE"

    banks = {}
    for bank, value in case["banks"].items():
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
        "banks": banks,
    }


def audit(lexicon, benchmark):
    lexicon_sha256 = fingerprint(lexicon)
    benchmark_sha256 = fingerprint(benchmark)
    cases = load_benchmark(benchmark)
    with GSEEncoder(lexicon) as encoder:
        encoder.conn.execute("PRAGMA query_only=ON")
        rows = [score_case(encoder, case) for case in cases]
    if fingerprint(lexicon) != lexicon_sha256 or fingerprint(benchmark) != benchmark_sha256:
        raise ValueError("SENTENCE_BENCHMARK_INPUT_CHANGED")
    counts = defaultdict(lambda: {"sense": Counter(), "runtime_bank": Counter(), "exact_sense_bank": Counter()})
    for row in rows:
        group = counts[row["class"]]
        group["sense"][row["sense_outcome"]] += 1
        for bank in row["banks"].values():
            group["runtime_bank"][bank["runtime"]] += 1
            group["exact_sense_bank"][bank["exact_sense"]] += 1
    return {
        "format": "GSE.lexicon-sentence-benchmark-report/1",
        "lexicon_sha256": lexicon_sha256,
        "benchmark_sha256": benchmark_sha256,
        "by_class": dict(counts),
        "cases": rows,
    }


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lexicon", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--baseline-report", type=Path)
    args = parser.parse_args()
    report = audit(args.lexicon.resolve(strict=True), args.benchmark)
    if args.baseline_report:
        report["comparison"] = compare_reports(read(args.baseline_report), report)
    record(args.report, report)
    if report.get("comparison", {}).get("failures"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
