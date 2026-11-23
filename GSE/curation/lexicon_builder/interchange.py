"""Strict JSON boundaries for authored evidence and rule manifests."""

import json
from pathlib import Path


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"DUPLICATE_JSON_FIELD:{key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"NONFINITE_JSON_VALUE:{value}")


def read_json(path: str | Path):
    return json.loads(Path(path).read_text(), object_pairs_hook=_object, parse_constant=_constant)
