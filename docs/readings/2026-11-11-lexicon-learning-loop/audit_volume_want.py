"""Derive a volume-specific WANT rule, stage it and audit withheld definitions."""

import argparse
import json
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from complete_unit_want_cycle import MODEL, MODEL_DIGEST
from complete_unit_want_cycle import OUTPUT as BASELINE
from probe_unit_banks import execute
from replay_body_exceptions import FOLDER, ROOT, read, sha256, write

from GSE.curation.lexicon_builder.model_batch import OllamaBatchTransport
from GSE.curation.lexicon_builder.residual import OllamaTransport
from GSE.curation.lexicon_builder.reviewed_export import export_reviewed_input
from GSE.curation.lexicon_builder.reviewed_patterns import run_workflow_input
from GSE.curation.lexicon_builder.rule_admission import _AuditReplay, admit_records
from GSE.curation.lexicon_builder.rule_history import digest
from GSE.curation.lexicon_builder.rule_revisions import exception_source

SEED = "wordnet:cup:cup.n.04"
ANCESTOR = "volume_unit.n.01"
EXCLUDED = "quarter.n.09"
AUDIT_IDS = (
    "wordnet:arroba:arroba.n.02",
    "wordnet:cord:cord.n.02",
    "wordnet:fifth:fifth.n.01",
    "wordnet:yard:cubic_yard.n.01",
)
STATEMENT = (
    "An attested native volume-unit noun in the reviewed source scope defines a volume standard, capacity, "
    "or amount by volume. That positive definitional role is orthogonal to WANT. A person's use, preference, "
    "or aim involving the measured material does not define the amount. A source that defines a weight, "
    "a vessel, or a conative state requires separate treatment. The exact quarter.n.09 gloss defines a "
    "fraction of a hundredweight, so its volume ancestry does not license this volume-specific rule."
)
PREFIX = "volume-want"
REVIEWER = "Codex source-backed review"


@dataclass(frozen=True)
class WantAudit:
    prefix: str
    baseline: Path
    parent_report: str
    ancestor: str
    seeds: tuple[tuple[str, str, str], ...]
    held_out: tuple[str, ...]
    exclusions: tuple[tuple[str, str], ...]
    statement: str
    rule_slug: str

    def load(self, name):
        return read(FOLDER / f"{self.prefix}-{name}.json")

    def save(self, name, value):
        write(FOLDER / f"{self.prefix}-{name}.json", value)


VOLUME = WantAudit(
    PREFIX,
    BASELINE,
    "unit-quantity-want-cycle-verification.json",
    ANCESTOR,
    (
        (
            SEED,
            "cup-discovery",
            "This cup is a conventional liquid amount of eight fluid ounces. The amount's definitional role is orthogonal to desire.",
        ),
    ),
    AUDIT_IDS,
    ((EXCLUDED, "The exact definition is a fraction of a hundredweight."),),
    STATEMENT,
    "volume",
)


def load(name):
    return VOLUME.load(name)


def save(name, value):
    VOLUME.save(name, value)


def prepare(spec=VOLUME):
    parent = read(FOLDER / spec.parent_report)
    if sha256(spec.baseline) != parent["candidate_sha256"]:
        raise ValueError("WANT_AUDIT_BASELINE_CHANGED")
    scope = read(FOLDER / "native-unit-quantity-scope.json")
    native = [
        row for row in scope["witnesses"] if row["native_lemma"] and any(spec.ancestor in path for path in row["paths"])
    ]
    excluded = dict(spec.exclusions)
    rows = {row["definition"]["entry_id"]: row for row in native if row["synset"] not in excluded}
    expected, distributions = [], Counter()
    with closing(sqlite3.connect(spec.baseline.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        for identity, item in rows.items():
            if digest(exception_source(conn, identity)) != item["source_sha256"]:
                raise ValueError("WANT_AUDIT_SCOPE_SOURCE_CHANGED:" + identity)
            [raw] = conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (identity,)).fetchone()
            state = json.loads(raw)
            distributions[tuple(state["WANT"])] += 1
            if state["QUANTITY"] != [1]:
                raise ValueError("WANT_AUDIT_UNPROVED_QUANTITY:" + identity)
            if len(state["WANT"]) > 1:
                expected.append(identity)
            elif state["WANT"] != [0]:
                raise ValueError("WANT_AUDIT_EXISTING_COUNTEREXAMPLE:" + identity)
    source_path = FOLDER / f"{spec.prefix}-scope.json"
    source_ref = str(source_path.relative_to(ROOT))
    spec.save(
        "scope",
        {
            "format": f"gse.{spec.prefix}-scope/1",
            "baseline_sha256": parent["candidate_sha256"],
            "source_warrant": spec.statement,
            "rows": list(rows.values()),
            "scope_challenges": [row for row in native if row["synset"] in excluded],
            "expected_new_want_zero": sorted(expected),
            "baseline_target_domains": [{"domain": domain, "count": n} for domain, n in sorted(distributions.items())],
        },
    )
    guards = [
        ["pos", "noun"],
        ["wordnet_native_lemma", "true"],
        [f"wordnet_ancestor:{spec.ancestor}", "true"],
        *[[f"wordnet_other_than_synset:{synset}", "true"] for synset, _ in spec.exclusions],
    ]
    # The stage tests the same relational semantics as the eventual migration.
    spec.save(
        "stage-input",
        {
            "format": "GSE.coherence-stage-input/2",
            "baseline_sha256": parent["candidate_sha256"],
            "semantics": "RELATIONAL_CONSTRAINT",
            "proposals": [
                {
                    "id": f"stage:native-{spec.rule_slug}-unit:quantity-want",
                    "antecedent": ["QUANTITY", 1],
                    "consequent": ["WANT", 0],
                    "guards": guards,
                    "source_refs": [source_ref],
                }
            ],
            "scope_challenges": [
                {
                    "antecedent": ["QUANTITY", 1],
                    "consequent": ["WANT", 0],
                    "native_synset": synset,
                    "reason": reason,
                }
                for synset, reason in spec.exclusions
            ],
        },
    )
    if (FOLDER / f"{spec.prefix}-input.json").exists():
        return
    selection = {
        "format": "GSE.reviewed-pattern-selection/1",
        "discovery_entry_ids": [identity for identity, _, _ in spec.seeds],
        "audit_entry_ids": [],
        "reviews": [],
    }
    seeds = {
        row["entry_id"]: row
        for row in export_reviewed_input(spec.baseline, selection)["inventory"]
        if row["bank"] == "WANT" and row["receipt"]["assertion"]["value"] == 0
    }
    if seeds.keys() != set(selection["discovery_entry_ids"]):
        raise ValueError("WANT_AUDIT_SEED_MISMATCH")
    selection.update(
        audit_entry_ids=list(spec.held_out),
        reviews=[
            {
                "request_id": seeds[identity]["request_id"],
                "review": {
                    "code": "ACCEPTED",
                    "receipt_sha256": seeds[identity]["receipt_sha256"],
                    "review_id": f"{spec.prefix}-{review_id}",
                    "reviewer": REVIEWER,
                    "source_refs": [source_ref, "exact-source:sha256:" + rows[identity]["source_sha256"]],
                    "rationale": rationale,
                },
            }
            for identity, review_id, rationale in spec.seeds
        ],
        guarded_candidates=[
            {
                "antecedent": ["QUANTITY", 1],
                "consequent": ["WANT", 0],
                "guards": guards,
                "absent_evidence": [],
                "warrant": {
                    "kind": "DEFINITIONAL_DERIVATION",
                    "warrant_id": f"exact-{spec.rule_slug}-unit-quantity-want",
                    "review_id": f"{spec.prefix}-source-scope",
                    "reviewer": REVIEWER,
                    "source_refs": [source_ref],
                    "statement": spec.statement,
                },
            }
        ],
    )
    spec.save("input", export_reviewed_input(spec.baseline, selection)["input"])


def transport(*, batch_size=4, timeout=240):
    model = OllamaBatchTransport(
        OllamaTransport(MODEL, context_tokens=65536, timeout=timeout, thinking=False, output_tokens=256),
        max_items=batch_size,
    )
    model.pin()
    if not model.identity.startswith(f"{MODEL}#{MODEL_DIGEST}@"):
        raise ValueError("VOLUME_WANT_MODEL_DIGEST_CHANGED")
    return model


def audit(spec=VOLUME):
    raw = spec.load("input")
    [draft] = run_workflow_input(raw)["candidates"]
    questions = draft["audits"]
    if not all(item["code"] == "AUDIT_CALL_BUDGET_EXHAUSTED" for item in questions):
        raise ValueError("WANT_AUDIT_WITHHELD_QUESTION_NOT_READY")
    folder = FOLDER / f"{spec.prefix}-held-out-answers"
    folder.mkdir(exist_ok=True)
    execute(questions, folder, transport())
    captured = [{**item, **read(folder / (item["request_id"] + ".json"))} for item in questions]
    if any("raw_output" not in row for row in captured):
        spec.save(
            "audit-operational-refusals",
            [
                {key: row[key] for key in ("entry_id", "request_id", "code")}
                for row in captured
                if "raw_output" not in row
            ],
        )
        raise ValueError("WANT_AUDIT_OPERATIONALLY_INCOMPLETE")
    replay = _AuditReplay(captured)
    report = run_workflow_input(raw, replay, max_calls=len(captured))
    spec.save("audit", report)
    [candidate] = report["candidates"]
    print(
        json.dumps(
            {
                "discovery": candidate["discovery_outcomes"],
                "audit": candidate["audit_outcomes"],
                "staging": dict(Counter(row["code"] for row in candidate["staging"])),
            }
        ),
        flush=True,
    )


def review(spec=VOLUME):
    raw, audit, stage_report, scope = [spec.load(name) for name in ("input", "audit", "stage-report", "scope")]
    [candidate] = audit["candidates"]
    staged = {row["definition"]["entry_id"]: row["changes"] for row in stage_report["changes"]}
    expected = {
        identity: {"WANT": {"before": [-1, 0, 1], "after": [0]}} for identity in scope["expected_new_want_zero"]
    }
    if (
        staged != expected
        or stage_report["contradictions"]
        or stage_report["candidate_sha256"] != scope["baseline_sha256"]
    ):
        raise ValueError("WANT_AUDIT_FULL_POPULATION_CHALLENGE")
    review = {
        "rule_id": candidate["relation"]["rule_id"],
        "warrant_sha256": candidate["warrant_sha256"],
        "review_id": f"{spec.prefix}-admission-review",
        "reviewer": REVIEWER,
        "decision": "APPROVE_DEFINITIONAL_RULE",
        "source_refs": [f"{spec.prefix}-{name}.json" for name in ("scope", "audit", "stage-report")],
        "rationale": spec.statement,
    }
    admission = admit_records(raw, audit, review)
    spec.save("review", review)
    spec.save(
        "revision-plan",
        {
            "format": "GSE.rule-revision-plan/1",
            "baseline_version": admission["baseline_version"],
            "admissions": [{kind: f"{spec.prefix}-{kind}.json" for kind in ("input", "audit", "review")}],
            "retirements": [],
            "exceptions": [],
        },
    )
    print(
        json.dumps(
            {
                "code": admission["code"],
                "new_want_zero": len(expected),
                "rule_id": candidate["relation"]["rule_id"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "audit", "review"))
    args = parser.parse_args()
    {"prepare": prepare, "audit": audit, "review": review}[args.phase]()
