"""Immutable rule versions and original model authority across migrations."""

from __future__ import annotations

import hashlib
from dataclasses import asdict

from .storage import _json

TABLES = {
    "rule_versions": "version TEXT PRIMARY KEY NOT NULL,payload TEXT NOT NULL",
    "model_rule_versions": (
        "request_id TEXT NOT NULL,entry_id TEXT NOT NULL,version TEXT NOT NULL,receipt_sha256 TEXT NOT NULL,"
        "PRIMARY KEY (request_id,receipt_sha256)"
    ),
    "rule_migrations": "event_id TEXT PRIMARY KEY NOT NULL,payload TEXT NOT NULL",
}


def digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def receipt_binding_key(receipt):
    """A repeated typed question can produce distinct, independently bound rulings."""
    return receipt["request_id"], digest(receipt)


def relation_records(relations):
    # The canonical JSON round trip fixes tuple/list interchange without changing order.
    import json

    return json.loads(_json([asdict(rule) for rule in relations]))


def install_history(conn):
    """Install append-only tables within the caller's transaction; never commit."""
    primary_key = tuple(row[1] for row in conn.execute("PRAGMA table_info(model_rule_versions)") if row[5])
    if primary_key == ("request_id",):
        conn.execute("ALTER TABLE model_rule_versions RENAME TO model_rule_versions_legacy")
        conn.execute(f"CREATE TABLE model_rule_versions ({TABLES['model_rule_versions']})")
        conn.execute("INSERT INTO model_rule_versions SELECT * FROM model_rule_versions_legacy")
        conn.execute("DROP TABLE model_rule_versions_legacy")
    elif primary_key not in {(), ("request_id", "receipt_sha256")}:
        raise ValueError("INVALID_MODEL_RULE_VERSION_SCHEMA")
    for table, columns in TABLES.items():
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({columns})")
        keys = {
            "model_rule_versions": ("request_id", "receipt_sha256"),
            "rule_versions": ("version",),
            "rule_migrations": ("event_id",),
        }[table]
        equality = " AND ".join(f"{key}=NEW.{key}" for key in keys)
        for suffix, clause in (
            ("update", "BEFORE UPDATE"),
            ("delete", "BEFORE DELETE"),
            ("replace", "BEFORE INSERT"),
        ):
            condition = f" WHEN EXISTS (SELECT 1 FROM {table} WHERE {equality})" if suffix == "replace" else ""
            conn.execute(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_{suffix} {clause} ON {table}{condition} "
                "BEGIN SELECT RAISE(ABORT,'RULE_HISTORY_APPEND_ONLY'); END"
            )


def read_history(conn, current):
    """Verify hashes and indexes before any historical request gets authority."""
    from .foundation import EXCEPTION_GUARD_PREFIX
    from .rule_admission import verify_admission
    from .validation import _metadata, _read_json, _relations

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    present = set(TABLES) & tables
    marker = conn.execute("SELECT value FROM builder_metadata WHERE key='rule_version'").fetchone()
    if not present:
        if marker:
            raise ValueError("MISSING_RULE_HISTORY")
        if any(key.startswith(EXCEPTION_GUARD_PREFIX) for rule in current for key, _ in rule.guards):
            raise ValueError("UNREVIEWED_DEFINITION_EXCEPTION")
        return None
    if present != set(TABLES) or marker is None:
        raise ValueError("INCOMPLETE_RULE_HISTORY")
    versions = {}
    for version, payload in conn.execute("SELECT version,payload FROM rule_versions"):
        raw = _read_json(payload)
        if digest(raw) != version:
            raise ValueError("RULE_VERSION_HASH_MISMATCH")
        versions[version] = _relations(raw)
    version = digest(relation_records(current))
    if _metadata(conn, "rule_version") != version or version not in versions:
        raise ValueError("CURRENT_RULE_VERSION_MISMATCH")
    bindings = {}
    for request, entry, original, receipt_hash in conn.execute("SELECT * FROM model_rule_versions"):
        key = (request, receipt_hash)
        if original not in versions or len(receipt_hash) != 64 or key in bindings:
            raise ValueError("INVALID_MODEL_RULE_VERSION")
        bindings[key] = (entry, original)
    from .rule_revisions import reviewed_model_withdrawals, revision_relations

    events = {}
    for event_id, payload in conn.execute("SELECT event_id,payload FROM rule_migrations"):
        event = _read_json(payload)
        if digest(event) != event_id or event.get("format") not in {
            "gse.rule-migration-event/1",
            "gse.rule-migration-event/2",
        }:
            raise ValueError("RULE_MIGRATION_HASH_MISMATCH")
        if event.get("from_version") not in versions or event.get("to_version") not in versions:
            raise ValueError("RULE_MIGRATION_VERSION_MISSING")
        if not isinstance(event.get("archived"), list):
            raise ValueError("INVALID_RULE_MIGRATION_ARCHIVE")
        before = versions[event["from_version"]]
        if event["format"] == "gse.rule-migration-event/1":
            verify_admission(event["admission"])
            if (
                event["admission"]["warrant"].get("required_exception_ids")
                or event["admission"]["warrant"].get("required_reservation_ids")
            ):
                raise ValueError("RULE_REQUIRES_JOINT_EXCEPTION_REVIEW")
            if event["admission"]["baseline_version"] != event["from_version"]:
                raise ValueError("RULE_MIGRATION_ADMISSION_DELTA_MISMATCH")
            expected = relation_records(before) + [event["admission"]["relation"]]
        else:
            if "previous_event" not in event:
                raise ValueError("RULE_MIGRATION_CHAIN_INVALID")
            expected = relation_records(revision_relations(conn, before, event["revision"]))
            archived = [receipt for record in event["archived"] for receipt in record["receipts"]]
            reviewed_model_withdrawals(event["revision"]["exceptions"], archived)
        if digest(expected) != event["to_version"]:
            raise ValueError("RULE_MIGRATION_ADMISSION_DELTA_MISMATCH")
        events[event_id] = event
    if not events:
        raise ValueError("MISSING_RULE_MIGRATION_EVENT")
    ordered = _event_chain(events, versions, version)
    root = versions[events[ordered[0]]["from_version"]]
    if any(key.startswith(EXCEPTION_GUARD_PREFIX) for rule in root for key, _ in rule.guards):
        raise ValueError("UNREVIEWED_DEFINITION_EXCEPTION")
    _binding_inventory(conn, bindings, [events[key] for key in ordered], tables)
    return {
        "versions": versions,
        "bindings": bindings,
        "events": [events[key] for key in ordered],
        "head": ordered[-1],
        "allow_revisions": any(events[key]["format"] == "gse.rule-migration-event/2" for key in ordered),
    }


def _event_chain(events, versions, current):
    """Legacy additions chain by version; revisions chain by event identity."""
    legacy = {}
    destinations = set()
    successors = {}
    for key, event in events.items():
        old, new = event["from_version"], event["to_version"]
        if old == new:
            raise ValueError("RULE_MIGRATION_CHAIN_INVALID")
        if event["format"] == "gse.rule-migration-event/1":
            if old in legacy or new in destinations:
                raise ValueError("RULE_MIGRATION_CHAIN_INVALID")
            legacy[old] = key
            destinations.add(new)
        else:
            parent = event["previous_event"]
            if parent is not None and (type(parent) is not str or parent not in events):
                raise ValueError("RULE_MIGRATION_CHAIN_INVALID")
            if parent in successors:
                raise ValueError("RULE_MIGRATION_CHAIN_INVALID")
            successors[parent] = key
    ordered, reached = [], set()
    if legacy:
        roots = set(legacy) - destinations
        if len(roots) != 1:
            raise ValueError("RULE_MIGRATION_CHAIN_INVALID")
        version = next(iter(roots))
        reached.add(version)
        while version in legacy:
            key = legacy[version]
            version = events[key]["to_version"]
            if version in reached:
                raise ValueError("RULE_MIGRATION_CHAIN_INVALID")
            reached.add(version)
            ordered.append(key)
        if len(ordered) != len(legacy):
            raise ValueError("RULE_MIGRATION_CHAIN_INVALID")
    elif None in successors:
        version = events[successors[None]]["from_version"]
        reached.add(version)
    else:
        raise ValueError("RULE_MIGRATION_CHAIN_INVALID")
    parent = ordered[-1] if ordered else None
    seen = set(ordered)
    while parent in successors:
        key = successors[parent]
        event = events[key]
        if key in seen or event["from_version"] != version:
            raise ValueError("RULE_MIGRATION_CHAIN_INVALID")
        version = event["to_version"]
        reached.add(version)
        ordered.append(key)
        seen.add(key)
        parent = key
    if version != current or reached != set(versions) or len(ordered) != len(events):
        raise ValueError("RULE_MIGRATION_CHAIN_INVALID")
    return ordered


def _binding_inventory(conn, bindings, events, tables):
    """Every historical binding must have exactly one active or archived receipt."""
    from .model_receipts import read_model_receipts
    from .validation import _read_json

    observed, unbound_requests = set(), set()

    def include(receipt):
        key = receipt_binding_key(receipt)
        if key not in bindings:
            unbound_requests.add(key[0])
            return
        if key in observed:
            raise ValueError("DUPLICATE_HISTORICAL_MODEL_RECEIPT")
        entry, _ = bindings[key]
        if receipt["entry_id"] != entry:
            raise ValueError("MODEL_RULE_BINDING_MISMATCH")
        observed.add(key)

    for receipts in read_model_receipts(conn).values():
        for receipt in receipts:
            include(receipt)
    for event in events:
        for archived in event["archived"]:
            for receipt in archived["receipts"]:
                include(receipt)
    if "model_reconsideration_archive" in tables:
        for event_id, payload in conn.execute("SELECT event_id,payload FROM model_reconsideration_archive"):
            archived = _read_json(payload)
            if digest(archived) != event_id:
                raise ValueError("RECONSIDERATION_ARCHIVE_HASH_MISMATCH")
            for row in archived["archived_receipts"]:
                include(row["receipt"])
    missing = set(bindings) - observed
    if any(request in unbound_requests for request, _ in missing):
        raise ValueError("MODEL_RULE_BINDING_MISMATCH")
    if missing:
        raise ValueError("MISSING_HISTORICAL_MODEL_RECEIPT")


def receipt_relations(receipt, current, context, history, *, definition=None, observations=()):
    """Replay a retained answer at its original rules outside changed scopes."""
    if history is None:
        return current
    binding = history["bindings"].get(receipt_binding_key(receipt))
    if binding is None:
        return current
    entry, version = binding
    if entry != receipt["entry_id"]:
        raise ValueError("MODEL_RULE_BINDING_MISMATCH")
    original = history["versions"][version]
    from .foundation import lexical_context
    from .rule_revisions import rule_changes, touches_scope

    removed, added = rule_changes(original, current)
    if not history.get("allow_revisions"):
        by_id = {rule.rule_id: rule for rule in current}
        if any(by_id.get(rule.rule_id) != rule for rule in original):
            raise ValueError("NONADDITIVE_RULE_HISTORY")
    if not removed and not added:
        return original
    if definition is None:
        if removed:
            raise ValueError("NONADDITIVE_RULE_HISTORY")
        affected = touches_scope(added, context)
    else:
        affected = (
            bool(removed)
            and touches_scope(removed, lexical_context(definition, observations, original))
            or bool(added)
            and touches_scope(added, lexical_context(definition, observations, current))
        )
    if affected:
        raise ValueError("HISTORICAL_MODEL_CONTEXT_AFFECTED")
    return original


def replay_archives(conn, history, native, relevant, anchors):
    """Replay archived model chains against their original rules and evidence."""
    if history is None:
        return
    from .engine import Assertion, DomainRestriction
    from .evidence import Definition
    from .validation import _provenance, _restriction_provenance

    seen = set()
    for event in history["events"]:
        relations = history["versions"][event["from_version"]]
        for archived in event["archived"]:
            definition = Definition(**archived["definition"])
            entry = definition.entry_id
            assertions = tuple(Assertion(**raw) for raw in archived["assertions"])
            restrictions = tuple(
                DomainRestriction(
                    raw["bank"],
                    tuple(raw["allowed_values"]),
                    raw["source"],
                    raw["record_id"],
                    raw["family"],
                    raw["scope"],
                )
                for raw in archived["restrictions"]
            )
            receipts = archived["receipts"]
            keys = {receipt_binding_key(row) for row in receipts}
            if not receipts or len(keys) != len(receipts) or keys & seen:
                raise ValueError("INVALID_RULE_MIGRATION_RECEIPT_CHAIN")
            prefix = archived.get("retained_prefix", [])
            if type(prefix) is not list or any(
                receipt_binding_key(row) not in history["bindings"] or row["entry_id"] != entry for row in prefix
            ):
                raise ValueError("INVALID_RULE_MIGRATION_RETAINED_PREFIX")
            seen.update(keys)
            _restriction_provenance(entry, restrictions, native)
            _provenance(
                entry,
                assertions,
                definition,
                relations,
                native,
                relevant,
                anchors,
                {entry: prefix + receipts},
                conn,
                tuple(archived["evidence_banks"]),
                restrictions,
                rule_history=history,
            )
