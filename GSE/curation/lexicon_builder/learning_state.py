"""Compact, transactional control state for the existing lexicon learner.

This ledger stores hypotheses and execution evidence, never lexical values or
an alternative rule registry. A reviewed candidate still goes through the
ordinary teaching, independent audit, admission and whole-corpus replay path.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .engine import Relation
from .rule_history import digest

FORMAT = "GSE.lexicon-learning-state/1"
DISPOSITIONS = frozenset(
    {
        "AWAITING_WARRANT",
        "READY_FOR_TEACHING",
        "NEEDS_REFINEMENT",
        "AWAITING_AUDIT_REVIEW",
        "RESERVED",
        "UNAVAILABLE",
        "ALREADY_ENTAILED",
        "ADMITTED",
        "REJECTED",
        "RETIRED",
    }
)
SCHEMA = (
    """
CREATE TABLE IF NOT EXISTS learning_metadata (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
""",
    """
CREATE TABLE IF NOT EXISTS mechanisms (
 mechanism_id TEXT PRIMARY KEY, contract TEXT NOT NULL, disposition TEXT NOT NULL,
 reviewed_family TEXT);
""",
    """
CREATE TABLE IF NOT EXISTS mechanism_evidence (
 mechanism_id TEXT NOT NULL, evidence_sha256 TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(mechanism_id,evidence_sha256),
 FOREIGN KEY(mechanism_id) REFERENCES mechanisms(mechanism_id));
""",
    """
CREATE TABLE IF NOT EXISTS learning_events (
 event_sha256 TEXT PRIMARY KEY, kind TEXT NOT NULL, subject TEXT NOT NULL, payload TEXT NOT NULL);
""",
    """
CREATE TABLE IF NOT EXISTS learning_epochs (
 epoch INTEGER PRIMARY KEY, outcome_sha256 TEXT NOT NULL, outcome TEXT NOT NULL);
""",
)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def mechanism_contract(relation):
    """Identify a hypothesis by its actual table and scope, not its label."""
    if not isinstance(relation, Relation):
        raise ValueError("LEARNING_REQUIRES_TYPED_RELATION")
    banks = sorted(relation.banks)
    indices = [relation.banks.index(bank) for bank in banks]
    return {
        "banks": banks,
        "allowed_rows": [list(row) for row in sorted(tuple(row[i] for i in indices) for row in relation.allowed_rows)],
        "guards": [list(guard) for guard in sorted(relation.guards)],
        "absent_evidence": list(sorted(relation.absent_evidence)),
    }


def mechanism_id(relation):
    return digest(mechanism_contract(relation))


class LearningState:
    """Bind control records to one frozen run, keeping original evidence intact."""

    def __init__(self, path, identity):
        self.path = Path(path)
        if self.path.is_symlink() or not self.path.parent.is_dir() or not isinstance(identity, dict):
            raise ValueError("INVALID_LEARNING_STATE_LOCATION_OR_IDENTITY")
        self.identity = _json(identity)
        with self._connect(initialize=True) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and "learning_metadata" not in tables:
                raise ValueError("UNRELATED_DATABASE_IS_NOT_LEARNING_STATE")
            if tables:
                metadata = dict(conn.execute("SELECT key,payload FROM learning_metadata"))
                if metadata.get("format") != _json(FORMAT) or metadata.get("identity") != self.identity:
                    raise ValueError("LEARNING_RUN_IDENTITY_CHANGED")
                if not {"mechanisms", "mechanism_evidence", "learning_events", "learning_epochs"} <= tables:
                    raise ValueError("INCOMPLETE_LEARNING_SCHEMA")
            for statement in SCHEMA:
                conn.execute(statement)
            for key, value in (("format", _json(FORMAT)), ("identity", self.identity)):
                row = conn.execute("SELECT payload FROM learning_metadata WHERE key=?", (key,)).fetchone()
                if row is not None and row[0] != value:
                    raise ValueError("LEARNING_RUN_IDENTITY_CHANGED")
                conn.execute("INSERT OR IGNORE INTO learning_metadata VALUES (?,?)", (key, value))

    @contextmanager
    def _connect(self, *, initialize=False):
        if self.path.is_symlink() or not initialize and not self.path.is_file():
            raise ValueError("LEARNING_STATE_MISSING_OR_REPLACED")
        conn = sqlite3.connect(self.path, timeout=0)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            if not initialize:
                metadata = dict(conn.execute("SELECT key,payload FROM learning_metadata"))
                if metadata.get("format") != _json(FORMAT) or metadata.get("identity") != self.identity:
                    raise ValueError("LEARNING_RUN_IDENTITY_CHANGED")
            with conn:
                yield conn
        except sqlite3.DatabaseError as error:
            if getattr(error, "sqlite_errorname", "") in {"SQLITE_BUSY", "SQLITE_LOCKED"}:
                raise ValueError("LEARNING_STATE_BUSY") from error
            raise ValueError("INVALID_LEARNING_STATE_DATABASE") from error
        finally:
            conn.close()

    @staticmethod
    def _event(conn, kind, subject, payload):
        record = {"kind": kind, "subject": subject, "payload": payload}
        identity, encoded = digest(record), _json(record)
        previous = conn.execute("SELECT payload FROM learning_events WHERE event_sha256=?", (identity,)).fetchone()
        if previous is not None and previous[0] != encoded:
            raise ValueError("LEARNING_EVENT_HASH_COLLISION")
        conn.execute("INSERT OR IGNORE INTO learning_events VALUES (?,?,?,?)", (identity, kind, subject, encoded))
        return identity

    def propose(self, relation, evidence, *, origin):
        if not isinstance(evidence, dict) or not evidence or not isinstance(origin, str) or not origin:
            raise ValueError("LEARNING_PROPOSAL_REQUIRES_EVIDENCE_REFERENCE")
        contract = mechanism_contract(relation)
        identity = digest(contract)
        with self._connect() as conn:
            previous = conn.execute("SELECT contract FROM mechanisms WHERE mechanism_id=?", (identity,)).fetchone()
            if previous is not None and previous[0] != _json(contract):
                raise ValueError("LEARNING_MECHANISM_HASH_COLLISION")
            conn.execute(
                "INSERT OR IGNORE INTO mechanisms VALUES (?,?,?,NULL)",
                (identity, _json(contract), "AWAITING_WARRANT"),
            )
            witness = {"origin": origin, "evidence": evidence}
            encoded, evidence_id = _json(witness), digest(witness)
            existing = conn.execute(
                "SELECT payload FROM mechanism_evidence WHERE mechanism_id=? AND evidence_sha256=?",
                (identity, evidence_id),
            ).fetchone()
            if existing is not None and existing[0] != encoded:
                raise ValueError("LEARNING_EVIDENCE_HASH_COLLISION")
            conn.execute("INSERT OR IGNORE INTO mechanism_evidence VALUES (?,?,?)", (identity, evidence_id, encoded))
            self._event(conn, "PROPOSAL_OBSERVED", identity, witness)
        return identity

    def review(self, identity, relation, family):
        """Queue an externally warranted family; this does not admit its law."""
        self.review_many(((identity, relation, family),))

    def review_many(self, records):
        """Validate the whole intake before installing any review atomically."""
        with self._connect() as conn:
            pending = {}
            for identity, relation, family in records:
                if identity != mechanism_id(relation) or not isinstance(family, dict):
                    raise ValueError("LEARNING_REVIEW_MECHANISM_CHANGED")
                encoded = _json(family)
                row = conn.execute(
                    "SELECT reviewed_family,disposition,contract FROM mechanisms WHERE mechanism_id=?", (identity,)
                ).fetchone()
                if row is None:
                    raise ValueError("LEARNING_REVIEW_REQUIRES_OBSERVED_CANDIDATE")
                if digest(json.loads(row[2])) != identity:
                    raise ValueError("LEARNING_MECHANISM_HASH_MISMATCH")
                previous = row[0] if row[0] is not None else pending.get(identity)
                if previous is not None:
                    if previous != encoded:
                        raise ValueError("LEARNING_REVIEW_CHANGED_REQUIRES_VERSIONED_REVISION")
                    continue
                if row[1] != "AWAITING_WARRANT":
                    raise ValueError("LEARNING_REVIEW_NOT_AWAITING_WARRANT")
                pending[identity] = encoded
            for identity, encoded in pending.items():
                conn.execute(
                    "UPDATE mechanisms SET reviewed_family=?,disposition=? WHERE mechanism_id=?",
                    (encoded, "READY_FOR_TEACHING", identity),
                )
                self._event(conn, "WARRANT_REVIEW_RECEIVED", identity, json.loads(encoded))

    def disposition(self, identity, state, reason):
        if state not in DISPOSITIONS:
            raise ValueError("INVALID_LEARNING_DISPOSITION")
        with self._connect() as conn:
            row = conn.execute("SELECT reviewed_family FROM mechanisms WHERE mechanism_id=?", (identity,)).fetchone()
            if row is None:
                raise ValueError("UNKNOWN_LEARNING_MECHANISM")
            if state == "READY_FOR_TEACHING" and row[0] is None:
                raise ValueError("LEARNING_WARRANT_REQUIRED")
            conn.execute("UPDATE mechanisms SET disposition=? WHERE mechanism_id=?", (state, identity))
            self._event(conn, "DISPOSITION", identity, {"state": state, "reason": reason})

    def ready(self):
        with self._connect() as conn:
            return [
                {"mechanism_id": identity, "family": json.loads(payload)}
                for identity, payload in conn.execute(
                    "SELECT mechanism_id,reviewed_family FROM mechanisms WHERE disposition='READY_FOR_TEACHING' ORDER BY mechanism_id"
                )
            ]

    def witnesses(self, identity):
        """Return original proposal evidence after checking its content address."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT evidence_sha256,payload FROM mechanism_evidence WHERE mechanism_id=? ORDER BY evidence_sha256",
                (identity,),
            ).fetchall()
        result = []
        for expected, encoded in rows:
            value = json.loads(encoded)
            if digest(value) != expected:
                raise ValueError("LEARNING_EVIDENCE_HASH_MISMATCH")
            result.append(value)
        return result

    def reviewed(self):
        with self._connect() as conn:
            return [
                {"mechanism_id": identity, "family": json.loads(payload), "disposition": state}
                for identity, payload, state in conn.execute(
                    "SELECT mechanism_id,reviewed_family,disposition FROM mechanisms "
                    "WHERE reviewed_family IS NOT NULL ORDER BY mechanism_id"
                )
            ]

    def pending(self):
        with self._connect() as conn:
            return [
                {"mechanism_id": identity, "disposition": state, "contract": json.loads(contract)}
                for identity, state, contract in conn.execute(
                    "SELECT mechanism_id,disposition,contract FROM mechanisms "
                    "WHERE disposition NOT IN ('ADMITTED','REJECTED','RETIRED','ALREADY_ENTAILED') ORDER BY mechanism_id"
                )
            ]

    def record_epoch(self, epoch, outcome):
        if type(epoch) is not int or epoch < 1 or not isinstance(outcome, dict) or outcome.get("epoch") != epoch:
            raise ValueError("INVALID_LEARNING_EPOCH")
        encoded, identity = _json(outcome), digest(outcome)
        with self._connect() as conn:
            previous = conn.execute(
                "SELECT outcome_sha256,outcome FROM learning_epochs WHERE epoch=?", (epoch,)
            ).fetchone()
            if previous is not None and previous != (identity, encoded):
                raise ValueError("LEARNING_EPOCH_CHANGED")
            conn.execute("INSERT OR IGNORE INTO learning_epochs VALUES (?,?,?)", (epoch, identity, encoded))
            self._event(conn, "EPOCH_COMPLETED", str(epoch), {"outcome_sha256": identity})

    def epochs(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT outcome_sha256,outcome FROM learning_epochs ORDER BY epoch").fetchall()
        result = []
        for identity, encoded in rows:
            outcome = json.loads(encoded)
            if digest(outcome) != identity:
                raise ValueError("LEARNING_EPOCH_HASH_MISMATCH")
            result.append(outcome)
        return result
