"""Verify and publish the pinned 019-to-020 coherence learning round."""

import argparse
from collections import Counter
from fractions import Fraction
from importlib import import_module
from math import log2, prod
from pathlib import Path

from GSE.api.encoder import GSEEncoder
from GSE.curation.lexicon_builder.epoch import (
    _domains,
    _resolve,
    fingerprint,
    read,
    record,
    scope_rows,
)
from GSE.lexicon_resource import ACTIVE_POINTER, resolve_lexicon_path
from scripts.audit_lexicon_sentences import audit, compare_reports
from scripts.run_lexicon_epochs import publish_round

NOTES = Path(__file__).resolve().parent
ROOT = NOTES.parents[2]
BASE = ROOT / "data/lexicon_builder/2026-11-12/sparse-release-019.db"
WORK = BASE.parent / "ssl-explicit-genera/coherence-020"


def freeze():
    parent = read(NOTES / "sparse-release-019-activation.json")
    if (
        resolve_lexicon_path() != BASE
        or fingerprint(BASE) != parent["sha256"]
        or fingerprint(ACTIVE_POINTER) != parent["pointer_sha256"]
    ):
        raise ValueError("COHERENCE_020_BASELINE_CHANGED")
    return parent


def support_count(state):
    """Count the recorded complete components, including free coordinates."""
    if state.code == "CONFLICT" or any(row["kind"] == "SOLVER_LIMIT" for row in state.trace):
        raise ValueError("COHERENCE_020_INCOMPLETE_SUPPORT")
    used, count = set(), 1
    for check in (row for row in state.trace if row["kind"] == "JOINT_CHECK"):
        if used.intersection(check["banks"]) or check["witnesses"] < 1:
            raise ValueError("COHERENCE_020_INVALID_COMPONENT_PARTITION")
        used.update(check["banks"])
        count *= check["witnesses"]
    return count * prod(len(values) for bank, values in state.domains.items() if bank not in used)


def joint_replay(candidate):
    inventory = read(WORK / "inventory.json")
    everyone = {row["entry_id"]: row for members in inventory.values() for row in members}
    before_rules, before_rows = scope_rows(BASE, everyone.values())
    after_rules, after_rows = scope_rows(candidate, everyone.values())
    stage = read(NOTES / "020-joint-support-stage.json")
    expected = {row["entry_id"]: row for row in stage["records"]}
    observed, ratios, factor = [], Counter(), Fraction(1)
    for identity, before_row in sorted(before_rows.items()):
        before = _resolve(before_row, before_rules)
        after = _resolve(after_rows[identity], after_rules)
        if _domains(before) != before_row[-1] or _domains(after) != after_rows[identity][-1]:
            raise ValueError("COHERENCE_020_COMPONENT_REPLAY_MISMATCH:" + identity)
        old_count, new_count = support_count(before), support_count(after)
        ratio = Fraction(old_count, new_count)
        changes = {
            bank: {"before": sorted(before.domains[bank]), "after": sorted(after.domains[bank])}
            for bank in before.domains
            if before.domains[bank] != after.domains[bank]
        }
        if ratio != 1 or changes:
            row = expected.get(identity)
            if row is None or (old_count, new_count, changes) != (
                row["support_before"], row["support_after"], row["domain_changes"]
            ):
                raise ValueError("COHERENCE_020_SUPPORT_DIFFERS_FROM_STAGE:" + identity)
            observed.append(row)
            ratios[str(ratio)] += 1
            factor *= ratio
    if len(observed) != len(expected):
        raise ValueError("COHERENCE_020_MISSING_SUPPORT_CHANGES")
    return {
        **stage,
        "code": "CANDIDATE_EXACT_SUPPORT_REPLAY_VALIDATED",
        "candidate": str(candidate),
        "candidate_sha256": fingerprint(candidate),
        "support_ratio_frequency": dict(ratios),
        "support_ratio_numerator": factor.numerator,
        "support_ratio_denominator": factor.denominator,
        "log2_support_ratio": log2(factor.numerator) - log2(factor.denominator),
        "records": observed,
    }


def verify():
    parent = freeze()
    result = read(WORK / "zipf/arm-result.json")
    if (
        len(result["epochs"]) != 2
        or any(row["code"] != "RULE_ADMITTED" for row in result["epochs"])
        or result["typed_questions_used"] != 8
        or result["reopened_cells"]
        or result["replay"]["code"] != "REPLAY_VALIDATED"
        or not result["replay"]["complete_search"]
    ):
        raise ValueError("COHERENCE_020_COMPLETE_LEARNING_CYCLE_REQUIRED")
    candidate = Path(result["candidate"])
    if fingerprint(candidate) != result["candidate_sha256"]:
        raise ValueError("COHERENCE_020_CANDIDATE_CHANGED")
    stage = read(NOTES / "020-joint-support-stage.json")
    expected = {
        (row["entry_id"], bank): change
        for row in stage["records"]
        for bank, change in row["domain_changes"].items()
    }
    actual = {(row["entry_id"], row["bank"]): {"before": row["before"], "after": row["after"]} for row in result["changes"]}
    if actual != expected:
        raise ValueError("COHERENCE_020_FULL_DELTA_DIFFERS_FROM_STAGE")
    with GSEEncoder(candidate) as encoder:
        encoder.conn.execute("PRAGMA query_only=ON")
        for family in read(WORK / "plan.json")["families"]:
            for entry in family["holdouts"]:
                bank = family["consequent"][0]
                if encoder.lookup_definition(entry)["selected"]["domains"][bank] != [1]:
                    raise ValueError("COHERENCE_020_PREPUBLICATION_CONTROL_FAILED:" + entry)
                encoder.encode_definition(entry)
    joint = joint_replay(candidate)
    record(NOTES / "020-joint-support-validation.json", joint)
    prior = import_module("docs.readings.2026-11-13-ssl-explicit-genera.stative_transfer")
    comparisons = {}
    for name, cases, baseline in (
        ("sentences", prior.previous.anatomy.previous.prior.SOURCE_CASES, "019-candidate-sentences.json"),
        ("contrasts", prior.previous.anatomy.previous.prior.CONTRAST_CASES, "019-candidate-contrasts.json"),
        ("states", NOTES / "018-stative-diagnostic-cases.json", "019-candidate-states.json"),
    ):
        report = audit(candidate, cases)
        comparison = compare_reports(read(NOTES / baseline), report)
        record(NOTES / f"020-candidate-{name}.json", {**report, "comparison": comparison})
        if comparison["failures"]:
            raise ValueError("COHERENCE_020_BENCHMARK_REGRESSION:" + name)
        comparisons[name] = comparison
    state_corpus = import_module("docs.readings.2026-11-13-ssl-explicit-genera.state_corpus")
    corpus = state_corpus.audit(candidate)
    previous = read(NOTES / "019-candidate-state-corpus.json")
    old = {(row["entry_id"], row["style"]): row for row in previous["results"]}
    regressions = [
        row for row in corpus["results"]
        if old[(row["entry_id"], row["style"])]["code"] == "IDENTIFIED_CORRECT"
        and row["code"] != "IDENTIFIED_CORRECT"
    ]
    if corpus["code"] != "STATE_CORPUS_GROUNDING_VALIDATED" or regressions:
        raise ValueError("COHERENCE_020_STATE_CORPUS_REGRESSION")
    record(NOTES / "020-candidate-state-corpus.json", {**corpus, "regressions": regressions})
    record(NOTES / "020-verification.json", {
        "code": "COHERENCE_020_CANDIDATE_VALIDATED", "result": result,
        "baseline_sha256": parent["sha256"], "benchmark_comparisons": comparisons,
        "state_corpus_outcomes": dict(Counter(row["code"] for row in corpus["results"])),
        "joint_support_reduction_bits": joint["log2_support_ratio"],
        "marginal_potential_reduction_bits": joint["marginal_potential_reduction_bits"],
    })
    print("COHERENCE_020_CANDIDATE_VALIDATED", result["new_cells"], flush=True)


def publish():
    parent = freeze()
    verification = read(NOTES / "020-verification.json")
    if verification["code"] != "COHERENCE_020_CANDIDATE_VALIDATED":
        raise ValueError("COHERENCE_020_VERIFICATION_REQUIRED")
    result = verification["result"]
    destination = BASE.with_name("sparse-release-020.db")
    publication = WORK / "publication"
    publication.mkdir(exist_ok=True)
    release = publish_round(result, publication, destination, NOTES / "sparse-release-020-gold.json")
    record(NOTES / "020-publication.json", release)
    if release["code"] != "PUBLISHED_SPARSE_LEXICON":
        raise ValueError("COHERENCE_020_PUBLICATION_BLOCKED")
    if Path(release["previous_path"]) != BASE or resolve_lexicon_path() != destination:
        raise ValueError("COHERENCE_020_ACTIVE_RELEASE_MISMATCH")
    if (
        release["cells"]["assigned"] != parent["cells"]["assigned"] + result["new_cells"]
        or release["cells"]["explicit_zero"] != parent["cells"]["explicit_zero"]
    ):
        raise ValueError("COHERENCE_020_PUBLICATION_COUNTS_DIFFER")
    checks = []
    with GSEEncoder() as encoder:
        encoder.conn.execute("PRAGMA query_only=ON")
        if encoder.db_path != destination:
            raise ValueError("COHERENCE_020_DEFAULT_CONSUMER_CHANGED")
        for family in read(WORK / "plan.json")["families"]:
            for entry in family["holdouts"]:
                bank = family["consequent"][0]
                domain = encoder.lookup_definition(entry)["selected"]["domains"][bank]
                if domain != [1]:
                    raise ValueError("COHERENCE_020_CONSUMER_DOMAIN_MISMATCH:" + entry)
                encoder.encode_definition(entry)
                checks.append({"entry_id": entry, "bank": bank, "domain": domain, "compiled": True})
    record(NOTES / "sparse-release-020-activation.json", {
        "code": "ACTIVE_COHERENCE_020_VERIFIED", "path": str(destination), "previous_path": str(BASE),
        "sha256": release["sha256"], "pointer_sha256": fingerprint(ACTIVE_POINTER),
        "cells": release["cells"], "replay": release["replay"],
        "semantic_outcomes": release["semantic_audit"]["outcomes"], "fresh_default_consumer": checks,
    })
    print("ACTIVE_COHERENCE_020_VERIFIED", release["cells"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("verify", "publish"))
    {"verify": verify, "publish": publish}[parser.parse_args().phase]()
