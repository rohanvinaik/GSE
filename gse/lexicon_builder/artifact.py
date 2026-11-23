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
        "definition_accounting": reading.get("definition_accounting"),
        "model_selection_policy": reading.get("model_selection_policy"),
        "review_status": "PROVISIONAL_CANDIDATE",
        "production_eligible": False,
        "provenance": {
            "source_record_ids": reading["premise_record_ids"],
            "rule_id": reading["rule_id"],
            "fired_rules": reading["after_closure"]["fired_rules"],
            "rule_applications": reading["after_closure"].get("rule_applications", []),
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


def export_sparse(reading: dict) -> dict:
    """An honest partial artifact: unknown presence is distinct from a silent row.

    Every reading uses the same coordinate order. A null mask is unresolved;
    false is proven silence; true includes an explicitly written zero.
    """
    resolution = reading["after_selection"]
    cells = {}
    for coordinate in CANONICAL_COORDINATES:
        domain = resolution["domains"][coordinate]
        state = domain[0] if len(domain) == 1 else "conflict" if not domain else "unresolved"
        cells[coordinate] = {
            "state": state,
            "domain": domain,
            "written": None if len(domain) != 1 else state != Cell.SILENT,
            "value": int(state) if state in {"-1", "0", "+1"} else None,
        }
    return {
        "schema": "GSE_LEXICON_SPARSE_V1",
        "basis_id": BASIS_ID,
        "word": reading["word"],
        "reading_id": reading["reading_id"],
        "code": reading["code"],
        "source_scope": reading.get("source_scope", "SOURCE_CONTRACT_PROJECTION"),
        "rule_id": reading.get("rule_id"),
        "residual_coordinates": reading.get("residual_coordinates", []),
        "model_selection_policy": reading.get("model_selection_policy"),
        "number_scale": reading.get("number_scale"),
        "definition_accounting": reading.get("definition_accounting"),
        "constructions": reading.get("constructions", reading.get("relations", [])),
        "decisions": reading.get("decisions", []),
        "coordinate_order": list(CANONICAL_COORDINATES),
        "cells": cells,
        "production_eligible": False,
        "provenance": {
            "source_record_ids": reading.get("premise_record_ids", []),
            "fired_rules": resolution["fired_rules"],
            "rule_applications": resolution.get("rule_applications", []),
            "trace": resolution["trace"],
            "model_requests": [call["request_sha256"] for call in reading.get("model_calls", [])],
        },
    }


def read_sparse(path: Path) -> Iterator[dict]:
    """Consumer for partial vectors; never interprets unknown cells as silence."""
    with path.open() as stream:
        for line in stream:
            yield validate_sparse(json.loads(line))


def sparse_status(record: dict) -> str:
    """Validate storage without confusing unresolved, silent, zero or conflict."""
    if not isinstance(record, dict):
        return "MALFORMED_SPARSE_RECORD"
    if record.get("schema") != "GSE_LEXICON_SPARSE_V1" or record.get("basis_id") != BASIS_ID:
        return "INCOMPATIBLE_SPARSE_BASIS"
    if record.get("coordinate_order") != list(CANONICAL_COORDINATES):
        return "SPARSE_COORDINATE_MISMATCH"
    if any(not isinstance(record.get(k), str) or not record[k] for k in ("word", "reading_id", "code")):
        return "MISSING_SPARSE_IDENTITY"
    cells = record.get("cells")
    if not isinstance(cells, dict) or set(cells) != set(CANONICAL_COORDINATES):
        return "SPARSE_COORDINATE_MISMATCH"
    for coordinate, cell in cells.items():
        if not isinstance(cell, dict) or set(cell) != {"state", "domain", "written", "value"}:
            return "MALFORMED_SPARSE_CELL"
        domain = cell["domain"]
        if (
            not isinstance(domain, list)
            or any(not isinstance(v, str) for v in domain)
            or len(domain) != len(set(domain))
            or any(v not in legal_domain(coordinate) for v in domain)
        ):
            return "ILLEGAL_SPARSE_DOMAIN"
        state = domain[0] if len(domain) == 1 else "conflict" if not domain else "unresolved"
        written = None if len(domain) != 1 else state != Cell.SILENT
        value = int(state) if state in {"-1", "0", "+1"} else None
        if not isinstance(cell["state"], str) or cell["state"] != state:
            return "SPARSE_STATE_MISMATCH"
        if cell["written"] is not written:
            return "SPARSE_MASK_MISMATCH"
        if (value is None and cell["value"] is not None) or (
            value is not None and (type(cell["value"]) is not int or cell["value"] != value)
        ):
            return "SPARSE_VALUE_MISMATCH"
    return "VALID_SPARSE_RECORD"


def validate_sparse(record: dict) -> dict:
    status = sparse_status(record)
    if status != "VALID_SPARSE_RECORD":
        raise ValueError(status)
    return record
