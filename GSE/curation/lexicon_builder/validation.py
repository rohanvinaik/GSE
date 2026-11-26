"""Read-only replay checks for a versioned lexicon build.

Replay establishes agreement between stored evidence, rules, domains and runtime
projection. It does not establish semantic gold correctness or perform a complete
satisfiability search beyond the construction engine's local arc consistency.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, fields
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from GSE.namespace import current_id, identity_form

from .definition_frames import NATIVE_FRAME_PREFIX, WIKTIONARY_ANATOMY_FRAME_PREFIX, native_noun_frames
from .discovery import BankObservation
from .engine import TERNARY, Assertion, DomainRestriction, Relation, propagate
from .evidence import Definition, Observation, validate_assertion_competence
from .foundation import BANKS, lexical_context
from .model_receipts import read_model_receipts
from .residual import build_request
from .resolution import resolve_dictionary
from .storage import DOMAIN_RESTRICTIONS_VERSION, VERSION

_REQUIRED_COLUMNS = {
    "builder_metadata": {"key", "value"},
    "definition_states": {"entry_id", "lexeme_id", "code", "domains", "conflicts", "trace", "hierarchy"},
    "lexemes": {"id", "lemma", "pos", "sense_id", "gloss", "source", "validation_status"},
    "source_observations": {"record_id", "entry_id", "source", "family", "scope", "payload"},
    "builder_assertions": {"entry_id", "ordinal", "payload"},
    "primitive_values": {"lexeme_id", "primitive", "value"},
    "unresolved_sources": {"ordinal", "code", "payload"},
    "candidate_relations": {"rule_id", "summary"},
    "candidate_evidence": {"rule_id", "category", "ordinal", "payload"},
}

_CANDIDATE_CATEGORIES = ("support", "counterexamples", "unknown", "conflicting", "ineligible")


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def _constant(_value: str) -> None:
    raise ValueError("NONFINITE_JSON_NUMBER")


def _float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("NONFINITE_JSON_NUMBER")
    return number


def _read_json(value: object):
    if not isinstance(value, str):
        raise ValueError("NON_TEXT_JSON")
    return json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)


def _diagnostic(value):
    """Keep malformed SQLite scalar types from corrupting the JSON report."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, dict):
        return {str(key): _diagnostic(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_diagnostic(item) for item in value]
    return {"invalid_type": type(value).__name__}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _schema(conn: sqlite3.Connection) -> None:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not _REQUIRED_COLUMNS.keys() <= tables:
        raise ValueError("INVALID_BUILD_SCHEMA")
    for table, required in _REQUIRED_COLUMNS.items():
        actual = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if not required <= actual:
            raise ValueError(f"INVALID_BUILD_SCHEMA:{table}")
    if "builder_domain_restrictions" in tables:
        actual = {row[1] for row in conn.execute("PRAGMA table_info(builder_domain_restrictions)")}
        if not {"entry_id", "ordinal", "payload"} <= actual:
            raise ValueError("INVALID_BUILD_SCHEMA:builder_domain_restrictions")


def _metadata(conn: sqlite3.Connection, key: str):
    rows = conn.execute("SELECT value FROM builder_metadata WHERE key=?", (key,)).fetchall()
    if len(rows) != 1:
        raise ValueError(f"MISSING_OR_AMBIGUOUS_METADATA:{key}")
    try:
        return _read_json(rows[0][0])
    except (ValueError, TypeError) as error:
        raise ValueError(f"INVALID_BUILD_METADATA:{key}") from error


def _relations(raw: object) -> tuple[Relation, ...]:
    if not isinstance(raw, list):
        raise ValueError("INVALID_BUILD_RELATIONS")
    required = {field.name for field in fields(Relation)}
    relations = []
    for index, record in enumerate(raw):
        try:
            if not isinstance(record, dict) or set(record) not in (required, required - {"absent_evidence"}):
                raise ValueError("INVALID_RELATION_FIELDS")
            record = dict(record)
            record.setdefault("absent_evidence", [])
            if any(
                not isinstance(record[key], list)
                for key in ("banks", "allowed_rows", "provenance", "guards", "absent_evidence")
            ):
                raise ValueError("INVALID_RELATION_ARRAY")
            if any(not isinstance(row, list) for row in record["allowed_rows"] + record["guards"]):
                raise ValueError("INVALID_RELATION_ROW")
            if any(len(guard) != 2 for guard in record["guards"]):
                raise ValueError("INVALID_RELATION_GUARD")
            relation = Relation(
                rule_id=record["rule_id"],
                banks=tuple(record["banks"]),
                allowed_rows=tuple(tuple(row) for row in record["allowed_rows"]),
                provenance=tuple(record["provenance"]),
                authority=record["authority"],
                approved=record["approved"],
                guards=tuple((row[0], row[1]) for row in record["guards"]),
                absent_evidence=tuple(record["absent_evidence"]),
            )
        except (ValueError, TypeError) as error:
            raise ValueError(f"INVALID_BUILD_RELATION:{index}") from error
        relations.append(relation)
    result = tuple(relations)
    try:
        propagate(BANKS, (), result)
    except ValueError as error:
        raise ValueError("INVALID_BUILD_RELATIONS") from error
    return result


def _assertions(rows: list[tuple[int, str]]) -> tuple[Assertion, ...]:
    if any(type(ordinal) is not int or ordinal < 0 for ordinal, _ in rows):
        raise ValueError("INVALID_ASSERTION_ORDINAL")
    ordered = sorted(rows, key=lambda row: row[0])
    if [ordinal for ordinal, _ in ordered] != list(range(len(rows))):
        raise ValueError("MISSING_OR_DUPLICATE_ASSERTION_ORDINAL")
    required = {field.name for field in fields(Assertion)}
    result = []
    for _, payload in ordered:
        record = _read_json(payload)
        if not isinstance(record, dict) or set(record) != required:
            raise ValueError("INVALID_ASSERTION_FIELDS")
        result.append(Assertion(**record))
    return tuple(result)


def _domain_restrictions(rows) -> tuple[DomainRestriction, ...]:
    ordered = sorted(rows, key=lambda row: row[0])
    if any(type(ordinal) is not int for ordinal, _ in rows) or [ordinal for ordinal, _ in ordered] != list(
        range(len(rows))
    ):
        raise ValueError("INVALID_RESTRICTION_ORDINAL")
    result = []
    required = {field.name for field in fields(DomainRestriction)}
    for _, payload in ordered:
        record = _read_json(payload)
        if not isinstance(record, dict) or set(record) != required or not isinstance(record["allowed_values"], list):
            raise ValueError("INVALID_RESTRICTION_FIELDS")
        result.append(
            DomainRestriction(
                record["bank"],
                tuple(record["allowed_values"]),
                record["source"],
                record["record_id"],
                record["family"],
                record["scope"],
            )
        )
    return tuple(result)


def _restriction_provenance(entry_id, restrictions, native):
    for restriction in restrictions:
        validate_assertion_competence(restriction)
        observation = native.get((restriction.source, restriction.record_id))
        if (
            observation is None
            or observation.entry_id != entry_id
            or observation.family != restriction.family
            or observation.scope != "lexical"
            or restriction.source.startswith(("model:", "rule:", "derived:"))
            or restriction.family in {"model", "derived"}
        ):
            raise ValueError("DOMAIN_RESTRICTION_PROVENANCE_MISMATCH")


def _domains(raw: object) -> dict[str, frozenset[int]]:
    if not isinstance(raw, dict) or set(raw) != set(BANKS):
        raise ValueError("MISSING_OR_UNKNOWN_DOMAIN_BANK")
    result = {}
    for bank, values in raw.items():
        if not isinstance(values, list) or any(type(value) is not int or value not in TERNARY for value in values):
            raise ValueError("INVALID_DOMAIN_VALUES")
        if len(set(values)) != len(values):
            raise ValueError("DUPLICATE_DOMAIN_VALUE")
        result[bank] = frozenset(values)
    return result


def _published(rows: list[tuple[str, int]]) -> dict[str, int]:
    result = {}
    for bank, value in rows:
        if bank not in BANKS:
            raise ValueError("UNKNOWN_PUBLISHED_BANK")
        if type(value) is not int or value not in TERNARY:
            raise ValueError("INVALID_PUBLISHED_VALUE")
        if bank in result:
            raise ValueError("DUPLICATE_PUBLISHED_BANK")
        result[bank] = value
    return result


def _identity(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _optional_metadata(conn, key, default):
    rows = conn.execute("SELECT value FROM builder_metadata WHERE key=?", (key,)).fetchall()
    return default if not rows else _metadata(conn, key)


def _authorities(conn):
    anchors = _optional_metadata(conn, "anchors", {})
    if not isinstance(anchors, dict):
        raise ValueError("INVALID_ASSERTION_AUTHORITIES")
    anchor_records = {}
    for entry_id, records in anchors.items():
        if not _identity(entry_id) or not isinstance(records, list):
            raise ValueError("INVALID_ANCHOR_AUTHORITY")
        anchor_records[entry_id] = _assertions([(i, _canonical(record)) for i, record in enumerate(records)])
    return anchor_records, read_model_receipts(conn)


class _NativeReference(NamedTuple):
    entry_id: str | None
    family: str
    scope: str


def _observations(conn, entries, mismatch, model_entries=()):
    """Stream full validation but retain only narrow lexical provenance records.

    Full feature objects are discarded after each row. Model context retains
    record IDs only for definitions with accepted model receipts, and is loaded
    lazily during those receipts' replay.
    """
    native = {}
    relevant = defaultdict(list)
    bank_relevance = {}
    from .relevance import observation_relevance

    required = {field.name for field in fields(Observation)}
    duplicates = {
        row[0]
        for row in conn.execute("SELECT record_id FROM source_observations GROUP BY record_id HAVING COUNT(*) > 1")
    }
    for row in conn.execute("SELECT * FROM source_observations"):
        entry_id = row["entry_id"]
        try:
            record = _read_json(row["payload"])
            if not isinstance(record, dict) or set(record) != required:
                raise ValueError("INVALID_OBSERVATION_FIELDS")
            if not isinstance(record["candidate_entry_ids"], list):
                raise ValueError("INVALID_OBSERVATION_CANDIDATES")
            observation = Observation(
                entry_id=record["entry_id"],
                source=record["source"],
                record_id=record["record_id"],
                family=record["family"],
                features=record["features"],
                scope=record["scope"],
                candidate_entry_ids=tuple(record["candidate_entry_ids"]),
            )
            banks = observation_relevance(observation)
            if any(
                getattr(observation, key) != row[key] for key in ("entry_id", "record_id", "source", "family", "scope")
            ):
                raise ValueError("OBSERVATION_COLUMN_PAYLOAD_MISMATCH")
            if observation.record_id in duplicates:
                raise ValueError("AMBIGUOUS_OBSERVATION_ID")
            targets = (entry_id,) if entry_id is not None else observation.candidate_entry_ids
            if any(target not in entries for target in targets):
                raise ValueError("ORPHAN_OBSERVATION_DEFINITION")
        except (TypeError, ValueError) as error:
            mismatch(entry_id, "MALFORMED_OBSERVATION", record_id=row["record_id"], reason=str(error))
            continue
        if observation.scope == "lexical":
            native[(observation.source, observation.record_id)] = _NativeReference(
                observation.entry_id, observation.family, observation.scope
            )
        for target in targets:
            previous = bank_relevance.get(target, frozenset())
            if len(previous) < len(BANKS):
                bank_relevance[target] = previous | banks
            if target in model_entries:
                relevant[target].append(observation.record_id)
    return native, relevant, bank_relevance


def _validate_derived_witness(conn, entry_id, assertion):
    """Replay recomputes a derived assertion instead of trusting it (scripts/revise_lexicon_derived_layers.py)."""
    if assertion.source == "nsm-valency":
        from .valency_absence import absent_banks

        if assertion.value != 0 or assertion.bank not in absent_banks(entry_id):
            raise ValueError("DERIVED_VALENCY_WITNESS_MISMATCH")
    elif assertion.source == "nsm-molecule":
        from .word_sense_nsm_molecules import inherited

        if inherited(entry_id.rsplit(":", 1)[1]).get(assertion.bank, (None,))[0] != assertion.value:
            raise ValueError("DERIVED_MOLECULE_WITNESS_MISMATCH")
    elif assertion.source in ("subkind-inheritance", "form-of"):
        row = conn.execute(
            "SELECT payload FROM source_observations WHERE record_id=?", (assertion.record_id,)
        ).fetchone()
        features = _read_json(row[0])["features"] if row is not None else {}
        if (features.get("values") or {}).get(assertion.bank) != assertion.value:
            raise ValueError("DERIVED_INHERITANCE_WITNESS_MISMATCH")
    else:
        raise ValueError("UNKNOWN_DERIVED_CHANNEL")


def _model_observations(conn, record_ids):
    """Load only the requested definition's already-validated native records."""
    for record_id in record_ids:
        rows = conn.execute("SELECT payload FROM source_observations WHERE record_id=?", (record_id,))
        for row in rows:
            yield _read_json(row[0])


def _context_observations(conn, entry_id, relations, definition=None):
    """Load exact native evidence only where a requested guard can apply."""
    from .foundation import WORDNET_ANCESTRY_GUARD_PREFIXES

    wordnet = any(
        key.startswith(WORDNET_ANCESTRY_GUARD_PREFIXES) or key == "wordnet_native_lemma"
        for rule in relations
        for key, _ in rule.guards
    )
    frames = {key for rule in relations for key, _ in rule.guards if key.startswith(NATIVE_FRAME_PREFIX)}
    has_frame = (
        frames
        and definition is not None
        and definition.pos == "noun"
        and isinstance(definition.definition, str)
        and frames.intersection(NATIVE_FRAME_PREFIX + frame for frame in native_noun_frames(definition.definition))
    )
    if entry_id.startswith("wordnet:") and (wordnet or has_frame):
        row = conn.execute("SELECT payload FROM source_observations WHERE record_id=?", (entry_id,)).fetchone()
        return (_read_json(row[0]),) if row is not None else ()
    has_wiktionary_anatomy_scope = (
        definition is not None
        and definition.pos == "noun"
        and isinstance(definition.definition, str)
        and any(key.startswith(WIKTIONARY_ANATOMY_FRAME_PREFIX) for rule in relations for key, _ in rule.guards)
    )
    if entry_id.startswith("wiktionary:") and (has_frame or has_wiktionary_anatomy_scope):
        return tuple(
            _read_json(row[0])
            for row in conn.execute(
                "SELECT payload FROM source_observations "
                "WHERE entry_id=? AND source='wiktionary' AND scope='lexical' "
                "AND (? OR EXISTS (SELECT 1 FROM json_each(payload,'$.features.native_sense.topics') "
                "WHERE type='text' AND value='anatomy')) ORDER BY record_id",
                (entry_id, bool(has_frame)),
            )
        )
    return ()


def _stored_context(conn, definition, relations):
    return lexical_context(
        definition, _context_observations(conn, definition.entry_id, relations, definition), relations
    )


def _provenance(
    entry_id,
    assertions,
    definition,
    relations,
    native,
    relevant,
    anchors,
    models,
    conn,
    evidence_banks=(),
    domain_restrictions=(),
    *,
    rule_history=None,
):
    """Check authority separately from whether an assertion changes a domain."""
    remaining_anchors = Counter(anchors.get(entry_id, ()))
    remaining_models = list(models.get(entry_id, ()))
    prefix = ()
    model_started = False
    for assertion in assertions:
        if remaining_anchors[assertion]:
            if model_started:
                raise ValueError("MODEL_BEFORE_SYMBOLIC_EVIDENCE")
            remaining_anchors[assertion] -= 1
        else:
            matching = [record for record in remaining_models if record["assertion"] == asdict(assertion)]
            if matching:
                model_started = True
                if len(matching) != 1:
                    raise ValueError("AMBIGUOUS_MODEL_AUTHORITY")
                receipt = matching[0]
                from .rule_history import read_history, receipt_relations

                if rule_history is None:
                    rule_history = read_history(conn, relations)
                payload = receipt["request"]
                if not isinstance(payload, dict) or not isinstance(payload.get("observations"), list):
                    raise ValueError("INVALID_MODEL_REQUEST")
                if Counter(map(_canonical, payload["observations"])) != Counter(
                    map(_canonical, _model_observations(conn, relevant[entry_id]))
                ):
                    raise ValueError("MODEL_OBSERVATIONS_MISMATCH")
                request_relations = receipt_relations(
                    receipt, relations, None, rule_history, definition=definition, observations=payload["observations"]
                )
                request_context = lexical_context(definition, payload["observations"], request_relations)
                before = resolve_dictionary(
                    BANKS,
                    prefix,
                    request_relations,
                    request_context,
                    evidence_banks=evidence_banks,
                    domain_restrictions=domain_restrictions,
                )
                request = build_request(
                    entry_id,
                    assertion.bank,
                    before,
                    tuple(payload["observations"]),
                    definition=definition,
                    relations=request_relations,
                    context=request_context,
                    request_format=payload["format"],
                )
                if (
                    request.request_id != receipt["request_id"]
                    or _canonical(identity_form(request.payload())) != _canonical(identity_form(payload))
                    or _canonical(identity_form(request.output_schema()))
                    != _canonical(identity_form(receipt["schema"]))
                    or assertion.value not in request.allowed_values
                ):
                    raise ValueError("MODEL_REQUEST_MISMATCH")
                after = resolve_dictionary(
                    BANKS,
                    prefix + (assertion,),
                    request_relations,
                    request_context,
                    evidence_banks=evidence_banks,
                    domain_restrictions=domain_restrictions,
                )
                if after.code == "CONFLICT":
                    raise ValueError("MODEL_ACCEPTED_CONTRADICTION")
                previous_exceptions = {
                    rule_id
                    for record in before.trace
                    if record["kind"] == "CONDITIONAL_EXCEPTION"
                    for rule_id in record["rule_ids"]
                }
                if any(
                    record["kind"] == "CONDITIONAL_EXCEPTION" and set(record["rule_ids"]) - previous_exceptions
                    for record in after.trace
                ):
                    raise ValueError("MODEL_ADDED_CONDITIONAL_EXCEPTION")
                if any(after.assignments.get(bank) != value for bank, value in before.assignments.items()):
                    raise ValueError("MODEL_CHANGED_KNOWN_ASSIGNMENT")
                remaining_models.remove(receipt)
            else:
                if model_started:
                    raise ValueError("MODEL_BEFORE_SYMBOLIC_EVIDENCE")
                validate_assertion_competence(assertion)
                observation = native.get((assertion.source, assertion.record_id))
                if (
                    observation is None
                    or observation.entry_id != entry_id
                    or observation.family != assertion.family
                    or observation.scope != "lexical"
                ):
                    raise ValueError("ASSERTION_PROVENANCE_MISMATCH")
                if assertion.family == "derived":
                    _validate_derived_witness(conn, entry_id, assertion)
                if assertion.source == "wiktionary":
                    from .evidence import wiktionary_definition_projection

                    row = conn.execute(
                        "SELECT payload FROM source_observations WHERE record_id=?", (assertion.record_id,)
                    ).fetchone()
                    features = _read_json(row[0])["features"] if row is not None else {}
                    projected = wiktionary_definition_projection(definition, features)
                    if projected.get(assertion.bank) != assertion.value:
                        genus = "PERSON" if assertion.bank == "SOMEONE" else "ANATOMY"
                        raise ValueError(f"WIKTIONARY_{genus}_PROJECTION_WITNESS_MISMATCH")
                if assertion.source == "gse_closed_class" and assertion.bank in {"I", "YOU"}:
                    from GSE.curation.external_sources.gse_closed_class import GSEClosedClassParser

                    row = conn.execute(
                        "SELECT payload FROM source_observations WHERE record_id=?", (assertion.record_id,)
                    ).fetchone()
                    features = _read_json(row[0])["features"] if row is not None else {}
                    if (
                        features.get("entry_id") != entry_id
                        or features.get("lemma") != definition.lemma
                        or features.get("definition") != definition.definition
                        or GSEClosedClassParser().reference_projection_for_observation(features).get(assertion.bank)
                        != assertion.value
                    ):
                        raise ValueError("CLOSED_CLASS_REFERENCE_PROJECTION_WITNESS_MISMATCH")
        prefix += (assertion,)
    if any(remaining_anchors.values()) or remaining_models:
        raise ValueError("UNCONSUMED_ASSERTION_AUTHORITY")


def _unresolved_integrity(conn, mismatch):
    counts = Counter()
    total = 0
    for row in conn.execute("SELECT ordinal,code,payload FROM unresolved_sources ORDER BY ordinal"):
        try:
            if type(row["ordinal"]) is not int or row["ordinal"] != total:
                raise ValueError("INVALID_DIAGNOSTIC_ORDINAL")
            record = _read_json(row["payload"])
            if not isinstance(record, dict) or not _identity(record.get("code")) or record["code"] != row["code"]:
                raise ValueError("DIAGNOSTIC_CODE_MISMATCH")
            counts[record["code"]] += 1
        except (TypeError, ValueError) as error:
            mismatch(None, "MALFORMED_SOURCE_DIAGNOSTIC", ordinal=row["ordinal"], reason=str(error))
        total += 1
    expected = {"table": "unresolved_sources", "records": total, "outcomes": dict(counts)}
    if _canonical(identity_form(_optional_metadata(conn, "unresolved_sources", None))) != _canonical(
        identity_form(expected)
    ):
        mismatch(None, "SOURCE_DIAGNOSTIC_METADATA_MISMATCH")


def _candidate_summary(raw, rule_id):
    required = {
        "relation",
        "antecedent",
        "consequent",
        "by_family",
        "admission",
        "propagation_scope",
        "evidence_counts",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError("INVALID_CANDIDATE_SUMMARY_FIELDS")
    relation = _relations([raw["relation"]])[0]
    if (
        relation.rule_id != rule_id
        or relation.approved is not False
        or relation.authority != "conditional"
        or relation.guards
    ):
        raise ValueError("INVALID_CANDIDATE_AUTHORITY")
    if raw["admission"] != "UNAPPROVED_CANDIDATE" or raw["propagation_scope"] != "LOCAL_ARC_CONSISTENCY":
        raise ValueError("INVALID_CANDIDATE_ADMISSION")
    for key in ("antecedent", "consequent"):
        literal = raw[key]
        if (
            not isinstance(literal, list)
            or len(literal) != 2
            or literal[0] not in BANKS
            or type(literal[1]) is not int
            or literal[1] not in TERNARY
        ):
            raise ValueError("INVALID_CANDIDATE_LITERAL")
    (left, a), (right, b) = raw["antecedent"], raw["consequent"]
    identity = hashlib.sha256(json.dumps([left, a, right, b], separators=(",", ":")).encode()).hexdigest()[:20]
    rows = tuple((x, y) for x in sorted(TERNARY) for y in sorted(TERNARY) if x != a or y == b)
    if relation.rule_id != f"candidate:{identity}" or relation.banks != (left, right) or relation.allowed_rows != rows:
        raise ValueError("CANDIDATE_RELATION_MISMATCH")
    counts = raw["evidence_counts"]
    if (
        not isinstance(counts, dict)
        or set(counts) != set(_CANDIDATE_CATEGORIES)
        or any(type(value) is not int or value < 0 for value in counts.values())
    ):
        raise ValueError("INVALID_CANDIDATE_COUNTS")
    if not isinstance(raw["by_family"], dict):
        raise ValueError("INVALID_CANDIDATE_FAMILIES")
    allowed = {*_CANDIDATE_CATEGORIES, "eligible", "antecedent_unknown", "antecedent_other"} - {"ineligible"}
    for family, values in raw["by_family"].items():
        if not _identity(family) or not isinstance(values, dict):
            raise ValueError("INVALID_CANDIDATE_FAMILY_COUNTS")
        for key, value in values.items():
            if key.removeprefix("weighted_") not in allowed or type(value) not in (int, float) or value < 0:
                raise ValueError("INVALID_CANDIDATE_FAMILY_COUNTS")
            if not key.startswith("weighted_") and type(value) is not int:
                raise ValueError("INVALID_CANDIDATE_FAMILY_COUNTS")
            if key.startswith("weighted_"):
                _candidate_weight(value)
    return relation


def _candidate_weight(value):
    try:
        valid = type(value) in (int, float) and value >= 0 and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("INVALID_CANDIDATE_WEIGHT")


def _candidate_receipt(record, category, summary, native, assertions_for):
    if category == "ineligible":
        observations = [dict(record)]
        if observations[0].pop("code", None) != "NOT_SOURCE_LEXICAL_EVIDENCE":
            raise ValueError("INVALID_INELIGIBLE_REASON")
    else:
        required = {
            "entry_id",
            "source",
            "family",
            "weight",
            "code",
            "antecedent_values",
            "consequent_values",
            "observations",
        }
        if not isinstance(record, dict) or set(record) != required or not isinstance(record["observations"], list):
            raise ValueError("INVALID_CANDIDATE_RECEIPT_FIELDS")
        _candidate_weight(record["weight"])
        observations = record["observations"]
    cross_source = (
        category != "ineligible"
        and record["source"] == f"definition:{record['entry_id']}"
        and record["family"] == "cross-source"
    )
    values = defaultdict(set)
    provenance = set()
    for raw in observations:
        observation = BankObservation(**raw)
        if observation.bank not in BANKS:
            raise ValueError("UNKNOWN_CANDIDATE_BANK")
        if observation.value is None:
            raise ValueError("CANDIDATE_EVIDENCE_REQUIRES_STORED_ASSERTION")
        reference = native.get((observation.source, observation.record_id))
        assertion = Assertion(
            observation.bank, observation.value, observation.source, observation.record_id, observation.family
        )
        if (
            reference is None
            or reference.entry_id != observation.entry_id
            or reference.family != observation.family
            or reference.scope != observation.scope
            or assertion not in assertions_for(observation.entry_id)
        ):
            raise ValueError("CANDIDATE_EVIDENCE_PROVENANCE_MISMATCH")
        origin = (
            "model"
            if observation.source.startswith("model:") or observation.family == "model"
            else "derived"
            if observation.source.startswith(("rule:", "derived:")) or observation.family == "derived"
            else "source"
        )
        if observation.origin != origin:
            raise ValueError("CANDIDATE_ORIGIN_MISMATCH")
        if category == "ineligible":
            if observation.origin == "source" and observation.scope == "lexical":
                raise ValueError("ELIGIBLE_EVIDENCE_MARKED_INELIGIBLE")
        else:
            if (
                observation.origin != "source"
                or observation.scope != "lexical"
                or any(
                    getattr(observation, key) != record[key]
                    for key in (("entry_id",) if cross_source else ("entry_id", "source", "family"))
                )
                or observation.bank not in (summary["antecedent"][0], summary["consequent"][0])
            ):
                raise ValueError("INVALID_CANDIDATE_GROUP")
            values[observation.bank].add(observation.value)
            provenance.add(f"{observation.source}:{observation.record_id}")
    if category == "ineligible":
        return set()
    if cross_source:
        expected = set()
        for assertion in assertions_for(record["entry_id"]):
            reference = native.get((assertion.source, assertion.record_id))
            if (
                assertion.bank in (summary["antecedent"][0], summary["consequent"][0])
                and reference is not None
                and reference.entry_id == record["entry_id"]
                and reference.family == assertion.family
                and reference.scope == "lexical"
                and not assertion.source.startswith(("model:", "rule:", "derived:"))
                and assertion.family not in {"model", "derived"}
            ):
                expected.add(
                    BankObservation(
                        record["entry_id"],
                        assertion.bank,
                        assertion.value,
                        assertion.source,
                        assertion.record_id,
                        assertion.family,
                    )
                )
        if {BankObservation(**raw) for raw in observations} != expected:
            raise ValueError("CROSS_SOURCE_CANDIDATE_INCOMPLETE_EVIDENCE")
    (left, a), (right, b) = summary["antecedent"], summary["consequent"]
    left_values, right_values = values[left], values[right]
    if _canonical(identity_form(record["antecedent_values"])) != _canonical(
        identity_form(sorted(left_values))
    ) or _canonical(identity_form(record["consequent_values"])) != _canonical(identity_form(sorted(right_values))):
        raise ValueError("CANDIDATE_DOMAIN_RECEIPT_MISMATCH")
    if len(left_values) > 1:
        expected = ("conflicting", "ANTECEDENT_CONFLICT")
    elif left_values != {a}:
        raise ValueError("CANDIDATE_ANTECEDENT_NOT_ELIGIBLE")
    elif len(right_values) > 1:
        expected = ("conflicting", "CONSEQUENT_CONFLICT")
    elif not right_values:
        expected = ("unknown", "CONSEQUENT_UNOBSERVED")
    elif b in right_values:
        expected = ("support", "OBSERVED_AGREEMENT")
    else:
        expected = ("counterexamples", "OBSERVED_COUNTEREXAMPLE")
    if expected != (category, record["code"]):
        raise ValueError("CANDIDATE_CATEGORY_MISMATCH")
    return provenance if category == "support" else set()


def _candidates_integrity(conn, native, mismatch):
    @lru_cache(maxsize=512)
    def assertions_for(entry_id):
        return frozenset(
            _assertions(
                conn.execute("SELECT ordinal,payload FROM builder_assertions WHERE entry_id=?", (entry_id,)).fetchall()
            )
        )

    for row in conn.execute(
        "SELECT e.rule_id,e.category,e.ordinal FROM candidate_evidence e LEFT JOIN candidate_relations r ON r.rule_id=e.rule_id WHERE r.rule_id IS NULL"
    ):
        mismatch(None, "ORPHAN_CANDIDATE_EVIDENCE", rule_id=row[0], category=row[1], ordinal=row[2])
    seen = set()
    total = 0
    for row in conn.execute("SELECT rule_id,summary FROM candidate_relations ORDER BY rule_id"):
        rule_id = row["rule_id"]
        total += 1
        try:
            if rule_id in seen:
                raise ValueError("DUPLICATE_CANDIDATE_RULE")
            seen.add(rule_id)
            summary = _read_json(row["summary"])
            relation = _candidate_summary(summary, rule_id)
            counts, families, weighted = Counter(), Counter(), Counter()
            support_provenance = set()
            groups = set()
            for evidence in conn.execute(
                "SELECT category,ordinal,payload FROM candidate_evidence WHERE rule_id=? ORDER BY category,ordinal",
                (rule_id,),
            ):
                category = evidence["category"]
                if (
                    category not in _CANDIDATE_CATEGORIES
                    or type(evidence["ordinal"]) is not int
                    or evidence["ordinal"] != counts[category]
                ):
                    raise ValueError("INVALID_CANDIDATE_EVIDENCE_ORDINAL")
                receipt = _read_json(evidence["payload"])
                support_provenance.update(_candidate_receipt(receipt, category, summary, native, assertions_for))
                counts[category] += 1
                if category != "ineligible":
                    group = (receipt["entry_id"], receipt["source"], receipt["family"])
                    if group in groups:
                        raise ValueError("DUPLICATE_CANDIDATE_EVIDENCE_GROUP")
                    groups.add(group)
                    evidence_families = (
                        {item["family"] for item in receipt["observations"]}
                        if receipt["source"] == f"definition:{receipt['entry_id']}"
                        and receipt["family"] == "cross-source"
                        else {receipt["family"]}
                    )
                    for family in sorted(evidence_families):
                        for status in (
                            (category, "eligible") if category in {"support", "counterexamples"} else (category,)
                        ):
                            families[(family, status)] += 1
                            weighted[(family, status)] += receipt["weight"]
                            _candidate_weight(weighted[(family, status)])
            if {category: counts[category] for category in _CANDIDATE_CATEGORIES} != summary["evidence_counts"]:
                raise ValueError("CANDIDATE_EVIDENCE_COUNT_MISMATCH")
            if tuple(sorted(support_provenance)) != relation.provenance:
                raise ValueError("CANDIDATE_SUPPORT_PROVENANCE_MISMATCH")
            for family in set(summary["by_family"]) | {key[0] for key in families}:
                saved = summary["by_family"].get(family, {})
                for status in (*_CANDIDATE_CATEGORIES[:-1], "eligible"):
                    if saved.get(status, 0) != families[(family, status)] or not math.isclose(
                        saved.get(f"weighted_{status}", 0), weighted[(family, status)], rel_tol=1e-12, abs_tol=1e-12
                    ):
                        raise ValueError("CANDIDATE_FAMILY_COUNT_MISMATCH")
        except (TypeError, ValueError, KeyError) as error:
            mismatch(None, "MALFORMED_CANDIDATE", rule_id=rule_id, reason=str(error))
    saved = _optional_metadata(conn, "candidate_relations", None)
    expected = {"table": "candidate_relations", "evidence_table": "candidate_evidence", "records": total}
    if (saved is not None or total) and _canonical(identity_form(saved)) != _canonical(identity_form(expected)):
        mismatch(None, "CANDIDATE_METADATA_MISMATCH")


def _catalog_foundation(links, anchors, models, evidence, restriction_evidence, native):
    """Recover linked native records without conflating their authority with anchors/models."""
    assertions_by_entry, restrictions_by_entry = {}, {}
    for entry_id in {entry for entries in links.values() for entry in entries}:
        remaining_anchors = Counter(anchors.get(entry_id, ()))
        remaining_models = Counter(Assertion(**record["assertion"]) for record in models.get(entry_id, ()))
        assertions = []
        for assertion in _assertions(evidence.get(entry_id, [])):
            if remaining_anchors[assertion]:
                remaining_anchors[assertion] -= 1
            elif remaining_models[assertion]:
                remaining_models[assertion] -= 1
            else:
                validate_assertion_competence(assertion)
                observation = native.get((assertion.source, assertion.record_id))
                if (
                    observation is None
                    or observation.entry_id != entry_id
                    or observation.family != assertion.family
                    or observation.scope != "lexical"
                ):
                    raise ValueError("CATALOG_NATIVE_PROVENANCE_MISMATCH")
                assertions.append(assertion)
        if any(remaining_anchors.values()) or any(remaining_models.values()):
            raise ValueError("UNCONSUMED_CATALOG_ASSERTION_AUTHORITY")
        restrictions = _domain_restrictions(restriction_evidence.get(entry_id, []))
        _restriction_provenance(entry_id, restrictions, native)
        assertions_by_entry[entry_id] = tuple(assertions)
        restrictions_by_entry[entry_id] = restrictions
    return assertions_by_entry, restrictions_by_entry


def _native_catalog(
    anchors,
    relations,
    lexemes,
    links,
    models,
    evidence,
    restriction_evidence,
    native,
    bank_relevance,
    *,
    conn=None,
    legacy_duration=False,
):
    from .catalog import catalog_report
    from .foundation import WORDNET_ANCESTRY_GUARD_PREFIXES

    definitions = tuple(Definition(row["sense_id"], row["lemma"], row["pos"], row["gloss"]) for row in lexemes.values())
    assertions, restrictions = _catalog_foundation(links, anchors, models, evidence, restriction_evidence, native)
    needs_context = any(
        key.startswith((*WORDNET_ANCESTRY_GUARD_PREFIXES, NATIVE_FRAME_PREFIX)) or key == "wordnet_native_lemma"
        for rule in relations
        for key, _ in rule.guards
    )
    if needs_context and conn is None:
        raise ValueError("CATALOG_SOURCE_CONTEXT_REQUIRED")
    observations = (
        {
            definition.entry_id: _context_observations(conn, definition.entry_id, relations, definition)
            for definition in definitions
            if definition.entry_id in assertions
        }
        if needs_context
        else {}
    )
    return catalog_report(
        anchors,
        definitions,
        relations,
        prime_entries=links,
        native_assertions=assertions,
        native_domain_restrictions=restrictions,
        evidence_banks={entry: tuple(sorted(bank_relevance.get(entry, ()))) for entry in assertions},
        observations_by_entry=observations,
        legacy_duration=legacy_duration,
    )


def _catalog_integrity(
    conn, anchors, relations, lexemes, mismatch, models, evidence, restriction_evidence, native, bank_relevance
):
    from .catalog import catalog_report

    saved = _optional_metadata(conn, "catalog", None)
    links = _optional_metadata(conn, "prime_entries", {})
    if saved is None:
        mismatch(None, "CATALOG_METADATA_MISSING")
        return "MISSING"
    try:
        if not isinstance(saved, dict):
            raise ValueError("INVALID_CATALOG_METADATA")
        legacy_duration = any(
            unit["unit_id"] == "nsm:v20:some-time" and unit["mapping"]["code"] == "MISSING" for unit in saved["units"]
        )
        if current_id(saved.get("format")) == "GSE.nsm-catalog-coverage/1":
            definitions = tuple(
                Definition(row["sense_id"], row["lemma"], row["pos"], row["gloss"]) for row in lexemes.values()
            )
            expected = catalog_report(
                anchors, definitions, relations, prime_entries=links, legacy_duration=legacy_duration
            )
        elif current_id(saved.get("format")) == "GSE.nsm-catalog-coverage/2":
            expected = _native_catalog(
                anchors,
                relations,
                lexemes,
                links,
                models,
                evidence,
                restriction_evidence,
                native,
                bank_relevance,
                conn=conn,
                legacy_duration=legacy_duration,
            )
        else:
            raise ValueError("UNSUPPORTED_CATALOG_FORMAT")
        for report in (saved, expected):
            for unit in report["units"]:
                for record in unit["definitions"]:
                    record["definition"].pop("source_ids", None)
        if _canonical(identity_form(saved)) != _canonical(identity_form(expected)):
            raise ValueError("CATALOG_REPLAY_MISMATCH")
    except (TypeError, ValueError, KeyError, AttributeError) as error:
        mismatch(None, "CATALOG_METADATA_MISMATCH", reason=str(error))
        return "MISMATCH"
    return "RECOMPUTED_EXCLUDING_UNPERSISTED_SOURCE_IDS"


def _replay(conn: sqlite3.Connection, relations: tuple[Relation, ...], *, catalog_links: dict | None = None) -> dict:
    mismatches: list[dict] = []

    def mismatch(entry_id, code, **details):
        mismatches.append({"entry_id": entry_id if _identity(entry_id) else None, "code": code, **_diagnostic(details)})

    from .foundation import representation_contract

    convention = _optional_metadata(conn, "convention_version", None)
    representation_verification = "LEGACY_NOT_DECLARED"
    if convention is not None:
        expected_contract = representation_contract()
        if (
            identity_form(convention) != identity_form(expected_contract["version"])
            or identity_form(_optional_metadata(conn, "representation_contract", None))
            != identity_form(expected_contract)
            or identity_form(_optional_metadata(conn, "want_polarity", None))
            != identity_form(expected_contract["want_polarity"])
        ):
            mismatch(None, "REPRESENTATION_CONTRACT_MISMATCH")
            representation_verification = "MISMATCH"
        else:
            representation_verification = "VERIFIED"

    identities = conn.execute("SELECT entry_id,lexeme_id FROM definition_states").fetchall()
    entry_counts = Counter(row[0] for row in identities)
    state_counts = Counter(row[1] for row in identities)
    anchors, models = _authorities(conn)
    from .rule_history import read_history, replay_archives

    rule_history = read_history(conn, relations)
    archived_entries = {
        record["definition"]["entry_id"]
        for event in (rule_history["events"] if rule_history else ())
        for record in event["archived"]
    }
    for entry_id in (set(anchors) | set(models)) - entry_counts.keys():
        mismatch(entry_id, "ORPHAN_ASSERTION_AUTHORITY")
    native, relevant, bank_relevance = _observations(conn, entry_counts, mismatch, set(models) | archived_entries)
    replay_archives(conn, rule_history, native, relevant, anchors)
    _unresolved_integrity(conn, mismatch)
    _candidates_integrity(conn, native, mismatch)
    for entry_id, count in entry_counts.items():
        if not _identity(entry_id):
            mismatch(entry_id, "INVALID_DEFINITION_ID")
        if count != 1:
            mismatch(entry_id, "DUPLICATE_DEFINITION_STATE", rows=count)
    for entry_id, lexeme_id in identities:
        if type(lexeme_id) is not int or lexeme_id <= 0:
            mismatch(entry_id, "INVALID_LEXEME_ID")
        elif state_counts[lexeme_id] != 1:
            mismatch(entry_id, "AMBIGUOUS_LEXEME_LINK", lexeme_id=lexeme_id)

    lexemes: dict[int, sqlite3.Row] = {}
    duplicate_lexemes = set()
    for row in conn.execute("SELECT id,lemma,pos,sense_id,gloss,source,validation_status FROM lexemes"):
        if row["id"] in lexemes:
            duplicate_lexemes.add(row["id"])
            mismatch(row["sense_id"], "DUPLICATE_LEXEME_ID", lexeme_id=row["id"])
        lexemes[row["id"]] = row
        if row["id"] not in state_counts:
            mismatch(row["sense_id"], "LEXEME_WITHOUT_DEFINITION_STATE", lexeme_id=row["id"])

    evidence: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for row in conn.execute("SELECT entry_id,ordinal,payload FROM builder_assertions"):
        if row["entry_id"] not in entry_counts:
            mismatch(row["entry_id"], "ORPHAN_ASSERTION", ordinal=row["ordinal"])
        evidence[row["entry_id"]].append((row["ordinal"], row["payload"]))
    restriction_evidence = defaultdict(list)
    restriction_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='builder_domain_restrictions'"
    ).fetchone()
    restriction_format = _optional_metadata(conn, "domain_restrictions_format", None)
    if restriction_table is None:
        if restriction_format is not None:
            raise ValueError("MISSING_DOMAIN_RESTRICTIONS_TABLE")
    else:
        if current_id(restriction_format) != DOMAIN_RESTRICTIONS_VERSION:
            raise ValueError("UNSUPPORTED_DOMAIN_RESTRICTIONS_FORMAT")
        for row in conn.execute("SELECT entry_id,ordinal,payload FROM builder_domain_restrictions"):
            if row["entry_id"] not in entry_counts:
                mismatch(row["entry_id"], "ORPHAN_DOMAIN_RESTRICTION", ordinal=row["ordinal"])
            restriction_evidence[row["entry_id"]].append((row["ordinal"], row["payload"]))
    projections: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for row in conn.execute("SELECT lexeme_id,primitive,value FROM primitive_values"):
        if row["lexeme_id"] not in state_counts:
            mismatch(None, "ORPHAN_PUBLISHED_ASSIGNMENT", lexeme_id=row["lexeme_id"], bank=row["primitive"])
        projections[row["lexeme_id"]].append((row["primitive"], row["value"]))

    validated = set()
    outcomes: Counter = Counter()
    inference_counts: Counter = Counter()
    for row in conn.execute("SELECT * FROM definition_states ORDER BY entry_id,lexeme_id"):
        entry_id, lexeme_id = row["entry_id"], row["lexeme_id"]
        if not _identity(entry_id) or entry_counts[entry_id] != 1 or state_counts[lexeme_id] != 1:
            continue
        if type(lexeme_id) is not int or lexeme_id <= 0 or lexeme_id in duplicate_lexemes:
            continue
        lexeme = lexemes.get(lexeme_id)
        if lexeme is None:
            mismatch(entry_id, "DEFINITION_WITHOUT_LEXEME", lexeme_id=lexeme_id)
            continue
        start = len(mismatches)
        if lexeme["sense_id"] != entry_id:
            mismatch(entry_id, "DEFINITION_IDENTITY_MISMATCH", stored_sense_id=lexeme["sense_id"])
        if not _identity(lexeme["lemma"]) or not _identity(lexeme["pos"]):
            mismatch(entry_id, "INVALID_LEXICAL_IDENTITY")
            continue
        if current_id(lexeme["source"]) != VERSION:
            mismatch(entry_id, "LEXEME_FORMAT_MISMATCH")
        try:
            assertions = _assertions(evidence[entry_id])
            domain_restrictions = _domain_restrictions(restriction_evidence[entry_id])
            _restriction_provenance(entry_id, domain_restrictions, native)
            definition = Definition(entry_id, lexeme["lemma"], lexeme["pos"], lexeme["gloss"])
            evidence_banks = tuple(sorted(bank_relevance.get(entry_id, ())))
            _provenance(
                entry_id,
                assertions,
                definition,
                relations,
                native,
                relevant,
                anchors,
                models,
                conn,
                evidence_banks,
                domain_restrictions,
                rule_history=rule_history,
            )
            saved_domains = _domains(_read_json(row["domains"]))
            published = _published(projections[lexeme_id])
            hierarchy = _read_json(row["hierarchy"])
            saved_trace = _read_json(row["trace"])
            saved_conflicts = _read_json(row["conflicts"])
            if row["code"] not in {"RESOLVED", "PARTIAL", "CONFLICT"}:
                raise ValueError("INVALID_STORED_RESOLUTION_CODE")
            if not isinstance(hierarchy, dict):
                raise ValueError("INVALID_HIERARCHY")
            if not isinstance(saved_trace, list) or any(not isinstance(record, dict) for record in saved_trace):
                raise ValueError("INVALID_TRACE")
            if not isinstance(saved_conflicts, list) or any(not isinstance(record, dict) for record in saved_conflicts):
                raise ValueError("INVALID_CONFLICT_RECORDS")
            resolution = resolve_dictionary(
                BANKS,
                assertions,
                relations,
                _stored_context(conn, definition, relations),
                evidence_banks=evidence_banks,
                domain_restrictions=domain_restrictions,
            )
        except (ValueError, TypeError) as error:
            mismatch(entry_id, "MALFORMED_ENTRY", reason=str(error))
            continue
        outcomes[resolution.code] += 1
        scope = next(record for record in resolution.trace if record["kind"] == "INFERENCE_SCOPE")
        inference_counts["entries_replayed"] += 1
        inference_counts["entries_complete_search"] += int(scope["complete_search"])
        limited_components = sum(record["kind"] == "SOLVER_LIMIT" for record in resolution.trace)
        inference_counts["entries_solver_limited"] += int(limited_components > 0)
        inference_counts["components_solver_limited"] += limited_components
        inference_counts["components_joint_checked"] += sum(
            record["kind"] == "JOINT_CHECK" for record in resolution.trace
        )
        if resolution.code != row["code"]:
            mismatch(entry_id, "RESOLUTION_CODE_MISMATCH", stored=row["code"], replayed=resolution.code)
        if resolution.domains != saved_domains:
            mismatch(
                entry_id,
                "DOMAIN_MISMATCH",
                banks=sorted(bank for bank in BANKS if resolution.domains[bank] != saved_domains[bank]),
            )
        expected = {} if resolution.code == "CONFLICT" else resolution.assignments
        if published != expected:
            mismatch(entry_id, "PUBLISHED_ASSIGNMENT_MISMATCH", stored=published, replayed=expected)
        if (row["code"] == "CONFLICT" or resolution.code == "CONFLICT") and published:
            mismatch(entry_id, "CONFLICT_PUBLISHED_ASSIGNMENTS")
        expected_status = {"CONFLICT": "rejected", "PARTIAL": "partial", "RESOLVED": "validated"}[resolution.code]
        if lexeme["validation_status"] != expected_status:
            mismatch(entry_id, "LEXEME_STATUS_MISMATCH", stored=lexeme["validation_status"], replayed=expected_status)
        for bank, level in hierarchy.items():
            if bank not in BANKS or type(level) is not int:
                mismatch(entry_id, "INVALID_HIERARCHY_TARGET", bank=bank)
            elif resolution.code == "CONFLICT" or resolution.assignments.get(bank) not in {-1, 1}:
                mismatch(entry_id, "HIERARCHY_WITHOUT_NONZERO_BASE", bank=bank)
        if _canonical(identity_form(saved_trace)) != _canonical(identity_form(resolution.trace)):
            mismatch(entry_id, "TRACE_MISMATCH")
        if _canonical(identity_form(saved_conflicts)) != _canonical(identity_form(resolution.conflicts)):
            mismatch(entry_id, "CONFLICT_RECEIPT_MISMATCH")
        if len(mismatches) == start:
            validated.add(entry_id)
    # Explicit link replacement rebuilds this derived cache from the replayed
    # state below. Requiring the old cache to match first prevents repairing a
    # stale catalogue. Every authoritative input and dictionary check above is
    # still required; ordinary replay continues to verify the saved cache.
    catalog_verification = "REPLACEMENT_NOT_VALIDATED"
    if catalog_links is None:
        catalog_verification = _catalog_integrity(
            conn, anchors, relations, lexemes, mismatch, models, evidence, restriction_evidence, native, bank_relevance
        )
    mismatches.sort(key=lambda item: _canonical(item))
    validated.difference_update(item["entry_id"] for item in mismatches)
    report = {
        "format": "GSE.lexicon-replay-report/1",
        "code": "REPLAY_MISMATCH" if mismatches else "REPLAY_VALIDATED",
        "gold": "NOT_CHECKED",
        "inference_scope": "GENERALIZED_ARC_CONSISTENCY_AND_BOUNDED_JOINT_SUPPORT",
        "complete_search": (
            bool(identities)
            and len(validated) == len(identities)
            and inference_counts["entries_complete_search"] == len(identities)
        ),
        "inference_counts": dict(sorted(inference_counts.items())),
        "metadata_verification": {
            "representation_contract": representation_verification,
            "catalog": catalog_verification,
            "catalog_definition_source_ids": "NOT_PERSISTED",
            "source_diagnostics": "STRUCTURE_AND_COUNTS_CHECKED",
            "domain_restrictions": "SOURCE_PROVENANCE_AND_REPLAY_CHECKED"
            if restriction_table
            else "LEGACY_NO_RESTRICTIONS",
            "candidate_evidence": "STRUCTURE_COUNTS_AND_SOURCE_PROVENANCE_CHECKED",
            "candidate_antecedent_population_counts": "NOT_RECOMPUTED",
            "candidate_weights": "SUMS_CHECKED_ORIGINAL_WEIGHTS_NOT_PERSISTED",
            "build_report": "NOT_CHECKED",
        },
        "entries_checked": len(identities),
        "entries_validated": len(validated),
        "entries_mismatched": len({item["entry_id"] for item in mismatches if item["entry_id"] is not None}),
        "replayed_outcomes": dict(sorted(outcomes.items())),
        "mismatch_counts": dict(sorted(Counter(item["code"] for item in mismatches).items())),
        "mismatches": mismatches,
    }
    if catalog_links is not None and not mismatches:
        # Reuse the one source-observation pass and its validated authority maps.
        # This proposal changes no saved semantics and excludes model assertions.
        report["proposed_catalog"] = _native_catalog(
            anchors,
            relations,
            lexemes,
            catalog_links,
            models,
            evidence,
            restriction_evidence,
            native,
            bank_relevance,
            conn=conn,
        )
        report["metadata_verification"]["catalog"] = "RECOMPUTED_REPLACEMENT_FROM_VALIDATED_STATE"
    return report


def _prime_definition_links(path: str | Path) -> dict[str, tuple[str, ...]]:
    """A complete identity-link replacement; no assertions, rules or definitions."""
    from .interchange import read_json

    raw = read_json(path)
    if (
        not isinstance(raw, dict)
        or set(raw) != {"format", "prime_entries"}
        or current_id(raw["format"]) != "GSE.prime-definition-links/1"
        or not isinstance(raw["prime_entries"], dict)
    ):
        raise ValueError("INVALID_PRIME_DEFINITION_LINKS")
    for unit, entries in raw["prime_entries"].items():
        if not _identity(unit) or not isinstance(entries, list) or any(not _identity(entry) for entry in entries):
            raise ValueError("INVALID_PRIME_DEFINITION_LINKS")
    return {unit: tuple(entries) for unit, entries in raw["prime_entries"].items()}


def _catalog_revision(conn) -> str:
    """Fingerprint saved metadata in addition to the same-connection change counter."""
    digest = hashlib.sha256()
    for key, value in conn.execute("SELECT key,value FROM builder_metadata ORDER BY key"):
        digest.update(_canonical((key, value)).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def refresh_catalog(path: str | Path, links_path: str | Path, *, apply_links: bool = False) -> dict:
    """Replay authoritative state, rebuild the catalog, optionally install metadata.

    The read snapshot's revision must survive obtaining the write lock. A busy
    or changed database is refused, never retried against a different snapshot.
    No source records, dictionary states, bank values or schema are rewritten.
    """
    if type(apply_links) is not bool:
        raise ValueError("INVALID_CATALOG_APPLY_FLAG")
    links = _prime_definition_links(links_path)
    file = Path(path).expanduser().resolve()
    if not file.is_file():
        raise ValueError("BUILD_NOT_FOUND")
    conn = sqlite3.connect(file.as_uri() + ("?mode=rw" if apply_links else "?mode=ro"), uri=True, timeout=0)
    try:
        conn.row_factory = sqlite3.Row
        if not apply_links:
            conn.execute("PRAGMA query_only=ON")
        version = conn.execute("PRAGMA data_version").fetchone()[0]
        conn.execute("BEGIN")
        _schema(conn)
        if current_id(_metadata(conn, "format")) != VERSION:
            raise ValueError("UNSUPPORTED_BUILD_FORMAT")
        revision = _catalog_revision(conn)
        replay = _replay(conn, _relations(_metadata(conn, "relations")), catalog_links=links)
        if replay["code"] != "REPLAY_VALIDATED":
            raise ValueError("CATALOG_REQUIRES_VALID_REPLAY:" + _canonical(replay["mismatch_counts"]))
        if not replay["complete_search"]:
            raise ValueError("CATALOG_REQUIRES_COMPLETE_REPLAY")
        catalog = replay.pop("proposed_catalog")
        result = {
            "format": "GSE.catalog-links-update/1",
            "code": "CATALOG_LINKS_PREVIEW",
            "link_semantics": "COMPLETE_REPLACEMENT",
            "prime_entries": links,
            "catalog": catalog,
            "replay": replay,
            "snapshot_metadata_sha256": revision,
            "dictionary_states": "UNCHANGED",
        }
        if not apply_links:
            return result
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("PRAGMA data_version").fetchone()[0] != version or _catalog_revision(conn) != revision:
            raise ValueError("CATALOG_CONCURRENT_MODIFICATION")
        build_report = _optional_metadata(conn, "last_report", None)
        if not isinstance(build_report, dict):
            raise ValueError("CATALOG_BUILD_REPORT_UNAVAILABLE")
        build_report["foundation_readiness"] = catalog["readiness"]
        build_report["prime_coverage"] = catalog["coverage_counts"]
        for key, value in (("prime_entries", links), ("catalog", catalog), ("last_report", build_report)):
            conn.execute("INSERT OR REPLACE INTO builder_metadata VALUES (?,?)", (key, _canonical(value)))
        conn.commit()
        result["code"] = "CATALOG_LINKS_APPLIED"
        return result
    except sqlite3.DatabaseError as error:
        if getattr(error, "sqlite_errorname", "") in {"SQLITE_BUSY", "SQLITE_LOCKED"}:
            raise ValueError("CATALOG_WRITER_BUSY") from error
        raise ValueError("INVALID_BUILD_DATABASE") from error
    finally:
        conn.close()


def validate_build(path: str | Path) -> dict:
    """Replay an existing build using a read-only SQLite connection.

    Unsupported formats or unreadable global contracts raise named ValueError.
    Malformed entry records produce REPLAY_MISMATCH receipts and are never silently
    coerced into a valid assignment or default zero.
    """
    file = Path(path).expanduser().resolve()
    if not file.is_file():
        raise ValueError("BUILD_NOT_FOUND")
    try:
        conn = sqlite3.connect(file.as_uri() + "?mode=ro", uri=True)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN")
            _schema(conn)
            if current_id(_metadata(conn, "format")) != VERSION:
                raise ValueError("UNSUPPORTED_BUILD_FORMAT")
            relations = _relations(_metadata(conn, "relations"))
            return _replay(conn, relations)
        finally:
            conn.close()
    except sqlite3.DatabaseError as error:
        raise ValueError("INVALID_BUILD_DATABASE") from error
