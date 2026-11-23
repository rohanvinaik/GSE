"""Hand-declared atomic vectors checked through the same symbolic engine.

An explicit prime-reading axiom is distinct from a one-cell seed, an English
surface match, and a completed research review of its combinatorial profile.
"""

from __future__ import annotations

from gse.lexicon_builder.basis import BASIS_ID, PRIMES
from gse.lexicon_builder.core import CANONICAL_COORDINATES, Cell, Law, Observation, atomic_seed, resolve
from gse.lexicon_builder.registry import compile_law, load_rulebook


def atomic_proof(rulebook: dict | None = None) -> dict:
    book = load_rulebook() if rulebook is None else rulebook
    declarations = book["atomic_definitions"]
    if {r["prime"] for r in declarations} != set(PRIMES) or len(declarations) != len(PRIMES):
        raise ValueError("atomic declarations must cover each of the 72 names exactly once")
    records = []
    for record in declarations:
        seed = atomic_seed(record["prime"])
        expected = {seed.coordinate: seed.sign.value}
        if record["content_axiom"] != expected:
            raise ValueError("atomic content does not match its declared signed basis identity")
        assigned = set(record["content_axiom"]) | set(record["explicit_absence"]) | set(record["silent"])
        if (
            assigned != set(CANONICAL_COORDINATES)
            or sum(map(len, (record["content_axiom"], record["explicit_absence"], record["silent"]))) != 58
        ):
            raise ValueError("atomic mask axioms must partition all 58 coordinates")
        states = {
            **record["content_axiom"],
            **dict.fromkeys(record["explicit_absence"], "0"),
            **dict.fromkeys(record["silent"], "empty"),
        }
        laws = [compile_law(r) for r in book["laws"]]
        laws.extend(
            Law(
                "ATOMIC_DECLARATION:" + record["reading_id"] + ":" + c,
                (c,),
                ((Cell(states[c]),),),
                (),
                record["warrant"],
            )
            for c in CANONICAL_COORDINATES
        )
        fact = Observation(
            record["reading_id"], "founder-atomic-declaration", record["prime"], "own_role", record["own_role"], True
        )
        result = resolve(record["reading_id"], (fact,), seed=record["prime"], laws=tuple(laws))
        forced = result.forced()
        records.append(
            {
                **record,
                "code": result.code,
                "vector": {c: forced[c].value for c in CANONICAL_COORDINATES} if result.code == "RESOLVED" else None,
                "resolution": result.to_json(),
            }
        )
    return {
        "basis_id": BASIS_ID,
        "code": "DECLARED_ATOMIC_VECTORS" if all(r["code"] == "RESOLVED" for r in records) else "ATOMIC_CONFLICT",
        "lexical_primes": 72,
        "canonical_coordinates": 58,
        "number_is_lexical_prime": False,
        "scope": "Full declared basis vectors; lexical combinatorial profile review is separate and unfinished",
        "records": records,
    }
