"""Usable, mask-preserving candidate vectors emitted by the real builder.

This validates representation, not lexical truth. Candidate export preserves
the model/provisional status; it does not install a production lexicon.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from gse.lexicon_builder.basis import BASIS_ID, PRIMES
from gse.lexicon_builder.core import CANONICAL_COORDINATES, Cell, canonical_pole, legal_domain


def vector_status(states: dict, mask: list, values: list) -> str:
    """Require all states; zero is written and silence has no numeric value."""
    if not isinstance(states, dict) or not isinstance(mask, list) or not isinstance(values, list):
        return "MALFORMED_VECTOR"
    if set(states) != set(CANONICAL_COORDINATES):
        return "COORDINATE_MISMATCH"
    if len(mask) != len(CANONICAL_COORDINATES) or len(values) != len(CANONICAL_COORDINATES):
        return "SHAPE_MISMATCH"
    for index, coordinate in enumerate(CANONICAL_COORDINATES):
        state = states[coordinate]
        if not isinstance(state, str) or state not in legal_domain(coordinate):
            return "ILLEGAL_STATE"
        written = state != Cell.SILENT
        if type(mask[index]) is not bool or mask[index] != written:
            return "MASK_MISMATCH"
        value = values[index]
        if not written:
            if value is not None:
                return "SILENCE_HAS_VALUE"
        elif type(value) is not int or value != int(state):
            return "VALUE_MISMATCH"
    return "VALID_VECTOR"


def export_vector(reading: dict) -> dict:
    """Export a complete candidate without concealing its provisional warrants."""
    vector = reading["candidate_vector"]
    if reading["code"] != "CANDIDATE_COMPLETE" or vector is None:
        raise ValueError("only a complete candidate has an exportable vector")
    status = vector_status(vector["states"], vector["mask"], vector["signs"])
    if status != "VALID_VECTOR":
        raise ValueError(status)
    aliases = {}
    for prime in PRIMES:
        coordinate, direction = canonical_pole(prime)
        state = vector["states"][coordinate]
        aliases[prime] = None if state == Cell.SILENT else direction * int(state)
    return {
        "schema": "GSE_LEXICON_CANDIDATE_V1",
        "basis_id": BASIS_ID,
        "word": reading["word"],
        "reading_id": reading["reading_id"],
        "coordinate_order": list(CANONICAL_COORDINATES),
        "states": vector["states"],
        "mask": vector["mask"],
        "values": vector["signs"],
        "prime_views": aliases,
        "number_scale": reading["number_scale"],
        "review_status": "PROVISIONAL_CANDIDATE",
        "production_eligible": False,
        "provenance": {
            "source_record_ids": reading["premise_record_ids"],
            "rule_id": reading["rule_id"],
            "fired_rules": reading["after_closure"]["fired_rules"],
            "model_requests": [c["request_sha256"] for c in reading["model_calls"]],
            "provisional_silence": vector["provisional_silence"],
        },
    }


def read_vectors(path: Path) -> Iterator[dict]:
    """Read the emitted artifact and refuse an incompatible or damaged vector."""
    with path.open() as stream:
        for line in stream:
            record = json.loads(line)
            if (
                record["schema"] != "GSE_LEXICON_CANDIDATE_V1"
                or record["basis_id"] != BASIS_ID
                or record["coordinate_order"] != list(CANONICAL_COORDINATES)
            ):
                raise ValueError("incompatible candidate vector contract")
            status = vector_status(record["states"], record["mask"], record["values"])
            if status != "VALID_VECTOR":
                raise ValueError(status)
            expected = {
                prime: None
                if record["states"][canonical_pole(prime)[0]] == Cell.SILENT
                else canonical_pole(prime)[1] * int(record["states"][canonical_pole(prime)[0]])
                for prime in PRIMES
            }
            if record["prime_views"] != expected:
                raise ValueError("alias views do not match canonical signs and masks")
            yield record
