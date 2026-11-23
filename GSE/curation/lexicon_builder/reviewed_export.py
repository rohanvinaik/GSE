"""Read-only candidate export for explicit reviewed-pattern preparation.

An inventory is not a review. Only supplied hash-pinned ACCEPTED reviews enter
the executable input; all other receipts remain visibly unreviewed.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from GSE.namespace import current_id

from .evidence import Observation
from .foundation import lexical_context
from .interchange import read_json
from .residual import _request_id
from .reviewed_patterns import INPUT_FORMAT, LEGACY_INPUT_FORMAT, _definition_input, _fields, _ids, reviewed_rulings
from .validation import (
    _assertions,
    _authorities,
    _domain_restrictions,
    _metadata,
    _NativeReference,
    _provenance,
    _read_json,
    _relations,
    _restriction_provenance,
)

SELECTION_FORMAT = "GSE.reviewed-pattern-selection/1"
EXPORT_FORMAT = "GSE.reviewed-pattern-export/1"


def _selected_observations(conn, entry_ids):
    """One source-table scan; retain full records for exact and candidate links."""
    selected = set(entry_ids)
    result = defaultdict(list)
    # SQL chooses records, not textual fragments; every matching native record
    # is decoded and checked whole. The connection is query-only.
    selection_json = json.dumps(sorted(selected))
    rows = conn.execute(
        "SELECT record_id,entry_id,source,family,scope,payload FROM source_observations "
        "WHERE entry_id IN (SELECT value FROM json_each(?)) "
        "OR (entry_id IS NULL AND EXISTS (SELECT 1 FROM json_each(payload,'$.candidate_entry_ids') c "
        "WHERE c.value IN (SELECT value FROM json_each(?)))) ORDER BY record_id",
        (selection_json, selection_json),
    )
    seen = set()
    for record_id, entry_id, source, family, scope, payload in rows:
        raw = _read_json(payload)
        _fields(raw, ("record_id", "entry_id", "source", "family", "scope", "features", "candidate_entry_ids"))
        candidates = _ids(raw["candidate_entry_ids"])
        observation = Observation(
            raw["entry_id"], raw["source"], raw["record_id"], raw["family"], raw["features"], raw["scope"], candidates
        )
        if (observation.record_id, observation.entry_id, observation.source, observation.family, observation.scope) != (
            record_id,
            entry_id,
            source,
            family,
            scope,
        ):
            raise ValueError("OBSERVATION_COLUMN_PAYLOAD_MISMATCH")
        if record_id in seen:
            raise ValueError("AMBIGUOUS_OBSERVATION_ID")
        seen.add(record_id)
        targets = (entry_id,) if entry_id is not None else candidates
        for target in set(targets) & selected:
            result[target].append(raw)
    return result


def export_reviewed_input(candidate: str | Path, selection: dict, *, input_format=INPUT_FORMAT) -> dict:
    """Export a consistent read-only selected snapshot and explicit review input."""
    from .rule_history import digest, read_history, receipt_binding_key, relation_records

    if type(input_format) is not str or current_id(input_format) not in {INPUT_FORMAT, LEGACY_INPUT_FORMAT}:
        raise ValueError("INVALID_PATTERN_INPUT_FORMAT")
    _fields(
        selection, ("format", "discovery_entry_ids", "audit_entry_ids", "reviews"), ("candidates", "guarded_candidates")
    )
    if current_id(selection["format"]) != SELECTION_FORMAT or type(selection["reviews"]) is not list:
        raise ValueError("INVALID_PATTERN_SELECTION")
    discovery = _ids(selection["discovery_entry_ids"])
    audit = _ids(selection["audit_entry_ids"])
    if set(discovery) & set(audit):
        raise ValueError("DISCOVERY_AUDIT_ID_OVERLAP")
    selected = tuple(sorted(set(discovery) | set(audit)))
    if not selected:
        raise ValueError("EMPTY_PATTERN_EXPORT")
    reviews = {}
    for record in selection["reviews"]:
        _fields(record, ("request_id", "review"))
        if type(record["request_id"]) is not str or not record["request_id"]:
            raise ValueError("INVALID_PATTERN_REVIEW_ID")
        if record["request_id"] in reviews:
            raise ValueError("DUPLICATE_PATTERN_REVIEW")
        review = record["review"]
        if (
            type(review) is not dict
            or not _ids(review.get("source_refs", []))
            or type(review.get("rationale")) is not str
            or not review["rationale"].strip()
        ):
            raise ValueError("SOURCE_BACKED_REVIEW_REQUIRED")
        reviews[record["request_id"]] = record["review"]
    path = Path(candidate).resolve(strict=True)
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        relations = _relations(_metadata(conn, "relations"))
        history = read_history(conn, relations)
        anchors, models = _authorities(conn)
        observations = _selected_observations(conn, selected)
        entries, inventory, accepted = [], [], []
        for entry_id in selected:
            row = conn.execute(
                "SELECT l.lemma,l.pos,l.gloss FROM definition_states d JOIN lexemes l ON l.id=d.lexeme_id "
                "WHERE d.entry_id=?",
                (entry_id,),
            ).fetchone()
            if row is None:
                raise ValueError("UNKNOWN_PATTERN_DEFINITION")
            assertions = _assertions(
                conn.execute("SELECT ordinal,payload FROM builder_assertions WHERE entry_id=?", (entry_id,)).fetchall()
            )
            restrictions = _domain_restrictions(
                conn.execute(
                    "SELECT ordinal,payload FROM builder_domain_restrictions WHERE entry_id=?", (entry_id,)
                ).fetchall()
            )
            anchor_counts = Counter(anchors.get(entry_id, ()))
            native_assertions, explicit_anchors = [], []
            for assertion in assertions:
                if anchor_counts[assertion]:
                    explicit_anchors.append(asdict(assertion))
                    anchor_counts[assertion] -= 1
                elif assertion.family != "model" and not assertion.source.startswith("model:"):
                    native_assertions.append(asdict(assertion))
            raw = {
                "definition": {"entry_id": entry_id, "lemma": row[0], "pos": row[1], "definition": row[2]},
                "assertions": native_assertions,
                "anchors": explicit_anchors,
                "observations": observations[entry_id],
                "domain_restrictions": [asdict(item) for item in restrictions],
            }
            raw["context"] = lexical_context(raw["definition"], raw["observations"], relations)
            # JSON normalization preserves the public schema's arrays.
            raw = _read_json(json.dumps(raw))
            parsed = _definition_input(raw, relations)
            native = {
                (item["source"], item["record_id"]): _NativeReference(item["entry_id"], item["family"], item["scope"])
                for item in observations[entry_id]
                if item["scope"] == "lexical"
            }
            relevant = {entry_id: [item["record_id"] for item in observations[entry_id]]}
            _restriction_provenance(entry_id, restrictions, native)
            _provenance(
                entry_id,
                assertions,
                parsed.definition,
                relations,
                native,
                relevant,
                anchors,
                models,
                conn,
                evidence_banks=parsed.evidence_banks,
                domain_restrictions=restrictions,
                rule_history=history,
            )
            entries.append(raw)
            for receipt in models.get(entry_id, ()):
                request_id = receipt["request_id"]
                dependencies = [
                    item["record_id"]
                    for item in receipt["request"]["scaffold"]["proof_trace"]
                    if item.get("kind") == "ASSERTION" and item.get("family") == "model"
                ]
                status = "EXPLICIT_REVIEW_SUPPLIED" if request_id in reviews else "NOT_INDEPENDENTLY_REVIEWED"
                inventory.append(
                    {
                        "entry_id": entry_id,
                        "bank": receipt["assertion"]["bank"],
                        "request_id": request_id,
                        "receipt_sha256": _request_id(receipt),
                        "review_status": status,
                        "dependency_status": "PRIOR_MODEL_DEPENDENCIES" if dependencies else "NATIVE_ANCHOR_BASELINE",
                        "dependency_request_ids": dependencies,
                        "receipt": receipt,
                    }
                )
                binding_key = receipt_binding_key(receipt) if history is not None else None
                if history is not None and binding_key is not None and binding_key in history["bindings"]:
                    identity, version = history["bindings"][binding_key]
                    inventory[-1]["rule_binding"] = {
                        "request_id": request_id,
                        "entry_id": identity,
                        "version": version,
                        "receipt_sha256": binding_key[1],
                    }
                if request_id in reviews:
                    accepted.append({"receipt": receipt, "review": reviews.pop(request_id)})
        if reviews:
            raise ValueError("REVIEW_NOT_IN_SELECTED_ACTIVE_RECEIPTS")
        reviewed_rulings(accepted)
        executable = {
            "format": input_format,
            "rulings": accepted,
            "discovery_entry_ids": list(discovery),
            "audit_entry_ids": list(audit),
            "entries": entries,
            "relations": relation_records(relations),
        }
        for key in ("candidates", "guarded_candidates"):
            if key in selection:
                executable[key] = selection[key]
        if history is not None:
            bindings = []
            for accepted_record in accepted:
                key = receipt_binding_key(accepted_record["receipt"])
                if key in history["bindings"]:
                    entry_id, version = history["bindings"][key]
                    bindings.append(
                        {
                            "request_id": key[0],
                            "entry_id": entry_id,
                            "version": version,
                            "receipt_sha256": key[1],
                        }
                    )
            if bindings:
                current_version = digest(relation_records(relations))
                needed = {current_version, *(record["version"] for record in bindings)}
                executable["rule_history"] = {
                    "format": "GSE.reviewed-pattern-history/2"
                    if history["allow_revisions"]
                    else "GSE.reviewed-pattern-history/1",
                    "current_version": current_version,
                    "versions": [
                        {"version": version, "relations": relation_records(history["versions"][version])}
                        for version in sorted(needed)
                    ],
                    "bindings": sorted(bindings, key=lambda record: record["request_id"]),
                }
        return {
            "format": EXPORT_FORMAT,
            "candidate": str(path),
            "lexicon_writes": False,
            "model_calls": 0,
            "selected_provenance": "REPLAY_VALIDATED",
            "input": executable,
            "input_sha256": _request_id(executable),
            "selection_sha256": _request_id(selection),
            "inventory": inventory,
            "review_outcomes": dict(Counter(item["review_status"] for item in inventory)),
            "authority": "EXPLICIT_REVIEWS_ONLY_EXPORT_DOES_NOT_REVIEW_OR_APPROVE",
        }
    finally:
        conn.close()


def export_from_selection(candidate: str | Path, selection_path: str | Path) -> dict:
    return export_reviewed_input(candidate, read_json(selection_path))
