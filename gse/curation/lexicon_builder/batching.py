"""Dispatch independent definition–bank questions; retain per-cell authority."""

import hashlib
from collections import Counter
from dataclasses import asdict

from .foundation import BANKS, lexical_context, validate_lexical_guards
from .model_receipts import append_model_receipt
from .residual import build_request, complete_bank
from .resolution import resolve_dictionary
from .scheduling import pending_banks
from .storage import store_entry


class _ReturnedItem:
    def __init__(self, model, raw=None, error=None):
        self.identity, self.raw, self.error = model, raw, error

    def __call__(self, payload, schema):
        if self.error is not None:
            raise self.error
        return self.raw


def run_batched_cohort(
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
    *,
    max_model_calls,
    max_calls_per_entry,
    chosen_banks,
    batch_size,
    retry,
    continue_cohorts,
    report_progress,
    bank_priority="constraint",
):
    """At most one pending bank per definition; re-close before its next item.

    Budget units are questions, not HTTP invocations. Every item is journaled
    RUNNING before sending the batch. Each accepted item uses complete_bank's
    original freshness/constraint checks and an atomic assignment+receipt commit.
    An interrupted batch leaves its uncommitted items RUNNING, never zero-filled.
    """
    from .completion import _account, _entry, _journal, _state_key

    validate_lexical_guards(relations)
    attempted = {key[2]: set() for key in cohort}
    calls = Counter()
    finished = set()
    priorities = {key[2]: key for key in cohort}

    def next_item(entry):
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
        if resolution.code != "PARTIAL" or calls[entry] >= max_calls_per_entry:
            return None
        remaining = pending_banks(
            resolution,
            chosen_banks,
            attempted[entry],
            policy=bank_priority,
            observations=observations[entry],
            relations=relations,
            context=context,
        )
        for bank in remaining:
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
            in_session = (
                continue_cohorts
                and conn.execute(
                    "SELECT 1 FROM completion_session_attempts WHERE entry_id=? AND bank=? AND request_id=?",
                    (entry, bank, request.request_id),
                ).fetchone()
            )
            if previous and (not retry or in_session):
                attempted[entry].add(bank)
                skipped[previous[0]] += 1
                continue
            return {
                "request": request,
                "definition": definition,
                "assertions": assertions,
                "restrictions": restrictions,
                "hierarchy": hierarchy,
                "context": context,
                "evidence_banks": evidence_banks,
                "state_key": _state_key({name: sorted(values) for name, values in resolution.domains.items()}),
            }
        return None

    def commit(item, raw, error):
        request = item["request"]
        wrapped = _ReturnedItem(model, raw, error)
        result = complete_bank(
            request,
            BANKS,
            item["assertions"],
            relations,
            wrapped,
            item["context"],
            evidence_banks=item["evidence_banks"],
            domain_restrictions=item["restrictions"],
        )
        details = {
            **result.details,
            "state_key": item["state_key"],
            "transport_started": item["transport_started"],
            "batch_id": item["batch_id"],
        }
        if isinstance(raw, str):
            details["raw_output"] = raw if len(raw) <= 4096 else None
            details["raw_output_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
        conn.execute("BEGIN IMMEDIATE")
        try:
            changed = conn.execute("PRAGMA data_version").fetchone()[0] != revision
            code = "STALE_SNAPSHOT" if changed else result.code
            if code == "ASSIGNED":
                if result.assertion is None or result.resolution is None:
                    raise ValueError("INVALID_COMPLETION_RECEIPT")
                store_entry(
                    conn,
                    item["definition"],
                    result.resolution,
                    item["assertions"] + (result.assertion,),
                    item["hierarchy"],
                    domain_restrictions=item["restrictions"],
                )
                append_model_receipt(
                    conn,
                    {
                        "entry_id": request.entry_id,
                        "assertion": asdict(result.assertion),
                        "request_id": request.request_id,
                        "code": code,
                        "request": request.payload(),
                        "schema": request.output_schema(),
                    },
                )
            _journal(conn, request, model, code, details)
            if continue_cohorts:
                conn.execute(
                    "INSERT OR IGNORE INTO completion_session_attempts VALUES (?,?,?)",
                    (request.entry_id, request.bank, request.request_id),
                )
            _account(conn, before="RUNNING", after=code)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        outcomes[code] += 1
        report_progress(entry_id=request.entry_id, bank=request.bank, code=code)
        if changed:
            raise ValueError("COMPLETION_SNAPSHOT_CHANGED")

    while session["calls"] < max_model_calls:
        pending = []
        capacity = min(batch_size, max_model_calls - session["calls"])
        for entry in priorities:
            if entry in finished:
                continue
            item = next_item(entry)
            if item is None:
                finished.add(entry)
                continue
            pending.append(item)
            if len(pending) == capacity:
                break
        if not pending:
            break
        # Shrink only the group, never any item's evidence. Deferred entries
        # remain eligible for the next round. A single oversized item is refused.
        preparation_error = None
        while True:
            items = tuple((item["request"].payload(), item["request"].output_schema()) for item in pending)
            try:
                prepare = getattr(transport, "prepare", None)
                if prepare is not None:
                    prepare(items)
                break
            except Exception as exc:
                if getattr(exc, "code", None) in {"BATCH_INPUT_TOO_LARGE", "BATCH_OUTPUT_BUDGET_EXCEEDED"}:
                    if len(pending) > 1:
                        pending.pop()
                        continue
                    preparation_error = exc
                    break
                raise
        if conn.execute("PRAGMA data_version").fetchone()[0] != revision:
            raise ValueError("COMPLETION_SNAPSHOT_CHANGED")
        batch_id = hashlib.sha256("\n".join(item["request"].request_id for item in pending).encode()).hexdigest()
        with conn:
            for item in pending:
                item["batch_id"] = batch_id
                item["transport_started"] = preparation_error is None
                request = item["request"]
                _journal(
                    conn,
                    request,
                    model,
                    "RUNNING",
                    {
                        "state_key": item["state_key"],
                        "transport_started": item["transport_started"],
                        "batch_id": batch_id,
                    },
                )
                _account(conn, after="RUNNING", calls=1)
        session["calls"] += len(pending)
        session["transport_invocations"] += preparation_error is None
        for item in pending:
            request = item["request"]
            attempted[request.entry_id].add(request.bank)
            calls[request.entry_id] += 1
        error = preparation_error
        try:
            raw_items = transport.callable_batch(items) if preparation_error is None else (None,) * len(pending)
            if not isinstance(raw_items, tuple) or len(raw_items) != len(pending):
                raise ValueError("INVALID_BATCH_RESULT_CARDINALITY")
        except Exception as exc:
            error = exc
            raw_items = (None,) * len(pending)
        for item, raw in zip(pending, raw_items, strict=True):
            commit(item, raw, error)
    # Do not advance past entries for which a budget left pending work.
    for entry in priorities:
        if entry not in finished and next_item(entry) is None:
            finished.add(entry)
    return tuple(priority for priority in cohort if priority[2] in finished)
