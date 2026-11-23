"""Admit one warranted reviewed rule and create a fully replayed new candidate."""

import argparse
import json
from pathlib import Path

from gse.curation.lexicon_builder.interchange import read_json
from gse.curation.lexicon_builder.rule_migration import migrate_rule


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        raise ValueError("MIGRATION_REPORT_MUST_BE_NEW")
    for file in (args.candidate, args.output, args.input, args.audit, args.review):
        if args.report.resolve() == file.resolve() or (
            args.report.exists() and file.exists() and args.report.samefile(file)
        ):
            raise ValueError("MIGRATION_REPORT_COLLISION")
    result = migrate_rule(args.candidate, args.output, args.input, args.audit, read_json(args.review))
    # Exclusive creation also refuses a symlink installed after preflight.
    with args.report.open("x") as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("code", "candidate", "event_id")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
