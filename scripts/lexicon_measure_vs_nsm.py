"""Measure the live lexicon against NSM's verified explications (element 10; F148: the tail is disagreement with NSM
per word and bank).

For every verified explication whose explicandum is a lemma in the active lexicon, compare the word's sense readings
(``GSE.lexicon.senses.read_senses``) with the primes in the explication's own components (``template_types``): a prime
NSM uses that the reading holds at +1 agrees; one the reading holds at 0 or -1 contradicts; one the reading leaves open
is missing. The extracts are copyrighted and git-ignored; the receipt holds source keys, line ranges and bank names.

    .venv/bin/python scripts/lexicon_measure_vs_nsm.py --receipt docs/verification/<date>-lexicon-vs-nsm.json [--db X.db]
"""

import argparse
import json
import re
import sqlite3
from pathlib import Path

from GSE.curation.lexicon_builder.template_types import banks_in, own_lines, verified_records
from GSE.lexicon.senses import read_senses
from GSE.lexicon_resource import resolve_lexicon_path

POS_GUESS = ("noun", "verb", "adj")


def _lemma(explicandum: str) -> str | None:
    words = re.sub(r"\(.*?\)|\[.*?\]", " ", explicandum.lower()).split()
    return words[0] if len(words) == 1 else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--db", type=Path, help="a candidate lexicon (default: the active pointer)")
    args = parser.parse_args()
    db = args.db or resolve_lexicon_path()
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows, totals = [], {"agree": 0, "contradict": 0, "missing": 0}
    for record in verified_records():
        if record["kind"] != "explication":
            continue
        lemma = _lemma(record["explicates"])
        if not lemma:
            continue
        candidates = [lemma, lemma[:-1] if lemma.endswith("s") else lemma]
        reading, used = None, None
        for form in dict.fromkeys(candidates):
            for pos in POS_GUESS:
                found = read_senses(conn, form, pos)
                if found and found["pos"] == pos:
                    reading, used = found, (form, pos)
                    break
            if reading:
                break
        if not reading:
            continue
        nsm = sorted(set().union(set(), *(banks_in(c) for c in own_lines(record["text"]))))
        held = reading["assignments"]
        agree = [b for b in nsm if held.get(b) == 1]
        contradict = [b for b in nsm if b in held and held[b] != 1]
        missing = [b for b in nsm if b not in held]
        for key, banks in (("agree", agree), ("contradict", contradict), ("missing", missing)):
            totals[key] += len(banks)
        rows.append(
            {
                "source": record["source"],
                "lines": [record["start_line"], record["end_line"]],
                "lemma": used[0],
                "pos": used[1],
                "nsm_primes": nsm,
                "agree": agree,
                "contradict": {b: held[b] for b in contradict},
                "missing": missing,
                "lexicon_only": sorted(b for b, v in held.items() if v and b not in nsm),
            }
        )
    receipt = {"lexicon": str(db), "explications_matched": len(rows), "totals": totals, "rows": rows}
    args.receipt.write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps({"explications_matched": len(rows), "totals": totals}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
