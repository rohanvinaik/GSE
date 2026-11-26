"""Positive gloss composition over a release (round 3; GSE/curation/lexicon_builder/gloss_composition.py).

.venv/bin/python scripts/compose_lexicon_glosses.py parse  --candidate DB   # parse every definition once (cached)
.venv/bin/python scripts/compose_lexicon_glosses.py sample --candidate DB   # one pass on the seed-7 3,000 sample
.venv/bin/python scripts/compose_lexicon_glosses.py close  --candidate DB   # the whole-lexicon fixpoint, measured
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import random
import sqlite3
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from GSE.curation.lexicon_builder import gloss_composition as gcm  # noqa: E402

DEFAULT = ROOT / "data/lexicon_builder/2026-11-12/sparse-release-022-verbnet-do.db"


def _connect(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _parses_path(candidate: Path) -> Path:
    return candidate.with_name(candidate.stem + "-gloss-parses.pkl")


def cmd_parse(candidate: Path, workers: int) -> None:
    rows = (
        _connect(candidate)
        .execute(
            "SELECT d.entry_id, l.lemma, l.pos, l.gloss FROM definition_states d JOIN lexemes l ON d.lexeme_id = l.id "
            "WHERE l.pos IN ('noun','verb','adj','adv') ORDER BY d.entry_id"
        )
        .fetchall()
    )
    chunks = [rows[i : i + 2000] for i in range(0, len(rows), 2000)]
    started, parses = time.time(), {}
    with Pool(workers) as pool:
        for k, done in enumerate(pool.imap_unordered(gcm._parse_chunk, chunks), 1):
            parses.update(done)
            if k % 20 == 0:
                print(f"  {k}/{len(chunks)} chunks, {time.time() - started:.0f}s", flush=True)
    out = _parses_path(candidate)
    with out.open("wb") as handle:
        pickle.dump(parses, handle, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"parsed {len(parses)} definitions in {time.time() - started:.0f}s -> {out}")


def _sample(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "select d.entry_id, l.gloss, d.domains, l.pos from definition_states d join lexemes l on d.lexeme_id=l.id "
        "where l.gloss is not null"
    ).fetchall()
    random.Random(7).shuffle(
        rows
    )  # the prototype's sample (docs/verification/2026-11-26-gloss-composition-prototype.py)
    return [row[0] for row in rows[:3000]]


def _lexicon(candidate: Path) -> tuple[sqlite3.Connection, gcm.Lexicon]:
    conn = _connect(candidate)
    started = time.time()
    lexicon = gcm.Lexicon(conn, ROOT, gcm.load_parses(_parses_path(candidate)))
    print(f"loaded {len(lexicon.domain)} definitions, {len(lexicon.parses)} parses in {time.time() - started:.0f}s")
    return conn, lexicon


def _examples(lexicon: gcm.Lexicon, comp: gcm.Composition, entries: list[str], limit: int) -> list[dict]:
    out = []
    for entry in entries:
        if comp.derived.get(entry):
            out.append(
                {
                    "entry": entry,
                    "gloss": lexicon.gloss[entry][:90],
                    "gained": {b: f"{v:+d} <- {comp.trace[entry][b]}" for b, v in comp.derived[entry].items()},
                }
            )
        if len(out) >= limit:
            break
    return out


def cmd_sample(candidate: Path, passes: int) -> None:
    conn, lexicon = _lexicon(candidate)
    entries = _sample(conn)
    comp = lexicon.close(entries, max_passes=passes)
    print(json.dumps(gcm.measure(lexicon, comp, entries), indent=1, default=str))
    for example in _examples(lexicon, comp, entries, 40):
        print(json.dumps(example, ensure_ascii=False))


def cmd_close(candidate: Path, out: Path) -> None:
    conn, lexicon = _lexicon(candidate)
    started = time.time()
    comp = lexicon.close()
    entries = sorted(lexicon.domain)
    result = {
        "format": gcm.FORMAT,
        "channel": gcm.CHANNEL,
        "candidate": str(candidate.relative_to(ROOT)),
        "seconds": round(time.time() - started),
        "measure": gcm.measure(lexicon, comp, entries),
        "sample_measure": gcm.measure(lexicon, comp, _sample(conn)),
    }
    payload = {
        "derived": comp.derived,
        "trace": comp.trace,
        "contested": comp.contested,
        "contradictions": comp.contradictions,
    }
    with out.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    result["output"] = str(out.relative_to(ROOT))
    result["output_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    print(json.dumps(result, indent=1, default=str))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("parse", "sample", "close"))
    parser.add_argument("--candidate", type=Path, default=DEFAULT)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--passes", type=int, default=1)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    if args.command == "parse":
        cmd_parse(candidate, args.workers)
    elif args.command == "sample":
        cmd_sample(candidate, args.passes)
    else:
        cmd_close(candidate, (args.out or candidate.with_name(candidate.stem + "-gloss-composition.pkl")).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
