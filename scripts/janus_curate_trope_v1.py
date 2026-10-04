"""TROPE batch v1 — the curated, two-rater-cleared seed for Face B (the `trope` core).

Data-as-code: this script IS the provenance record (the DB at ``data/janus_figures.db``
is gitignored; scripts are truth, per project convention). Each example is an *attested*
span (LLM-as-parser-not-source), modern-leaning, with its figure label(s), source, and
curator confidence. Both raters cleared this batch on 2026-06-21 (curator: self-review
in the proposal table; user: "your work on this past set seems good to me"), so it
ingests with ``cleared_self`` set and is then marked ``cleared_user``.

Run from the repo root:  ``python scripts/janus_curate_trope_v1.py``
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gse.pragmatics.figure_store import (  # noqa: E402
    FigureExample,
    Label,
    clear_user,
    ingest_example,
    init_db,
    training_ready,
)

DB_PATH = str(Path(__file__).resolve().parents[1] / "data" / "janus_figures.db")

_PED = "standard pedagogy"
_ANL = "curator analysis"

# The cleared TROPE v1 batch (figures + matched literals).
BATCH = [
    # — metaphor (similarity) —
    FigureExample("Baby, you're a firework.", "Katy Perry, 'Firework' (2010)",
                  [Label("metaphor", 0.97, _PED, "literal TypeAssertion incoherent", True)]),
    FigureExample("Life is a highway.", "Tom Cochrane (1991) / Rascal Flatts (2006)",
                  [Label("metaphor", 0.96, _PED, "X is Y, cross-domain", True)]),
    FigureExample("The arc of the moral universe is long, but it bends toward justice.",
                  "Martin Luther King Jr. (1965)",
                  [Label("metaphor", 0.93, _PED, "arc / bends — cross-domain", True)]),
    # — simile (similarity, marked) —
    FigureExample("Life is like a box of chocolates; you never know what you're gonna get.",
                  "Forrest Gump (1994)",
                  [Label("simile", 0.97, _PED, "explicit 'like'", True)]),
    FigureExample("Float like a butterfly, sting like a bee.", "Muhammad Ali (1964)",
                  [Label("simile", 0.97, _PED, "explicit 'like'", True)]),
    FigureExample("You're as cold as ice.", "Foreigner (1977)",
                  [Label("simile", 0.95, _PED, "explicit 'as...as'", True)]),
    # — metonymy (contiguity) —
    FigureExample("The White House announced new sanctions today.", "journalism idiom",
                  [Label("metonymy", 0.95, _PED, "institution-for-administration", True)]),
    FigureExample("Silicon Valley is obsessed with AI.", "journalism idiom",
                  [Label("metonymy", 0.93, _PED, "place-for-industry", True)]),
    FigureExample("Boots on the ground.", "news / military idiom",
                  [Label("metonymy", 0.88, _ANL, "worn-by relation (contrast with 'all hands')", True)]),
    # — the multi-label showcase: metonymy AND metaphor —
    FigureExample("The pen is mightier than the sword.", "Bulwer-Lytton (1839); ubiquitous idiom",
                  [Label("metonymy", 0.90, _PED, "pen=writing, sword=force (contiguity)", True),
                   Label("metaphor", 0.85, _ANL, "figurative power comparison (Goossens metaphtonymy)", True)]),
    # — synecdoche (contiguity, part-for-whole) —
    FigureExample("All hands on deck.", "nautical idiom",
                  [Label("synecdoche", 0.95, _PED, "part-of relation (hands part-of crew)", True)]),
    FigureExample("He's got a lot of mouths to feed.", "idiom",
                  [Label("synecdoche", 0.90, _PED, "part-of (mouths of dependents)", True)]),
    # — personification (similarity to a person) —
    FigureExample("Hello darkness, my old friend.", "Simon & Garfunkel, 'The Sound of Silence' (1964)",
                  [Label("personification", 0.95, _PED, "darkness addressed as a person", True)]),
    FigureExample("Money talks.", "idiom",
                  [Label("personification", 0.92, _PED, "abstraction given agency", True)]),
    FigureExample("The camera loves her.", "idiom",
                  [Label("personification", 0.90, _PED, "inanimate given agency", True)]),
    # — matched literals (same topic/register, no figure) —
    FigureExample("They lit fireworks over the bay on the Fourth of July.", "curated literal",
                  [Label("literal", 0.95, _ANL, "control for metaphor (firework)", True)],
                  matched_to="metaphor"),
    FigureExample("The morning air was cold and damp.", "curated literal",
                  [Label("literal", 0.95, _ANL, "control for simile (cold as ice)", True)],
                  matched_to="simile"),
    FigureExample("The White House press room seats forty-nine reporters.", "curated literal",
                  [Label("literal", 0.95, _ANL, "control for metonymy (White House — literal building)", True)],
                  matched_to="metonymy"),
    FigureExample("She raised her hand to ask a question.", "curated literal",
                  [Label("literal", 0.95, _ANL, "control for synecdoche (literal hand)", True)],
                  matched_to="synecdoche"),
    FigureExample("He counted the money on the table.", "curated literal",
                  [Label("literal", 0.95, _ANL, "control for personification (literal money)", True)],
                  matched_to="personification"),
]


def main() -> None:
    conn = init_db(DB_PATH)
    n_labels = 0
    for ex in BATCH:
        res = ingest_example(conn, ex, apply=True)
        n_labels += len(res["labels"])
    # Both raters cleared this batch — mark the human final-check on every label.
    for row in conn.execute("SELECT label_id FROM figure_label").fetchall():
        clear_user(conn, row["label_id"], note="TROPE v1 — user-cleared 2026-06-21")
    ready = training_ready(conn)
    print(f"ingested {len(BATCH)} examples, {n_labels} labels → {DB_PATH}")
    print(f"training-ready (both raters cleared): {len(ready)} (example, figure) pairs")
    by_fig: dict[str, int] = {}
    for r in ready:
        by_fig[r["figure"]] = by_fig.get(r["figure"], 0) + 1
    for fig in sorted(by_fig):
        print(f"  {fig:16s} {by_fig[fig]}")


if __name__ == "__main__":
    main()
