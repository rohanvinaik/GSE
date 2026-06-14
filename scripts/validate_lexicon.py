#!/usr/bin/env python3
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gse.lexicon_generator import Lexicon
from gse.lexicon_validator import VALIDATION_PAIRS, validate_lexicon
from gse.vectors import PrimitiveBasis


def main():
    parser = argparse.ArgumentParser(description="Validate GSE Lexicon")
    parser.add_argument("--db", default="data/lexicon.db", help="Path to lexicon database")
    parser.add_argument("--basis", default="data/basis.msgpack", help="Path to primitive basis")
    parser.add_argument("--output", default="data/validation_report.json", help="Path to output report")

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Error: Lexicon database not found at {args.db}")
        sys.exit(1)

    if not os.path.exists(args.basis):
        print(f"Error: Basis not found at {args.basis}")
        sys.exit(1)

    print(f"Loading basis from {args.basis}...")
    basis = PrimitiveBasis.load(args.basis)

    print(f"Loading lexicon from {args.db}...")
    lexicon = Lexicon(args.db, basis)

    print("Running validation...")
    results = validate_lexicon(lexicon, VALIDATION_PAIRS)

    # Print summary
    print("\nValidation Results:")
    for category in ["synonyms", "antonyms", "unrelated"]:
        stats = results[category]
        total = stats["passed"] + stats["failed"]
        if total > 0:
            rate = stats["passed"] / total * 100
            print(f"  {category.capitalize()}: {stats['passed']}/{total} passed ({rate:.1f}%) - {stats['missing']} missing")
        else:
            print(f"  {category.capitalize()}: No pairs found (Missing: {stats['missing']})")

    if results["failures"]:
        print(f"\n{len(results['failures'])} Failures detected (see report for details)")

    # JSON serialization of failures might include numpy types or custom types?
    # failures list contains (type, w1, w2, sim) where sim is float (maybe numpy float)
    # create a clean dict for JSON

    clean_results = {k: v for k, v in results.items() if k != "failures"}
    clean_results["failures"] = []
    for f in results["failures"]:
        clean_results["failures"].append({
            "type": f[0],
            "word1": f[1],
            "word2": f[2],
            "similarity": float(f[3])
        })

    with open(args.output, 'w') as f:
        json.dump(clean_results, f, indent=2)

    print(f"\nDetailed report saved to {args.output}")

if __name__ == "__main__":
    main()
