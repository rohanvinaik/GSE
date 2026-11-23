"""Export selected candidate evidence and explicit reviews without changing the lexicon."""

import argparse
import json
from pathlib import Path

from GSE.curation.lexicon_builder.reviewed_export import export_from_selection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    paths = [args.candidate, args.selection, args.input, args.report]
    for index, path in enumerate(paths):
        if any(
            path.resolve() == other.resolve() or path.exists() and other.exists() and path.samefile(other)
            for other in paths[:index]
        ):
            raise ValueError("PATTERN_EXPORT_PATH_COLLISION")
    report = export_from_selection(args.candidate, args.selection)
    args.input.write_text(json.dumps(report["input"], indent=2, sort_keys=True) + "\n")
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"lexicon_writes": False, "model_calls": 0, "review_outcomes": report["review_outcomes"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
