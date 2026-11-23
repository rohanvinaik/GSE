"""Freeze F075's random rank cohort before the real symbolic CLI sees it."""

import hashlib
import json
import random
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
PACKET = Path(__file__).resolve().parent
OUTPUT = Path("/private/tmp/gse-f075-random-20261026")
SEED = 20261026


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    database = REPO / "data/frequency.db"
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        pool = connection.execute(
            "SELECT word,combined_rank,david47k_rank,local_rank FROM frequency "
            "WHERE combined_rank BETWEEN 2000 AND 10000 ORDER BY combined_rank,word"
        ).fetchall()
    sample = sorted(random.Random(SEED).sample(pool, 24), key=lambda row: (row[1], row[0]))
    freeze = {
        "schema": "GSE_F075_COHORT_V1",
        "seed": SEED,
        "algorithm": "random.Random(seed).sample(ordered_database_rows,24)",
        "source": "data/frequency.db",
        "source_sha256": digest(database),
        "rank": "combined_rank BETWEEN 2000 AND 10000 inclusive; no lexical/POS/source filtering",
        "pool_count": len(pool),
        "pool_sha256": hashlib.sha256(json.dumps(pool).encode()).hexdigest(),
        "sample": [
            dict(zip(("word", "combined_rank", "david47k_rank", "local_rank"), row, strict=True)) for row in sample
        ],
        "selected_before_build": True,
        "reference_or_gold_input": None,
    }
    freeze_path = PACKET / "cohort.json"
    if freeze_path.exists() and json.loads(freeze_path.read_text()) != freeze:
        raise ValueError("COHORT_CHANGED")
    freeze_path.write_text(json.dumps(freeze, indent=2) + "\n")
    words = PACKET / "words.txt"
    words.write_text("".join(row[0] + "\n" for row in sample))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    command = [
        "uv",
        "run",
        "python",
        "-m",
        "gse.lexicon_builder",
        "build",
        "--symbolic-only",
        "--word-file",
        str(words),
        "--output",
        str(OUTPUT),
    ]
    with (OUTPUT / "build.log").open("w") as log:
        subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT, check=True)
    records = [json.loads(line) for line in (OUTPUT / "sparse.jsonl").read_text().splitlines()]
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    outcomes = []
    for row in sample:
        readings = [record for record in records if record["word"] == row[0]]
        outcomes.append(
            {
                "word": row[0],
                "rank": row[1],
                "readings": [
                    {
                        "reading_id": record["reading_id"],
                        "code": record["code"],
                        "cell_counts": dict(Counter(cell["state"] for cell in record["cells"].values())),
                        "resolved_coordinates": {
                            c: cell["state"]
                            for c, cell in record["cells"].items()
                            if cell["state"] not in ("unresolved", "conflict")
                        },
                        "fired_rules": record["provenance"]["fired_rules"],
                        "source_record_ids": record["provenance"]["source_record_ids"],
                    }
                    for record in readings
                ],
                "status": "PARTIAL" if readings else "NO_LEXICAL_READING",
            }
        )
    result = {
        "schema": "GSE_F075_SYMBOLIC_DIAGNOSIS_V1",
        "cohort_sha256": digest(freeze_path),
        "command": command,
        "artifacts": {p.name: digest(p) for p in sorted(OUTPUT.iterdir()) if p.is_file()},
        "manifest": manifest,
        "counts": dict(Counter(record["code"] for record in records)),
        "cell_counts": dict(Counter(cell["state"] for record in records for cell in record["cells"].values())),
        "outcomes": outcomes,
        "limits": [
            "No semantic accuracy is inferred without references.",
            "This is the local combined-rank table, not a claim of a universal English rank.",
            "No model calls or word-specific corrections are made.",
        ],
    }
    (PACKET / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "words": len(sample),
                "readings": len(records),
                "codes": result["counts"],
                "cells": result["cell_counts"],
                "output": str(OUTPUT),
            }
        )
    )


if __name__ == "__main__":
    main()
