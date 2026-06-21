"""Storage + ingest scaffold for the curated figure corpus (Face B's training data).

The data contract from ``docs/JANUS_FIGURE_SYSTEM.md`` §3, applied per the two workflow
docs (``STRUCTURED_WEB_KNOWLEDGE_EXTRACTION.md``, ``PERSISTENT_KNOWLEDGE_GROUNDED_DATABASES.md``):

  * **LLM-as-parser-not-source** — examples are *attested* and carry provenance; we do
    not synthesize figures.
  * **Multi-label** — a single span may carry several figures at once ("the pen is
    mightier than the sword" is metaphor AND metonymy). Labels are a *set* per example,
    each with its own confidence and clearance — never a 1-of-N choice.
  * **Typed-skeleton enum** — every label's ``figure`` is validated against the closed
    set in ``gse.pragmatics.figures``; an unknown label is a hard error, never a new row.
  * **Two-rater gate** (Rohan's method), *per label* — a (example, figure) pairing is
    training-ready only when both ``cleared_self`` (curator) and ``cleared_user`` (human
    final-check) are set. Their agreement is the cleanliness signal.
  * **Dry-run by default** — ``ingest_example(..., apply=False)`` validates and returns
    the rows it *would* write, but does not touch the DB (the ``patch_field`` discipline,
    workflow doc 2 §8). Nothing is written until a batch is cleared.

The GSE profile vector (``profile_vec``) is the bounded representation Face B trains
over; it is populated by the Face-B prep step, NOT at curation time, so the schema and
the encoder stay decoupled here.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import List, Optional

from gse.pragmatics.figures import BY_NAME, FIGURE_NAMES

_SCHEMA = """
CREATE TABLE IF NOT EXISTS figure_example (
    example_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    text         TEXT NOT NULL,            -- paragraph-scale span (minimal sufficient frame)
    matched_to   TEXT,                     -- for a 'literal' example: the figure it is a control for
    source       TEXT NOT NULL,            -- citation (work / author / outlet)
    source_url   TEXT,                     -- where attested online, if any
    profile_vec  TEXT,                     -- JSON TextProfile.vector(); filled by the Face-B prep step
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS figure_label (
    label_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    example_id   INTEGER NOT NULL REFERENCES figure_example(example_id),
    figure       TEXT NOT NULL,            -- validated against figures.FIGURE_NAMES
    bank         TEXT NOT NULL,            -- denormalized from the figure
    confidence   REAL NOT NULL,            -- curator confidence in THIS label
    labeled_by   TEXT NOT NULL,            -- how we know it is this figure (glossary / corpus / pedagogy / analysis)
    cleared_self INTEGER NOT NULL DEFAULT 0,
    cleared_user INTEGER NOT NULL DEFAULT 0,
    review_note  TEXT,                     -- curator verdict / flags for this label
    UNIQUE (example_id, figure)
);

CREATE TABLE IF NOT EXISTS figure_shadow_ledger (
    entry_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    example_id INTEGER,
    event_type TEXT NOT NULL,              -- hand_curated | pipeline_extracted | cleared_self | cleared_user | rejected
    event_data TEXT,                       -- JSON
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@dataclass
class Label:
    """One figure assignment on an example (multi-label: an example can carry several)."""

    figure: str
    confidence: float
    labeled_by: str
    review_note: Optional[str] = None
    cleared_self: bool = False

    @property
    def bank(self) -> str:
        return BY_NAME[self.figure].bank


@dataclass
class FigureExample:
    """One curated span plus its *set* of figure labels."""

    text: str
    source: str
    labels: List[Label]
    matched_to: Optional[str] = None
    source_url: Optional[str] = None


def init_db(path: str) -> sqlite3.Connection:
    """Open (creating if absent) the figure DB and ensure the schema exists."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def _validate(ex: FigureExample) -> None:
    if not ex.labels:
        raise ValueError("an example must carry at least one figure label")
    figs = [lab.figure for lab in ex.labels]
    if len(figs) != len(set(figs)):
        raise ValueError(f"duplicate figure label on one example: {figs}")
    for lab in ex.labels:
        if lab.figure not in FIGURE_NAMES:
            raise ValueError(
                f"unknown figure {lab.figure!r} — not in the closed set "
                f"(gse.pragmatics.figures.FIGURE_NAMES)"
            )
        if not (0.0 <= lab.confidence <= 1.0):
            raise ValueError(f"confidence {lab.confidence} out of [0, 1] for {lab.figure!r}")
    if any(lab.figure == "literal" for lab in ex.labels):
        if len(ex.labels) != 1:
            raise ValueError("'literal' is exclusive — it cannot share an example with a figure")
        if ex.matched_to is None:
            raise ValueError("a 'literal' example must name the figure it controls for (matched_to)")
    if ex.matched_to is not None and ex.matched_to not in FIGURE_NAMES:
        raise ValueError(f"matched_to {ex.matched_to!r} is not a known figure")


def ingest_example(
    conn: sqlite3.Connection,
    ex: FigureExample,
    *,
    apply: bool = False,
) -> dict:
    """Validate an example + its label set, and (if ``apply``) insert them.

    Dry-run by default: returns the example row and label rows that *would* be written.
    On ``apply=True``, inserts the example and each label, and logs ``hand_curated``
    (+ ``cleared_self`` per pre-cleared label) to the shadow ledger.
    """
    _validate(ex)
    ex_row = {"text": ex.text, "matched_to": ex.matched_to,
              "source": ex.source, "source_url": ex.source_url}
    label_rows = [
        {"figure": lab.figure, "bank": lab.bank, "confidence": lab.confidence,
         "labeled_by": lab.labeled_by, "cleared_self": int(lab.cleared_self),
         "review_note": lab.review_note}
        for lab in ex.labels
    ]
    if not apply:
        return {"example": ex_row, "labels": label_rows}

    cur = conn.execute(
        "INSERT INTO figure_example (text, matched_to, source, source_url) "
        "VALUES (:text, :matched_to, :source, :source_url)",
        ex_row,
    )
    ex_id = cur.lastrowid
    _log(conn, ex_id, "hand_curated", {"source": ex.source})
    for lab_row in label_rows:
        conn.execute(
            """INSERT INTO figure_label
               (example_id, figure, bank, confidence, labeled_by, cleared_self, review_note)
               VALUES (:example_id, :figure, :bank, :confidence, :labeled_by,
                       :cleared_self, :review_note)""",
            {**lab_row, "example_id": ex_id},
        )
        if lab_row["cleared_self"]:
            _log(conn, ex_id, "cleared_self", {"figure": lab_row["figure"]})
    conn.commit()
    return {"example_id": ex_id, "example": ex_row, "labels": label_rows}


def clear_user(conn: sqlite3.Connection, label_id: int, note: str = "") -> None:
    """Record the human final-check on one label (the second rater of the gate)."""
    conn.execute("UPDATE figure_label SET cleared_user = 1 WHERE label_id = ?", (label_id,))
    row = conn.execute("SELECT example_id, figure FROM figure_label WHERE label_id = ?",
                       (label_id,)).fetchone()
    _log(conn, row["example_id"] if row else None, "cleared_user",
         {"figure": row["figure"] if row else None, "note": note})
    conn.commit()


def training_ready(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """(example, figure) labels both raters have cleared — what Face B trains on."""
    return conn.execute(
        """SELECT e.example_id, e.text, l.figure, l.bank, l.confidence
           FROM figure_label l JOIN figure_example e ON e.example_id = l.example_id
           WHERE l.cleared_self = 1 AND l.cleared_user = 1"""
    ).fetchall()


def _log(conn: sqlite3.Connection, example_id: Optional[int], event_type: str,
         data: dict) -> None:
    conn.execute(
        "INSERT INTO figure_shadow_ledger (example_id, event_type, event_data) "
        "VALUES (?, ?, ?)",
        (example_id, event_type, json.dumps(data)),
    )
