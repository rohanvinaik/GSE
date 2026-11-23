"""Located lexical facts, independent of encoding and optional resource acquisition.

Lookups use read-only SQLite and local files. Legacy dictionaries retain their
first-row projection; versioned dictionaries select only a unique or explicitly
named definition. Raw ratings never pass through their curation-to-prime conversions.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path
from typing import Any

from gse.lexicon_resource import resolve_lexicon_path
from gse.prime_projection import epa_projection

DATA = Path(__file__).resolve().parents[1] / "data"
POLICY = "gse.lexical-evidence/1"


@lru_cache(maxsize=32)
def _digest(path: str, mtime_ns: int, size: int, inode: int) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def resource_identity(path: str | Path) -> dict[str, Any]:
    """A local resource's byte identity, or an explicit unavailable source."""
    path = Path(path).resolve()
    try:
        stat = path.stat()
        digest = _digest(str(path), stat.st_mtime_ns, stat.st_size, stat.st_ino)
    except OSError as exc:
        return {"path": str(path), "state": "unread", "sha256": None, "reason": type(exc).__name__}
    return {"path": str(path), "state": "read", "sha256": digest}


def is_definition_database(conn: sqlite3.Connection) -> bool:
    """Recognize the versioned builder format; never downgrade unknown versions."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='builder_metadata'").fetchone() is None:
        return False
    from gse.curation.lexicon_builder.storage import VERSION

    row = conn.execute("SELECT value FROM builder_metadata WHERE key='format'").fetchone()
    if row is None or json.loads(row[0]) != VERSION:
        raise ValueError("UNSUPPORTED_BUILD_FORMAT")
    return True


def _definition_evidence(conn: sqlite3.Connection, word: str, entry_id: str | None, out: dict) -> dict:
    """Keep ambiguity and residual domains visible without choosing a first row."""
    from gse.curation.lexicon_builder.storage import read_entries, runtime_lookup

    selection = runtime_lookup(conn, word, entry_id)
    records = read_entries(conn, word, entry_id)
    out.update(
        selection_status=selection["code"],
        candidate_entry_ids=selection["candidates"],
        candidates=records,
        ambiguous=selection["code"] == "AMBIGUOUS",
        selection_policy="definition-identity/1",
    )
    selected = selection["selected"]
    if selected is None:
        out.update(
            state="no_row" if selection["code"] == "NOT_FOUND" else "unread",
            reason=selection["code"],
        )
        return out
    prime_rows = conn.execute(
        "SELECT * FROM primitive_values WHERE lexeme_id=? ORDER BY primitive", (selected["id"],)
    ).fetchall()
    out["primitive_evidence"] = [dict(row) for row in prime_rows]
    if any(type(row["value"]) is not int or row["value"] not in (-1, 0, 1) for row in prime_rows):
        out.update(reason="malformed_primitive_value", selection_status="INVALID")
        return out
    out.update(
        selected_record=selected,
        sense_resolved=True,
        definition_status=selected["code"],
        domains=selected["domains"],
        hierarchy=selected["hierarchy"],
        primitives={bank: value for bank, value in selected["assignments"].items() if value != 0},
    )
    if out["primitives"]:
        out["state"] = "primes"
    elif selected["code"] == "PARTIAL":
        # Identity can be resolved while the representation remains unresolved.
        # An empty projection of known nonzero values does not establish zero.
        out.update(state="unread", reason="UNRESOLVED_DEFINITION_VALUES")
    else:
        out["state"] = "no_primes"
    return out


def lookup_lexeme(
    word: str,
    db_path: str | Path | None = None,
    *,
    pos: str | None = None,
    entry_id: str | None = None,
) -> dict[str, Any]:
    """Return primes/no_primes/no_row/unread and complete selected-record evidence.

    Legacy policy retains its POS/first-ID projection. Versioned dictionaries
    require a unique definition or an explicit entry_id; POS alone does not
    authorize choosing among definitions. All candidate identities are retained.
    """
    path = resolve_lexicon_path(db_path)
    provenance = resource_identity(path)
    out: dict[str, Any] = {
        "word": word,
        "state": "unread",
        "primitives": {},
        "selected_record": None,
        "candidates": [],
        "ambiguous": False,
        "sense_resolved": False,
        "selection_policy": "lemma-pos-generic-id/1",
        "policy": POLICY,
        "provenance": provenance,
    }
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            if is_definition_database(conn):
                return _definition_evidence(conn, word.lower(), entry_id, out)
            if entry_id is not None:
                out["reason"] = "DEFINITION_SELECTION_REQUIRES_VERSIONED_DATABASE"
                return out
            rows = conn.execute("SELECT * FROM lexemes WHERE lemma = ? ORDER BY id", (word.lower(),)).fetchall()
            records = [dict(row) for row in rows]
            if pos is not None:
                records = [row for row in records if row.get("pos") in (pos, "x", None)]
                records.sort(key=lambda row: (row.get("pos") != pos, row["id"]))
            out["candidates"] = records
            out["ambiguous"] = len(records) > 1
            if not records:
                out["state"] = "no_row"
                return out
            selected = records[0]
            out["selected_record"] = selected
            prime_rows = conn.execute(
                "SELECT * FROM primitive_values WHERE lexeme_id = ? ORDER BY primitive", (selected["id"],)
            ).fetchall()
            out["primitive_evidence"] = [dict(row) for row in prime_rows]
            if any(type(row["value"]) is not int or row["value"] not in (-1, 0, 1) for row in prime_rows):
                out["reason"] = "malformed_primitive_value"
                return out
            out["primitives"] = {row["primitive"]: row["value"] for row in prime_rows if row["value"]}
            out["state"] = "primes" if out["primitives"] else "no_primes"
    except (OSError, sqlite3.Error, ValueError) as exc:
        out["reason"] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
    return out


@lru_cache(maxsize=8)
def _vad_resource(path: str, signature: tuple, version: str | None) -> dict[str, Any]:
    """Parse each immutable local resource once; no network or numeric-scale guesses."""
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream, delimiter="\t"))
        if not rows:
            raise ValueError("empty_resource")
        header = [field.casefold() for field in rows[0]]
        declared = None
        if header == ["term", "valence", "arousal", "dominance"]:
            declared = "2"
        elif header == ["word", "valence", "arousal", "dominance"]:
            declared = "1"
        if version is not None and version not in ("1", "2"):
            raise ValueError("unsupported_version")
        if declared is not None and version is not None and declared != version:
            raise ValueError("version_header_conflict")
        family = version or declared
        if family is None:
            raise ValueError("unrecognized_header_or_missing_version")
        scale = {"min": 0.0 if family == "1" else -1.0, "max": 1.0}
        records = {}
        for row in rows[1:] if declared else rows:
            if not row:
                continue
            if len(row) != 4 or not row[0]:
                raise ValueError("malformed_rating_row")
            values = tuple(float(value) for value in row[1:])
            if any(not math.isfinite(value) or not scale["min"] <= value <= scale["max"] for value in values):
                raise ValueError("rating_outside_declared_scale")
            key = row[0].casefold()
            if key in records:
                raise ValueError("duplicate_word")
            records[key] = values
        return {
            "state": "read",
            "records": records,
            "version": family,
            "scale": scale,
            "layout": "header" if declared else "explicit-version-headerless",
        }
    except (OSError, UnicodeError, ValueError, csv.Error) as exc:
        return {"state": "unread", "reason": str(exc)}


def _resource_signature(path: Path) -> tuple:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size, stat.st_ino


def raw_vad(word: str, path: str | Path | None = None, *, version: str | None = None) -> dict[str, Any]:
    """Raw local NRC VAD: v1 0..1; v2 -1..1, with declared layout/version.

    The released v2 ``term`` header and v1 ``Word`` header identify the supported
    family. Headerless exports must supply version="1" or "2". No min/max-based
    scale inference, rescaling, curation conversion, or download occurs.
    """
    path = Path(path) if path is not None else DATA / "external" / "nrc_vad.txt"
    out = _rating_base(word, path, "NRC-VAD", None)
    try:
        resource = _vad_resource(str(path.resolve()), _resource_signature(path), version)
        out.update(version=resource.get("version"), scale=resource.get("scale"), layout=resource.get("layout"))
        if resource["state"] == "unread":
            out.update(reason=resource["reason"])
            return out
        values = resource["records"].get(word.casefold())
        out.update(
            state="measured" if values is not None else "absent",
            value=dict(zip(("valence", "arousal", "dominance"), values)) if values is not None else None,
        )
    except OSError as exc:
        out.update(reason=type(exc).__name__)
    return out


@lru_cache(maxsize=8)
def _concreteness_resource(path: str, signature: tuple) -> dict[str, Any]:
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as stream:
            rows = csv.DictReader(stream)
            if not rows.fieldnames or not {"Word", "Conc.M"} <= set(rows.fieldnames):
                raise ValueError("missing_concreteness_columns")
            records = {}
            percent_column = next((name for name in ("Percent_known", "%known") if name in rows.fieldnames), None)
            count_column = next((name for name in ("Total", "N") if name in rows.fieldnames), None)
            for row in rows:
                rating = float(row["Conc.M"])
                if not math.isfinite(rating) or not 1 <= rating <= 5:
                    raise ValueError("concreteness_outside_raw_scale")
                key = row["Word"].casefold()
                if key in records:
                    raise ValueError("duplicate_word")
                percent = float(row[percent_column]) if percent_column and row.get(percent_column) else None
                count = int(row[count_column]) if count_column and row.get(count_column) else None
                if percent is not None and (not math.isfinite(percent) or not 0 <= percent <= 100):
                    raise ValueError("invalid_known_percent")
                if count is not None and count < 0:
                    raise ValueError("invalid_rater_count")
                records[key] = (rating, percent, count)
        return {"state": "read", "records": records, "percent_column": percent_column, "count_column": count_column}
    except (OSError, UnicodeError, ValueError, TypeError, csv.Error) as exc:
        return {"state": "unread", "reason": str(exc)}


def raw_concreteness(word: str, path: str | Path | None = None) -> dict[str, Any]:
    """Original local Brysbaert 1..5 ratings and source-supplied metadata only."""
    path = Path(path) if path is not None else DATA / "external" / "concreteness.csv"
    out = _rating_base(word, path, "Brysbaert-concreteness", {"min": 1.0, "max": 5.0})
    try:
        resource = _concreteness_resource(str(path.resolve()), _resource_signature(path))
        if resource["state"] == "unread":
            out.update(reason=resource["reason"])
            return out
        values = resource["records"].get(word.casefold())
        out.update(
            state="measured" if values is not None else "absent",
            value=dict(zip(("concreteness", "known_percent", "n_ratings"), values)) if values is not None else None,
            metadata_columns={"known_percent": resource["percent_column"], "n_ratings": resource["count_column"]},
        )
    except OSError as exc:
        out.update(reason=type(exc).__name__)
    return out


def _rating_base(word: str, path: Path, source: str, scale: dict[str, float] | None) -> dict[str, Any]:
    return {
        "word": word,
        "state": "unread",
        "value": None,
        "source": source,
        "scale": scale,
        "policy": POLICY,
        "provenance": resource_identity(path),
        "acquisition": "explicit-local-resource-required",
    }


def structural_epa(signature: dict[str, int]) -> dict[str, Any]:
    """Preserve projection silence separately from a measured structural zero."""
    value = epa_projection(signature)
    return {
        "state": "measured" if value is not None else "absent",
        "value": value,
        "source": "gse.prime_projection.epa_projection",
        "policy": POLICY,
        "scale": "structural-prime-weights; not lexical-VAD",
    }
