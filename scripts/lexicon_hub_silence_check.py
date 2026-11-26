"""Can a hub explication's unused primes be inherited as silence by its subkinds? Checked against NSM's own subkind
explications (NEGATIVE_SPECIFICATION Prop. 5.5: every proposed silence is tested against observed content).

Reads the verified explication extracts (copyrighted, git-ignored) and writes only source keys, line ranges and prime
sets to the receipt.

    .venv/bin/python scripts/lexicon_hub_silence_check.py --receipt docs/verification/<date>-hub-silence-vs-nsm-subkinds.json
"""

import argparse
import json
from pathlib import Path

from GSE.curation.lexicon_builder.template_types import banks_in, own_lines, verified_records

HUBS = {
    ("G18", "creatures"): ("animals", "birds", "fish", "snakes", "dogs", "kangaroos"),
    ("G18", "animals"): ("dogs", "kangaroos"),
    ("GW2014", "children"): ("boys", "girls", "babies"),
}


def _record(source: str, name: str) -> dict:
    return next(r for r in verified_records() if r["source"] == source and r["explicates"].lower() == name)


def _own(record: dict) -> set[str]:
    return set().union(set(), *(banks_in(clause) for clause in own_lines(record["text"])))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    hubs, fails, total = [], 0, 0
    for (source, hub), members in HUBS.items():
        record = _record(source, hub)
        hub_primes = _own(record)
        row = {
            "hub": hub,
            "source": source,
            "lines": [record["start_line"], record["end_line"]],
            "own_primes": sorted(hub_primes),
            "members": [],
        }
        for member in members:
            m = _record(source, member)
            primes = _own(m)
            extra = sorted(primes - hub_primes)
            fails += bool(extra)
            total += 1
            row["members"].append(
                {
                    "member": member,
                    "lines": [m["start_line"], m["end_line"]],
                    "own_primes": sorted(primes),
                    "used_but_hub_silent": extra,
                }
            )
        hubs.append(row)
    receipt = {
        "question": __doc__.split("\n\n")[0],
        "method": "template_types.own_lines (category line + clauses whose subject is the referent) -> banks_in "
        "(catalog exponent forms, WordNet morphology, [m] molecules skipped)",
        "hubs": hubs,
        "result": f"{fails} of {total} subkinds use primes their hub never uses",
    }
    args.receipt.write_text(json.dumps(receipt, indent=1) + "\n")
    print(receipt["result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
