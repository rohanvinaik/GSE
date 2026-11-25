"""Verify extracted NSM explications against their source texts, by exact match.

Each record in ``data/external/references/notes/explications/<KEY>.jsonl`` names its source key, a 1-based
inclusive line range and the explication text. A record is accepted only if its text, with runs of
whitespace collapsed, occurs within the source's same line range, collapsed the same way. Nothing is
corrected or inferred; rejected records are listed with their reason. The sources are copyrighted and
git-ignored; this script and its counts are what the repository keeps.

    .venv/bin/python scripts/verify_nsm_explications.py [--write-verified]
"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path("data/external/references")
SOURCES = {
    "G12": "goddard-2012-primes-molecules-templates.txt",
    "GW07": "goddard-wierzbicka-2007-physical-qualities.txt",
    "GW16": "goddard-wierzbicka-2016-doing-and-happening.txt",
    "G18": "goddard-2018-semantic-menagerie.txt",
    "LFH22": "levisen-fernandez-hein-2022-nordic-guide-to-nsm.txt",
    "GW2014": "goddard-wierzbicka-2014-words-and-meanings.txt",
}


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def check(record: dict, lines: list[str]) -> str:
    """ACCEPTED, or the named reason the record is rejected."""
    start, end = record.get("start_line"), record.get("end_line")
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        return "INVALID_LINE_RANGE"
    text = record.get("text")
    if not isinstance(text, str) or not text.strip():
        return "EMPTY_TEXT"
    if _collapse(text) not in _collapse("\n".join(lines[start - 1 : end])):
        return "TEXT_NOT_IN_CITED_LINES"
    return "ACCEPTED"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write-verified", action="store_true")
    args = parser.parse_args()
    for path in sorted((ROOT / "notes" / "explications").glob("*.jsonl")):
        if path.name.endswith(".verified.jsonl"):
            continue
        key = path.stem
        lines = (ROOT / SOURCES[key]).read_text(encoding="utf-8").splitlines()
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        results = [(record, check(record, lines)) for record in records]
        accepted = [record for record, code in results if code == "ACCEPTED"]
        rejected = [(record.get("start_line"), code) for record, code in results if code != "ACCEPTED"]
        print(f"{key}: {len(records)} records, {len(accepted)} accepted, rejected {rejected[:20]}")
        if args.write_verified:
            out = path.with_suffix(".verified.jsonl")
            out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in accepted), encoding="utf-8")


if __name__ == "__main__":
    main()
