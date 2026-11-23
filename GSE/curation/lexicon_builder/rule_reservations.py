"""Exact unresolved audit reservations, distinct from signed counterexamples."""

from dataclasses import replace

from .foundation import EXCEPTION_GUARD_PREFIX, _exact_wordnet_ancestry, lexical_context, native_frame_source
from .residual import _request_id
from .rule_history import digest, relation_records


def reservation_source(conn, entry_id):
    """Reuse the exact native identity witnesses for WordNet and Wiktionary."""
    from .validation import _read_json

    rows = conn.execute(
        "SELECT l.lemma,l.pos,l.gloss,o.payload FROM definition_states d "
        "JOIN lexemes l ON l.id=d.lexeme_id JOIN source_observations o ON o.entry_id=d.entry_id "
        "WHERE d.entry_id=? AND o.scope='lexical' AND o.source IN ('wordnet_hierarchy','wiktionary') "
        "ORDER BY o.record_id", (entry_id,),
    )
    witnesses = []
    for lemma, pos, gloss, payload in rows:
        definition = dict(entry_id=entry_id, lemma=lemma, pos=pos, definition=gloss)
        observation = _read_json(payload)
        if _exact_wordnet_ancestry(definition, observation) or native_frame_source(definition, observation):
            witnesses.append({"definition": definition, "observation": observation})
    if len(witnesses) != 1:
        raise ValueError("REVISION_RESERVATION_SOURCE_NOT_UNIQUE")
    return witnesses[0]


def reserve_relation(conn, rule, review, baseline):
    """Withhold one exact definition after a genuine null audit, assigning no sign."""
    from .rule_revisions import touches_scope
    from .validation import _read_json

    identity, bank, audit = review["entry_id"], review["bank"], review["audit"]
    if (
        type(identity) is not str or not identity or type(bank) is not str or bank not in rule.banks
        or rule.authority != "conditional" or not rule.approved
    ):
        raise ValueError("INVALID_REVISION_RESERVATION_TARGET")
    guard = (EXCEPTION_GUARD_PREFIX + identity, "true")
    if guard in rule.guards:
        raise ValueError("DUPLICATE_REVISION_RESERVATION")
    source = reservation_source(conn, identity)
    if digest(source) != review["source_sha256"]:
        raise ValueError("REVISION_RESERVATION_SOURCE_CHANGED")
    scope = replace(rule, guards=tuple(g for g in rule.guards if not g[0].startswith(EXCEPTION_GUARD_PREFIX)))
    context = lexical_context(source["definition"], (source["observation"],), (scope,))
    if not touches_scope((scope,), context):
        raise ValueError("REVISION_RESERVATION_OUTSIDE_SCOPE")
    if (
        type(audit) is not dict or audit.get("code") != "MODEL_ABSTAINED"
        or type(audit.get("model_calls")) is not int or audit["model_calls"] != 1
        or audit.get("entry_id") != identity or audit.get("bank") != bank or audit.get("writes") is not False
        or type(audit.get("transport_identity")) is not str or not audit["transport_identity"]
        or type(audit.get("raw_output")) is not str
    ):
        raise ValueError("REVISION_RESERVATION_REQUIRES_ABSTAINING_AUDIT")
    if _read_json(audit["raw_output"]) != {bank: None}:
        raise ValueError("REVISION_RESERVATION_NOT_NULL")
    request = audit.get("request")
    if (
        type(request) is not dict or audit.get("request_id") != _request_id(request)
        or request.get("entry_id") != identity or request.get("bank") != bank
        or request.get("definition") != source["definition"] or request.get("fill") != {bank: None}
        or type(request.get("observations")) is not list
        or digest(source["observation"]) not in {digest(item) for item in request["observations"]}
    ):
        raise ValueError("REVISION_RESERVATION_REQUEST_MISMATCH")
    values, known, scaffold = request.get("allowed_values"), request.get("known"), request.get("scaffold")
    if (
        type(values) is not list or len(values) not in (2, 3)
        or any(type(value) is not int or value not in (-1, 0, 1) for value in values)
        or len(set(values)) != len(values)
        or type(known) is not dict or bank in known or type(scaffold) is not dict
        or type(scaffold.get("domains")) is not dict or scaffold["domains"].get(bank) != values
    ):
        raise ValueError("REVISION_RESERVATION_BASELINE_MISMATCH")
    records = scaffold.get("approved_relations")
    if type(records) is not list or any(type(record) is not dict for record in records):
        raise ValueError("REVISION_RESERVATION_BASELINE_MISMATCH")
    tables = [
        {key: value for key, value in record.items() if key not in {"disposition", "reason", "requested_component"}}
        for record in records
    ]
    expected = relation_records(sorted((rule for rule in baseline if rule.approved), key=lambda rule: rule.rule_id))
    if digest(tables) != digest(expected):
        raise ValueError("REVISION_RESERVATION_BASELINE_MISMATCH")
    expected_schema = {
        "type": "object", "properties": {bank: {"type": ["integer", "null"], "enum": [*values, None]}},
        "required": [bank], "additionalProperties": False,
    }
    if audit.get("schema") != expected_schema:
        raise ValueError("REVISION_RESERVATION_SCHEMA_MISMATCH")
    if any(
        type(value) is not int or value not in (-1, 0, 1) or scaffold["domains"].get(key) != [value]
        for key, value in known.items()
    ):
        raise ValueError("REVISION_RESERVATION_BASELINE_MISMATCH")
    return replace(rule, guards=tuple(sorted((*rule.guards, guard))))
