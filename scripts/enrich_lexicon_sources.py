"""Verify and add exact native context to a separate lexicon candidate."""

import argparse
import json
from pathlib import Path

from GSE.curation.lexicon_builder.source_enrichment import enrich_sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--wiktionary-source", type=Path)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        raise ValueError("ENRICHMENT_REPORT_MUST_BE_NEW")
    paths = [args.candidate, args.output, args.input, args.report]
    if args.wiktionary_source is not None:
        paths.append(args.wiktionary_source)
    for index, path in enumerate(paths):
        if any(
            path.resolve() == other.resolve() or path.exists() and other.exists() and path.samefile(other)
            for other in paths[:index]
        ):
            raise ValueError("ENRICHMENT_PATH_COLLISION")
    result = enrich_sources(args.candidate, args.output, args.input, wiktionary_source=args.wiktionary_source)
    with args.report.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    print(json.dumps({key: result[key] for key in ("code", "candidate", "added_records", "bank_changes")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
