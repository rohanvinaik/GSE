"""Check that every part file under the parts directory parses as JSON.

Touches only the agent's own part files. It does not open any source text.
Usage: python3 -I validate_parts.py <parts_dir>
"""
import json
import os
import sys


def main(parts_dir):
    names = sorted(n for n in os.listdir(parts_dir) if n.endswith(".json"))
    bad = 0
    for name in names:
        path = os.path.join(parts_dir, name)
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:  # report every failure, keep going
            bad += 1
            print("FAIL", name, exc)
            continue
        if isinstance(data, list):
            print("OK  ", name, "list of", len(data))
        elif isinstance(data, dict):
            facts = data.get("facts")
            if isinstance(facts, list):
                print("OK  ", name, "dict with", len(facts), "facts")
            else:
                print("OK  ", name, "dict with keys", len(data))
        else:
            print("OK  ", name, type(data).__name__)
    print("files", len(names), "failures", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
