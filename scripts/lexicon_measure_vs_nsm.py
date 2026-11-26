"""Measure the live lexicon against NSM's verified explications (element 10; F148: the tail is disagreement with NSM
per word and bank).

For every verified explication whose explicandum is a lemma in the active lexicon, compare the sense the explication
describes with the signed primes in the explication's own components (``template_types.signed_banks_in`` over
``own_lines``): BAD is GOOD -1, SMALL is BIG -1, OTHER is SAME -1. The described sense is the word's sense (or senses)
holding the most of the identity the explication's own category line states ("creatures of one kind", "people of one
kind"); with none, the whole word's reading (what all its senses agree on). A prime whose sign the sense holds agrees;
one it holds otherwise contradicts; one it leaves open is missing; a prime NSM uses with both signs is ambiguous. Not
counted: the deictic THIS (the catalog files it under SOMETHING as a contextual binding) and BE, which this instrument
cannot separate from the copula ("is", "are"). The extracts are copyrighted and git-ignored; the receipt holds source keys, line ranges and bank names.

    .venv/bin/python scripts/lexicon_measure_vs_nsm.py --receipt docs/verification/<date>-lexicon-vs-nsm.json [--db X.db]
"""

import argparse
import json
import re
import sqlite3
from pathlib import Path

from GSE.curation.lexicon_builder.template_types import own_lines, signed_banks_in, verified_records
from GSE.lexicon.senses import read_senses
from GSE.lexicon_resource import resolve_lexicon_path

POS_GUESS = ("noun", "verb", "adj")
THIS_UNIT = frozenset({"nsm:v20:this"})
UNMEASURED = frozenset({"BE"})


def _nsm_values(text: str) -> tuple[dict[str, int], list[str], dict[str, int]]:
    """(bank -> NSM's sign over the own clauses, banks used with both signs, the identity the category line states)."""
    clauses = own_lines(text)
    signs: dict[str, set[int]] = {}
    for clause in clauses:
        for bank, found in signed_banks_in(clause, skip_units=THIS_UNIT).items():
            signs.setdefault(bank, set()).update(found)
    category = _category(clauses[0]) if clauses else {}
    values = {b: next(iter(s)) for b, s in signs.items() if len(s) == 1 and b not in UNMEASURED}
    return (
        values,
        sorted(b for b, s in signs.items() if len(s) > 1 and b not in UNMEASURED),
        category if clauses else {},
    )


def _category(line: str, seen: frozenset[str] = frozenset()) -> dict[str, int]:
    """The identity a category line states. A molecule it names ("creatures [m] of one kind") contributes the category
    of that molecule's own verified explication (NSM: a molecule is defined by its explication)."""
    found = {b: next(iter(s)) for b, s in signed_banks_in(line, skip_units=THIS_UNIT).items() if len(s) == 1}
    for molecule in re.findall(r"([a-z’'-]+) \[m\]", line.lower()):
        if molecule in seen:
            continue
        record = next(
            (r for r in verified_records() if r["kind"] == "explication" and r["explicates"].lower() == molecule), None
        )
        clauses = own_lines(record["text"]) if record else []
        if clauses:
            found.update(_category(clauses[0], seen | {molecule}))
    return found


def _described(conn, lemma: str, pos: str, category: dict[str, int], fallback: dict) -> tuple[dict, list]:
    """The agreement of the senses holding the most of the category line's identity, or the whole reading."""
    rows = conn.execute(
        "SELECT sense, assignments FROM word_senses WHERE lemma = ? AND pos = ?", (lemma, pos)
    ).fetchall()
    scored = [(sum(json.loads(a).get(b) == v for b, v in category.items()), s, json.loads(a)) for s, a in rows]
    best = max((score for score, _s, _a in scored), default=0)
    if best == 0:
        return fallback, []
    chosen = [(s, a) for score, s, a in scored if score == best]
    banks = set().union(*(a for _s, a in chosen))
    agreed = {b: chosen[0][1][b] for b in banks if all(a.get(b) == chosen[0][1].get(b) for _s, a in chosen)}
    return agreed, [s for s, _a in chosen]


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
    rows, totals = [], {"agree": 0, "contradict": 0, "missing": 0, "ambiguous": 0}
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
        nsm, ambiguous, category = _nsm_values(record["text"])
        held, senses = _described(conn, used[0], used[1], category, reading["assignments"])
        agree = [b for b, v in sorted(nsm.items()) if held.get(b) == v]
        contradict = [b for b, v in sorted(nsm.items()) if b in held and held[b] != v]
        missing = [b for b in sorted(nsm) if b not in held]
        for key, banks in (
            ("agree", agree),
            ("contradict", contradict),
            ("missing", missing),
            ("ambiguous", ambiguous),
        ):
            totals[key] += len(banks)
        rows.append(
            {
                "source": record["source"],
                "lines": [record["start_line"], record["end_line"]],
                "lemma": used[0],
                "pos": used[1],
                "nsm_primes": nsm,
                "described_senses": senses,
                "ambiguous": ambiguous,
                "agree": agree,
                "contradict": {b: held[b] for b in contradict},
                "missing": missing,
                "lexicon_only": sorted(b for b, v in held.items() if v and b not in nsm and b not in ambiguous),
            }
        )
    receipt = {"lexicon": str(db), "explications_matched": len(rows), "totals": totals, "rows": rows}
    args.receipt.write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps({"explications_matched": len(rows), "totals": totals}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
