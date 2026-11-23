"""Conservatively withdraw an accepted ruling and its same-definition suffix.

Full preflight replay precedes any write. The original full receipts and
assertion ordinals survive in an append-only archive; original attempt journals
and schedules stay untouched. Only explicit model assertions are removed.
Retained evidence is re-resolved, never replaced by complement zeros. This does
not change conventions/rules or run a model. A hierarchy losing its nonzero base
requires a separate decision and is refused here.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from GSE.namespace import current_id, identity_form

from .completion import _entry, _refresh_coverage
from .engine import Assertion
from .evidence import Observation
from .foundation import BANKS, lexical_context
from .model_receipts import ModelReceipts, read_model_receipts
from .relevance import observation_relevance
from .resolution import resolve_dictionary
from .storage import _json, read_entries, store_entry
from .validation import _metadata, _provenance, _read_json, _relations, validate_build

FORMAT = "GSE.model-reconsideration/1"
TABLE = "model_reconsideration_archive"
SCHEMA = f"""CREATE TABLE {TABLE} (
 event_id TEXT PRIMARY KEY NOT NULL, root_request_id TEXT NOT NULL,
 entry_id TEXT NOT NULL, convention TEXT NOT NULL, reason TEXT NOT NULL,
 created_utc TEXT NOT NULL, payload TEXT NOT NULL)"""
TRIGGERS = {
    "no_update": f"BEFORE UPDATE ON {TABLE}",
    "no_delete": f"BEFORE DELETE ON {TABLE}",
    "no_replace": f"BEFORE INSERT ON {TABLE} WHEN EXISTS (SELECT 1 FROM {TABLE} WHERE event_id=NEW.event_id)",
}


def _digest(value):
    return hashlib.sha256(_json(identity_form(value)).encode()).hexdigest()


def _text(value, code, maximum):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ValueError(code)


def _revision(conn):
    return conn.execute("PRAGMA data_version").fetchone()[0]


def _archive_schema(conn):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone()
    if exists:
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info({TABLE})")]
        if columns != ["event_id", "root_request_id", "entry_id", "convention", "reason", "created_utc", "payload"]:
            raise ValueError("INVALID_RECONSIDERATION_ARCHIVE_SCHEMA")
        for row in conn.execute(f"SELECT * FROM {TABLE}"):
            payload = _read_json(row[6])
            if _digest(payload) != row[0]:
                raise ValueError("RECONSIDERATION_ARCHIVE_HASH_MISMATCH")
            if (
                not isinstance(payload, dict)
                or current_id(payload.get("format")) != FORMAT
                or any(
                    payload.get(key) != row[index]
                    for index, key in enumerate(
                        ("root_request_id", "entry_id", "convention", "reason", "created_utc"), start=1
                    )
                )
            ):
                raise ValueError("RECONSIDERATION_ARCHIVE_INDEX_MISMATCH")
    else:
        conn.execute(SCHEMA)
    for name, clause in TRIGGERS.items():
        sql = f"CREATE TRIGGER reconsideration_{name} {clause} BEGIN SELECT RAISE(ABORT,'RECONSIDERATION_ARCHIVE_APPEND_ONLY'); END"
        previous = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (f"reconsideration_{name}",)
        ).fetchone()
        if previous and previous[0] != sql:
            raise ValueError("INVALID_RECONSIDERATION_ARCHIVE_GUARD")
        if not previous:
            conn.execute(sql)


def _coverage(conn):
    outcomes = dict(conn.execute("SELECT code,COUNT(*) FROM definition_states GROUP BY code"))
    cells = conn.execute("""SELECT
        COALESCE(SUM(d.code!='CONFLICT' AND json_array_length(c.value)=1),0),
        COALESCE(SUM(d.code!='CONFLICT' AND c.value='[0]'),0),
        COALESCE(SUM(json_array_length(c.value)>1),0),
        COALESCE(SUM(json_array_length(c.value)=0),0)
        FROM definition_states d,json_each(d.domains) c""").fetchone()
    return {
        "definitions": sum(outcomes.values()),
        "outcomes": outcomes,
        "cells": dict(zip(("assigned", "explicit_zero", "unresolved", "conflicted"), cells)),
    }


def _prepare(conn, request_id):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='accepted_model_receipts'").fetchone():
        raise ValueError("RECONSIDERATION_REQUIRES_INDEXED_MODEL_RECEIPTS")
    root = conn.execute(
        "SELECT entry_id,ordinal FROM accepted_model_receipts WHERE request_id=?", (request_id,)
    ).fetchone()
    if root is None:
        raise ValueError("ROOT_NOT_ACCEPTED_MODEL_REQUEST")
    models = read_model_receipts(conn)
    if not isinstance(models, ModelReceipts):
        raise ValueError("RECONSIDERATION_REQUIRES_INDEXED_MODEL_RECEIPTS")
    entry_id, start = root
    receipts = models[entry_id]
    if not 0 <= start < len(receipts) or receipts[start]["request_id"] != request_id:
        raise ValueError("RECONSIDERATION_ROOT_INDEX_MISMATCH")
    definition, assertions, restrictions, hierarchy = _entry(conn, entry_id)
    removed = receipts[start:]
    removals = Counter(_json(receipt["assertion"]) for receipt in removed)
    retained, removed_assertions = [], []
    for ordinal, assertion in enumerate(assertions):
        key = _json(asdict(assertion))
        if removals[key]:
            if assertion.family != "model" or not assertion.source.startswith("model:"):
                raise ValueError("RECONSIDERATION_NONMODEL_ASSERTION")
            removals[key] -= 1
            removed_assertions.append({"original_ordinal": ordinal, "assertion": asdict(assertion)})
        else:
            retained.append(assertion)
    if any(removals.values()) or len(removed_assertions) != len(removed):
        raise ValueError("RECONSIDERATION_ASSERTION_RECEIPT_MISMATCH")
    relations = _relations(_metadata(conn, "relations"))
    # Full preflight has established this exact source context. Read each native
    # row again by its primary key rather than rescan the entire source corpus.
    observations, native, relevant = [], {}, set()
    for original in removed[0]["request"]["observations"]:
        row = conn.execute(
            "SELECT payload FROM source_observations WHERE record_id=?", (original["record_id"],)
        ).fetchone()
        if row is None or _json(_read_json(row[0])) != _json(original):
            raise ValueError("RECONSIDERATION_SOURCE_CONTEXT_CHANGED")
        raw = _read_json(row[0])
        observation = Observation(
            entry_id=raw["entry_id"],
            source=raw["source"],
            record_id=raw["record_id"],
            family=raw["family"],
            features=raw["features"],
            scope=raw["scope"],
            candidate_entry_ids=tuple(raw["candidate_entry_ids"]),
        )
        observations.append(raw)
        relevant.update(observation_relevance(observation))
        if observation.scope == "lexical":
            native[(observation.source, observation.record_id)] = observation
    anchors = {entry_id: tuple(Assertion(**raw) for raw in _metadata(conn, "anchors").get(entry_id, []))}
    evidence_banks = tuple(sorted(relevant))
    after = resolve_dictionary(
        BANKS,
        tuple(retained),
        relations,
        lexical_context(definition, observations, relations),
        evidence_banks=evidence_banks,
        domain_restrictions=restrictions,
    )
    if after.code == "CONFLICT":
        raise ValueError("RECONSIDERATION_RETAINED_EVIDENCE_CONFLICT")
    if any(after.assignments.get(bank) not in {-1, 1} for bank in hierarchy):
        raise ValueError("RECONSIDERATION_HIERARCHY_DEPENDS_ON_WITHDRAWN_MODEL")
    before = read_entries(conn, entry_id=entry_id)[0]
    snapshot = {
        "entry": before,
        "assertions": [asdict(item) for item in assertions],
        "restrictions": [asdict(item) for item in restrictions],
        "receipts": receipts,
        "relations": [asdict(item) for item in relations],
        "anchors": [asdict(item) for item in anchors[entry_id]],
        "observations": observations,
    }
    return {
        "definition": definition,
        "assertions": tuple(retained),
        "restrictions": restrictions,
        "hierarchy": hierarchy,
        "relations": relations,
        "anchors": anchors,
        "native": native,
        "observations": observations,
        "evidence_banks": evidence_banks,
        "after": after,
        "before": before,
        "original_assertions": assertions,
        "receipts": receipts,
        "retained_receipts": receipts[:start],
        "removed_receipts": removed,
        "removed_assertions": removed_assertions,
        "root_ordinal": start,
        "receipt_version": models.version,
        "snapshot_sha256": _digest(snapshot),
    }


def _local_replay(conn, plan):
    entry_id = plan["definition"].entry_id
    definition, assertions, restrictions, hierarchy = _entry(conn, entry_id)
    receipts = ModelReceipts(conn, (entry_id,), plan["receipt_version"])[entry_id]
    if (
        definition != plan["definition"]
        or assertions != plan["assertions"]
        or restrictions != plan["restrictions"]
        or hierarchy != plan["hierarchy"]
        or receipts != plan["retained_receipts"]
    ):
        raise ValueError("RECONSIDERATION_LOCAL_STATE_MISMATCH")
    _provenance(
        entry_id,
        assertions,
        definition,
        plan["relations"],
        plan["native"],
        {entry_id: [row["record_id"] for row in plan["observations"]]},
        plan["anchors"],
        {entry_id: receipts},
        conn,
        plan["evidence_banks"],
        restrictions,
    )
    expected = resolve_dictionary(
        BANKS,
        assertions,
        plan["relations"],
        lexical_context(definition, plan["observations"], plan["relations"]),
        evidence_banks=plan["evidence_banks"],
        domain_restrictions=restrictions,
    )
    saved = read_entries(conn, entry_id=entry_id)[0]
    if (
        saved["id"] != plan["before"]["id"]
        or saved["code"] != expected.code
        or saved["domains"] != {bank: sorted(values) for bank, values in expected.domains.items()}
        or saved["assignments"] != expected.assignments
        or _json(saved["trace"]) != _json(expected.trace)
        or _json(saved["conflicts"]) != _json(expected.conflicts)
    ):
        raise ValueError("RECONSIDERATION_LOCAL_REPLAY_MISMATCH")
    return "LOCAL_REPLAY_VALIDATED"


def reconsider(
    path: str | Path,
    request_id: str,
    *,
    convention: str,
    reason: str,
    apply: bool = False,
    expected_snapshot: str | None = None,
) -> dict:
    """Dry-run by default; explicit apply archives and retracts atomically.

    expected_snapshot optionally pins the exact definition/context dry-run plan.
    PRAGMA data_version independently refuses any concurrent database change
    throughout full preflight and plan construction. No replay cache is trusted.
    """
    _text(request_id, "INVALID_RECONSIDERATION_REQUEST_ID", 64)
    if len(request_id) != 64 or any(character not in "0123456789abcdef" for character in request_id):
        raise ValueError("INVALID_RECONSIDERATION_REQUEST_ID")
    _text(convention, "INVALID_RECONSIDERATION_CONVENTION", 512)
    _text(reason, "INVALID_RECONSIDERATION_REASON", 4096)
    if type(apply) is not bool:
        raise ValueError("INVALID_RECONSIDERATION_APPLY")
    if expected_snapshot is not None:
        _text(expected_snapshot, "INVALID_RECONSIDERATION_SNAPSHOT", 64)
        if len(expected_snapshot) != 64 or any(c not in "0123456789abcdef" for c in expected_snapshot):
            raise ValueError("INVALID_RECONSIDERATION_SNAPSHOT")
    file = Path(path).expanduser().resolve()
    if not file.is_file():
        raise ValueError("BUILD_NOT_FOUND")
    with closing(sqlite3.connect(file.as_uri() + ("?mode=rw" if apply else "?mode=ro"), uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        version = _revision(conn)
        preflight = validate_build(file)
        if preflight["code"] != "REPLAY_VALIDATED":
            raise ValueError("RECONSIDERATION_REQUIRES_VALIDATED_BUILD")
        if _revision(conn) != version:
            raise ValueError("RECONSIDERATION_SNAPSHOT_CHANGED")
        conn.execute("BEGIN")
        try:
            plan = _prepare(conn, request_id)
            before_coverage = _coverage(conn)
        finally:
            conn.rollback()
        if _revision(conn) != version:
            raise ValueError("RECONSIDERATION_SNAPSHOT_CHANGED")
        if expected_snapshot is not None and expected_snapshot != plan["snapshot_sha256"]:
            raise ValueError("RECONSIDERATION_SNAPSHOT_CHANGED")
        root_entry = plan["definition"].entry_id
        report = {
            "format": FORMAT,
            "code": "DRY_RUN",
            "root_request_id": request_id,
            "entry_id": root_entry,
            "convention": convention,
            "reason": reason,
            "snapshot_sha256": plan["snapshot_sha256"],
            "scope": "ROOT_AND_ALL_LATER_SAME_DEFINITION_MODEL_RECEIPTS",
            "root_ordinal": plan["root_ordinal"],
            "withdrawn_request_ids": [row["request_id"] for row in plan["removed_receipts"]],
            "withdrawn_banks": [row["assertion"]["bank"] for row in plan["removed_receipts"]],
            "retained_same_definition_model_receipts": len(plan["retained_receipts"]),
            "before_assignments": plan["before"]["assignments"],
            "after_assignments": plan["after"].assignments,
            "after_domains": {bank: sorted(values) for bank, values in plan["after"].domains.items()},
            "hierarchy": plan["hierarchy"],
            "preflight": preflight,
            "before_coverage": before_coverage,
            "journal_history": "UNCHANGED",
            "model_calls": 0,
            "applied": False,
        }
        if not apply:
            return report
        conn.execute("BEGIN IMMEDIATE")
        try:
            if _revision(conn) != version:
                raise ValueError("RECONSIDERATION_SNAPSHOT_CHANGED")
            _archive_schema(conn)
            archive = {
                "format": FORMAT,
                "root_request_id": request_id,
                "entry_id": root_entry,
                "convention": convention,
                "reason": reason,
                "created_utc": datetime.now(UTC).isoformat(),
                "snapshot_sha256": plan["snapshot_sha256"],
                "before": plan["before"],
                "original_assertions": [
                    {"ordinal": ordinal, "assertion": asdict(assertion)}
                    for ordinal, assertion in enumerate(plan["original_assertions"])
                ],
                "removed_assertions": plan["removed_assertions"],
                "archived_receipts": [
                    {"original_ordinal": plan["root_ordinal"] + ordinal, "receipt": receipt}
                    for ordinal, receipt in enumerate(plan["removed_receipts"])
                ],
                "after_assignments": plan["after"].assignments,
                "after_domains": report["after_domains"],
                "hierarchy": plan["hierarchy"],
            }
            event_id = _digest(archive)
            conn.execute(
                f"INSERT INTO {TABLE} VALUES (?,?,?,?,?,?,?)",
                (event_id, request_id, root_entry, convention, reason, archive["created_utc"], _json(archive)),
            )
            deleted = conn.execute(
                "DELETE FROM accepted_model_receipts WHERE entry_id=? AND ordinal>=?",
                (root_entry, plan["root_ordinal"]),
            ).rowcount
            if deleted != len(plan["removed_receipts"]):
                raise ValueError("RECONSIDERATION_RECEIPT_DELETE_MISMATCH")
            store_entry(
                conn,
                plan["definition"],
                plan["after"],
                plan["assertions"],
                plan["hierarchy"],
                domain_restrictions=plan["restrictions"],
            )
            local = _local_replay(conn, plan)
            coverage = _refresh_coverage(conn)
            report.update(
                code="RECONSIDERED",
                applied=True,
                archive_event_id=event_id,
                post_local_replay=local,
                after_coverage={key: coverage[key] for key in ("definitions", "outcomes", "cells")},
            )
            conn.execute(
                "INSERT OR REPLACE INTO builder_metadata VALUES ('last_reconsideration_report',?)", (_json(report),)
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return report
