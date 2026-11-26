"""What changed between two lexicons' word senses: filled, changed, removed, and by which warrant.

The audit of a rebuild is a tally, not a reading of every value. For each word and part of speech this
compares the main sense (the reading the runtime uses) of a ``before`` lexicon with an ``after`` one:

- filled: a bank that was open now has a value; counted by its warrant (the rule ids, the agreeing
  source families, or the definitions it came from);
- changed: a bank had one value and now has another (a correct value should never be destroyed);
- removed: a bank had a value and is open again (expected only where a rule deliberately withdraws a
  main sense, such as WP-0's untrusted first senses).

    .venv/bin/python scripts/compare_word_senses.py \\
        --before <the active lexicon> \\
        --after data/lexicon_builder/2026-11-12/building.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path


def readings(path: Path) -> dict[tuple[str, str], tuple[dict, dict]]:
    """(lemma, pos) -> the reading GSE takes for that part of speech (what every sense shares, as
    ``GSE.lexicon.senses`` reads it), with each agreed bank's provenance from the senses that hold it."""
    from GSE.lexicon.senses import reading

    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT lemma, pos, assignments, open, members, provenance FROM word_senses ORDER BY lemma, pos, sense"
    )
    grouped: dict[tuple[str, str], list[tuple[dict, dict]]] = {}
    for lemma, pos, a, o, m, p in rows:
        grouped.setdefault((lemma, pos), []).append(
            ({"assignments": json.loads(a), "open": json.loads(o), "members": json.loads(m)}, json.loads(p))
        )
    conn.close()
    found = {}
    for key, senses in grouped.items():
        agreed, _possible, _exceptions = reading([s for s, _ in senses])
        provenance = {
            bank: next(p[bank] for _s, p in senses if bank in p)
            for bank in agreed
            if any(bank in p for _s, p in senses)
        }
        found[key] = (agreed, provenance)
    return found


def warrant(origin: dict | None) -> str:
    if not isinstance(origin, dict):
        return "none"
    kind = origin.get("from")
    if kind == "rules":
        return "rules:" + ",".join(origin.get("rules") or ["?"])
    if kind == "source-agreement":
        return "agreement:" + "+".join(sorted(origin.get("families") or ["?"]))
    return str(kind)


def compare(before: dict, after: dict, examples: int = 50) -> dict:
    filled, filled_nonzero, changed, removed = Counter(), Counter(), [], []
    for key in sorted(set(before) | set(after)):
        old, _ = before.get(key, ({}, {}))
        new, provenance = after.get(key, ({}, {}))
        for bank, value in new.items():
            if bank not in old:
                filled[warrant(provenance.get(bank))] += 1
                filled_nonzero[warrant(provenance.get(bank))] += value != 0
            elif old[bank] != value:
                changed.append(f"{key[0]}/{key[1]} {bank}: {old[bank]} -> {value}")
        removed.extend(f"{key[0]}/{key[1]} {bank}={value}" for bank, value in old.items() if bank not in new)
    return {
        "readings_before": len(before),
        "readings_after": len(after),
        "filled": sum(filled.values()),
        "filled_nonzero": sum(filled_nonzero.values()),
        "changed": len(changed),
        "removed": len(removed),
        "filled_by_warrant": dict(filled.most_common()),
        "filled_nonzero_by_warrant": {k: v for k, v in filled_nonzero.most_common() if v},
        "changed_examples": changed[:examples],
        "removed_by_word": removed[: examples * 4],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--examples", type=int, default=50)
    args = parser.parse_args(argv)
    print(json.dumps(compare(readings(args.before), readings(args.after), args.examples), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
