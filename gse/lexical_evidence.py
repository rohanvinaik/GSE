"""Located lexical facts, independent of encoding and optional resource acquisition.

Lookups use read-only SQLite and local files.  A selected row is deterministic,
not a claim that a sense has been disambiguated.  Raw ratings never pass through
their curation-to-prime conversions.
"""

from __future__ import annotations

import csv
import hashlib
import math
import os
import sqlite3
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from gse.prime_projection import epa_projection

DATA = Path(__file__).resolve().parents[1] / "data"
POLICY = "gse.lexical-evidence/1"

_tls = threading.local()


def close_lexical_connections() -> None:
    """Close and clear all thread-local cached SQLite connections."""
    cache = getattr(_tls, "connections", None)
    if cache is not None:
        for _, conn in list(cache.values()):
            try:
                conn.close()
            except Exception:
                pass
        cache.clear()
    readers = getattr(_tls, "release_readers", None)
    if readers is not None:
        readers.clear()


@lru_cache(maxsize=32)
def _digest(path: str, mtime_ns: int, size: int, inode: int) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def resource_identity(path: str | Path, *, stat: os.stat_result | None = None) -> dict[str, Any]:
    """A local resource's byte identity, or an explicit unavailable source."""
    path = Path(path).resolve()
    try:
        if stat is None:
            stat = path.stat()
        digest = _digest(str(path), stat.st_mtime_ns, stat.st_size, stat.st_ino)
    except OSError as exc:
        return {"path": str(path), "state": "unread", "sha256": None, "reason": type(exc).__name__}
    return {"path": str(path), "state": "read", "sha256": digest}


def select_consumable_record(records: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    """Choose an encoding row without treating an unreviewed zero as absent."""
    for record in records:
        if record.get("validation_status") != "partial_candidate":
            return "SELECTED", record
    return ("PARTIAL_CANDIDATES_ONLY" if records else "NO_MATCHING_ROW"), None


def _valid_primitive_value(primitive: str, value: Any, source: str | None) -> bool:
    """Quantifier hierarchy levels are structural counts, not lexical signs."""
    if type(value) is not int:
        return False
    if value in (-1, 0, 1):
        return True
    return source == "quantifiers" and primitive in {"HIER_PLUS", "HIER_MINUS"} and value in (2, 3)


def lookup_lexeme(
    word: str,
    db_path: str | Path | None = None,
    *,
    pos: str | None = None,
    _retries: int = 1,
) -> dict[str, Any]:
    """Return primes/no_primes/no_row/unread and complete selected-record evidence.

    Policy: case-insensitive lemma, requested POS before generic x/NULL, then
    ascending row ID among consumable rows. Partial rebuild candidates are
    retained as evidence but cannot supply an encoding: their unreviewed zeros
    may mean omission. This policy does not resolve word senses.
    """
    path = Path(db_path) if db_path is not None else DATA / "lexicon_clean.db"
    resolved_path = str(path.resolve())
    try:
        stat_before = path.stat()
    except OSError as exc:
        return {
            "word": word,
            "state": "unread",
            "primitives": {},
            "selected_record": None,
            "candidates": [],
            "ambiguous": False,
            "sense_resolved": False,
            "selection_policy": "lemma-pos-consumable-id/2",
            "policy": POLICY,
            "provenance": {"path": resolved_path, "state": "unread", "sha256": None, "reason": type(exc).__name__},
            "reason": type(exc).__name__,
        }

    provenance = resource_identity(path, stat=stat_before)
    out: dict[str, Any] = {
        "word": word,
        "state": "unread",
        "primitives": {},
        "selected_record": None,
        "candidates": [],
        "ambiguous": False,
        "sense_resolved": False,
        "selection_policy": "lemma-pos-consumable-id/2",
        "policy": POLICY,
        "provenance": provenance,
    }
    cache = getattr(_tls, "connections", None)
    if cache is None:
        cache = _tls.connections = {}
    cached_entry = cache.get(resolved_path)
    try:
        key = (resolved_path, stat_before.st_mtime_ns, stat_before.st_size, stat_before.st_ino)
        if cached_entry is None or cached_entry[0] != key:
            if cached_entry is not None:
                try:
                    cached_entry[1].close()
                except Exception:
                    pass
            conn = sqlite3.connect(Path(resolved_path).as_uri() + "?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cached_entry = (key, conn)
            cache[resolved_path] = cached_entry
        else:
            conn = cached_entry[1]

        rows = conn.execute("SELECT * FROM lexemes WHERE lemma = ? ORDER BY id", (word.lower(),)).fetchall()
        records = [dict(row) for row in rows]
        if pos is not None:
            records = [row for row in records if row.get("pos") in (pos, "x", None)]
            records.sort(key=lambda row: (row.get("pos") != pos, row["id"]))
        out["candidates"] = records
        out["ambiguous"] = len(records) > 1
        selection_code, selected = select_consumable_record(records)
        out["selection_code"] = selection_code
        if selected is None:
            out["state"] = "no_row"
        else:
            out["selected_record"] = selected
            prime_rows = conn.execute(
                "SELECT * FROM primitive_values WHERE lexeme_id = ? ORDER BY primitive", (selected["id"],)
            ).fetchall()
            out["primitive_evidence"] = [dict(row) for row in prime_rows]
            if any(
                not _valid_primitive_value(row["primitive"], row["value"], selected.get("source")) for row in prime_rows
            ):
                out["reason"] = "malformed_primitive_value"
                return out
            if selected.get("source") == "gse_symbolic_release":
                from gse.lexicon_builder.runtime import ReleaseReader, read_released_reading

                try:
                    readers = getattr(_tls, "release_readers", None)
                    if readers is None:
                        readers = _tls.release_readers = {}
                    reader = readers.get(resolved_path)
                    if reader is None or reader.conn is not conn:
                        reader = readers[resolved_path] = ReleaseReader(conn)
                    definition = read_released_reading(conn, selected["id"], reader=reader)
                except ValueError as error:
                    out["reason"] = str(error)
                    return out
                expected = {
                    coordinate: cell["value"]
                    for coordinate, cell in definition["cells"].items()
                    if cell["written"] is True
                }
                if expected != {row["primitive"]: row["value"] for row in prime_rows}:
                    out["reason"] = "RELEASE_COMPATIBILITY_PROJECTION_MISMATCH"
                    return out
                out["definition"] = definition
                out["definition_status"] = selected["validation_status"]
                out["projection_code"] = "SETTLED_COMPONENTS_ONLY; UNKNOWN_CELLS_RETAINED_IN_DEFINITION"
            out["primitives"] = {row["primitive"]: row["value"] for row in prime_rows if row["value"]}
            out["state"] = "primes" if out["primitives"] else "no_primes"

        # Verify that the file identity did not change during reading.
        # If atomic replacement occurred between stat_before and query completion,
        # retry once so provenance and rows are guaranteed to originate from the same file.
        stat_after = path.stat()
        if (
            stat_after.st_mtime_ns != stat_before.st_mtime_ns
            or stat_after.st_size != stat_before.st_size
            or stat_after.st_ino != stat_before.st_ino
        ):
            if _retries > 0:
                return lookup_lexeme(word, db_path, pos=pos, _retries=_retries - 1)
            out.update(state="unread", reason="LEXICON_CHANGED_DURING_READ", primitives={}, selected_record=None)

    except (OSError, sqlite3.Error) as exc:
        out["reason"] = type(exc).__name__
        if cached_entry is not None:
            try:
                cached_entry[1].close()
            except Exception:
                pass
            cache.pop(resolved_path, None)
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
