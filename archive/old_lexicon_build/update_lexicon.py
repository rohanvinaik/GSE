#!/usr/bin/env python3
"""
Update Lexicon Database

This script performs critical updates to lexicon.db:
1. Populates frequency field from frequency.db
2. Re-encodes all vectors with the new Hadamard-OTP architecture
3. Optionally filters low-quality heuristic entries

Usage:
    python scripts/update_lexicon.py --frequency   # Update frequency only
    python scripts/update_lexicon.py --reencode    # Re-encode vectors only
    python scripts/update_lexicon.py --all         # Both operations
    python scripts/update_lexicon.py --stats       # Show statistics only
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gse.vectors import PrimitiveBasis


def get_paths():
    """Get standard paths."""
    base = Path(__file__).parent.parent / "data"
    return {
        "lexicon": base / "lexicon.db",
        "frequency": base / "frequency.db",
        "basis": base / "basis.msgpack",
    }


def show_stats(lexicon_path: Path, frequency_path: Path):
    """Show current database statistics."""
    print("\n" + "=" * 70)
    print("LEXICON DATABASE STATISTICS")
    print("=" * 70)

    conn = sqlite3.connect(str(lexicon_path))

    # Total entries
    total = conn.execute("SELECT COUNT(*) FROM lexicon").fetchone()[0]
    print(f"\nTotal entries: {total:,}")

    # By source
    print("\nBy source:")
    rows = conn.execute("""
        SELECT source, COUNT(*) as cnt, AVG(confidence) as avg_conf,
               SUM(CASE WHEN frequency > 0 THEN 1 ELSE 0 END) as has_freq
        FROM lexicon
        GROUP BY source
        ORDER BY cnt DESC
    """).fetchall()

    print(f"  {'Source':<30} {'Count':>10} {'Avg Conf':>10} {'Has Freq':>10}")
    print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*10}")
    for source, cnt, conf, has_freq in rows:
        print(f"  {source or 'NULL':<30} {cnt:>10,} {conf:>10.2f} {has_freq:>10,}")

    # Frequency coverage
    print("\nFrequency coverage:")
    has_freq = conn.execute("SELECT COUNT(*) FROM lexicon WHERE frequency > 0").fetchone()[0]
    no_freq = conn.execute("SELECT COUNT(*) FROM lexicon WHERE frequency = 0 OR frequency IS NULL").fetchone()[0]
    print(f"  With frequency: {has_freq:,} ({100*has_freq/total:.1f}%)")
    print(f"  Without frequency: {no_freq:,} ({100*no_freq/total:.1f}%)")

    conn.close()

    # Frequency.db stats
    if frequency_path.exists():
        freq_conn = sqlite3.connect(str(frequency_path))
        freq_total = freq_conn.execute("SELECT COUNT(*) FROM frequency").fetchone()[0]
        freq_conn.close()
        print(f"\nFrequency.db entries: {freq_total:,}")

    print("\n" + "=" * 70)


def update_frequency(lexicon_path: Path, frequency_path: Path, batch_size: int = 1000):
    """
    Populate lexicon.frequency from frequency.db.

    Uses the weight field from frequency.db which is already computed
    as a semantic weight (higher = rarer = more semantically specific).
    """
    print("\n" + "=" * 70)
    print("UPDATING FREQUENCY DATA")
    print("=" * 70)

    if not frequency_path.exists():
        print(f"ERROR: frequency.db not found at {frequency_path}")
        return False

    # Load frequency data into memory (only 18k entries)
    print("\nLoading frequency data...")
    freq_conn = sqlite3.connect(str(frequency_path))
    freq_data = {}
    for word, rank, weight in freq_conn.execute(
        "SELECT word, combined_rank, weight FROM frequency"
    ):
        freq_data[word.lower()] = (rank, weight)
    freq_conn.close()
    print(f"  Loaded {len(freq_data):,} frequency entries")

    # Update lexicon
    print("\nUpdating lexicon...")
    lex_conn = sqlite3.connect(str(lexicon_path))

    # Get all lemmas that need updating
    rows = lex_conn.execute(
        "SELECT id, lemma FROM lexicon WHERE frequency = 0 OR frequency IS NULL"
    ).fetchall()

    print(f"  Found {len(rows):,} entries to update")

    updates = []
    matched = 0
    for id_, lemma in rows:
        lemma_lower = lemma.lower() if lemma else ""
        if lemma_lower in freq_data:
            rank, weight = freq_data[lemma_lower]
            # Store the weight as frequency (higher = more semantically specific)
            updates.append((weight, id_))
            matched += 1

    print(f"  Matched {matched:,} entries with frequency data")

    # Batch update
    if updates:
        print("  Applying updates...")
        lex_conn.executemany(
            "UPDATE lexicon SET frequency = ? WHERE id = ?",
            updates
        )
        lex_conn.commit()
        print(f"  Updated {len(updates):,} entries")

    lex_conn.close()
    print("\nFrequency update complete!")
    return True


def reencode_vectors(lexicon_path: Path, basis_path: Path, batch_size: int = 500):
    """
    Re-encode all lexicon vectors with the current Hadamard-OTP architecture.

    This ensures all stored vectors use the new encoding scheme with:
    - Proper polarity handling (antonyms share vectors with opposite signs)
    - Hadamard orthogonality
    - Correct bank structure
    """
    print("\n" + "=" * 70)
    print("RE-ENCODING VECTORS")
    print("=" * 70)

    # Load basis
    print("\nLoading Hadamard-OTP basis...")
    basis = PrimitiveBasis.load(str(basis_path))
    print(f"  Dimension: {basis.dimension}")
    print(f"  Primitives: {len(basis.primitives)}")
    print(f"  Roles: {len(basis.roles)}")

    # Import encoder
    from gse.lexicon_generator import LexiconGenerator
    encoder = LexiconGenerator(basis)

    # Get all entries with decompositions
    conn = sqlite3.connect(str(lexicon_path))
    rows = conn.execute("""
        SELECT id, lemma, pos, decomposition
        FROM lexicon
        WHERE decomposition IS NOT NULL AND decomposition != '[]'
    """).fetchall()

    print(f"\nRe-encoding {len(rows):,} entries...")

    updates = []
    errors = 0

    for i, (id_, lemma, pos, decomp_json) in enumerate(rows):
        try:
            decomp = json.loads(decomp_json)
            if not decomp:
                continue

            # Re-encode with new architecture
            vector = encoder.encode_decomposition(decomp)

            if vector.nnz > 0:
                updates.append((vector.serialize(), id_))

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error encoding {lemma}: {e}")

        # Progress
        if (i + 1) % 10000 == 0:
            print(f"  Processed {i+1:,}/{len(rows):,} ({100*(i+1)/len(rows):.1f}%)")

    # Batch update
    print(f"\nApplying {len(updates):,} vector updates...")
    conn.executemany("UPDATE lexicon SET vector = ? WHERE id = ?", updates)
    conn.commit()
    conn.close()

    print(f"  Updated: {len(updates):,}")
    print(f"  Errors: {errors}")
    print("\nVector re-encoding complete!")
    return True


def get_quality_stats(lexicon_path: Path) -> Dict:
    """Get quality breakdown for filtering decisions."""
    conn = sqlite3.connect(str(lexicon_path))

    stats = {
        "high_quality": conn.execute("""
            SELECT COUNT(*) FROM lexicon
            WHERE source IN ('claude-code', 'manual-fix', 'curated-enhanced', 'enhanced-v2', 'audit_fix')
            AND confidence >= 0.8
        """).fetchone()[0],

        "medium_quality": conn.execute("""
            SELECT COUNT(*) FROM lexicon
            WHERE source IN ('ollama-enhanced', 'heuristic_suffix')
            AND confidence >= 0.5
        """).fetchone()[0],

        "low_quality": conn.execute("""
            SELECT COUNT(*) FROM lexicon
            WHERE source IN ('medical_heuristic', 'external_20k_heuristic', 'physics_heuristic',
                           'math_heuristic', 'cs_heuristic')
            OR confidence < 0.5
        """).fetchone()[0],
    }

    conn.close()
    return stats


def filter_low_quality(lexicon_path: Path, min_confidence: float = 0.5,
                       keep_sources: List[str] = None, dry_run: bool = True):
    """
    Filter out low-quality heuristic entries.

    Args:
        min_confidence: Minimum confidence threshold
        keep_sources: List of sources to always keep
        dry_run: If True, only show what would be deleted
    """
    print("\n" + "=" * 70)
    print("FILTERING LOW-QUALITY ENTRIES")
    print("=" * 70)

    if keep_sources is None:
        keep_sources = [
            'claude-code', 'manual-fix', 'curated-enhanced',
            'enhanced-v2', 'audit_fix', 'ollama-enhanced'
        ]

    conn = sqlite3.connect(str(lexicon_path))

    # Count what would be deleted
    placeholders = ','.join('?' * len(keep_sources))
    to_delete = conn.execute(f"""
        SELECT COUNT(*) FROM lexicon
        WHERE source NOT IN ({placeholders})
        OR confidence < ?
    """, (*keep_sources, min_confidence)).fetchone()[0]

    to_keep = conn.execute(f"""
        SELECT COUNT(*) FROM lexicon
        WHERE source IN ({placeholders})
        AND confidence >= ?
    """, (*keep_sources, min_confidence)).fetchone()[0]

    print("\nProposed filtering:")
    print(f"  Entries to keep: {to_keep:,}")
    print(f"  Entries to delete: {to_delete:,}")

    if dry_run:
        print("\n[DRY RUN - no changes made]")
        print("Run with --filter --no-dry-run to apply changes")
    else:
        # Create backup first
        backup_path = lexicon_path.with_suffix('.db.backup')
        print(f"\nCreating backup at {backup_path}...")
        import shutil
        shutil.copy(lexicon_path, backup_path)

        # Delete low-quality entries
        print("Deleting low-quality entries...")
        conn.execute(f"""
            DELETE FROM lexicon
            WHERE source NOT IN ({placeholders})
            OR confidence < ?
        """, (*keep_sources, min_confidence))
        conn.commit()

        # Vacuum to reclaim space
        print("Vacuuming database...")
        conn.execute("VACUUM")

        remaining = conn.execute("SELECT COUNT(*) FROM lexicon").fetchone()[0]
        print(f"\nRemaining entries: {remaining:,}")

    conn.close()
    return True


def main():
    parser = argparse.ArgumentParser(description="Update lexicon database")
    parser.add_argument("--frequency", action="store_true", help="Update frequency from frequency.db")
    parser.add_argument("--reencode", action="store_true", help="Re-encode vectors with Hadamard-OTP")
    parser.add_argument("--filter", action="store_true", help="Filter low-quality entries")
    parser.add_argument("--no-dry-run", action="store_true", help="Actually apply filter changes")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")
    parser.add_argument("--all", action="store_true", help="Run frequency + reencode")

    args = parser.parse_args()

    paths = get_paths()

    if not paths["lexicon"].exists():
        print(f"ERROR: lexicon.db not found at {paths['lexicon']}")
        return 1

    if args.stats or not any([args.frequency, args.reencode, args.filter, args.all]):
        show_stats(paths["lexicon"], paths["frequency"])
        quality = get_quality_stats(paths["lexicon"])
        print("\nQuality breakdown:")
        print(f"  High quality (conf>=0.8, good sources): {quality['high_quality']:,}")
        print(f"  Medium quality (conf>=0.5): {quality['medium_quality']:,}")
        print(f"  Low quality (heuristics): {quality['low_quality']:,}")
        return 0

    if args.frequency or args.all:
        update_frequency(paths["lexicon"], paths["frequency"])

    if args.reencode or args.all:
        reencode_vectors(paths["lexicon"], paths["basis"])

    if args.filter:
        filter_low_quality(paths["lexicon"], dry_run=not args.no_dry_run)

    # Show final stats
    show_stats(paths["lexicon"], paths["frequency"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
