#!/usr/bin/env python3
"""The L2 dogfooding flywheel — one reproducible cycle, as a stable process.

The loop that turns coverage into refinement instead of brittleness:

    parse the corpus with GSE  →  train the register router  →
    find the gaps (audit)      →  fix the CLEAN/structural ones  →  re-run

This script automates the MEASURE half — rebuild → re-train → audit → emit the
failure-shape worklist — as a single, compact, repeatable command. The FIX half is
deliberately human: apply the clean/structural fixes the audit surfaces, DEFER the
messy ones (more data often resolves them), then run again. The process is *stable*
when a cycle's audit surfaces no new clean fix and the router's super-register
confusion stops shrinking — that's convergence; grow the corpus and continue.

Reuses the canonical scripts (build_l2_corpus / train_register_router /
audit_l2_parses) — single source of truth, no reimplementation.

Usage:
    python scripts/flywheel.py               # full cycle (rebuild + re-train + audit)
    python scripts/flywheel.py --no-rebuild  # iterate re-train + audit only (fast)
    python scripts/flywheel.py --level genre # train/confuse at a different level
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-rebuild", action="store_true", help="skip the corpus rebuild (re-train + audit only)")
    ap.add_argument("--docs-per-genre", type=int, default=20)
    ap.add_argument("--max-sents", type=int, default=40)
    ap.add_argument("--level", default="super_register", choices=["genre", "super_register", "register_class"])
    args = ap.parse_args()

    dpg, ms = str(args.docs_per_genre), str(args.max_sents)
    steps = []
    if not args.no_rebuild:
        # ALWAYS --fresh: encoder/tokenizer enhancements only take effect on a full
        # re-encode. The append/resume default skips already-done docs, so without
        # this the corpus silently keeps a stale encoding ("wrote 0 new records").
        steps.append(
            (
                "REBUILD corpus (FRESH re-encode — fixes change tokenization)",
                ["build_l2_corpus.py", "--fresh", "--docs-per-genre", dpg, "--max-sents", ms],
            )
        )
    steps += [
        (
            "RE-TRAIN hierarchical SoM (nested cascade) → accuracy + confusion",
            ["train_register_router.py", "--nested", "--level", args.level],
        ),
        # The audit MUST mirror the build's sampling — same docs-per-genre/max-sents —
        # so the gap analysis covers the WHOLE grown corpus. Hardcoding it to a small
        # fixed slice meant growing the corpus never broadened gap-finding (you'd just
        # re-audit the same sentences forever).
        ("AUDIT parses → failure-shape worklist", ["audit_l2_parses.py", "--docs-per-genre", dpg, "--max-sents", ms]),
    ]

    # Tee the whole run to a persistent file so NOTHING is lost — the SoM confusion
    # (failure shapes) AND the audit worklist both land here, in addition to the
    # audit's own data/flywheel_worklist.txt. A prior run was useless precisely
    # because nothing was recorded.
    runlog = ROOT / "data" / "flywheel_run.log"
    with runlog.open("w") as logf:
        for i, (name, cmd) in enumerate(steps, 1):
            banner = f"\n{'=' * 72}\n  FLYWHEEL [{i}/{len(steps)}]  {name}\n{'=' * 72}"
            print(banner, flush=True)
            logf.write(banner + "\n")
            logf.flush()
            proc = subprocess.Popen(
                [sys.executable, str(SCRIPTS / cmd[0]), *cmd[1:]],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in proc.stdout:  # tee: live to stdout + the log
                sys.stdout.write(line)
                logf.write(line)
            proc.wait()
            if proc.returncode != 0:
                print(f"\n  ✗ step failed: {name} — stopping the cycle.")
                return 1
    print(f"\n  [run log saved] {runlog}")

    print(
        f"\n{'=' * 72}\n  CYCLE COMPLETE. Now the human half:\n"
        "    • apply the CLEAN / structural fixes the audit surfaced,\n"
        "    • DEFER the messy ones (more data may resolve them),\n"
        "    • then re-run `python scripts/flywheel.py`.\n"
        "  Stable when the audit shows no new clean fix and confusion stops\n"
        f"  shrinking — then grow the corpus and continue.\n{'=' * 72}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
