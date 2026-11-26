"""Build the founder-corrected word senses into a release candidate (lexicon FC-2 to FC-4).

Copies a published definition release to a candidate beside it, unless the candidate exists,
and adds two tables: ``word_source_agreement`` (each lemma's independent-family votes) and
``word_senses`` (its senses, closed under the release's own rules). No release table is changed.
The release itself is opened read-only.

    uv run python scripts/build_word_senses.py --words happy dog give
    uv run python scripts/build_word_senses.py --top 1000
    uv run python scripts/build_word_senses.py --all
    uv run python scripts/build_word_senses.py --verify 200

Switching ``data/lexicon_active.json`` to a candidate is a separate, owner-approved step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from GSE.curation.external_sources.integrator import ExternalSourcesIntegrator  # noqa: E402
from GSE.curation.lexicon_builder import source_agreement as sa  # noqa: E402
from GSE.curation.lexicon_builder import word_senses as ws  # noqa: E402
from GSE.curation.lexicon_builder.validation import _relations  # noqa: E402

# Rohan, 2026-11-26: one live lexicon (the active pointer) and at most one build in progress beside it.
RELEASE = None  # the active lexicon, resolved when the script runs
CANDIDATE = ROOT / "data/lexicon_builder/2026-11-12/building.db"


def _code_identity() -> dict:
    files = [
        ROOT / "GSE/curation/lexicon_builder/source_agreement.py",
        ROOT / "GSE/curation/lexicon_builder/word_senses.py",
    ]
    return {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def subtlex_counts(path: Path = ROOT / "data/external/concreteness.csv") -> dict[str, int]:
    """SUBTLEX word counts from the Brysbaert table, the builder's own Zipf order (used for ordering only)."""
    import csv

    counts: dict[str, int] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            word, count = (row.get("Word") or "").strip().casefold(), row.get("SUBTLEX") or ""
            if word and count.isdecimal() and int(count) > 0:
                counts[word] = int(count)
    return counts


def _lemmas(conn: sqlite3.Connection, args) -> list[str]:
    """Named words, or the release's lemmas in the builder's own Zipf order (SUBTLEX counts,
    descending; unranked lemmas last, alphabetically)."""
    if args.words:
        return list(args.words)
    counts = subtlex_counts()
    lemmas = [row[0] for row in conn.execute("SELECT DISTINCT lemma FROM lexemes WHERE pos != 'name'")]
    lemmas.sort(key=lambda lemma: (-counts.get(lemma.casefold(), 0), lemma))
    return lemmas[: args.top] if args.top else lemmas


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--release", type=Path, default=RELEASE)  # default: the active lexicon
    parser.add_argument("--candidate", type=Path, default=CANDIDATE)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--words", nargs="+")
    group.add_argument("--top", type=int)
    group.add_argument("--all", action="store_true")
    group.add_argument("--verify", type=int, metavar="N", help="rebuild N stored lemmas at random and compare")
    args = parser.parse_args(argv)
    if args.release is None:
        from GSE.lexicon_resource import resolve_lexicon_path

        args.release = resolve_lexicon_path()

    if not args.candidate.exists():
        print(f"copying {args.release.name} -> {args.candidate.name}", flush=True)
        shutil.copyfile(args.release, args.candidate)
    conn = sqlite3.connect(args.candidate)
    conn.executescript(ws.SCHEMA)
    relations = _relations(
        json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='relations'").fetchone()[0])
    )
    reach = ws.downstream_reach(relations)
    started = time.time()
    integrator = ExternalSourcesIntegrator()
    integrator.load_all_sources()
    print(f"sources loaded in {time.time() - started:.0f}s", flush=True)

    if args.verify:
        stored = [row[0] for row in conn.execute("SELECT lemma FROM word_source_agreement ORDER BY lemma")]
        sample = random.Random(0).sample(stored, min(args.verify, len(stored)))
        mismatched = []
        for lemma in sample:
            rebuilt = ws.build_word(conn, lemma, sa.word_votes(integrator.parsers, lemma), relations, reach)
            if json.loads(json.dumps(rebuilt, sort_keys=True)) != ws.stored_rows(conn, lemma):
                mismatched.append(lemma)
        print(json.dumps({"verified": len(sample), "mismatched": mismatched[:50], "mismatch_count": len(mismatched)}))
        return 1 if mismatched else 0

    lemmas = _lemmas(conn, args)
    print(f"building {len(lemmas)} lemmas", flush=True)
    for done, lemma in enumerate(lemmas, 1):
        votes = sa.word_votes(integrator.parsers, lemma)
        record = {"votes": votes}
        rows = ws.build_word(conn, lemma, votes, relations, reach)
        ws.write_word(conn, lemma, record, rows)
        if done % 500 == 0:
            conn.commit()
            print(f"  {done}/{len(lemmas)} {time.time() - started:.0f}s", flush=True)
    conn.execute(
        "INSERT OR REPLACE INTO builder_metadata(key, value) VALUES ('word_senses', ?)",
        (
            json.dumps(
                {
                    "format": ws.FORMAT,
                    "code": _code_identity(),
                    "release": str(args.release.name),
                    "min_families": sa.MIN_FAMILIES,
                    "families": sa.FAMILY,
                },
                sort_keys=True,
            ),
        ),
    )
    conn.commit()
    print(f"done: {len(lemmas)} lemmas in {time.time() - started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
