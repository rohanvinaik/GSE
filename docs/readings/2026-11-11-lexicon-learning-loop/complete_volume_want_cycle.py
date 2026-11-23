"""Review five exact QUANTITY boundaries, continue Zipf, and replay the result."""

import argparse
import json
import os
import sqlite3
import tempfile
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from audit_volume_want import FOLDER, MODEL, MODEL_DIGEST, VOLUME, WantAudit, transport
from complete_unit_want_cycle import DATA, ROOT, ReviewedReplay, compare, question
from probe_unit_banks import execute
from replay_body_exceptions import read, sha256

from gse.curation.lexicon_builder.completion import _contexts, _priority_source, _select_entries, complete_dictionary
from gse.curation.lexicon_builder.foundation import lexical_context
from gse.curation.lexicon_builder.model_receipts import read_model_receipts
from gse.curation.lexicon_builder.publication import publication_readiness
from gse.curation.lexicon_builder.rule_admission import admit_records
from gse.curation.lexicon_builder.rule_history import digest
from gse.curation.lexicon_builder.rule_revisions import exception_source, touches_scope
from gse.curation.lexicon_builder.validation import _metadata, _relations, validate_build

MIGRATED = DATA / "constructed-corpus-volume-want.db"
OUTPUT = DATA / "constructed-corpus-volume-want-zipf.db"
QUANTITY_REVIEWS = {
    "wordnet:em:em.n.01": (
        0,
        "The referent is a printing spacer, defined by a square body. The corpus gloss for the printing quad "
        "identifies a blank type block used for spacing. Square shape specifies geometry while leaving magnitude "
        "free. The separate linear-measure sense em.n.02 requires its own ruling.",
    ),
    "wordnet:emu:electromagnetic_unit.n.01": (
        None,
        "The source defines a system of measurement units. The system is quantitative in subject matter, while "
        "the gloss gives no magnitude that the system itself denotes. The conflicting sense label and gloss "
        "do not establish either sign or orthogonality.",
    ),
    "wordnet:exposure:exposure.n.06": (
        1,
        "This exact sense denotes the intensity of incident light, a magnitude of illumination. The corpus "
        "also distinguishes intensity as transmitted energy amount from other intensity senses. The present "
        "warrant comes from the magnitude in this gloss, independent of the measurement-unit ancestry.",
    ),
    "wordnet:partition:partition.n.02": (
        None,
        "The role is an allocated disk region accessed as a single logical unit. The quantitative contribution "
        "of 'single unit' is ambiguous between a quantity and an access boundary; the gloss gives no capacity.",
    ),
    "wordnet:word:word.n.07": (
        None,
        "The definition describes a stored bit string without a constitutive number or unit magnitude. The "
        "example gives a machine-specific width. A definition explicitly specifying the architecture's native "
        "grouping would be relevant to deciding whether amount belongs to this exact sense.",
    ),
}
ZIPF_REVIEWS = {
    "wordnet:won:south_korean_won.n.01": "The definition identifies South Korea's denomination. Desire for money is independent of that denomination.",
    "wordnet:sent:sent.n.01": "The sent is one hundredth of the Estonian kroon. Its denomination is independent of anyone's aims or wishes.",
    "wordnet:l:lambert.n.01": "The lambert is a luminance unit defined by the brightness of a specified surface. The surface and light supply the defining scale.",
    "wordnet:bob:british_shilling.n.01": "This bob is a former British denomination. A money holder's intentions are independent of the monetary unit.",
    "wordnet:bar:bar.n.07": "The bar is pressure equivalent to a million dynes per square centimeter. The definition supplies a physical magnitude.",
    "wordnet:mark:mark.n.07": "This mark is a historical German denomination. The monetary standard has its own identity across different purposes of exchange.",
}


@dataclass(frozen=True)
class ResidualCycle:
    audit: WantAudit
    migrated: Path
    output: Path
    quantity_reviews: dict[str, tuple[int | None, str]]
    zipf_reviews: dict[str, str]
    source_refs: dict[str, tuple[str, ...]] = field(default_factory=dict)
    probe_without_warrant: bool = True

    @property
    def answers(self):
        return FOLDER / f"{self.audit.prefix}-residual-answers"

    @property
    def retry_answers(self):
        return FOLDER / f"{self.audit.prefix}-residual-timeout-retry"


VOLUME_CYCLE = ResidualCycle(VOLUME, MIGRATED, OUTPUT, QUANTITY_REVIEWS, ZIPF_REVIEWS)


def proposed_rule(spec):
    if not (FOLDER / f"{spec.audit.prefix}-revision-plan.json").exists():
        return ()
    admitted = admit_records(*(spec.audit.load(name) for name in ("input", "audit", "review")))
    return _relations(json.loads(json.dumps([admitted["relation"]])))


def prepare(spec=VOLUME_CYCLE):
    parent = read(FOLDER / spec.audit.parent_report)
    source = read(FOLDER / "native-unit-quantity-scope.json")
    if "unresolved_reviewed_cells" in parent:
        boundaries = {row["entry_id"] for row in parent["unresolved_reviewed_cells"] if row["bank"] == "QUANTITY"}
    else:
        exclusions = read(FOLDER / "unit-quantity-scope-review.json")["scope_exclusions"]
        boundaries = {row["definition"]["entry_id"] for row in exclusions}
    if boundaries != spec.quantity_reviews.keys():
        raise ValueError("QUANTITY_BOUNDARY_SET_CHANGED")
    rows = {row["definition"]["entry_id"]: row for row in source["witnesses"] if row["native_lemma"]}
    reserved = {row["definition"]["entry_id"] for row in spec.audit.load("scope")["rows"]}
    earlier = read(FOLDER / "unit-banks-probe-plan.json")
    prior = {row["entry_id"] for row in earlier["questions"] if row["bank"] == "WANT"} | set(
        parent.get("new_want_zero", [])
    )
    new_rules = proposed_rule(spec)
    priority, frequencies = _priority_source("zipf", None)
    with closing(sqlite3.connect(spec.audit.baseline.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        old = _relations(_metadata(conn, "relations"))
        # Reserve the audited population for the rule cycle even if the
        # audit is inconclusive. This cohort measures transfer to other senses.
        remaining = set(rows) - prior - reserved - boundaries
        eligible = {
            identity
            for identity, payload in conn.execute(
                "SELECT entry_id,domains FROM definition_states WHERE entry_id IN (SELECT value FROM json_each(?))",
                (json.dumps(sorted(remaining)),),
            )
            if len(json.loads(payload)["WANT"]) > 1
        }
        ranked, _ = _select_entries(conn, eligible, ("WANT",), len(spec.zipf_reviews), frequencies=frequencies)
        selected = {}
        used = set()
        for _, _, identity in ranked:
            lemma = rows[identity]["definition"]["lemma"].casefold()
            if lemma in used:
                continue
            selected[identity] = "WANT"
            used.add(lemma)
            if len(selected) == len(spec.zipf_reviews):
                break
        if set(selected) != spec.zipf_reviews.keys():
            raise ValueError("NEXT_ZIPF_COHORT_REQUIRES_SOURCE_REVIEW:" + str(selected))
        selected = {**dict.fromkeys(spec.quantity_reviews, "QUANTITY"), **selected}
        observations, relevance = _contexts(conn, tuple(selected))
        questions = []
        for identity, bank in selected.items():
            native = exception_source(conn, identity)
            source_sha = digest(native)
            if source_sha != rows[identity]["source_sha256"]:
                raise ValueError("BOUNDARY_OR_ZIPF_SOURCE_CHANGED:" + identity)
            context = lexical_context(native["definition"], (native["observation"],), new_rules)
            if touches_scope(new_rules, context):
                raise ValueError("RESIDUAL_QUESTION_OVERLAPS_MIGRATION:" + identity)
            request = question(conn, identity, observations, relevance, old + new_rules, bank=bank)
            value, rationale = (
                spec.quantity_reviews[identity] if bank == "QUANTITY" else (0, spec.zipf_reviews[identity])
            )
            questions.append(
                {
                    **request,
                    "source_sha256": source_sha,
                    "expected": value,
                    "source_rationale": rationale,
                    **({"source_refs": list(spec.source_refs[identity])} if identity in spec.source_refs else {}),
                    "frequency": frequencies.get(native["definition"]["lemma"].casefold(), 0),
                    "scope": "QUANTITY_BOUNDARY" if bank == "QUANTITY" else "ZIPF_CONTINUATION",
                }
            )
    return {
        "format": f"gse.{spec.audit.prefix}-cycle-residual/1",
        "baseline_sha256": parent["candidate_sha256"],
        "approved_want_rule": new_rules[0].rule_id if new_rules else None,
        "priority": priority,
        "questions": questions,
    }


def probe(spec=VOLUME_CYCLE):
    if (FOLDER / f"{spec.audit.prefix}-residual-worklist.json").exists():
        worklist = spec.audit.load("residual-worklist")
    else:
        worklist = prepare(spec)
        spec.audit.save("residual-worklist", worklist)
    spec.answers.mkdir(exist_ok=True)
    questions = [row for row in worklist["questions"] if row["expected"] is not None or spec.probe_without_warrant]
    if questions:
        execute(questions, spec.answers, transport())


def retry_timeouts(spec):
    """Retry only requests that produced an operational timeout."""
    questions = []
    for row in spec.audit.load("residual-worklist")["questions"]:
        original = spec.answers / (row["request_id"] + ".json")
        if original.is_file() and read(original)["code"] == "MODEL_TIMEOUT":
            questions.append(row)
    if questions:
        spec.retry_answers.mkdir(exist_ok=True)
        execute(questions, spec.retry_answers, transport(batch_size=1, timeout=360))


def review_answers(candidate, worklist, spec):
    selected = tuple(row["request"]["entry_id"] for row in worklist["questions"])
    accepted, ledger = {}, []
    with closing(sqlite3.connect(candidate.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        relations = _relations(_metadata(conn, "relations"))
        if worklist["approved_want_rule"] and worklist["approved_want_rule"] not in {
            relation.rule_id for relation in relations if relation.approved
        }:
            raise ValueError("RESIDUAL_BASELINE_MISSING_ADMITTED_WANT_RULE")
        observations, relevance = _contexts(conn, selected)
        for row in worklist["questions"]:
            identity, bank = (row["request"][key] for key in ("entry_id", "bank"))
            fresh = question(conn, identity, observations, relevance, relations, bank=bank)
            native = exception_source(conn, identity)
            if fresh != {key: row[key] for key in fresh} or digest(native) != row["source_sha256"]:
                raise ValueError("RESIDUAL_QUESTION_OR_SOURCE_CHANGED:" + identity)
            expected = row["expected"]
            prior_timeout = None
            if expected is None and not spec.probe_without_warrant:
                answer = {"code": "NOT_REQUERIED_SOURCE_WARRANT_STILL_UNRESOLVED"}
            else:
                answer_file = row["request_id"] + ".json"
                answer = read(spec.answers / answer_file)
                retry = spec.retry_answers / answer_file
                if answer["code"] == "MODEL_TIMEOUT" and retry.is_file():
                    prior_timeout = answer
                    answer = read(retry)
                if answer["request_id"] != fresh["request_id"] or not answer["transport_identity"].startswith(
                    f"{MODEL}#{MODEL_DIGEST}@"
                ):
                    raise ValueError("RESIDUAL_ANSWER_IDENTITY_CHANGED")
            raw = json.loads(answer["raw_output"]) if answer["code"] == "TYPED_ANSWER" else None
            value = raw.get(bank) if type(raw) is dict and raw.keys() == {bank} else None
            if expected is None:
                code = "UNRESOLVED_NO_DEFINITIONAL_WARRANT"
            elif type(value) is int and value == expected:
                code = "ACCEPTED_SOURCE_AND_MODEL_AGREE"
                accepted[identity, bank] = {**fresh, **answer}
            else:
                code = "UNRESOLVED_MODEL_DISAGREES" if value is not None else "UNRESOLVED_MODEL_NO_RULING"
            ledger.append(
                {
                    **{key: value for key, value in row.items() if key not in {"request", "schema"}},
                    "definition": native["definition"],
                    "answer": answer,
                    **({"prior_timeout": prior_timeout} if prior_timeout is not None else {}),
                    "code": code,
                }
            )
    return accepted, ledger


def copy(candidate, output):
    if output.exists():
        return
    with tempfile.NamedTemporaryFile(prefix=".gse-residual-", suffix=".db", dir=output.parent) as temp:
        path = Path(temp.name)
        with closing(sqlite3.connect(candidate.as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(path)) as working:
                original.backup(working)
        os.link(path, output)


def write_bank(bank, accepted, spec):
    work = {identity: row for (identity, target), row in accepted.items() if bank == target}
    if not work:
        return
    replay = ReviewedReplay(work.values())
    pending = []
    with closing(sqlite3.connect(spec.output.as_uri() + "?mode=ro", uri=True)) as conn:
        receipts = read_model_receipts(conn)
        for identity, row in work.items():
            [payload] = conn.execute("SELECT domains FROM definition_states WHERE entry_id=?", (identity,)).fetchone()
            domain = json.loads(payload)[bank]
            if len(domain) > 1:
                pending.append(identity)
            elif domain != [json.loads(row["raw_output"])[bank]] or not any(
                receipt["request_id"] == row["request_id"]
                and receipt["assertion"]["source"] == "model:" + replay.identity
                for receipt in receipts.get(identity, ())
            ):
                raise ValueError("RESIDUAL_EXISTING_AUTHORITY_CHANGED:" + identity)
    if pending:
        result = complete_dictionary(
            spec.output,
            replay,
            len(pending),
            entry_ids=tuple(pending),
            banks=(bank,),
            max_entries_per_pass=len(pending),
            max_calls_per_entry=1,
            priority="zipf",
            progress=lambda row: print(json.dumps(row), flush=True),
        )
        if result["outcomes"] != {"ASSIGNED": len(pending)}:
            raise ValueError("RESIDUAL_TYPED_WRITER_INCOMPLETE:" + str(result["outcomes"]))
        spec.audit.save(f"{bank.lower()}-completion", result)


def finish(spec=VOLUME_CYCLE):
    worklist = spec.audit.load("residual-worklist")
    parent = read(FOLDER / spec.audit.parent_report)
    if worklist["baseline_sha256"] != parent["candidate_sha256"]:
        raise ValueError("RESIDUAL_BASELINE_CHANGED")
    baseline = spec.audit.baseline
    base = spec.migrated if worklist["approved_want_rule"] else baseline
    expected = {}
    if base == spec.migrated:
        migration = spec.audit.load("migration")
        if migration["postflight"]["code"] != "REPLAY_VALIDATED" or not migration["postflight"]["complete_search"]:
            raise ValueError("RESIDUAL_REQUIRES_REPLAYED_MIGRATION")
        expected = {(identity, "WANT"): 0 for identity in spec.audit.load("scope")["expected_new_want_zero"]}
        compare(base, expected, parent["body_receipts_preserved"], baseline=baseline)
    accepted, ledger = review_answers(base, worklist, spec)
    spec.audit.save("residual-review", ledger)
    final = base
    if accepted:
        copy(base, spec.output)
        for bank in ("QUANTITY", "WANT"):
            write_bank(bank, accepted, spec)
        final = spec.output
    print('{"phase":"FULL_POST_COMPLETION_REPLAY"}', flush=True)
    replay = validate_build(final)
    if replay["code"] != "REPLAY_VALIDATED" or not replay["complete_search"]:
        raise ValueError("WANT_CYCLE_FINAL_REPLAY_FAILED")
    model_delta = {pair: json.loads(record["raw_output"])[pair[1]] for pair, record in accepted.items()}
    if expected.keys() & model_delta.keys():
        raise ValueError("SYMBOLIC_AND_MODEL_SCOPES_OVERLAP")
    count = compare(final, {**expected, **model_delta}, parent["body_receipts_preserved"], baseline=baseline)
    publication = publication_readiness(final)
    active = sha256(ROOT / "data/lexicon_active.json")
    if active != parent["active_pointer_sha256"] or sha256(baseline) != parent["candidate_sha256"]:
        raise ValueError("WANT_CYCLE_BASELINE_OR_ACTIVE_CHANGED")
    spec.audit.save(
        "cycle-verification",
        {
            "format": f"gse.{spec.audit.prefix}-cycle-verification/1",
            "candidate": str(final),
            "candidate_sha256": sha256(final),
            "baseline_sha256": parent["candidate_sha256"],
            "active_pointer_sha256": active,
            "activation_performed": False,
            "definitions_compared": count,
            "symbolic_new_want_zero": sorted(identity for identity, _ in expected),
            "model_delta": [
                {"entry_id": identity, "bank": bank, "value": sign}
                for (identity, bank), sign in sorted(model_delta.items())
            ],
            "unresolved_reviewed_cells": [
                {
                    "entry_id": row["definition"]["entry_id"],
                    "bank": "QUANTITY" if row["scope"] == "QUANTITY_BOUNDARY" else "WANT",
                    "reason": row["code"],
                }
                for row in ledger
                if row["code"].startswith("UNRESOLVED")
            ],
            "review_outcomes": dict(Counter(row["code"] for row in ledger)),
            "body_receipts_preserved": parent["body_receipts_preserved"],
            "replay": replay,
            "publication": publication,
        },
    )
    print(
        json.dumps(
            {
                "definitions": count,
                "new_symbolic_cells": len(expected),
                "new_model_cells": len(model_delta),
                "replay": replay["code"],
                "publication": publication["code"],
                "cells": publication["cells"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("probe", "finish"))
    args = parser.parse_args()
    {"probe": probe, "finish": finish}[args.phase]()
