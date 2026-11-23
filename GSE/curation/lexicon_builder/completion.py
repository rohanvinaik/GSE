"""Bounded, journaled completion of an already validated dictionary snapshot."""

from __future__ import annotations

import csv
import hashlib
import heapq
import io
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from .catalog import SENTENCE_DURATION_SOURCE_RECORD
from .evidence import Definition, Observation
from .foundation import BANKS, definition_context, lexical_context, validate_lexical_guards
from .model_receipts import append_model_receipt, migrate_model_receipts
from .relevance import observation_relevance
from .residual import build_request, complete_bank
from .resolution import resolve_dictionary
from .scheduling import pending_banks, question_order_policy, spelling_cohort
from .storage import _json, store_entry
from .validation import _assertions, _domain_restrictions, _read_json, _relations, validate_build

JOURNAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS completion_attempts (
 entry_id TEXT NOT NULL, bank TEXT NOT NULL, request_id TEXT NOT NULL,
 model TEXT NOT NULL, code TEXT NOT NULL, details TEXT NOT NULL,
 PRIMARY KEY(entry_id,bank,request_id,model));
CREATE TABLE IF NOT EXISTS completion_schedule (
 scope_id TEXT PRIMARY KEY, protocol TEXT NOT NULL, banks TEXT NOT NULL,
 cursor TEXT NOT NULL, pass_number INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS completion_visits (
 scope_id TEXT NOT NULL, pass_number INTEGER NOT NULL, entry_id TEXT NOT NULL,
 PRIMARY KEY(scope_id,pass_number,entry_id));
"""
SCHEDULE_POLICY = "gse.completion-schedule/2"
QUESTION_ORDER_SCHEDULE_POLICY = "gse.completion-schedule/3"


class CompletionDatabaseBusy(ValueError):
    """An interrupted invocation whose committed journal remains authoritative."""

    def __init__(self, receipt):
        self.receipt = receipt
        super().__init__("COMPLETION_DATABASE_BUSY")


def _database_busy(error):
    """Recognize SQLite's typed lock codes, including wrapped validation errors."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        code = getattr(error, "sqlite_errorcode", None)
        if (
            isinstance(error, sqlite3.DatabaseError)
            and type(code) is int
            and (code & 255) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
        ):
            return True
        error = error.__cause__
    return False


def _selection(value, name, allowed=None):
    if value is None:
        return None
    if (
        not isinstance(value, tuple)
        or not value
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise ValueError(f"INVALID_{name}")
    if len(set(value)) != len(value) or allowed is not None and not set(value) <= set(allowed):
        raise ValueError(f"INVALID_{name}")
    return set(value)


def _metadata(conn, key, default=None):
    row = conn.execute("SELECT value FROM builder_metadata WHERE key=?", (key,)).fetchone()
    return _read_json(row[0]) if row else default


def _set_metadata(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO builder_metadata VALUES (?,?)", (key, _json(value)))


def _state_key(domains):
    return hashlib.sha256(_json(domains).encode()).hexdigest()


def _priority_source(priority, frequency_path):
    """Pin scheduling evidence; frequency never supplies a semantic coordinate.

    The local Brysbaert table preserves SUBTLEX counts. Descending positive
    counts have the same order as a monotonic Zipf transform, but do not supply
    calibrated absolute Zipf scores. Zero counts and absent words are unranked.
    The bytes parsed here are the bytes hashed, independent of later file edits.
    Blank words are excluded with their count, physical CSV line, and one-based
    data-record number (excluding the header); no missing spelling is invented.
    """
    if priority not in ("constraint", "zipf"):
        raise ValueError("INVALID_COMPLETION_PRIORITY")
    if priority == "constraint":
        if frequency_path is not None:
            raise ValueError("FREQUENCY_PATH_REQUIRES_ZIPF_PRIORITY")
        return {"mode": "constraint", "policy": "gse.completion-priority/constraint/1"}, None
    if frequency_path is not None and not isinstance(frequency_path, (str, Path)):
        raise ValueError("INVALID_COMPLETION_FREQUENCY_PATH")
    path = (
        Path(frequency_path).expanduser().resolve()
        if frequency_path is not None
        else Path(__file__).resolve().parents[3] / "data" / "external" / "concreteness.csv"
    )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError("COMPLETION_FREQUENCY_UNAVAILABLE") from exc
    frequencies, seen, excluded = {}, set(), []
    records = 0
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        fields = reader.fieldnames
        if not fields or len(set(fields)) != len(fields) or not {"Word", "SUBTLEX"} <= set(fields):
            raise ValueError("schema")
        for records, row in enumerate(reader, start=1):
            word, count = row["Word"], row["SUBTLEX"]
            if None in row or word is None or count is None or not count.isdecimal():
                raise ValueError("record")
            value = int(count)
            if not word.strip():
                excluded.append(
                    {"code": "MISSING_WORD", "record_number": records, "csv_line": reader.line_num, "count": value}
                )
                continue
            word = word.strip().casefold()
            if word in seen:
                raise ValueError("duplicate_word")
            seen.add(word)
            if value > 0:
                frequencies[word] = value
        if not frequencies:
            raise ValueError("no_ranked_words")
    except (UnicodeError, csv.Error, ValueError) as exc:
        raise ValueError("INVALID_COMPLETION_FREQUENCY_SOURCE") from exc
    return {
        "mode": "zipf",
        "policy": "gse.completion-priority/subtlex-count-order/2",
        "source": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "word_column": "Word",
        "frequency_column": "SUBTLEX",
        "ordering": "DESCENDING_POSITIVE_COUNT_THEN_CONSTRAINT_PRIORITY_THEN_DEFINITION_ID",
        "score": "MONOTONIC_ZIPF_ORDER_NOT_ABSOLUTE_ZIPF_SCORE",
        "unranked": "ZERO_OR_ABSENT_FREQUENCY_LAST_NOT_SEMANTIC_ZERO",
        "rows": records,
        "included_words": len(seen),
        "excluded_count": len(excluded),
        "excluded_records": excluded,
        "ranked_words": len(frequencies),
        "zero_count_words": len(seen) - len(frequencies),
        "semantic_authority": "NONE_SCHEDULING_ONLY",
    }, frequencies


def _select_entries(
    conn, entry_ids, banks, limit, visited=frozenset(), *, frequencies=None, cohort_policy="definition"
):
    """Rank unvisited definitions using a bounded heap, never a mutable frontier.

    A later definition can finish before an earlier one, and accepted values
    change a definition's priority key. A cursor cannot prove either one visited.
    """
    requested = set(entry_ids or ())
    if SENTENCE_DURATION_SOURCE_RECORD in requested:
        raise ValueError("SENTENCE_CONSTRUCTION_OUTSIDE_LEXICAL_SCOPE")
    found, candidates = set(), []

    def rows():
        for entry, code, payload, lemma in conn.execute(
            "SELECT d.entry_id,d.code,d.domains,l.lemma FROM definition_states d JOIN lexemes l ON d.lexeme_id=l.id"
        ):
            if entry == SENTENCE_DURATION_SOURCE_RECORD:
                continue
            if entry_ids is None and entry in visited:
                continue
            if entry_ids is not None and entry not in entry_ids:
                continue
            if entry_ids is not None:
                found.add(entry)
            domains = _read_json(payload)
            remaining = [len(domains[bank]) for bank in banks if len(domains[bank]) > 1]
            if entry_ids is None:
                if code != "PARTIAL" or not remaining:
                    continue
            known = sum(len(domain) == 1 for domain in domains.values())
            residual_size = min(remaining, default=4)
            first = residual_size if frequencies is None else (-frequencies.get(lemma.casefold(), 0), residual_size)
            key = (first, -known, entry)
            yield key, lemma.casefold()

    if entry_ids is None:
        if cohort_policy == "spelling":
            return spelling_cohort(rows(), limit)
        candidates = heapq.nsmallest(limit + 1, (key for key, _ in rows()))
        return tuple(candidates[:limit]), len(candidates) > limit
    else:
        candidates = sorted(key for key, _ in rows())
        if requested - found:
            raise ValueError("UNKNOWN_COMPLETION_DEFINITION")
    return tuple(candidates), False


def _schedule(conn, model, banks, priority_identity=None, order_policy=None):
    # Old cursor-filtered scopes are deliberately not reinterpreted. The new scope
    # starts a fresh scheduling pass, retaining all exact model-request journals.
    policy = QUESTION_ORDER_SCHEDULE_POLICY if order_policy is not None else SCHEDULE_POLICY
    scope = [model, banks, {"schedule_policy": policy}]
    if priority_identity is not None:
        scope.append(priority_identity)
    if order_policy is not None:
        scope.append(order_policy)
    scope_id = hashlib.sha256(_json(scope).encode()).hexdigest()
    result = {
        "scope_id": scope_id,
        "protocol": model,
        "banks": banks,
        "cursor": None,
        "pass_number": 1,
        "visited": frozenset(),
    }
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='completion_schedule'").fetchone():
        return result
    row = conn.execute(
        "SELECT protocol,banks,cursor,pass_number FROM completion_schedule WHERE scope_id=?", (scope_id,)
    ).fetchone()
    if row is None:
        return result
    cursor = _read_json(row[2])
    zipf = priority_identity is not None
    first_valid = (
        isinstance(cursor, list)
        and len(cursor) == 3
        and (
            isinstance(cursor[0], list)
            and len(cursor[0]) == 2
            and type(cursor[0][0]) is int
            and cursor[0][0] <= 0
            and type(cursor[0][1]) is int
            and cursor[0][1] in (2, 3)
            if zipf
            else type(cursor[0]) is int and cursor[0] in (2, 3)
        )
    )
    if (
        row[0] != model
        or _read_json(row[1]) != list(banks)
        or type(row[3]) is not int
        or row[3] < 1
        or not first_valid
        or type(cursor[1]) is not int
        or not -len(BANKS) <= cursor[1] <= 0
        or not isinstance(cursor[2], str)
        or not cursor[2]
    ):
        raise ValueError("INVALID_COMPLETION_SCHEDULE")
    restored = (tuple(cursor[0]), cursor[1], cursor[2]) if zipf else tuple(cursor)
    result.update(cursor=restored, pass_number=row[3])
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='completion_visits'").fetchone():
        result["visited"] = frozenset(
            row[0]
            for row in conn.execute(
                "SELECT entry_id FROM completion_visits WHERE scope_id=? AND pass_number=?",
                (scope_id, result["pass_number"]),
            )
        )
    return result


def _advance_schedule(conn, schedule, cursor, revision):
    if conn.execute("PRAGMA data_version").fetchone()[0] != revision:
        raise ValueError("COMPLETION_SNAPSHOT_CHANGED")
    with conn:
        conn.execute(
            "DELETE FROM completion_visits WHERE scope_id=? AND pass_number<>?",
            (schedule["scope_id"], schedule["pass_number"]),
        )
        conn.execute(
            "INSERT OR IGNORE INTO completion_visits VALUES (?,?,?)",
            (schedule["scope_id"], schedule["pass_number"], cursor[2]),
        )
        conn.execute(
            "INSERT OR REPLACE INTO completion_schedule VALUES (?,?,?,?,?)",
            (
                schedule["scope_id"],
                schedule["protocol"],
                _json(schedule["banks"]),
                _json(cursor),
                schedule["pass_number"],
            ),
        )
    schedule["cursor"] = cursor


def _prepare_context_index(conn):
    """Build invocation-local links from the already replay-validated snapshot.

    Exact links already have a persistent source index. Candidate links live in
    native JSON and are expanded once into file-backed temporary storage. No
    index or validation result is trusted across connections or process restarts.
    """
    conn.execute("PRAGMA temp_store=FILE")
    conn.execute(
        "CREATE TEMP TABLE completion_context_targets (entry_id TEXT NOT NULL,record_id TEXT NOT NULL,PRIMARY KEY(entry_id,record_id)) WITHOUT ROWID"
    )
    conn.execute(
        "CREATE TEMP TABLE completion_session_attempts (entry_id TEXT NOT NULL,bank TEXT NOT NULL,request_id TEXT NOT NULL,PRIMARY KEY(entry_id,bank,request_id)) WITHOUT ROWID"
    )
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO completion_context_targets
               SELECT candidate.value, observation.record_id
               FROM source_observations observation,
                    json_each(observation.payload, '$.candidate_entry_ids') candidate
               WHERE observation.entry_id IS NULL"""
        )


def _contexts(conn, selected, *, indexed=False):
    """Retain only selected payloads, with identical ordering on both paths."""
    observations, relevance = defaultdict(list), defaultdict(set)
    wanted = set(selected)
    if not wanted:
        return observations, relevance
    if indexed:
        parameters = ",".join("?" for _ in selected)
        rows = conn.execute(
            f"""SELECT observation.payload FROM source_observations observation
                JOIN (
                    SELECT record_id FROM source_observations WHERE entry_id IN ({parameters})
                    UNION
                    SELECT record_id FROM completion_context_targets WHERE entry_id IN ({parameters})
                ) target ON target.record_id=observation.record_id
                ORDER BY observation.record_id""",
            (*selected, *selected),
        )
    else:
        rows = conn.execute("SELECT payload FROM source_observations ORDER BY record_id")
    for (payload,) in rows:
        raw = _read_json(payload)
        targets = (raw["entry_id"],) if raw["entry_id"] is not None else raw["candidate_entry_ids"]
        matched = wanted.intersection(targets)
        if not matched:
            continue
        observation = Observation(
            raw["entry_id"],
            raw["source"],
            raw["record_id"],
            raw["family"],
            raw["features"],
            raw["scope"],
            tuple(raw["candidate_entry_ids"]),
        )
        relevant = observation_relevance(observation)
        for entry in sorted(matched):
            observations[entry].append(raw)
            relevance[entry].update(relevant)
    return observations, relevance


def _entry(conn, entry_id):
    row = conn.execute(
        "SELECT l.lemma,l.pos,l.gloss,d.hierarchy FROM definition_states d JOIN lexemes l ON d.lexeme_id=l.id WHERE d.entry_id=?",
        (entry_id,),
    ).fetchone()
    if row is None:
        raise ValueError("COMPLETION_DEFINITION_DISAPPEARED")
    definition = Definition(entry_id, row[0], row[1], row[2])
    assertions = _assertions(
        conn.execute("SELECT ordinal,payload FROM builder_assertions WHERE entry_id=?", (entry_id,)).fetchall()
    )
    restrictions = _domain_restrictions(
        conn.execute("SELECT ordinal,payload FROM builder_domain_restrictions WHERE entry_id=?", (entry_id,)).fetchall()
    )
    return definition, assertions, restrictions, _read_json(row[3])


def _journal(conn, request, model, code, details):
    conn.execute(
        "INSERT OR REPLACE INTO completion_attempts VALUES (?,?,?,?,?,?)",
        (request.entry_id, request.bank, request.request_id, model, code, _json(details)),
    )


def _account(conn, before=None, after=None, calls=0):
    report = _metadata(conn, "last_report", {})
    if not isinstance(report, dict):
        raise ValueError("INVALID_COMPLETION_BUILD_REPORT")
    report["model_calls"] = report.get("model_calls", 0) + calls
    outcomes = Counter(report.get("model_outcomes", {}))
    if before:
        outcomes[before] -= 1
        if outcomes[before] <= 0:
            del outcomes[before]
    if after:
        outcomes[after] += 1
    report["model_outcomes"] = dict(outcomes)
    _set_metadata(conn, "last_report", report)


def _refresh_coverage(conn):
    """Recompute actual dictionary coverage; retain native source/build metadata."""
    outcomes, cells, per_pos = Counter(), Counter(), defaultdict(Counter)
    count = 0
    for code, payload, pos in conn.execute(
        "SELECT d.code,d.domains,l.pos FROM definition_states d JOIN lexemes l ON d.lexeme_id=l.id"
    ):
        count += 1
        domains = _read_json(payload)
        outcomes[code] += 1
        per_pos[definition_context(pos)["pos"]][code] += 1
        cells["assigned"] += sum(len(values) == 1 for values in domains.values()) if code != "CONFLICT" else 0
        cells["explicit_zero"] += sum(values == [0] for values in domains.values()) if code != "CONFLICT" else 0
        cells["unresolved"] += sum(len(values) > 1 for values in domains.values())
        cells["conflicted"] += sum(not values for values in domains.values())
    report = _metadata(conn, "last_report", {})
    report.update(
        definitions=count,
        outcomes=dict(outcomes),
        cells=dict(cells),
        per_pos={pos: dict(values) for pos, values in sorted(per_pos.items())},
    )
    # Original per-definition weights were not persisted, so old weighted
    # outcomes cannot be represented as current after assignments change.
    if report.get("weighted_outcomes") is not None:
        report["weighted_outcomes"] = None
        report["weighted_outcomes_status"] = "NOT_RECOMPUTED_WEIGHTS_NOT_PERSISTED"
    _set_metadata(conn, "last_report", report)
    return report


def _scope_remaining(conn, selected, banks):
    entries = cells = conflicts = 0
    for entry in selected:
        row = conn.execute("SELECT code,domains FROM definition_states WHERE entry_id=?", (entry,)).fetchone()
        domains = _read_json(row[1])
        remaining = sum(len(domains[bank]) != 1 for bank in banks)
        entries += bool(remaining or row[0] == "CONFLICT")
        cells += remaining
        conflicts += row[0] == "CONFLICT"
    return {"entries": entries, "cells": cells, "conflicted_entries": conflicts}


def _has_remaining(conn, banks):
    for code, payload in conn.execute(
        "SELECT code,domains FROM definition_states WHERE entry_id!=?", (SENTENCE_DURATION_SOURCE_RECORD,)
    ):
        domains = _read_json(payload)
        if code == "CONFLICT" or any(len(domains[bank]) != 1 for bank in banks):
            return True
    return False


class _JournaledTransport:
    def __init__(self, conn, transport, model, request, state_key, revision, session):
        self.conn, self.transport, self.model, self.request = conn, transport, model, request
        self.identity = model
        self.state_key, self.revision, self.session = state_key, revision, session
        self.called = False
        self.raw = None

    def __call__(self, payload, schema):
        if self.conn.execute("PRAGMA data_version").fetchone()[0] != self.revision:
            raise ValueError("COMPLETION_SNAPSHOT_CHANGED")
        with self.conn:
            _journal(
                self.conn, self.request, self.model, "RUNNING", {"state_key": self.state_key, "transport_started": True}
            )
            _account(self.conn, after="RUNNING", calls=1)
        self.called = True
        self.session["calls"] += 1
        self.session["transport_invocations"] += 1
        self.raw = self.transport(payload, schema)
        return self.raw


def complete_dictionary(
    path,
    transport,
    max_model_calls,
    *,
    entry_ids=None,
    banks=None,
    max_calls_per_entry=3,
    max_entries_per_pass=64,
    continue_cohorts=False,
    retry=False,
    progress=None,
    batch_size=1,
    priority="constraint",
    frequency_path=None,
    cohort_policy="definition",
    bank_priority="constraint",
):
    """Complete only explicitly budgeted residual cells, with durable resumption.

    The existing artifact is replay-validated before any write or model call.
    Every accepted ruling and its proof receipt commit atomically. A RUNNING
    journal record survives interruption and is skipped on resume unless retry
    was explicitly selected. No native/anchor coordinate is overwritten. Each
    invocation retains source contexts for at most max_entries_per_pass entries,
    independently of its call budget. Automatic cohorts resume through the
    durable fair cursor; oversized explicit scopes are refused, never truncated.
    Optional sustained mode retains this connection and replay across bounded
    cohorts. A full pass without new attempts stops; an explicit retry applies
    at most once per unchanged request identity in this invocation.
    Zipf priority uses pinned local SUBTLEX counts only for scheduling, never
    for model answers or bank inference. Its cursor scope is source-specific.
    Optional spelling cohorts take one definition per casefolded spelling per
    round. Optional evidence bank ordering uses typed hints and active rule
    connectivity only to choose questions. Both policies have separate durable
    visit scopes; earlier exact request journals remain authoritative.
    """
    if type(max_model_calls) is not int or max_model_calls <= 0:
        raise ValueError("INVALID_MODEL_BUDGET")
    if type(max_calls_per_entry) is not int or max_calls_per_entry <= 0:
        raise ValueError("INVALID_PER_ENTRY_MODEL_BUDGET")
    if type(max_entries_per_pass) is not int or max_entries_per_pass <= 0:
        raise ValueError("INVALID_COMPLETION_ENTRY_LIMIT")
    if type(batch_size) is not int or not 1 <= batch_size <= 64:
        raise ValueError("INVALID_COMPLETION_BATCH_SIZE")
    if batch_size > 1 and not callable(getattr(transport, "callable_batch", None)):
        raise ValueError("BATCH_TRANSPORT_REQUIRED")
    if (
        type(retry) is not bool
        or type(continue_cohorts) is not bool
        or not callable(transport)
        or (progress is not None and not callable(progress))
    ):
        raise ValueError("INVALID_COMPLETION_OPTIONS")
    order_info = question_order_policy(cohort_policy, bank_priority)
    order_identity = order_info if (cohort_policy, bank_priority) != ("definition", "constraint") else None
    schedule_policy = QUESTION_ORDER_SCHEDULE_POLICY if order_identity is not None else SCHEDULE_POLICY
    priority_info, frequencies = _priority_source(priority, frequency_path)
    priority_identity = (
        {"policy": priority_info["policy"], "sha256": priority_info["sha256"]}
        if priority_info["mode"] == "zipf"
        else None
    )
    requested = _selection(entry_ids, "COMPLETION_DEFINITIONS")
    if requested is not None and len(requested) > max_entries_per_pass:
        raise ValueError("EXPLICIT_SCOPE_EXCEEDS_ENTRY_LIMIT")
    cohort_limit = min(max_model_calls, max_entries_per_pass)
    chosen_banks = tuple(sorted(_selection(banks, "COMPLETION_BANKS", BANKS) or BANKS))
    model = getattr(transport, "identity", getattr(transport, "model", "typed-residual"))
    if not isinstance(model, str) or not model.strip():
        raise ValueError("INVALID_COMPLETION_MODEL")
    file = Path(path).expanduser().resolve()
    if not file.is_file():
        raise ValueError("BUILD_NOT_FOUND")
    conn = sqlite3.connect(file.as_uri() + "?mode=rw", uri=True)
    session = {"calls": 0, "transport_invocations": 0}
    outcomes, skipped = Counter(), Counter()
    selected = ()
    started = False
    phase = "PREFLIGHT"

    def report_progress(**details):
        if progress is not None:
            progress(
                {
                    "format": "gse.lexicon-completion-progress/1",
                    "phase": phase,
                    "model_calls": session["calls"],
                    "transport_invocations": session["transport_invocations"],
                    "max_model_calls": max_model_calls,
                    "committed_outcomes": dict(outcomes),
                    "dictionary_status": "NOT_RECOUNTED",
                    **details,
                }
            )

    def busy_receipt(failed_phase):
        return {
            "format": "gse.lexicon-completion-failure/1",
            "code": "COMPLETION_DATABASE_BUSY",
            "phase": failed_phase,
            "model": model,
            "model_calls": session["calls"],
            "transport_invocations": session["transport_invocations"],
            "max_model_calls": max_model_calls,
            "committed_outcomes": dict(outcomes),
            "skipped_attempts": dict(skipped),
            "selected_entry_ids": list(selected),
            "selected_scope": "CURRENT_COHORT",
            "banks": list(chosen_banks),
            "continue_cohorts": continue_cohorts,
            "priority": priority_info,
            "question_order": order_info,
            "coverage": "NOT_REFRESHED_AFTER_FAILURE",
            "pending_attempts": "COMMITTED_RUNNING_JOURNAL_IS_AUTHORITATIVE",
            "retry_policy": "EXPLICIT_RETRY_REQUIRED_FOR_UNCHANGED_REQUEST",
        }

    try:
        report_progress()
        revision = conn.execute("PRAGMA data_version").fetchone()[0]
        validation = validate_build(file)
        if validation["code"] != "REPLAY_VALIDATED":
            raise ValueError("COMPLETION_REQUIRES_VALIDATED_BUILD")
        if conn.execute("PRAGMA data_version").fetchone()[0] != revision:
            raise ValueError("BUILD_CHANGED_DURING_PREFLIGHT")
        relations = _relations(_metadata(conn, "relations"))
        validate_lexical_guards(relations)
        schedule = (
            _schedule(conn, model, chosen_banks, priority_identity, order_identity) if requested is None else None
        )
        cursor_before = schedule["cursor"] if schedule else None
        cohort, more_in_pass = _select_entries(
            conn,
            requested,
            chosen_banks,
            cohort_limit,
            schedule["visited"] if schedule else frozenset(),
            frequencies=frequencies,
            cohort_policy=cohort_policy,
        )
        wrapped_pass = False
        if schedule and not cohort and cursor_before is not None:
            schedule["pass_number"] += 1
            schedule["cursor"] = None
            schedule["visited"] = frozenset()
            wrapped_pass = True
            cohort, more_in_pass = _select_entries(
                conn, requested, chosen_banks, cohort_limit, frequencies=frequencies, cohort_policy=cohort_policy
            )
        selected = tuple(key[2] for key in cohort)
        phase = "CONTEXT_PREPARATION"
        report_progress()
        if continue_cohorts:
            _prepare_context_index(conn)
            observations, relevance = _contexts(conn, selected, indexed=True)
        else:
            observations, relevance = _contexts(conn, selected)
        if conn.execute("PRAGMA data_version").fetchone()[0] != revision:
            raise ValueError("COMPLETION_SNAPSHOT_CHANGED")
        # Add the optional empty restriction table for valid older snapshots.
        # Keep this connection: data_version then detects any external writer.
        phase = "JOURNAL_SETUP"
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='builder_domain_restrictions'").fetchone():
            from .storage import DOMAIN_RESTRICTIONS_VERSION

            with conn:
                conn.execute(
                    "CREATE TABLE builder_domain_restrictions (entry_id TEXT NOT NULL,ordinal INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(entry_id,ordinal))"
                )
                _set_metadata(conn, "domain_restrictions_format", DOMAIN_RESTRICTIONS_VERSION)
        conn.executescript(JOURNAL_SCHEMA)
        with conn:
            migrate_model_receipts(conn)
        started = True
        visited = []
        visited_set = set()
        selected_in_session = dict.fromkeys(selected)
        cohort_count = 0
        pass_start_calls = session["calls"]
        full_pass = cursor_before is None or wrapped_pass
        stop_reason = "SINGLE_COHORT"
        while True:
            if not cohort:
                stop_reason = "NO_ELIGIBLE_ENTRIES"
                break
            cohort_count += 1
            if batch_size > 1:
                from .batching import run_batched_cohort

                phase = "BATCH_DISPATCH_AND_ACCEPTANCE"
                finished = run_batched_cohort(
                    conn,
                    transport,
                    model,
                    cohort,
                    observations,
                    relevance,
                    relations,
                    revision,
                    session,
                    outcomes,
                    skipped,
                    max_model_calls=max_model_calls,
                    max_calls_per_entry=max_calls_per_entry,
                    chosen_banks=chosen_banks,
                    batch_size=batch_size,
                    retry=retry,
                    continue_cohorts=continue_cohorts,
                    report_progress=report_progress,
                    bank_priority=bank_priority,
                )
                for priority in finished:
                    if schedule:
                        _advance_schedule(conn, schedule, priority, revision)
                    if priority[2] not in visited_set:
                        visited.append(priority[2])
                        visited_set.add(priority[2])
            else:
                for priority in cohort:
                    entry = priority[2]
                    if session["calls"] >= max_model_calls:
                        break
                    definition, assertions, restrictions, hierarchy = _entry(conn, entry)
                    context = lexical_context(definition, observations[entry], relations)
                    evidence_banks = tuple(sorted(relevance[entry]))
                    resolution = resolve_dictionary(
                        BANKS,
                        assertions,
                        relations,
                        context,
                        evidence_banks=evidence_banks,
                        domain_restrictions=restrictions,
                    )
                    attempted_banks = set()
                    entry_calls = 0
                    while (
                        resolution.code == "PARTIAL"
                        and session["calls"] < max_model_calls
                        and entry_calls < max_calls_per_entry
                    ):
                        remaining = pending_banks(
                            resolution,
                            chosen_banks,
                            attempted_banks,
                            policy=bank_priority,
                            observations=observations[entry],
                            relations=relations,
                            context=context,
                        )
                        if not remaining:
                            break
                        bank = remaining[0]
                        attempted_banks.add(bank)
                        request = build_request(
                            entry,
                            bank,
                            resolution,
                            tuple(observations[entry]),
                            definition=definition,
                            relations=relations,
                            context=context,
                        )
                        previous = conn.execute(
                            "SELECT code FROM completion_attempts WHERE entry_id=? AND bank=? AND request_id=? AND model=?",
                            (entry, bank, request.request_id, model),
                        ).fetchone()
                        attempted_in_session = (
                            continue_cohorts
                            and conn.execute(
                                "SELECT 1 FROM completion_session_attempts WHERE entry_id=? AND bank=? AND request_id=?",
                                (entry, bank, request.request_id),
                            ).fetchone()
                        )
                        if previous and (not retry or attempted_in_session):
                            skipped[previous[0]] += 1
                            continue
                        state_key = _state_key({bank: sorted(values) for bank, values in resolution.domains.items()})
                        wrapped = _JournaledTransport(conn, transport, model, request, state_key, revision, session)
                        phase = "REQUEST_AND_RUNNING_JOURNAL"
                        result = complete_bank(
                            request,
                            BANKS,
                            assertions,
                            relations,
                            wrapped,
                            context,
                            evidence_banks=evidence_banks,
                            domain_restrictions=restrictions,
                        )
                        entry_calls += wrapped.called
                        details = {**result.details, "state_key": state_key, "transport_started": wrapped.called}
                        if isinstance(wrapped.raw, str):
                            details["raw_output"] = wrapped.raw if len(wrapped.raw) <= 4096 else None
                            details["raw_output_sha256"] = hashlib.sha256(wrapped.raw.encode()).hexdigest()
                        phase = "ACCEPTANCE_COMMIT"
                        conn.execute("BEGIN IMMEDIATE")
                        try:
                            changed = conn.execute("PRAGMA data_version").fetchone()[0] != revision
                            code = "STALE_SNAPSHOT" if changed else result.code
                            if not changed and code == "ASSIGNED":
                                if result.assertion is None or result.resolution is None:
                                    raise ValueError("INVALID_COMPLETION_RECEIPT")
                                assertions += (result.assertion,)
                                resolution = result.resolution
                                store_entry(
                                    conn,
                                    definition,
                                    resolution,
                                    assertions,
                                    hierarchy,
                                    domain_restrictions=restrictions,
                                )
                                append_model_receipt(
                                    conn,
                                    {
                                        "entry_id": entry,
                                        "assertion": asdict(result.assertion),
                                        "request_id": request.request_id,
                                        "code": code,
                                        "request": request.payload(),
                                        "schema": request.output_schema(),
                                    },
                                )
                            _journal(conn, request, model, code, details)
                            if wrapped.called:
                                if continue_cohorts:
                                    conn.execute(
                                        "INSERT OR IGNORE INTO completion_session_attempts VALUES (?,?,?)",
                                        (entry, bank, request.request_id),
                                    )
                                _account(conn, before="RUNNING", after=code)
                            conn.commit()
                        except BaseException:
                            conn.rollback()
                            raise
                        outcomes[code] += 1
                        report_progress(entry_id=entry, bank=bank, code=code)
                        if changed:
                            raise ValueError("COMPLETION_SNAPSHOT_CHANGED")
                    finished = (
                        resolution.code != "PARTIAL"
                        or entry_calls >= max_calls_per_entry
                        or not any(
                            len(resolution.domains[bank]) > 1 and bank not in attempted_banks for bank in chosen_banks
                        )
                    )
                    if finished:
                        if schedule:
                            phase = "SCHEDULE_COMMIT"
                            _advance_schedule(conn, schedule, priority, revision)
                        if entry not in visited_set:
                            visited.append(entry)
                            visited_set.add(entry)
            if not continue_cohorts or schedule is None:
                break
            if session["calls"] >= max_model_calls:
                stop_reason = "MODEL_BUDGET_EXHAUSTED"
                break
            schedule.update(_schedule(conn, model, chosen_banks, priority_identity, order_identity))
            cohort, more_in_pass = _select_entries(
                conn,
                requested,
                chosen_banks,
                min(cohort_limit, max_model_calls - session["calls"]),
                schedule["visited"],
                frequencies=frequencies,
                cohort_policy=cohort_policy,
            )
            if not cohort:
                if full_pass and session["calls"] == pass_start_calls:
                    stop_reason = "NO_NEW_ATTEMPTS_IN_PASS"
                    break
                schedule["pass_number"] += 1
                schedule["cursor"] = None
                schedule["visited"] = frozenset()
                wrapped_pass = True
                full_pass = True
                pass_start_calls = session["calls"]
                cohort, more_in_pass = _select_entries(
                    conn,
                    requested,
                    chosen_banks,
                    min(cohort_limit, max_model_calls - session["calls"]),
                    frequencies=frequencies,
                    cohort_policy=cohort_policy,
                )
                if not cohort:
                    stop_reason = "NO_ELIGIBLE_ENTRIES"
                    break
            selected = tuple(key[2] for key in cohort)
            selected_in_session.update(dict.fromkeys(selected))
            observations.clear()
            relevance.clear()
            phase = "CONTEXT_PREPARATION"
            observations, relevance = _contexts(conn, selected, indexed=True)
            if conn.execute("PRAGMA data_version").fetchone()[0] != revision:
                raise ValueError("COMPLETION_SNAPSHOT_CHANGED")
        selected = tuple(selected_in_session)
        remaining = _scope_remaining(conn, selected, chosen_banks)
        unselected_residual = not selected and requested is None and _has_remaining(conn, chosen_banks)
        code = (
            "RESIDUAL_REMAINS"
            if unselected_residual
            else "SELECTED_SCOPE_RESOLVED"
            if not remaining["entries"]
            else "BUDGET_EXHAUSTED"
            if session["calls"] >= max_model_calls
            else "RESIDUAL_REMAINS"
        )
        result = {
            "format": "gse.lexicon-completion-report/1",
            "code": code,
            "model": model,
            "model_calls": session["calls"],
            "transport_invocations": session["transport_invocations"],
            "max_model_calls": max_model_calls,
            "max_calls_per_entry": max_calls_per_entry,
            "max_entries_per_pass": max_entries_per_pass,
            "batch_size": batch_size,
            "continue_cohorts": continue_cohorts,
            "priority": priority_info,
            "question_order": order_info,
            "selected_entry_ids": list(selected),
            "banks": list(chosen_banks),
            "outcomes": dict(outcomes),
            "skipped_attempts": dict(skipped),
            "remaining_selected_scope": remaining,
            "unselected_residual": unselected_residual,
            "scheduling": {
                "policy": schedule_policy,
                "resume_frontier": "COMPLETED_OR_PER_ENTRY_LIMIT_VISITS",
                "code": "EXPLICIT_SCOPE"
                if schedule is None
                else stop_reason
                if continue_cohorts
                else "NO_ELIGIBLE_ENTRIES"
                if not selected
                else "COHORT_PARTIAL"
                if len(visited) < len(selected)
                else "COHORT_EXHAUSTED"
                if more_in_pass
                else "PASS_EXHAUSTED",
                "visited_entry_ids": visited,
                "cohorts_processed": cohort_count,
                "pass_number": schedule["pass_number"] if schedule else None,
                "wrapped": wrapped_pass,
                "cursor_before": list(cursor_before) if cursor_before is not None else None,
                "cursor_after": list(schedule["cursor"]) if schedule and schedule["cursor"] is not None else None,
            },
            "preflight": "REPLAY_VALIDATED",
            "semantic_gold": "NOT_CHECKED",
        }
        phase = "COVERAGE_COMMIT"
        with conn:
            coverage = _refresh_coverage(conn)
            result["dictionary_outcomes"] = coverage["outcomes"]
            result["dictionary_cells"] = coverage["cells"]
            result["dictionary_status"] = (
                "INCOMPLETE"
                if coverage["cells"].get("unresolved", 0)
                or coverage["cells"].get("conflicted", 0)
                or coverage["outcomes"].get("CONFLICT", 0)
                else "ALL_BANKS_ASSIGNED"
            )
            # Selected scope may be just one coordinate of one definition.
            # Report the rest of the dictionary even when that scope is done.
            result["outside_selected_scope"] = {
                "unresolved_or_conflicted_cells": max(
                    0,
                    coverage["cells"].get("unresolved", 0)
                    + coverage["cells"].get("conflicted", 0)
                    - remaining["cells"],
                )
            }
            _set_metadata(conn, "last_completion_report", result)
        return result
    except BaseException as error:
        conn.rollback()
        if _database_busy(error):
            # A read transaction can block COMMIT. Preserve the last committed
            # RUNNING/accepted records, and never mask this with another write.
            raise CompletionDatabaseBusy(busy_receipt(phase)) from error
        if started:
            try:
                with conn:
                    _refresh_coverage(conn)
            except sqlite3.DatabaseError as cleanup_error:
                if _database_busy(cleanup_error):
                    receipt = busy_receipt("COVERAGE_RECOVERY")
                    receipt["original_error_type"] = type(error).__name__
                    raise CompletionDatabaseBusy(receipt) from cleanup_error
                raise
        raise
    finally:
        conn.close()
