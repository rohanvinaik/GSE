"""Dry-run or explicitly apply conservative withdrawal of one accepted model suffix."""

import argparse
import json
from pathlib import Path

from GSE.curation.lexicon_builder.reconsideration import reconsider, reconsider_many


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lexicon-db", type=Path, required=True)
    parser.add_argument("--request-id", required=True, action="append")
    parser.add_argument("--convention", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--expected-snapshot")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.report is not None and (
        args.report.resolve() == args.lexicon_db.resolve()
        or args.report.exists()
        and args.report.samefile(args.lexicon_db)
    ):
        raise ValueError("RECONSIDERATION_REPORT_CANNOT_OVERWRITE_DATABASE")
    writer = reconsider if len(args.request_id) == 1 else reconsider_many
    report = writer(
        args.lexicon_db,
        args.request_id[0] if len(args.request_id) == 1 else args.request_id,
        convention=args.convention,
        reason=args.reason,
        apply=args.apply,
        expected_snapshot=args.expected_snapshot,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if args.report is not None:
        args.report.write_text(encoded + "\n")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
