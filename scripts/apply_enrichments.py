#!/usr/bin/env python3
"""
Apply enriched decompositions to the lexicon.

This script:
1. Loads the current word_decompositions.json
2. Merges enriched decompositions (preferring enriched versions)
3. Saves the updated decompositions
4. Triggers a rebuild of the database
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_json(path: str) -> dict:
    """Load JSON file."""
    with open(path, 'r') as f:
        return json.load(f)


def save_json(data: dict, path: str):
    """Save JSON file."""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def merge_decompositions(base_path: str, enriched_path: str, output_path: str) -> tuple:
    """Merge enriched decompositions into base lexicon."""
    base = load_json(base_path)
    enriched = load_json(enriched_path)

    # Create lookup for enriched words
    enriched_lookup = {}
    for entry in enriched['words']:
        key = (entry['word'].lower(), entry['pos'])
        enriched_lookup[key] = entry

    # Track changes
    updated = 0
    added = 0
    existing_keys = set()

    # Update existing entries
    for entry in base['words']:
        key = (entry['word'].lower(), entry['pos'])
        existing_keys.add(key)

        if key in enriched_lookup:
            enriched_entry = enriched_lookup[key]
            # Always prefer enriched version (curated over auto-generated)
            entry['decomposition'] = enriched_entry['decomposition']
            updated += 1

    # Add new entries
    for key, enriched_entry in enriched_lookup.items():
        if key not in existing_keys:
            base['words'].append({
                'word': enriched_entry['word'],
                'pos': enriched_entry['pos'],
                'decomposition': enriched_entry['decomposition'],
                'frequency': 0.8,
                'definition': '',
            })
            added += 1

    # Update metadata
    base['metadata']['enriched'] = True
    base['metadata']['enriched_count'] = updated + added

    save_json(base, output_path)

    return updated, added


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Apply enriched decompositions")
    parser.add_argument("--base", default="data/word_decompositions.json",
                        help="Path to base decompositions")
    parser.add_argument("--enriched", default="data/enriched_decompositions.json",
                        help="Path to enriched decompositions")
    parser.add_argument("--output", default=None,
                        help="Output path (defaults to base path)")
    parser.add_argument("--rebuild", action="store_true",
                        help="Rebuild database after merging")

    args = parser.parse_args()

    output_path = args.output or args.base

    print(f"Loading base decompositions from {args.base}...")
    print(f"Loading enriched decompositions from {args.enriched}...")

    updated, added = merge_decompositions(args.base, args.enriched, output_path)

    print("\nMerge complete:")
    print(f"  Updated entries: {updated}")
    print(f"  Added entries: {added}")
    print(f"  Output saved to: {output_path}")

    if args.rebuild:
        print("\nRebuilding database...")
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/rebuild_lexicon.py"],
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print("Rebuild failed!")
            print(result.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
