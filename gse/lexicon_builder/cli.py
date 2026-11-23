"""Installed entry point for construction, evaluation and symbolic publication."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def release_main() -> int:
    from gse.lexicon_builder.runtime import build_release

    parser = argparse.ArgumentParser(description="Publish a validated mask-aware SQLite lexicon.")
    parser.add_argument("command", choices=["release"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_release(args.input, args.output), indent=2))
    return 0


def main() -> int:
    from gse.lexicon_builder.audit import main as audit_main
    from gse.lexicon_builder.build import main as build_main
    from gse.lexicon_builder.core import _run_cli
    from gse.lexicon_builder.number import main as number_main
    from gse.lexicon_builder.release_audit import main as release_audit_main
    from gse.lexicon_builder.surprise import main as surprise_main
    from gse.lexicon_builder.tail import main as tail_main

    commands = {
        "build": build_main,
        "rules": build_main,
        "symbolic-audit": audit_main,
        "number-order": number_main,
        "audit-sparse": surprise_main,
        "plan-tail": tail_main,
        "release": release_main,
        "release-audit": lambda: release_audit_main(sys.argv[2:]),
    }
    if len(sys.argv) < 2 or sys.argv[1] in {"--help", "-h"}:
        print("gse-lexicon COMMAND [options]\n\nCommands: " + ", ".join([*commands, "prime-proof", "resolve"]))
        print("Ordinary builds are symbolic. Model decisions require an explicit diagnosed tail queue.")
        return 0
    return commands.get(sys.argv[1], _run_cli)()
