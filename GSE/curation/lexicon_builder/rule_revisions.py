"""A reviewed change to one pinned rule set, with exact-definition exceptions."""

import json
from dataclasses import replace

from GSE.namespace import current_id

from .foundation import EXCEPTION_GUARD_PREFIX, _exact_wordnet_ancestry, lexical_context, validate_lexical_guards
from .rule_history import digest, relation_records

FORMAT = "GSE.rule-revision/1"
RESERVATION_FORMAT = "GSE.rule-revision/2"
REVIEW_FIELDS = {"review_id", "reviewer", "rationale", "source_refs"}


def _review(record, fields, *, optional=()):
    required = REVIEW_FIELDS | fields
    if type(record) is not dict or not required <= record.keys() <= required | set(optional):
        raise ValueError("INVALID_REVISION_REVIEW")
    if any(type(record[key]) is not str or not record[key].strip() for key in REVIEW_FIELDS - {"source_refs"}):
        raise ValueError("INVALID_REVISION_REVIEW")
    refs = record["source_refs"]
    if type(refs) is not list or not refs or any(type(ref) is not str or not ref.strip() for ref in refs):
        raise ValueError("REVISION_SOURCE_REQUIRED")


def exception_source(conn, entry_id):
    """Read the exact native definition and evidence used by a local exception."""
    from .validation import _read_json

    row = conn.execute(
        "SELECT l.lemma,l.pos,l.gloss,o.payload FROM definition_states d "
        "JOIN lexemes l ON l.id=d.lexeme_id JOIN source_observations o ON o.record_id=d.entry_id "
        "WHERE d.entry_id=? AND o.entry_id=d.entry_id AND o.scope='lexical' AND o.source='wordnet_hierarchy'",
        (entry_id,),
    ).fetchone()
    if row is None:
        raise ValueError("REVISION_EXCEPTION_SOURCE_MISSING")
    definition = dict(entry_id=entry_id, lemma=row[0], pos=row[1], definition=row[2])
    observation = _read_json(row[3])
    if not _exact_wordnet_ancestry(definition, observation):
        raise ValueError("REVISION_EXCEPTION_SOURCE_IDENTITY_MISMATCH")
    return {"definition": definition, "observation": observation}


def rule_changes(before, after):
    """Approved relations whose applicability or consequence may have changed."""
    old = {rule.rule_id: rule for rule in before}
    new = {rule.rule_id: rule for rule in after}
    return (
        tuple(rule for rule in before if rule.approved and new.get(rule.rule_id) != rule),
        tuple(rule for rule in after if rule.approved and old.get(rule.rule_id) != rule),
    )


def touches_scope(relations, context):
    return any(all(context.get(key) == value for key, value in rule.guards) for rule in relations)


def reviewed_model_withdrawals(reviews, receipts):
    """Match an explicit local reconsideration to a live or archived receipt."""
    requested = set()
    for review in reviews:
        if "withdraw_model_receipt_sha256" not in review:
            continue
        key = review["withdraw_model_receipt_sha256"]
        matches = [row for row in receipts if digest(row) == key]
        if len(matches) != 1:
            raise ValueError("REVISION_EXCEPTION_MODEL_RECEIPT_CHANGED")
        [receipt] = matches
        claim = receipt["assertion"]
        if (
            receipt["entry_id"] != review["entry_id"]
            or claim["bank"] not in review["counterexample"]
            or claim["value"] == review["counterexample"][claim["bank"]]
        ):
            raise ValueError("REVISION_EXCEPTION_MODEL_RECEIPT_NOT_OPPOSING")
        requested.add(receipt["request_id"])
    return tuple(sorted(requested))


def _except(conn, rule, review):
    identity = review["entry_id"]
    if type(identity) is not str or not identity or rule.authority != "conditional" or not rule.approved:
        raise ValueError("INVALID_REVISION_EXCEPTION_TARGET")
    guard = (EXCEPTION_GUARD_PREFIX + identity, "true")
    if guard in rule.guards:
        raise ValueError("DUPLICATE_REVISION_EXCEPTION")
    source = exception_source(conn, identity)
    if digest(source) != review["source_sha256"]:
        raise ValueError("REVISION_EXCEPTION_SOURCE_CHANGED")
    scope = replace(rule, guards=tuple(item for item in rule.guards if not item[0].startswith(EXCEPTION_GUARD_PREFIX)))
    context = lexical_context(source["definition"], (source["observation"],), (scope,))
    if not touches_scope((scope,), context):
        raise ValueError("REVISION_EXCEPTION_OUTSIDE_SCOPE")
    values = review["counterexample"]
    if (
        type(values) is not dict
        or not values
        or not values.keys() <= set(rule.banks)
        or any(type(value) is not int or value not in (-1, 0, 1) for value in values.values())
    ):
        raise ValueError("INVALID_REVISION_COUNTEREXAMPLE")
    if any(all(row[rule.banks.index(bank)] == value for bank, value in values.items()) for row in rule.allowed_rows):
        raise ValueError("REVISION_EXCEPTION_DOES_NOT_OPPOSE_RULE")
    return replace(rule, guards=tuple(sorted((*rule.guards, guard))))


def validate_revision_shape(revision):
    required = {"format", "baseline_version", "admissions", "retirements", "exceptions"}
    if type(revision) is dict and current_id(revision.get("format")) == RESERVATION_FORMAT:
        required.add("reservations")
    if (
        type(revision) is not dict
        or set(revision) != required
        or type(revision["format"]) is not str
        or current_id(revision["format"]) not in {FORMAT, RESERVATION_FORMAT}
        or any(type(revision[key]) is not list for key in ("admissions", "retirements", "exceptions"))
        or "reservations" in revision
        and type(revision["reservations"]) is not list
    ):
        raise ValueError("INVALID_RULE_REVISION")
    if any(type(record) is not dict or "input" not in record for record in revision["admissions"]):
        raise ValueError("INVALID_REVISION_ADMISSION")


def revision_relations(conn, before, revision):
    """Validate the exact change and reconstruct its resulting rule set."""
    from .rule_admission import verify_admission
    from .validation import _relations

    validate_revision_shape(revision)
    baseline = digest(relation_records(before))
    if revision["baseline_version"] != baseline:
        raise ValueError("MIGRATION_BASELINE_VERSION_MISMATCH")
    rules = {rule.rule_id: rule for rule in before}
    for review in revision["retirements"]:
        _review(review, {"rule_id", "rule_sha256"})
        identity = review["rule_id"]
        old = rules.get(identity) if type(identity) is str else None
        if old is None or old.authority != "conditional" or not old.approved:
            raise ValueError("INVALID_RULE_RETIREMENT_TARGET")
        if digest(relation_records((old,))[0]) != review["rule_sha256"]:
            raise ValueError("RULE_RETIREMENT_WITNESS_CHANGED")
        del rules[identity]
    admitted = {}
    for admission in revision["admissions"]:
        verify_admission(admission)
        if admission["baseline_version"] != baseline:
            raise ValueError("REVISION_ADMISSION_BASELINE_MISMATCH")
        [rule] = _relations(json.loads(json.dumps([admission["relation"]])))
        if rule.rule_id in rules or rule.rule_id in admitted:
            raise ValueError("MIGRATION_RULE_ALREADY_PRESENT")
        admitted[rule.rule_id] = rule
    rules.update(sorted(admitted.items()))
    for review in revision["exceptions"]:
        _review(
            review,
            {"rule_id", "entry_id", "source_sha256", "counterexample"},
            optional=("withdraw_model_receipt_sha256",),
        )
        identity = review["rule_id"]
        if type(identity) is not str or identity not in rules:
            raise ValueError("INVALID_REVISION_EXCEPTION_TARGET")
        rules[identity] = _except(conn, rules[identity], review)
    for review in revision.get("reservations", ()):
        from .rule_reservations import reserve_relation

        _review(review, {"rule_id", "entry_id", "source_sha256", "bank", "audit"})
        identity = review["rule_id"]
        if type(identity) is not str or identity not in rules:
            raise ValueError("INVALID_REVISION_RESERVATION_TARGET")
        rules[identity] = reserve_relation(conn, rules[identity], review, before)
    for admission in revision["admissions"]:
        rule = rules[admission["relation"]["rule_id"]]
        if any(
            (EXCEPTION_GUARD_PREFIX + entry, "true") not in rule.guards
            for entry in admission["warrant"].get("required_exception_ids", ())
        ):
            raise ValueError("REQUIRED_REVISION_EXCEPTION_MISSING")
        required = set(admission["warrant"].get("required_reservation_ids", ()))
        supplied = {r["entry_id"] for r in revision.get("reservations", ()) if r["rule_id"] == rule.rule_id}
        if not required <= supplied:
            raise ValueError("REQUIRED_REVISION_RESERVATION_MISSING")
    after = tuple(rules.values())
    validate_lexical_guards(after)
    if after == before:
        raise ValueError("EMPTY_RULE_REVISION")
    return after
