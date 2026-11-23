"""Replay and apply several reviewed rule changes in one candidate transaction."""

import argparse
import json
from pathlib import Path

from gse.curation.lexicon_builder.interchange import read_json
from gse.curation.lexicon_builder.rule_admission import admit_rule
from gse.curation.lexicon_builder.rule_migration import migrate_revision
from gse.curation.lexicon_builder.rule_revisions import FORMAT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        raise ValueError("MIGRATION_REPORT_MUST_BE_NEW")
    if args.report.resolve() in {args.candidate.resolve(), args.output.resolve(), args.plan.resolve()}:
        raise ValueError("MIGRATION_REPORT_COLLISION")
    plan = read_json(args.plan)
    fields = {"format", "baseline_version", "admissions", "retirements", "exceptions"}
    if type(plan) is not dict or set(plan) != fields or plan["format"] != "gse.rule-revision-plan/1":
        raise ValueError("INVALID_RULE_REVISION_PLAN")
    if type(plan["admissions"]) is not list or any(
        type(item) is not dict
        or set(item) != {"input", "audit", "review"}
        or any(type(value) is not str or not value.strip() for value in item.values())
        for item in plan["admissions"]
    ):
        raise ValueError("INVALID_REVISION_ADMISSION_PLAN")
    admissions = []
    for record in plan["admissions"]:
        files = {key: args.plan.parent / file for key, file in record.items()}
        admissions.append(admit_rule(files["input"], files["audit"], read_json(files["review"])))
    revision = {**plan, "format": FORMAT, "admissions": admissions}
    result = migrate_revision(args.candidate, args.output, revision)
    with args.report.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({key: result[key] for key in ("code", "candidate", "event_id")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
