#!/usr/bin/env python3
"""
Audit `data/lexicon.db` for NSM bipolar mutual-exclusion violations.

Pure read; no writes. Scans every lexeme in the legacy lexicon database,
collects its active primitive decomposition, and counts how many bipolar
pair members are simultaneously active per word. Emits:

* Aggregate stats: total lexemes, lexemes with ≥1 violation, average
  violations per lexeme.
* Per-bipolar-pair frequency: how often each pair (GOOD/BAD, BIG/SMALL,
  NEAR/FAR, …) appears with both poles active.
* Top-violating words (worst offenders).
* JSON report alongside the human-readable output.

Quantifies the noise level the rebuild would remove. Useful empirical
baseline for the gated archive+rebuild decision in CONSTRUCTION_PLAN.md §9.

Usage
-----

    python scripts/audit_lexicon_violations.py
    python scripts/audit_lexicon_violations.py --db data/lexicon.db --json out.json
    python scripts/audit_lexicon_violations.py --top 25
"""

import argparse
import json
import logging
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict

# When invoked directly (python scripts/audit_lexicon_violations.py) the
# gse package isn't on sys.path; fix that before importing.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gse.curation.external_sources.bipolar_exclusion import count_violations  # noqa: E402
from gse.curation.schema import BIPOLAR_PAIRS  # noqa: E402

logger = logging.getLogger(__name__)


def audit(db_path: Path, top_k: int = 20) -> Dict[str, Any]:
    """Scan `db_path` and produce the violation report."""
    if not db_path.exists():
        raise FileNotFoundError(f"Lexicon DB not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    total_lexemes = conn.execute("SELECT COUNT(*) FROM lexemes").fetchone()[0]
    if total_lexemes == 0:
        return {
            "db_path": str(db_path),
            "total_lexemes": 0,
            "note": "Lexicon is empty; no violations possible.",
        }

    lexemes_with_violations = 0
    total_violations = 0
    per_pair_counts: Counter = Counter()
    per_lexeme_violation_count: Dict[int, int] = {}
    worst_offenders: list = []

    cur = conn.execute("SELECT id, lemma FROM lexemes")
    progress = 0
    for row in cur:
        lex_id = row["id"]
        lemma = row["lemma"]
        progress += 1
        if progress % 50_000 == 0:
            logger.info("Audited %d / %d lexemes", progress, total_lexemes)

        pv_rows = conn.execute(
            "SELECT primitive, value FROM primitive_values "
            "WHERE lexeme_id = ? AND value != 0",
            (lex_id,),
        ).fetchall()
        if not pv_rows:
            continue
        active = {r["primitive"]: r["value"] for r in pv_rows}

        n_viols = count_violations(active)
        if n_viols > 0:
            lexemes_with_violations += 1
            total_violations += n_viols
            per_lexeme_violation_count[lex_id] = n_viols
            for pos, neg in BIPOLAR_PAIRS:
                if active.get(pos, 0) != 0 and active.get(neg, 0) != 0:
                    per_pair_counts[f"{pos}/{neg}"] += 1
            if len(worst_offenders) < top_k or n_viols > worst_offenders[-1][1]:
                worst_offenders.append((lemma, n_viols))
                worst_offenders.sort(key=lambda x: -x[1])
                worst_offenders = worst_offenders[:top_k]

    conn.close()

    report: Dict[str, Any] = {
        "db_path": str(db_path),
        "total_lexemes": total_lexemes,
        "lexemes_with_violations": lexemes_with_violations,
        "violation_rate": (
            lexemes_with_violations / total_lexemes if total_lexemes else 0.0
        ),
        "total_violations": total_violations,
        "avg_violations_per_violating_lexeme": (
            total_violations / lexemes_with_violations
            if lexemes_with_violations else 0.0
        ),
        "per_bipolar_pair_violation_count": dict(
            sorted(per_pair_counts.items(), key=lambda kv: -kv[1])
        ),
        "worst_offenders": [
            {"lemma": lem, "violations": viol} for lem, viol in worst_offenders
        ],
    }
    return report


def _print_report(report: Dict[str, Any]) -> None:
    print()
    print("=" * 78)
    print(f"Lexicon violation audit: {report['db_path']}")
    print("=" * 78)
    n = report["total_lexemes"]
    if n == 0:
        print(f"  Empty lexicon ({report.get('note', '')})")
        return
    nv = report["lexemes_with_violations"]
    print(f"  Total lexemes:                 {n:,}")
    print(f"  Lexemes with ≥1 violation:     {nv:,}  ({report['violation_rate']*100:.2f}%)")
    print(f"  Total violations counted:      {report['total_violations']:,}")
    print(
        f"  Avg violations per offender:   "
        f"{report['avg_violations_per_violating_lexeme']:.2f}"
    )
    print()
    print("  Per-bipolar-pair violation frequency (top 10):")
    items = list(report["per_bipolar_pair_violation_count"].items())[:10]
    for pair, count in items:
        bar = "█" * int(20 * count / max(items[0][1], 1)) if items else ""
        print(f"    {pair:24} {count:>8,}  {bar}")
    print()
    print("  Worst-offender lexemes:")
    for entry in report["worst_offenders"][:10]:
        print(f"    {entry['lemma']:24} {entry['violations']} violations")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/lexicon.db"),
        help="Path to lexicon SQLite database",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of worst-offender lexemes to record (default 20)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Optional path to write the full report as JSON",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    report = audit(args.db, top_k=args.top)
    _print_report(report)

    if args.json is not None:
        args.json.write_text(json.dumps(report, indent=2))
        print(f"\nFull report written to {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
