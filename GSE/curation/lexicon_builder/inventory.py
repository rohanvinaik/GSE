"""The pinned reading cohort (rebuild task 1.1): identities only, never values.

Every reading the lexicon covers is identified by its source: `wordnet:<lemma>:<synset>`, a Wiktionary or Webster's
native record id, a closed-class or NSM-chart unit, or an authored GSE prime. The cohort is read from the live
artifact's lexeme table (id, lemma, part of speech, gloss) and pinned by digest. No bank value is read: the old
assignments are comparison data, never premises.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SOURCES = ("wordnet", "wiktionary", "gse_closed_class", "nsm_chart", "gse", "websters1913")


@dataclass(frozen=True)
class Reading:
    reading_id: str
    lemma: str
    pos: str
    gloss: str

    @property
    def source(self) -> str:
        return self.reading_id.split(":", 1)[0]


def read_cohort(lexicon: Path) -> tuple[Reading, ...]:
    """The readings of the live artifact, sorted by id."""
    conn = sqlite3.connect(f"file:{lexicon}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT d.entry_id, l.lemma, l.pos, COALESCE(l.gloss, '') FROM definition_states d "
        "JOIN lexemes l ON l.id = d.lexeme_id ORDER BY d.entry_id"
    ).fetchall()
    readings = tuple(Reading(*row) for row in rows)
    unknown = Counter(r.source for r in readings if r.source not in SOURCES)
    if unknown:
        raise ValueError(f"UNKNOWN_READING_SOURCES {dict(unknown)}")
    return readings


def digest(readings) -> str:
    h = hashlib.sha256()
    for r in readings:
        h.update(json.dumps([r.reading_id, r.lemma, r.pos, r.gloss], ensure_ascii=False).encode())
        h.update(b"\n")
    return h.hexdigest()


def manifest(readings) -> dict:
    return {
        "format": "GSE.rebuild-cohort/1",
        "readings": len(readings),
        "by_source": dict(sorted(Counter(r.source for r in readings).items())),
        "by_pos": dict(sorted(Counter(r.pos for r in readings).items())),
        "lemmas": len({r.lemma for r in readings}),
        "sha256": digest(readings),
    }


def write(readings, path: Path) -> None:
    with path.open("w", encoding="utf-8") as out:
        for r in readings:
            out.write(json.dumps([r.reading_id, r.lemma, r.pos, r.gloss], ensure_ascii=False) + "\n")


def load(path: Path) -> tuple[Reading, ...]:
    with path.open(encoding="utf-8") as src:
        return tuple(Reading(*json.loads(line)) for line in src)
