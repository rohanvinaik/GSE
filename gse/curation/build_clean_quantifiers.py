"""Quantifier/intensifier layer: wire the hierarchy-level words to their ordinal
decompositions — the "scalar multiple for a specific bank, as a hierarchical
representation of intensity" (no arbitrary scalars).

A quantifier (``many``/``few``/``all``) or intensifier (``very``/``extremely``) is
NOT a flat bag of primitives — it is a position on an ordinal axis: a **base bank**
(QUANTITY / INTENSITY) carried with N **HIER_PLUS / HIER_MINUS markers**. The encoder
stacks the markers as permuted copies (``gse.vectors_v2.encode_hierarchy``), so the
level is real and stays inside the closed ternary basis.

Everything here is sourced from the system's OWN definitions — ``QUANTITY_HIERARCHY``
/ ``INTENSITY_HIERARCHY`` and ``get_hierarchy_encoding`` in ``primitives_v2`` — exactly
as the clause operators were wired from ``COMP_METADATA``. No hand-authored values.
The surface word is the level name lowercased (``MANY``→``many``); a level-0 word
(``middle``/``moderate``) carries the base with no markers.

This OVERWRITES the degenerate rows layer1/layer2 produced for these words
(``none``={GOOD:-1,SOMETHING:1}, ``more``={ALIVE,SOMEONE,SOMETHING}, ``few``=
{PEOPLE,SOMETHING}) — so it MUST run LAST in the build (after layer1/layer2/operators),
or a layer re-run will re-clobber them.

CERTAINTY (possible/likely/probable…) is deliberately OUT OF SCOPE here — that is the
modal track, a separate gap.
"""

from __future__ import annotations

import sqlite3
from typing import Dict

from gse.primitives_v2 import (
    INTENSITY_HIERARCHY,
    QUANTITY_HIERARCHY,
    get_hierarchy_encoding,
)

CLEAN_DB = "data/lexicon_clean.db"

# Closed-class quantifier synonyms that are NOT themselves level names, mapped to the
# system level they realize. A tiny, unambiguous set (NOT open lexical synonymy) — the
# ordinal value still comes from the system's get_hierarchy_encoding, only the
# surface→level link is named here. `most`→MANY (a large quantity; deliberately not
# ALL, which would over-claim totality).
_SYNONYM_LEVEL: Dict[str, str] = {
    # quantity
    "much": "MANY",
    "most": "MANY",
    "lots": "MANY",
    "no": "NONE",
    "every": "ALL",
    "less": "SOME",  # the -1 decrease counterpart of more→MORE(+1)
    # intensity (the gradable-adjective intensifiers surfaced by the flywheel)
    "too": "VERY",
    "really": "VERY",
    "quite": "VERY",
}


def _decomposition(level_name: str) -> Dict[str, int]:
    """{base: 1} plus N HIER_PLUS/HIER_MINUS markers — from the system's encoding."""
    base, signed_level, count = get_hierarchy_encoding(level_name)
    decomp = {base: 1}
    if count:
        decomp["HIER_PLUS" if signed_level > 0 else "HIER_MINUS"] = count
    return decomp


def main(clean_db: str = CLEAN_DB) -> dict:
    con = sqlite3.connect(clean_db)
    # (surface_word, level_name) pairs: the level names themselves (identity), QUANTITY
    # + INTENSITY only (CERTAINTY is the modal track), plus the closed synonym map.
    levels = list(QUANTITY_HIERARCHY) + list(INTENSITY_HIERARCHY)
    pairs = [(n.lower(), n) for n in levels] + list(_SYNONYM_LEVEL.items())
    updated = inserted = 0
    for word, level_name in pairs:
        decomp = _decomposition(level_name)
        row = con.execute("SELECT id FROM lexemes WHERE lemma=? LIMIT 1", (word,)).fetchone()
        if row:
            lex_id = row[0]
            con.execute("DELETE FROM primitive_values WHERE lexeme_id=?", (lex_id,))
            con.execute("UPDATE lexemes SET source='quantifiers', component_type='hierarchy' WHERE id=?", (lex_id,))
            updated += 1
        else:
            cur = con.execute(
                "INSERT INTO lexemes(lemma,pos,sense_id,source,confidence,"
                "validation_status,component_type) VALUES(?,?,?,?,?,?,?)",
                (word, "x", "0", "quantifiers", 1.0, "hierarchy", "hierarchy"),
            )
            lex_id = cur.lastrowid
            inserted += 1
        con.executemany(
            "INSERT INTO primitive_values(lexeme_id,primitive,value,confidence,source) VALUES(?,?,?,?,?)",
            [(lex_id, p, v, 1.0, "quantifiers") for p, v in decomp.items()],
        )
    con.commit()
    con.close()
    stats = {"levels": len(pairs), "updated_in_place": updated, "inserted": inserted}
    print(
        f"Quantifier/intensifier layer: {len(pairs)} hierarchy-level words ({updated} overwritten, {inserted} inserted)"
    )
    return stats


if __name__ == "__main__":
    main()
