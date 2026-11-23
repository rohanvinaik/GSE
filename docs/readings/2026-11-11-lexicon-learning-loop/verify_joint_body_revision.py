"""Compare the full joint BODY candidate to the original learning snapshot."""

import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[2]
DATA = ROOT / "data/lexicon_builder/2026-11-01"
BASELINE = DATA / "constructed-corpus-learning-alive.db"
CANDIDATE = DATA / "constructed-corpus-joint-body.db"


def load(name):
    return json.loads((FOLDER / name).read_text())


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def compare(conn):
    counts = [
        conn.execute(f"SELECT count(*) FROM {schema}.definition_states").fetchone()[0]
        for schema in ("main", "original")
    ]
    common = conn.execute(
        "SELECT count(*) FROM main.definition_states n JOIN original.definition_states o USING(entry_id)"
    ).fetchone()[0]
    if counts != [common, common]:
        raise ValueError("JOINT_REVISION_DEFINITION_POPULATION_CHANGED")
    changes = []
    for entry, before, after in conn.execute(
        "SELECT n.entry_id,o.domains,n.domains FROM main.definition_states n "
        "JOIN original.definition_states o USING(entry_id) WHERE n.domains<>o.domains ORDER BY n.entry_id"
    ):
        old, new = json.loads(before), json.loads(after)
        if old.keys() != new.keys():
            raise ValueError("JOINT_REVISION_BANK_BASIS_CHANGED")
        changes.extend(
            {"entry_id": entry, "bank": bank, "before": old[bank], "after": value}
            for bank, value in new.items()
            if old[bank] != value
        )
    return common, changes


def main():
    prior = load("alive-cycle-verification.json")
    migration = load("joint-body-migration.json")
    scope = load("joint-body-source-scope.json")
    plan = load("joint-body-revision-plan.json")
    teaching = load("joint-teaching-checkpoint.json")
    exceptions = {row["entry_id"] for row in plan["exceptions"]}
    witnessed = {row["definition"]["entry_id"]: row["BODY"] for rows in scope.values() for row in rows}
    expected = {entry for entry, domain in witnessed.items() if entry not in exceptions and domain != [0]}
    if any(
        migration[key]["code"] != "REPLAY_VALIDATED" or not migration[key]["complete_search"]
        for key in ("preflight", "postflight")
    ):
        raise ValueError("JOINT_REVISION_REPLAY_INCOMPLETE")
    if set(row["entry_id"] for row in migration["reviewed_exceptions"]) != exceptions:
        raise ValueError("JOINT_REVISION_EXCEPTION_CENSUS_MISMATCH")
    with closing(sqlite3.connect(CANDIDATE.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("ATTACH DATABASE ? AS original", (BASELINE.as_uri() + "?mode=ro",))
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        count, changes = compare(conn)
    if (
        {change["entry_id"] for change in changes} != expected
        or len(changes) != len(expected)
        or any(row["bank"] != "BODY" or row["before"] != [-1, 0, 1] or row["after"] != [0] for row in changes)
    ):
        raise ValueError("JOINT_REVISION_UNEXPECTED_DOMAIN_CHANGES")
    active_hash = sha256(ROOT / "data/lexicon_active.json")
    baseline_hash = sha256(BASELINE)
    if active_hash != prior["active_pointer_sha256"] or baseline_hash != prior["candidate_sha256"]:
        raise ValueError("JOINT_REVISION_PARENT_OR_ACTIVE_POINTER_CHANGED")
    result = {
        "format": "GSE.joint-body-cycle-verification/1",
        "code": "CYCLE_REPLAY_VALIDATED_CANDIDATE_INCOMPLETE",
        "candidate": str(CANDIDATE),
        "candidate_sha256": sha256(CANDIDATE),
        "baseline_sha256": baseline_hash,
        "active_pointer_sha256": active_hash,
        "definitions_compared": count,
        "admitted_rules": len(plan["admissions"]),
        "reviewed_local_exceptions": migration["reviewed_exceptions"],
        "reconsidered_known_domains": migration["known_domain_changes"],
        "teaching_attempts": dict(Counter(row["code"] for row in teaching["attempts"])),
        "teaching_never_started": len(teaching["never_started"]),
        "heldout_agreements": sum(
            load(f"joint-{name}-withheld.json")["candidates"][0]["audit_outcomes"].get("MODEL_AGREEMENT", 0)
            for name in ("linear", "monetary")
        ),
        "changed_domains": changes,
        "new_body_zero_assignments": len(changes),
        "coverage": migration["coverage"],
        "migration_event_id": migration["event_id"],
        "activation_performed": False,
    }
    with (FOLDER / "joint-body-verification.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "code",
                    "definitions_compared",
                    "new_body_zero_assignments",
                    "coverage",
                    "activation_performed",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
