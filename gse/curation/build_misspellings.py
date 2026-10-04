"""Offline build of the common-misspellings confusion table — the empirical P(x|w)
overlay for the spell-corrector (`gse/nlp/spellcheck.py`).

Spelling mistakes are not rules; they are random, common human errors. This table is
the "common-issue" filter that makes the corrector's candidate set REPRESENTATIVE of
real-world error patterns — observed (typo -> intended) pairs, used by the symbolic
scorer as an error-model prior (candidate injection + a bounded bonus). The grounding
gate still disposes: a table correction is only ever offered if it grounds.

Source: Wikipedia "Lists of common misspellings / For machines" (CC-BY-SA). We commit
the parsed table (small, attributable) to the source tree; the raw page is fetched
live and frozen into the TSV, which is the reproducible artifact.

Run:  python -m gse.curation.build_misspellings
Out:  gse/nlp/data/misspellings_wikipedia.tsv   (typo \t correct1|correct2|...)
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

WIKI_URL = ("https://en.wikipedia.org/wiki/"
            "Wikipedia:Lists_of_common_misspellings/For_machines?action=raw")
_UA = "GSE-spellcheck-build/1.0 (research; rohanpvinaik@gmail.com)"
OUT = Path(__file__).resolve().parents[1] / "nlp" / "data" / "misspellings_wikipedia.tsv"

# ` typo->correct1, correct2` (leading space is wikitext <pre>); skip header/markup.
_LINE = re.compile(r"^\s*([a-z][a-z'-]*)->(.+)$")


def fetch_raw(url: str = WIKI_URL) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse(raw: str) -> dict[str, list[str]]:
    table: dict[str, list[str]] = {}
    for line in raw.splitlines():
        m = _LINE.match(line.strip("\r\n"))
        if not m:
            continue
        typo = m.group(1).strip().lower()
        corrections = []
        for c in m.group(2).split(","):
            c = c.strip().lower()
            if c and re.fullmatch(r"[a-z][a-z'-]*", c) and c != typo:
                corrections.append(c)
        if typo and corrections and typo not in table:
            table[typo] = corrections
    return table


def write_tsv(table: dict[str, list[str]], snapshot_date: str, out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GSE common-misspellings confusion table (empirical P(x|w) overlay).",
        "# Source: Wikipedia 'Lists of common misspellings / For machines'.",
        f"# URL: {WIKI_URL}",
        "# License: CC-BY-SA (attribution + share-alike). Derivative of Wikipedia content.",
        f"# Snapshot: {snapshot_date}   Entries: {len(table)}",
        "# Format: <typo>\\t<correct1|correct2|...>  (corrections in listed order)",
    ]
    for typo in sorted(table):
        lines.append(f"{typo}\t{'|'.join(table[typo])}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> None:
    # snapshot date must be passed in (the build is deterministic given the snapshot)
    snapshot_date = argv[0] if argv else "unknown"
    raw_path = argv[1] if len(argv) > 1 else None
    raw = Path(raw_path).read_text(encoding="utf-8") if raw_path else fetch_raw()
    table = parse(raw)
    write_tsv(table, snapshot_date)
    print(f"wrote {OUT}  ({len(table)} typo entries, snapshot {snapshot_date})")


if __name__ == "__main__":
    main(sys.argv[1:])
