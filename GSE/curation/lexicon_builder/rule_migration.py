"""Apply a reviewed rule revision to a separate, fully replayed candidate.

The source database and active pointer are never modified. A failed or partial
migration never becomes the requested output. All model chains within the new
changed rules' typed scopes are conservatively archived for reconsideration; unaffected
chains retain their exact original authority under immutable rule versions.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from GSE.namespace import current_id

from .completion import _entry, _refresh_coverage
from .foundation import BANKS
from .resolution import resolve_dictionary
from .rule_admission import admit_rule
from .rule_history import digest, install_history, read_history, receipt_binding_key, relation_records
from .rule_revisions import FORMAT as REVISION_FORMAT
from .rule_revisions import (
    reviewed_model_withdrawals,
    revision_relations,
    rule_changes,
    touches_scope,
    validate_revision_shape,
)
from .storage import _json, store_entry
from .validation import (
    _authorities,
    _metadata,
    _native_catalog,
    _observations,
    _optional_metadata,
    _read_json,
    _relations,
    _replay,
    _schema,
    _stored_context,
)


def _put_version(conn, relations):
    records = relation_records(relations)
    version = digest(records)
    if not conn.execute("SELECT 1 FROM rule_versions WHERE version=?", (version,)).fetchone():
        conn.execute("INSERT INTO rule_versions VALUES (?,?)", (version, _json(records)))
    return version


def _refresh_catalog(conn, relations, native, bank_relevance):
    from .catalog import catalog_report
    from .evidence import Definition

    anchors, models = _authorities(conn)
    lexemes = {row["id"]: row for row in conn.execute("SELECT * FROM lexemes")}
    links = _optional_metadata(conn, "prime_entries", {})
    if current_id(_metadata(conn, "catalog")["format"]) == "GSE.nsm-catalog-coverage/1":
        definitions = tuple(Definition(r["sense_id"], r["lemma"], r["pos"], r["gloss"]) for r in lexemes.values())
        catalog = catalog_report(anchors, definitions, relations, prime_entries=links)
    else:
        evidence, restrictions = defaultdict(list), defaultdict(list)
        for entry, ordinal, payload in conn.execute("SELECT * FROM builder_assertions"):
            evidence[entry].append((ordinal, payload))
        for entry, ordinal, payload in conn.execute("SELECT * FROM builder_domain_restrictions"):
            restrictions[entry].append((ordinal, payload))
        catalog = _native_catalog(
            anchors, relations, lexemes, links, models, evidence, restrictions, native, bank_relevance, conn=conn
        )
    conn.execute("INSERT OR REPLACE INTO builder_metadata VALUES ('catalog',?)", (_json(catalog),))
    report = _refresh_coverage(conn)
    report.update(foundation_readiness=catalog["readiness"], prime_coverage=catalog["coverage_counts"])
    conn.execute("INSERT OR REPLACE INTO builder_metadata VALUES ('last_report',?)", (_json(report),))
    return report


def _exception_keys(resolution):
    # A newly requested predicate on another rule can add context fields to
    # an existing receipt. Its conflicting proofs and guards remain decisive.
    return {
        _json({key: value for key, value in record.items() if key != "context"})
        for record in resolution.trace
        if record["kind"] == "CONDITIONAL_EXCEPTION"
    }


def _apply_copy(conn, admission=None, *, revision=None):
    old = _relations(_metadata(conn, "relations"))
    if revision is None:
        if admission is None:
            raise ValueError("MIGRATION_REQUIRES_REVIEW")
        if admission["warrant"].get("required_exception_ids") or admission["warrant"].get("required_reservation_ids"):
            raise ValueError("RULE_REQUIRES_JOINT_EXCEPTION_REVIEW")
        if digest(relation_records(old)) != admission["baseline_version"]:
            raise ValueError("MIGRATION_BASELINE_VERSION_MISMATCH")
        addition = _relations([json.loads(_json(admission["relation"]))])[0]
        if any(rule.rule_id == addition.rule_id for rule in old):
            raise ValueError("MIGRATION_RULE_ALREADY_PRESENT")
        new = old + (addition,)
    else:
        new = revision_relations(conn, old, revision)
    removed, added = rule_changes(old, new)
    shared = tuple(rule for rule in old if rule not in removed)
    local_reviews = defaultdict(list)
    reservation_reviews = defaultdict(list)
    if revision is not None:
        for review in revision["exceptions"]:
            local_reviews[review["entry_id"]].append(review)
        for review in revision.get("reservations", ()):
            reservation_reviews[review["entry_id"]].append(review)
    preflight = _replay(conn, old)
    if preflight["code"] != "REPLAY_VALIDATED" or not preflight["complete_search"]:
        raise ValueError("MIGRATION_REQUIRES_COMPLETE_REPLAY")
    entries = tuple(row[0] for row in conn.execute("SELECT entry_id FROM definition_states ORDER BY entry_id"))
    _, models = _authorities(conn)
    failures = []
    native, _, relevance = _observations(conn, set(entries), lambda *a, **kw: failures.append((a, kw)), models)
    if failures:
        raise ValueError("MIGRATION_SOURCE_INVALID")
    history = read_history(conn, old)
    install_history(conn)
    old_version, new_version = _put_version(conn, old), _put_version(conn, new)
    archived, retained, changed, narrowed = [], 0, 0, 0
    known_changes, exception_checks = [], []
    reservation_checks = []
    for entry_id in entries:
        definition, assertions, restrictions, hierarchy = _entry(conn, entry_id)
        old_context = _stored_context(conn, definition, old)
        new_context = _stored_context(conn, definition, new)
        evidence_banks = tuple(sorted(relevance.get(entry_id, ())))
        receipts = models.get(entry_id, ())
        reviews = local_reviews.get(entry_id, ())
        withdrawn = reviewed_model_withdrawals(reviews, receipts)
        for receipt in receipts:
            request_id, receipt_hash = receipt_binding_key(receipt)
            if not conn.execute(
                "SELECT 1 FROM model_rule_versions WHERE request_id=? AND receipt_sha256=?", (request_id, receipt_hash)
            ).fetchone():
                conn.execute(
                    "INSERT INTO model_rule_versions VALUES (?,?,?,?)",
                    (request_id, entry_id, old_version, receipt_hash),
                )
        # Matching the guard is deliberately conservative, even if the premise
        # is currently unknown or an absence guard might block the new rule.
        scope_affected = touches_scope(removed, old_context) or touches_scope(added, new_context)
        first_affected = (
            0
            if scope_affected
            else next((i for i, receipt in enumerate(receipts) if receipt["request_id"] in withdrawn), len(receipts))
        )
        prefix, dropped = receipts[:first_affected], receipts[first_affected:]
        before = _read_json(
            conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (entry_id,)).fetchone()[0]
        )
        if dropped:
            archived.append(
                {
                    "definition": {key: getattr(definition, key) for key in ("entry_id", "lemma", "pos", "definition")},
                    "assertions": [asdict(a) for a in assertions],
                    "restrictions": [asdict(r) for r in restrictions],
                    "receipts": dropped,
                    **({"retained_prefix": prefix} if prefix else {}),
                    "evidence_banks": evidence_banks,
                    "reason": "REVIEWED_EXCEPTION_REQUIRES_MODEL_RECONSIDERATION"
                    if withdrawn
                    else "ADDED_RULE_SCOPE_REQUIRES_MODEL_CONTEXT_RECONSIDERATION"
                    if revision is None
                    else "REVISED_RULE_SCOPE_REQUIRES_MODEL_CONTEXT_RECONSIDERATION",
                }
            )
            retired_assertions = {_json(r["assertion"]) for r in dropped}
            assertions = tuple(a for a in assertions if _json(asdict(a)) not in retired_assertions)
            deleted = conn.execute(
                "DELETE FROM accepted_model_receipts WHERE entry_id=? AND ordinal>=?", (entry_id, first_affected)
            ).rowcount
            if deleted != len(dropped):
                raise ValueError("MIGRATION_MODEL_RECEIPT_DELETE_MISMATCH")
        retained += len(prefix)
        baseline = resolve_dictionary(
            BANKS, assertions, shared, old_context, evidence_banks=evidence_banks, domain_restrictions=restrictions
        )
        after = resolve_dictionary(
            BANKS, assertions, new, new_context, evidence_banks=evidence_banks, domain_restrictions=restrictions
        )
        if (
            baseline.code == "CONFLICT"
            or any(r["kind"] == "SOLVER_LIMIT" for r in baseline.trace)
            or after.code == "CONFLICT"
            or any(r["kind"] == "SOLVER_LIMIT" for r in after.trace)
            or _exception_keys(after) - _exception_keys(baseline)
        ):
            raise ValueError("MIGRATION_RULE_SCOPE_COUNTEREXAMPLE:" + entry_id)
        if any(after.assignments.get(bank) != value for bank, value in baseline.assignments.items()):
            raise ValueError("MIGRATION_CHANGED_RETAINED_KNOWN:" + entry_id)
        if any(after.assignments.get(bank) not in {-1, 1} for bank in hierarchy):
            raise ValueError("MIGRATION_HIERARCHY_REQUIRES_REVIEW:" + entry_id)
        after_domains = {bank: sorted(values) for bank, values in after.domains.items()}
        changed += before != after_domains
        narrowed += sum(len(after.domains[b]) < len(baseline.domains[b]) for b in BANKS)
        if revision is not None and before != after_domains:
            known_changes.extend(
                {"entry_id": entry_id, "bank": bank, "before": before[bank], "after": values}
                for bank, values in after_domains.items()
                if len(before[bank]) == 1 and before[bank] != values
            )
        for review in reviews:
            if any(value not in baseline.domains[bank] for bank, value in review["counterexample"].items()):
                raise ValueError("REVISION_EXCEPTION_CONFLICTS_WITH_RETAINED_EVIDENCE:" + entry_id)
            if any(value not in after.domains[bank] for bank, value in review["counterexample"].items()):
                raise ValueError("REVISION_EXCEPTION_NOT_HONORED:" + entry_id)
            exception_checks.append(
                {
                    "entry_id": entry_id,
                    "rule_id": review["rule_id"],
                    "code": "REVIEWED_LOCAL_EXCEPTION",
                    "reviewed_model_withdrawals": list(withdrawn),
                    "baseline_domains": {bank: sorted(baseline.domains[bank]) for bank in review["counterexample"]},
                    "after_domains": {bank: after_domains[bank] for bank in review["counterexample"]},
                }
            )
        for review in reservation_reviews.get(entry_id, ()):
            bank = review["bank"]
            expected = review["audit"]["request"]["allowed_values"]
            if (
                before[bank] != expected
                or sorted(baseline.domains[bank]) != expected
                or after_domains[bank] != expected
            ):
                raise ValueError("REVISION_RESERVATION_NOT_HONORED:" + entry_id)
            reservation_checks.append(
                {
                    "code": "REVIEWED_UNRESOLVED_RESERVATION",
                    "entry_id": entry_id,
                    "rule_id": review["rule_id"],
                    "bank": bank,
                    "baseline_domain": expected,
                    "after_domain": after_domains[bank],
                    "audit_request_id": review["audit"]["request_id"],
                }
            )
        store_entry(conn, definition, after, assertions, hierarchy, domain_restrictions=restrictions)
    event = {
        "format": "GSE.rule-migration-event/1",
        "from_version": old_version,
        "to_version": new_version,
        "created_utc": datetime.now(UTC).isoformat(),
        "admission": admission,
        "archived": archived,
    }
    if (
        revision is not None
        or history
        and any(current_id(item["format"]) == "GSE.rule-migration-event/2" for item in history["events"])
    ):
        del event["admission"]
        event.update(
            format="GSE.rule-migration-event/2",
            previous_event=history["head"] if history else None,
            revision=revision
            if revision is not None
            else {
                "format": REVISION_FORMAT,
                "baseline_version": old_version,
                "admissions": [admission],
                "retirements": [],
                "exceptions": [],
            },
        )
    event_id = digest(event)
    conn.execute("INSERT INTO rule_migrations VALUES (?,?)", (event_id, _json(event)))
    for key, value in (("relations", relation_records(new)), ("rule_version", new_version)):
        conn.execute("INSERT OR REPLACE INTO builder_metadata VALUES (?,?)", (key, _json(value)))
    coverage = _refresh_catalog(conn, new, native, relevance)
    verified = _replay(conn, new)
    if verified["code"] != "REPLAY_VALIDATED" or not verified["complete_search"]:
        raise ValueError("MIGRATION_POST_REPLAY_FAILED:" + _json(verified["mismatch_counts"]))
    return {
        "format": "GSE.rule-migration/1" if revision is None else "GSE.rule-migration/2",
        "code": "MIGRATED_CANDIDATE",
        "event_id": event_id,
        "from_version": old_version,
        "to_version": new_version,
        "entries_reclosed": len(entries),
        "entries_changed_domains": changed,
        "cells_symbolically_narrowed": narrowed,
        "archived_model_receipts": sum(len(e["receipts"]) for e in archived),
        "retained_model_receipts": retained,
        "preflight": preflight,
        "postflight": verified,
        "coverage": {key: coverage[key] for key in ("definitions", "outcomes", "cells")},
        "active_pointer_changed": False,
        "model_calls": 0,
        **(
            {
                "revised_scope_changes": {
                    "old_rule_ids": [rule.rule_id for rule in removed],
                    "new_rule_ids": [rule.rule_id for rule in added],
                },
                "known_domain_changes": known_changes,
                "reviewed_exceptions": exception_checks,
                **({"reviewed_reservations": reservation_checks} if reservation_checks else {}),
            }
            if revision is not None
            else {}
        ),
    }


def migrate_rule(source, output, input_path, audit_path, review):
    """Create a new candidate atomically after explicit admission and full replay.

    The existing source remains the rollback unit. Output must not exist; neither
    an active pointer nor an existing database can be overwritten by this API.
    """
    return _migrate(source, output, admission=admit_rule(input_path, audit_path, review))


def migrate_revision(source, output, revision):
    """Apply the complete reviewed delta as one atomic, replayed transition."""
    validate_revision_shape(revision)
    return _migrate(source, output, revision=revision)


def _migrate(source, output, *, admission=None, revision=None):
    if revision is None:
        if admission is None:
            raise ValueError("MIGRATION_REQUIRES_REVIEW")
        admissions = [admission]
    else:
        admissions = revision["admissions"]
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file():
        raise ValueError("BUILD_NOT_FOUND")
    if output.exists() or output == source:
        raise ValueError("MIGRATION_OUTPUT_MUST_BE_NEW")
    if output.suffix != ".db":
        raise ValueError("MIGRATION_OUTPUT_REQUIRES_DATABASE_PATH")
    from .sqlite_snapshot import copy_database

    directory = tempfile.TemporaryDirectory(prefix=".gse-migration-", dir=output.parent)
    temporary = Path(directory.name) / "snapshot.db"
    try:
        copy_database(source, temporary)
        return _migrate_snapshot(source, temporary, output, admissions, admission, revision)
    finally:
        directory.cleanup()


def _migrate_snapshot(source, temporary, output, admissions, admission, revision):
    conn = sqlite3.connect(temporary)
    try:
        from .residual import _request_id
        from .reviewed_export import export_reviewed_input

        for reviewed in admissions:
            raw = reviewed["input"]
            selection = {
                "format": "GSE.reviewed-pattern-selection/1",
                "discovery_entry_ids": raw["discovery_entry_ids"],
                "audit_entry_ids": raw["audit_entry_ids"],
                "reviews": [{"request_id": r["receipt"]["request_id"], "review": r["review"]} for r in raw["rulings"]],
                **{key: raw[key] for key in ("candidates", "guarded_candidates") if key in raw},
            }
            fresh = export_reviewed_input(temporary, selection, input_format=raw["format"])
            if fresh["input_sha256"] != _request_id(raw):
                raise ValueError("MIGRATION_AUDITED_SNAPSHOT_CHANGED")
        conn.row_factory = sqlite3.Row
        _schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        report = _apply_copy(conn, admission, revision=revision)
        conn.commit()
        conn.close()
        # link is a no-clobber atomic install on the same filesystem.
        os.link(temporary, output)
        report.update(source=str(source), candidate=str(output))
        return report
    except BaseException:
        conn.close()
        raise
