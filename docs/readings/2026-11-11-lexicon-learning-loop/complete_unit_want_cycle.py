"""Capture and write exact reviewed WANT cells, then replay the whole candidate."""

import argparse
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from probe_unit_banks import execute
from replay_body_exceptions import FOLDER, ROOT, ReviewedReplay, read, sha256, write

from GSE.curation.lexicon_builder.completion import (
    _contexts,
    _entry,
    _priority_source,
    _select_entries,
    complete_dictionary,
)
from GSE.curation.lexicon_builder.foundation import BANKS, lexical_context
from GSE.curation.lexicon_builder.model_batch import OllamaBatchTransport
from GSE.curation.lexicon_builder.model_receipts import read_model_receipts
from GSE.curation.lexicon_builder.publication import publication_readiness
from GSE.curation.lexicon_builder.residual import OllamaTransport, build_request
from GSE.curation.lexicon_builder.resolution import resolve_dictionary
from GSE.curation.lexicon_builder.rule_admission import admit_records
from GSE.curation.lexicon_builder.rule_history import digest
from GSE.curation.lexicon_builder.rule_revisions import exception_source, touches_scope
from GSE.curation.lexicon_builder.validation import _metadata, _relations, validate_build

DATA = ROOT / "data/lexicon_builder/2026-11-01"
BASELINE = DATA / "constructed-corpus-body-exceptions-resumed.db"
MIGRATED = DATA / "constructed-corpus-unit-quantity.db"
OUTPUT = DATA / "constructed-corpus-unit-quantity-want.db"
MODEL = "qwen3.8:27b-q4_K_M"
MODEL_DIGEST = "25b843619e944cd0ae6069f94ff4e5e26a16e109ccbc0a66a0f05979ed70098e"
DISAGREEMENTS = {
    "wordnet:point:point.n.10": "The point is a counting unit in a scoring system. Wanting to win belongs to a participant's goal, outside the unit's defining role.",
    "wordnet:word:word.n.07": "The stored bit string has a data representation role. Neither an intent to communicate nor an operator's purpose defines it.",
    "wordnet:key:key.n.05": "The key denotes one kilogram of a specified substance. An actor's desire for the substance is external to the unit's mass.",
    "wordnet:cup:cup.n.04": "The cup is a fixed volume of eight fluid ounces. Purposes of a vessel or desire for a drink belong to other definitions or situations.",
}
ZIPF_WARRANTS = {
    "wordnet:won:north_korean_won.n.01": "The won is a denomination in North Korea. Its defining unit role is independent of someone's desire for money.",
    "wordnet:won:south_korean_won.n.01": "The won is a denomination in South Korea. Its defining unit role is independent of someone's desire for money.",
    "wordnet:last:last.n.05": "The last is a weight fixed at 4,000 pounds. The standard itself has no conative argument.",
    "wordnet:last:last.n.06": "The last is a grain capacity fixed at 80 bushels. The standard itself has no conative argument.",
    "wordnet:real:real.n.02": "The Brazilian denomination is 100 centavos. Exchange use is compatible with any actor's desire.",
    "wordnet:minute:minute.n.04": "An angular minute is one sixtieth of a degree. Its definition is a geometrical fraction.",
    "wordnet:second:second.n.06": "An arcsecond is one sixtieth of an angular minute. Its definition is a geometrical fraction.",
    "wordnet:bit:bit.n.06": "The bit measures information in the stated two-state system. Its definition is an information quantity.",
    "wordnet:line:agate_line.n.01": "The line defines print space by width and depth. Advertising names the measurement's application.",
    "wordnet:ma:milliampere.n.01": "The milliampere is one thousandth of an ampere. Its definition is a physical magnitude.",
}
ANSWERS = FOLDER / "unit-want-qwen-refined-answers"


def question(conn, identity, observations, relevance, relations, *, bank="WANT"):
    definition, assertions, restrictions, _ = _entry(conn, identity)
    context = lexical_context(definition, observations[identity], relations)
    baseline = resolve_dictionary(
        BANKS,
        assertions,
        relations,
        context,
        evidence_banks=tuple(sorted(relevance[identity])),
        domain_restrictions=restrictions,
    )
    request = build_request(
        identity,
        bank,
        baseline,
        tuple(observations[identity]),
        definition=definition,
        relations=relations,
        context=context,
    )
    return {"request_id": request.request_id, "request": request.payload(), "schema": request.output_schema()}


def prior_audits():
    return {
        row["definition"]["entry_id"]: row
        for row in read(FOLDER / "unit-banks-audit.json")["audits"]
        if row["bank"] == "WANT"
    }


def prepare():
    raw, audit, review = [read(FOLDER / f"unit-quantity-refined-{name}.json") for name in ("input", "audit", "review")]
    admitted = admit_records(raw, audit, review)
    [addition] = _relations(json.loads(json.dumps([admitted["relation"]])))
    scope = read(FOLDER / "native-unit-quantity-scope.json")
    native = {
        row["definition"]["entry_id"]: row
        for row in scope["witnesses"]
        if row["native_lemma"] and len(row["domains"]["WANT"]) > 1
    }
    prior = prior_audits()
    priority, frequencies = _priority_source("zipf", None)
    with closing(sqlite3.connect(BASELINE.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        old = _relations(_metadata(conn, "relations"))
        relations = (*old, addition)
        ranked, _ = _select_entries(conn, set(native) - prior.keys(), ("WANT",), 8, frequencies=frequencies)
        distinct, seen = [], set()
        for _, _, entry in ranked:
            lemma = native[entry]["definition"]["lemma"].casefold()
            if lemma in seen:
                continue
            distinct.append(entry)
            seen.add(lemma)
            if len(distinct) == 8:
                break
        if len(distinct) != 8 or set(distinct) - ZIPF_WARRANTS.keys():
            raise ValueError("ZIPF_COHORT_REQUIRES_SOURCE_REVIEW:" + str(distinct))
        selected = tuple([*DISAGREEMENTS, *distinct])
        observations, relevance = _contexts(conn, selected)
        entries = []
        for identity in selected:
            source = exception_source(conn, identity)
            source_sha = digest(source)
            if source_sha != native[identity]["source_sha256"]:
                raise ValueError("WANT_EXACT_SOURCE_CHANGED:" + identity)
            context = lexical_context(source["definition"], (source["observation"],), (addition,))
            if (
                touches_scope((addition,), context)
                and conn.execute("SELECT 1 FROM accepted_model_receipts WHERE entry_id=?", (identity,)).fetchone()
            ):
                raise ValueError("WANT_FORECAST_REQUIRES_RECONSIDERATION:" + identity)
            record = question(conn, identity, observations, relevance, relations)
            entries.append(
                {
                    **record,
                    "source_sha256": source_sha,
                    "source_review": DISAGREEMENTS.get(identity, ZIPF_WARRANTS.get(identity)),
                    "scope": "DISAGREEMENT" if identity in DISAGREEMENTS else "ZIPF_CONTINUATION",
                    "frequency": frequencies.get(source["definition"]["lemma"].casefold(), 0),
                    **({"prior_audit": prior[identity]} if identity in DISAGREEMENTS else {}),
                }
            )
    return {
        "format": "GSE.unit-want-refinement-worklist/1",
        "baseline_sha256": scope["candidate_sha256"],
        "approved_quantity_rule": addition.rule_id,
        "priority": priority,
        "selection": "First eight distinct spellings ranked by GSE within exact unresolved native measurement senses outside the previous WANT audit.",
        "source_rule": "WANT records the definition's own conative role. The exact quantitative or representational role warrants orthogonality for these senses. QUANTITY alone is insufficient.",
        "questions": entries,
    }


def probe():
    prepared = FOLDER / "unit-want-refined-worklist.json"
    if prepared.exists():
        worklist = read(prepared)
    else:
        worklist = prepare()
        write(prepared, worklist)
    ANSWERS.mkdir(exist_ok=True)
    transport = OllamaBatchTransport(
        OllamaTransport(MODEL, context_tokens=65536, timeout=240, thinking=False, output_tokens=256),
        max_items=4,
    )
    transport.pin()
    if not transport.identity.startswith(f"{MODEL}#{MODEL_DIGEST}@"):
        raise ValueError("WANT_MODEL_DIGEST_CHANGED")
    execute(worklist["questions"], ANSWERS, transport)


def inspect_answers():
    worklist = read(FOLDER / "unit-want-refined-worklist.json")
    selected = [item["request"]["entry_id"] for item in worklist["questions"]]
    accepted, ledger = [], []
    with closing(sqlite3.connect(MIGRATED.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        relations = _relations(_metadata(conn, "relations"))
        if worklist["approved_quantity_rule"] not in {rule.rule_id for rule in relations if rule.approved}:
            raise ValueError("WANT_REQUIRES_MIGRATED_QUANTITY_RULE")
        observations, relevance = _contexts(conn, tuple(selected))
        for item in worklist["questions"]:
            identity = item["request"]["entry_id"]
            current = question(conn, identity, observations, relevance, relations)
            if current != {key: item[key] for key in current}:
                raise ValueError("WANT_MIGRATED_QUESTION_CHANGED:" + identity)
            source = exception_source(conn, identity)
            if digest(source) != item["source_sha256"]:
                raise ValueError("WANT_MIGRATED_SOURCE_CHANGED:" + identity)
            answer = read(ANSWERS / (item["request_id"] + ".json"))
            if answer["request_id"] != current["request_id"] or not answer["transport_identity"].startswith(
                f"{MODEL}#{MODEL_DIGEST}@"
            ):
                raise ValueError("WANT_ANSWER_IDENTITY_CHANGED")
            raw = json.loads(answer["raw_output"]) if answer["code"] == "TYPED_ANSWER" else None
            if type(raw) is dict and raw.keys() == {"WANT"} and type(raw["WANT"]) is int and raw["WANT"] == 0:
                code = "ACCEPTED_SOURCE_AND_MODEL_AGREE"
                accepted.append({**current, **answer})
            else:
                code = "UNRESOLVED_MODEL_DISAGREES" if raw is not None else "UNRESOLVED_MODEL_NO_RULING"
            ledger.append(
                {
                    **{key: value for key, value in item.items() if key not in {"request", "schema"}},
                    "definition": source["definition"],
                    "answer": answer,
                    "code": code,
                }
            )
    return accepted, ledger


def compare(candidate, expected, body_ids, *, baseline=BASELINE):
    with closing(sqlite3.connect(candidate.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("ATTACH DATABASE ? AS previous", (baseline.as_uri() + "?mode=ro",))
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        after_count, before_count, matched = conn.execute(
            "SELECT (SELECT count(*) FROM main.definition_states),"
            "(SELECT count(*) FROM previous.definition_states), count(*) "
            "FROM main.definition_states JOIN previous.definition_states USING(entry_id)"
        ).fetchone()
        if after_count != before_count or matched != before_count:
            raise ValueError("WANT_CYCLE_DEFINITION_COHORT_CHANGED")
        actual = set()
        for identity, before, after in conn.execute(
            "SELECT n.entry_id,b.domains,n.domains FROM main.definition_states n "
            "JOIN previous.definition_states b USING(entry_id) WHERE n.domains<>b.domains"
        ):
            old, new = json.loads(before), json.loads(after)
            for bank in BANKS:
                if old[bank] != new[bank]:
                    value = expected.get((identity, bank))
                    if old[bank] != [-1, 0, 1] or value is None or new[bank] != [value]:
                        raise ValueError(f"UNEXPECTED_CYCLE_BANK_DELTA:{identity}:{bank}")
                    actual.add((identity, bank))
        if actual != expected.keys():
            raise ValueError("INCOMPLETE_EXPECTED_CYCLE_DELTA")
        receipts_after = read_model_receipts(conn)
        with closing(sqlite3.connect(baseline.as_uri() + "?mode=ro", uri=True)) as previous:
            receipts_before = read_model_receipts(previous)
            for identity in body_ids:
                current = receipts_after.get(identity, ())
                if receipts_before.get(identity, ()) != current or not any(
                    receipt["assertion"]["bank"] == "BODY" and receipt["assertion"]["value"] == 1 for receipt in current
                ):
                    raise ValueError("BODY_REVIEWED_RECEIPT_CHANGED:" + identity)
    return after_count


def finish():
    parent = read(FOLDER / "body-exception-resumption-verification.json")
    migration = read(FOLDER / "unit-quantity-migration.json")
    scope = read(FOLDER / "unit-quantity-scope-review.json")
    if migration["postflight"]["code"] != "REPLAY_VALIDATED" or not migration["postflight"]["complete_search"]:
        raise ValueError("WANT_REQUIRES_VALIDATED_MIGRATION")
    accepted, ledger = inspect_answers()
    write(FOLDER / "unit-want-refined-review.json", ledger)
    expected = {(entry, "QUANTITY"): 1 for entry in scope["expected_new_quantity_positive"]}
    body_ids = parent["new_BODY_positive"]
    compare(MIGRATED, expected, body_ids)
    if not accepted:
        raise ValueError("WANT_NO_REVIEWED_TYPED_ANSWERS")
    if not OUTPUT.exists():
        with tempfile.NamedTemporaryFile(prefix=".gse-want-copy-", suffix=".db", dir=OUTPUT.parent) as temporary:
            copy = Path(temporary.name)
            with closing(sqlite3.connect(MIGRATED.as_uri() + "?mode=ro", uri=True)) as origin:
                with closing(sqlite3.connect(copy)) as target:
                    origin.backup(target)
            os.link(copy, OUTPUT)
    transport = ReviewedReplay(accepted)
    accepted_by_entry = {item["request"]["entry_id"]: item for item in accepted}
    pending = []
    with closing(sqlite3.connect(OUTPUT.as_uri() + "?mode=ro", uri=True)) as conn:
        receipts = read_model_receipts(conn)
        for identity, item in accepted_by_entry.items():
            row = conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (identity,)).fetchone()
            if row is None:
                raise ValueError("WANT_ENTRY_MISSING:" + identity)
            domain = json.loads(row[0])["WANT"]
            if len(domain) > 1:
                pending.append(identity)
            elif domain != [0] or not any(
                rec["request_id"] == item["request_id"]
                and rec["assertion"]["value"] == 0
                and rec["assertion"]["bank"] == "WANT"
                and rec["assertion"]["source"] == "model:" + transport.identity
                for rec in receipts.get(identity, ())
            ):
                raise ValueError("WANT_EXISTING_AUTHORITY_CHANGED:" + identity)
    if pending:
        result = complete_dictionary(
            OUTPUT,
            transport,
            len(pending),
            entry_ids=tuple(pending),
            banks=("WANT",),
            max_calls_per_entry=1,
            max_entries_per_pass=len(pending),
            priority="zipf",
            progress=lambda row: print(json.dumps(row), flush=True),
        )
        if result["outcomes"] != {"ASSIGNED": len(pending)}:
            raise ValueError("WANT_TYPED_WRITER_INCOMPLETE:" + str(result["outcomes"]))
        write(FOLDER / "unit-want-completion.json", result)
    expected.update({(identity, "WANT"): 0 for identity in accepted_by_entry})
    print('{"phase":"FULL_POST_COMPLETION_REPLAY"}', flush=True)
    replay = validate_build(OUTPUT)
    if replay["code"] != "REPLAY_VALIDATED" or not replay["complete_search"]:
        raise ValueError("WANT_FULL_REPLAY_FAILED")
    count = compare(OUTPUT, expected, body_ids)
    publication = publication_readiness(OUTPUT)
    active = sha256(ROOT / "data/lexicon_active.json")
    if active != parent["active_pointer_sha256"] or sha256(BASELINE) != parent["candidate_sha256"]:
        raise ValueError("WANT_CYCLE_BASELINE_OR_ACTIVE_CHANGED")
    write(
        FOLDER / "unit-quantity-want-cycle-verification.json",
        {
            "format": "GSE.unit-quantity-want-cycle/1",
            "candidate": str(OUTPUT),
            "candidate_sha256": sha256(OUTPUT),
            "baseline_sha256": parent["candidate_sha256"],
            "active_pointer_sha256": active,
            "activation_performed": False,
            "definitions_compared": count,
            "new_quantity_positive": scope["expected_new_quantity_positive"],
            "new_want_zero": sorted(accepted_by_entry),
            "remaining_want_cases": [
                row["definition"]["entry_id"] for row in ledger if row["code"].startswith("UNRESOLVED")
            ],
            "body_receipts_preserved": body_ids,
            "replay": replay,
            "publication": publication,
        },
    )
    print(
        {
            "definitions": count,
            "new_QUANTITY_positive": len(scope["expected_new_quantity_positive"]),
            "new_WANT_zero": len(accepted_by_entry),
            "replay": replay["code"],
            "publication": publication["code"],
            "cells": publication["cells"],
        },
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("probe", "finish"))
    args = parser.parse_args()
    {"probe": probe, "finish": finish}[args.phase]()
