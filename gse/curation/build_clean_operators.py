"""Operator layer: the clause/comparison operators the ENCODER reads from the
lexeme's comp_* metadata to build sentence structure.

Discovered during Phase-4 integration: a clause operator (`than→SET_DIFF`,
`so→CONSEQUENCE`, `because→CAUSAL_SOURCE`) is resolved by the encoder from
`lexemes.comp_primitive / comp_arity / comp_operation`, NOT from word-scale
primitives. These words carry no word content (the decomposer correctly routes
them to zero) but they MUST exist in the lexicon with their operator metadata, or
clause structure silently fails to form.

Grounded entirely in the system's own definition — `primitives_v2.COMP_METADATA`
(`COMP_THAN → {arity:2, operation:SET_DIFF}` …). The surface word is the COMP_
name lowercased, matching `pipeline_v2._COMP_LEMMA_MAP`. No invented values.

ADDITIVE: a word that already exists (e.g. `because`, a tier-0 prime) gets its
comp_* set in place; operator-only words (than, so, but…) are inserted as
`source='operators'`. Idempotent.
"""

from __future__ import annotations

import sqlite3

from gse.primitives_v2 import COMP_METADATA

CLEAN_DB = "data/lexicon_clean.db"


def main(clean_db: str = CLEAN_DB) -> dict:
    con = sqlite3.connect(clean_db)
    updated = inserted = 0
    for comp_prim, meta in COMP_METADATA.items():
        word = comp_prim[len("COMP_"):].lower()
        cur = con.execute(
            "UPDATE lexemes SET comp_primitive=?, comp_arity=?, comp_operation=? WHERE lemma=?",
            (comp_prim, meta["arity"], meta["operation"], word),
        )
        if cur.rowcount:
            updated += 1
        else:
            con.execute(
                "INSERT INTO lexemes(lemma,pos,sense_id,source,confidence,validation_status,"
                "comp_primitive,comp_arity,comp_operation) VALUES(?,?,?,?,?,?,?,?,?)",
                (word, "x", "0", "operators", 1.0, "operator",
                 comp_prim, meta["arity"], meta["operation"]),
            )
            inserted += 1
    con.commit()
    con.close()
    stats = {"operators": len(COMP_METADATA), "updated_in_place": updated, "inserted": inserted}
    print(f"Operator layer: {len(COMP_METADATA)} clause/comparison operators "
          f"({updated} updated in place, {inserted} inserted)")
    return stats


if __name__ == "__main__":
    main()
