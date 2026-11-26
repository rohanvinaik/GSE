"""Write sub-kind inheritance into a build copy's derived table (word_sense_subkinds), then report.

    .venv/bin/python scripts/word_sense_subkinds.py --db data/lexicon_builder/2026-11-12/building.db \
        --receipt docs/verification/<date>-subkind-inheritance.json [--dry-run]
"""

import argparse
import json
import random
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from GSE.curation.lexicon_builder.word_sense_subkinds import admit, inherit, write


def main() -> int:
    sys.setrecursionlimit(10000)  # kind-of, refinement and entailment chains run deeper than Python's default
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    conn = sqlite3.connect(args.db)
    candidates, census = inherit(conn)
    rows, admission = admit(
        conn,
        candidates,
        progress=lambda done, n: print(f"  admitted {done}/{n}", flush=True) if done % 5000 < 500 else None,
    )
    census = {
        **census,
        "candidates": census["definitions"],
        "candidate_cells": census["cells"],
        "definitions": admission["definitions"],
        "cells": admission["cells"],
    }
    by_bank = Counter(b for settled, _edge in rows.values() for b in settled)
    by_template = Counter(edge["template"] for _s, edge in rows.values())
    sample = random.Random(20261126).sample(sorted(rows), min(40, len(rows)))
    receipt = {
        "db": str(args.db),
        "definitions": census["definitions"],
        "cells": census["cells"],
        "by_bank": dict(by_bank.most_common()),
        "by_template": dict(by_template),
        "candidates": census["candidates"],
        "candidate_cells": census["candidate_cells"],
        "consequence_cells": admission["consequence_cells"],
        "suspended_defaults": admission["suspended"],
        "suspended_banks": dict(Counter(r["bank"] for r in admission["suspended_rows"]).most_common()),
        "suspended_sample": admission["suspended_rows"][:40],
        "known_conflicts": admission["known_conflicts"],
        "exceptions": census["exceptions"],
        "exception_banks": dict(Counter(e["bank"] for e in census["exception_rows"]).most_common()),
        "exception_sample": census["exception_rows"][:40],
        "sample": {e: {"settled": rows[e][0], "origins": rows[e][1]["origins"]} for e in sample},
    }
    args.receipt.write_text(json.dumps(receipt, indent=1) + "\n")
    if not args.dry_run:
        with conn:
            write(conn, rows)
    print(
        json.dumps(
            {
                k: receipt[k]
                for k in (
                    "candidates",
                    "candidate_cells",
                    "definitions",
                    "cells",
                    "consequence_cells",
                    "suspended_defaults",
                    "exceptions",
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
