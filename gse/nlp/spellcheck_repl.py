"""Standalone spelling door over the shared source-preserving healing core.

python -m gse.nlp.spellcheck_repl "teh wierd dog"
python -m gse.nlp.spellcheck_repl --json '"I beleive it,"'

A single quoted argument is retained exactly, including punctuation and CRLF.
The interactive presentation and JSON door consume the same result as the MCP.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List

from gse.nlp.heal import suggest


def _show(text: str) -> None:
    result = suggest(text)
    for record in result["ledger"]:
        if record["decision"] != "kept":
            print(
                f"  {record['span']} {record['original']!r} -> {record['replacement']!r} "
                f"({record['decision']}: {record['reason']})"
            )
    print(f"  corrected: {result['corrected']!r}")


def _run_word(word: str) -> None:
    _show(word)


def _run_sentence(text: str, encoder=None) -> None:
    """Compatibility presentation; correction is owned by the shared core."""
    _show(text)


def main(argv: List[str]) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the complete shared result as JSON")
    parser.add_argument("text", nargs="*")
    args = parser.parse_args(argv)
    if args.text:
        text = args.text[0] if len(args.text) == 1 else " ".join(args.text)
        if args.json:
            print(json.dumps(suggest(text), ensure_ascii=False))
        else:
            _show(text)
        return
    if args.json:
        parser.error("--json requires one quoted text argument")
    print("GSE deterministic spell-checker. Type text (Ctrl-D / 'quit' to exit).")
    while True:
        try:
            line = input("\nspell> ")
        except EOFError:
            break
        if line.strip() in ("quit", "exit"):
            break
        if line.strip():
            _show(line)


if __name__ == "__main__":
    main(sys.argv[1:])
