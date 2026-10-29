"""Replay through actual build/storage entry points and damaged SQLite records."""

import hashlib
import json
import sqlite3

import pytest

from gse.curation.lexicon_builder.engine import Assertion
from gse.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from gse.curation.lexicon_builder.pipeline import build_dictionary
from gse.curation.lexicon_builder.validation import validate_build


@pytest.fixture
def built(tmp_path):
    definitions = (
        Definition("bank:river", "bank", "noun", "the edge of a river"),
        Definition("bank:finance", "bank", "noun", "a financial institution"),
        Definition("conflict:noun", "conflict", "noun", "a deliberately conflicting test entry"),
    )
    observations = tuple(
        Observation(definition.entry_id, "dictionary", definition.entry_id, "dictionary", {}, "lexical")
        for definition in definitions
    )
    assertions = (
        Assertion("SOMETHING", 1, "dictionary", "bank:river", "dictionary"),
        Assertion("SOMETHING", 1, "dictionary", "bank:finance", "dictionary"),
        Assertion("GOOD", 1, "dictionary", "conflict:noun", "dictionary"),
    )
    path = tmp_path / "build.sqlite"
    report = build_dictionary(EvidenceBundle(definitions, observations, assertions, ()), path)
    assert report["outcomes"]["CONFLICT"] == 1
    return path


def modify(path, sql, parameters=()):
    with sqlite3.connect(path) as conn:
        conn.execute(sql, parameters)


def codes(report):
    return {item["code"] for item in report["mismatches"]}


def test_build_replays_with_zero_silence_conflicts_and_distinct_definitions(built):
    before = hashlib.sha256(built.read_bytes()).hexdigest()
    result = validate_build(built)
    assert result["code"] == "REPLAY_VALIDATED"
    assert result["entries_checked"] == result["entries_validated"] == 3
    assert result["entries_mismatched"] == 0
    assert result["gold"] == "NOT_CHECKED"
    assert result["complete_search"] is False
    assert result["replayed_outcomes"] == {"CONFLICT": 1, "PARTIAL": 2}
    assert result["mismatches"] == []
    assert hashlib.sha256(built.read_bytes()).hexdigest() == before


def test_missing_explicit_zero_is_a_published_mismatch(built):
    modify(
        built,
        "DELETE FROM primitive_values WHERE primitive='GOOD' AND lexeme_id=(SELECT id FROM lexemes WHERE sense_id='bank:river')",
    )
    result = validate_build(built)
    assert result["code"] == "REPLAY_MISMATCH"
    assert "PUBLISHED_ASSIGNMENT_MISMATCH" in codes(result)
    assert result["entries_validated"] == 2


def test_unresolved_bank_cannot_be_materialized_as_zero(built):
    modify(
        built,
        "INSERT INTO primitive_values(lexeme_id,primitive,value) SELECT id,'THINK',0 FROM lexemes WHERE sense_id='bank:river'",
    )
    result = validate_build(built)
    assert "PUBLISHED_ASSIGNMENT_MISMATCH" in codes(result)


def test_conflicted_entry_must_publish_nothing(built):
    modify(
        built,
        "INSERT INTO primitive_values(lexeme_id,primitive,value) SELECT id,'SOMETHING',1 FROM lexemes WHERE sense_id='conflict:noun'",
    )
    result = validate_build(built)
    assert "CONFLICT_PUBLISHED_ASSIGNMENTS" in codes(result)


def test_missing_domain_bank_is_malformed_not_unknown_default(built):
    with sqlite3.connect(built) as conn:
        raw = json.loads(
            conn.execute("SELECT domains FROM definition_states WHERE entry_id='bank:river'").fetchone()[0]
        )
        del raw["GOOD"]
        conn.execute("UPDATE definition_states SET domains=? WHERE entry_id='bank:river'", (json.dumps(raw),))
    result = validate_build(built)
    assert "MALFORMED_ENTRY" in codes(result)
    assert any(item.get("reason") == "MISSING_OR_UNKNOWN_DOMAIN_BANK" for item in result["mismatches"])


def test_domain_tampering_is_detected(built):
    with sqlite3.connect(built) as conn:
        raw = json.loads(
            conn.execute("SELECT domains FROM definition_states WHERE entry_id='bank:river'").fetchone()[0]
        )
        raw["THINK"] = [0]
        conn.execute("UPDATE definition_states SET domains=? WHERE entry_id='bank:river'", (json.dumps(raw),))
    result = validate_build(built)
    assert "DOMAIN_MISMATCH" in codes(result)


@pytest.mark.parametrize("value", [True, 1.0, "1", None, 2])
def test_malformed_assertion_value_is_never_coerced(built, value):
    with sqlite3.connect(built) as conn:
        raw = json.loads(
            conn.execute("SELECT payload FROM builder_assertions WHERE entry_id='bank:river'").fetchone()[0]
        )
        raw["value"] = value
        conn.execute("UPDATE builder_assertions SET payload=? WHERE entry_id='bank:river'", (json.dumps(raw),))
    result = validate_build(built)
    assert "MALFORMED_ENTRY" in codes(result)


def test_missing_assertion_changes_replay(built):
    modify(built, "DELETE FROM builder_assertions WHERE entry_id='bank:river'")
    result = validate_build(built)
    assert {"DOMAIN_MISMATCH", "PUBLISHED_ASSIGNMENT_MISMATCH", "TRACE_MISMATCH"} <= codes(result)


def test_trace_and_conflict_receipts_are_checked(built):
    modify(built, "UPDATE definition_states SET trace='[]' WHERE entry_id='bank:river'")
    modify(built, "UPDATE definition_states SET conflicts='[]' WHERE entry_id='conflict:noun'")
    result = validate_build(built)
    assert {"TRACE_MISMATCH", "CONFLICT_RECEIPT_MISMATCH"} <= codes(result)


@pytest.mark.parametrize(
    "hierarchy", [{"GOOD": 2}, {"THINK": 2}, {"SOMETHING": True}, {"SOMETHING": 2.0}, {"NUMBER": 1}]
)
def test_hierarchy_requires_known_nonzero_base_and_integer_level(built, hierarchy):
    modify(built, "UPDATE definition_states SET hierarchy=? WHERE entry_id='bank:river'", (json.dumps(hierarchy),))
    result = validate_build(built)
    assert codes(result) & {"HIERARCHY_WITHOUT_NONZERO_BASE", "INVALID_HIERARCHY_TARGET"}


def test_hierarchy_on_known_nonzero_coordinate_replays(built):
    modify(
        built, "UPDATE definition_states SET hierarchy=? WHERE entry_id='bank:river'", (json.dumps({"SOMETHING": -2}),)
    )
    assert validate_build(built)["code"] == "REPLAY_VALIDATED"


def test_orphan_lexeme_and_assertion_cannot_disappear_in_a_join(built):
    modify(built, "DELETE FROM definition_states WHERE entry_id='bank:river'")
    result = validate_build(built)
    assert {"LEXEME_WITHOUT_DEFINITION_STATE", "ORPHAN_ASSERTION", "ORPHAN_PUBLISHED_ASSIGNMENT"} <= codes(result)


def test_missing_lexeme_is_reported(built):
    modify(built, "DELETE FROM lexemes WHERE sense_id='bank:river'")
    result = validate_build(built)
    assert "DEFINITION_WITHOUT_LEXEME" in codes(result)


def test_ambiguous_entry_linkage_is_not_hidden_by_schema_assumptions(built):
    with sqlite3.connect(built) as conn:
        conn.execute("CREATE TABLE damaged_states AS SELECT * FROM definition_states")
        conn.execute("INSERT INTO damaged_states SELECT * FROM definition_states WHERE entry_id='bank:river'")
        conn.execute("DROP TABLE definition_states")
        conn.execute("ALTER TABLE damaged_states RENAME TO definition_states")
    result = validate_build(built)
    assert {"DUPLICATE_DEFINITION_STATE", "AMBIGUOUS_LEXEME_LINK"} <= codes(result)


def test_unknown_builder_format_is_refused(built):
    modify(built, "UPDATE builder_metadata SET value=? WHERE key='format'", (json.dumps("future/9000"),))
    with pytest.raises(ValueError, match="UNSUPPORTED_BUILD_FORMAT"):
        validate_build(built)


def test_malformed_relation_metadata_is_refused_not_silently_ignored(built):
    with sqlite3.connect(built) as conn:
        raw = json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='relations'").fetchone()[0])
        raw[0]["approved"] = 1
        conn.execute("UPDATE builder_metadata SET value=? WHERE key='relations'", (json.dumps(raw),))
    with pytest.raises(ValueError, match="INVALID_BUILD_RELATION"):
        validate_build(built)


def test_duplicate_json_fields_and_nonfinite_numbers_are_refused(built):
    modify(
        built,
        "UPDATE definition_states SET hierarchy=? WHERE entry_id='bank:river'",
        ('{"SOMETHING":1,"SOMETHING":2}',),
    )
    assert "MALFORMED_ENTRY" in codes(validate_build(built))
    modify(built, "UPDATE definition_states SET hierarchy=? WHERE entry_id='bank:river'", ('{"SOMETHING":1e999}',))
    assert "MALFORMED_ENTRY" in codes(validate_build(built))


def test_missing_file_is_not_created(tmp_path):
    absent = tmp_path / "missing.sqlite"
    with pytest.raises(ValueError, match="BUILD_NOT_FOUND"):
        validate_build(absent)
    assert not absent.exists()


def test_non_database_file_refused(tmp_path):
    file = tmp_path / "not.sqlite"
    file.write_text("not a SQLite database")
    with pytest.raises(ValueError, match="INVALID_BUILD_DATABASE"):
        validate_build(file)


@pytest.mark.parametrize("field,value", [("source", "forged"), ("record_id", "bank:finance"), ("family", "forged")])
def test_assertion_exact_native_provenance_is_required(built, field, value):
    with sqlite3.connect(built) as conn:
        record = json.loads(
            conn.execute("SELECT payload FROM builder_assertions WHERE entry_id='bank:river'").fetchone()[0]
        )
        record[field] = value
        conn.execute("UPDATE builder_assertions SET payload=? WHERE entry_id='bank:river'", (json.dumps(record),))
    assert any(item.get("reason") == "ASSERTION_PROVENANCE_MISMATCH" for item in validate_build(built)["mismatches"])


def test_missing_native_record_is_not_self_authorizing(built):
    modify(built, "DELETE FROM source_observations WHERE entry_id='bank:river'")
    assert any(item.get("reason") == "ASSERTION_PROVENANCE_MISMATCH" for item in validate_build(built)["mismatches"])


def test_native_observation_columns_must_match_payload(built):
    modify(built, "UPDATE source_observations SET family='forged' WHERE entry_id='bank:river'")
    report = validate_build(built)
    assert "MALFORMED_OBSERVATION" in codes(report)
    assert report["entries_validated"] == 2


def test_nonlexical_observation_cannot_authorize_assertion(built):
    with sqlite3.connect(built) as conn:
        record = json.loads(
            conn.execute("SELECT payload FROM source_observations WHERE entry_id='bank:river'").fetchone()[0]
        )
        record["scope"] = "association"
        conn.execute(
            "UPDATE source_observations SET scope=?,payload=? WHERE entry_id='bank:river'",
            ("association", json.dumps(record)),
        )
    assert any(item.get("reason") == "ASSERTION_PROVENANCE_MISMATCH" for item in validate_build(built)["mismatches"])


def test_ambiguous_native_record_is_rejected(built):
    with sqlite3.connect(built) as conn:
        conn.execute("CREATE TABLE damaged_observations AS SELECT * FROM source_observations")
        conn.execute("INSERT INTO damaged_observations SELECT * FROM source_observations WHERE entry_id='bank:river'")
        conn.execute("DROP TABLE source_observations")
        conn.execute("ALTER TABLE damaged_observations RENAME TO source_observations")
    assert "MALFORMED_OBSERVATION" in codes(validate_build(built))


def test_anchor_authority_is_explicit_metadata_not_source_name(tmp_path):
    from dataclasses import asdict

    definition = Definition("anchor:test", "test", "verb", "a test definition")
    anchor = Assertion("THINK", 1, "a cited declaration", "an exact source section", "declared")
    manifest = tmp_path / "rules.json"
    manifest.write_text(
        json.dumps({"format": "gse.lexicon-rules/1", "anchors": {definition.entry_id: [asdict(anchor)]}})
    )
    path = tmp_path / "anchors.sqlite"
    build_dictionary(EvidenceBundle((definition,), (), (), ()), path, manifest=manifest)
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"
    modify(path, "DELETE FROM builder_metadata WHERE key='anchors'")
    assert any(item.get("reason") == "ASSERTION_PROVENANCE_MISMATCH" for item in validate_build(path)["mismatches"])


@pytest.fixture
def modeled(tmp_path):
    definition = Definition("model:test", "test", "verb", "a test definition")
    observation = Observation(
        definition.entry_id, "dictionary", "native:test", "dictionary", {"meaning": "test"}, "source_structure"
    )
    path = tmp_path / "model.sqlite"
    build_dictionary(
        EvidenceBundle((definition,), (observation,), (), ()),
        path,
        transport=lambda payload, schema: json.dumps({payload["bank"]: 0}),
        max_model_calls=1,
    )
    return path


def test_model_receipt_replays_narrow_missing_coordinate(modeled):
    assert validate_build(modeled)["code"] == "REPLAY_VALIDATED"


@pytest.mark.parametrize("part", ["request_id", "schema", "observations", "definition", "known"])
def test_model_authority_cannot_bypass_request_replay(modeled, part):
    with sqlite3.connect(modeled) as conn:
        records = json.loads(
            conn.execute("SELECT value FROM builder_metadata WHERE key='model_completions'").fetchone()[0]
        )
        receipt = records[0]
        if part == "request_id":
            receipt["request_id"] = "forged"
        elif part == "schema":
            receipt["schema"]["additionalProperties"] = True
        elif part == "observations":
            receipt["request"]["observations"] = []
        elif part == "definition":
            receipt["request"]["definition"]["definition"] = "a different meaning"
        else:
            receipt["request"]["known"] = {"THINK": 0}
        conn.execute("UPDATE builder_metadata SET value=? WHERE key='model_completions'", (json.dumps(records),))
    if part == "request_id":
        with pytest.raises(ValueError, match="INVALID_MODEL_AUTHORITY"):
            validate_build(modeled)
    else:
        assert validate_build(modeled)["code"] == "REPLAY_MISMATCH"


def test_model_source_name_without_accepted_receipt_has_no_authority(modeled):
    modify(modeled, "DELETE FROM builder_metadata WHERE key='model_completions'")
    assert any(item.get("reason") == "ASSERTION_PROVENANCE_MISMATCH" for item in validate_build(modeled)["mismatches"])


def test_conflict_hierarchy_is_not_published(built):
    modify(built, "UPDATE definition_states SET hierarchy=? WHERE entry_id='conflict:noun'", (json.dumps({"GOOD": 1}),))
    assert "HIERARCHY_WITHOUT_NONZERO_BASE" in codes(validate_build(built))


def test_model_cannot_precede_native_symbolic_evidence(modeled):
    from dataclasses import asdict

    source = Assertion("THINK", 1, "dictionary", "native:late", "dictionary")
    observation = Observation("model:test", "dictionary", "native:late", "dictionary", {}, "lexical")
    with sqlite3.connect(modeled) as conn:
        conn.execute(
            "INSERT INTO source_observations VALUES (?,?,?,?,?,?)",
            (
                observation.record_id,
                observation.entry_id,
                observation.source,
                observation.family,
                observation.scope,
                json.dumps(asdict(observation)),
            ),
        )
        conn.execute("INSERT INTO builder_assertions VALUES (?,?,?)", ("model:test", 1, json.dumps(asdict(source))))
        records = json.loads(
            conn.execute("SELECT value FROM builder_metadata WHERE key='model_completions'").fetchone()[0]
        )
        # Supply the newly visible observation and regenerate the content hash;
        # this still cannot grant permission to defer its lexical assertion.
        payload = records[0]["request"]
        payload["observations"].append(asdict(observation))
        request_id = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        records[0]["request_id"] = request_id
        records[0]["assertion"]["record_id"] = request_id
        conn.execute(
            "UPDATE builder_assertions SET payload=? WHERE entry_id='model:test' AND ordinal=0",
            (json.dumps(records[0]["assertion"]),),
        )
        conn.execute("UPDATE builder_metadata SET value=? WHERE key='model_completions'", (json.dumps(records),))
    assert any(item.get("reason") == "MODEL_BEFORE_SYMBOLIC_EVIDENCE" for item in validate_build(modeled)["mismatches"])


def test_replay_streams_feature_payloads_without_retaining_corpus_copies(built):
    import tracemalloc
    from dataclasses import asdict

    feature_size = 128 * 1024
    with sqlite3.connect(built) as conn:
        for index in range(100):
            observation = Observation(
                "bank:river",
                "large-native",
                f"large:{index}",
                "large-native",
                {"complete_native_text": "x" * feature_size},
                "source_structure",
            )
            conn.execute(
                "INSERT INTO source_observations VALUES (?,?,?,?,?,?)",
                (
                    observation.record_id,
                    observation.entry_id,
                    observation.source,
                    observation.family,
                    observation.scope,
                    json.dumps(asdict(observation)),
                ),
            )
    tracemalloc.start()
    try:
        report = validate_build(built)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert report["code"] == "REPLAY_VALIDATED"
    # The input carries >12MiB of features. Streaming holds one complete row,
    # not a persistent parsed corpus or an asdict copy for every definition.
    assert peak < 4 * 1024 * 1024


def test_model_replay_rejects_new_conditional_exceptions(tmp_path):
    from dataclasses import asdict

    from gse.curation.lexicon_builder.engine import Relation
    from gse.curation.lexicon_builder.foundation import BANKS
    from gse.curation.lexicon_builder.residual import build_request
    from gse.curation.lexicon_builder.resolution import resolve_dictionary
    from gse.curation.lexicon_builder.storage import store_entry

    definition = Definition("odd:cycle", "cycle", "verb", "synthetic conditional cycle")
    rules = tuple(
        Relation(f"conditional:{i}", pair, ((-1, 1), (1, -1)), ("fixture",), "conditional", True)
        for i, pair in enumerate((("THINK", "KNOW"), ("KNOW", "FEEL"), ("FEEL", "THINK")))
    )
    manifest = tmp_path / "rules.json"
    manifest.write_text(json.dumps({"format": "gse.lexicon-rules/1", "relations": [asdict(rule) for rule in rules]}))
    path = tmp_path / "cycle.sqlite"
    build_dictionary(EvidenceBundle((definition,), (), (), ()), path, manifest=manifest)
    with sqlite3.connect(path) as conn:
        raw = json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='relations'").fetchone()[0])
        relations = tuple(
            Relation(
                record["rule_id"],
                tuple(record["banks"]),
                tuple(tuple(row) for row in record["allowed_rows"]),
                tuple(record["provenance"]),
                record["authority"],
                record["approved"],
                tuple(tuple(g) for g in record["guards"]),
            )
            for record in raw
        )
        before = resolve_dictionary(BANKS, (), relations, {"pos": "verb"})
        request = build_request(definition.entry_id, "THINK", before, (), definition=definition)
        assertion = Assertion("THINK", 1, "model:forged", request.request_id, "model")
        after = resolve_dictionary(BANKS, (assertion,), relations, {"pos": "verb"})
        assert after.code == "PARTIAL"
        store_entry(conn, definition, after, (assertion,))
        receipts = [
            {
                "entry_id": definition.entry_id,
                "assertion": asdict(assertion),
                "request_id": request.request_id,
                "code": "ASSIGNED",
                "request": request.payload(),
                "schema": request.output_schema(),
            }
        ]
        conn.execute("UPDATE builder_metadata SET value=? WHERE key='model_completions'", (json.dumps(receipts),))
    assert any(item.get("reason") == "MODEL_ADDED_CONDITIONAL_EXCEPTION" for item in validate_build(path)["mismatches"])


@pytest.fixture
def discovered(tmp_path):
    definition = Definition("candidate:noun", "candidate", "noun", "synthetic discovery fixture")
    observation = Observation(definition.entry_id, "native", "record:native", "family", {}, "lexical")
    assertions = tuple(
        Assertion(bank, value, "native", observation.record_id, "family")
        for bank, value in (("SOMETHING", 1), ("THINK", 1), ("GOOD", 0))
    )
    path = tmp_path / "discovered.sqlite"
    build_dictionary(
        EvidenceBundle(
            (definition,),
            (observation,),
            assertions,
            ({"code": "TEST_DIAGNOSTIC", "record_id": observation.record_id},),
        ),
        path,
        discover=True,
    )
    return path


def test_normalized_diagnostics_and_candidates_replay(discovered):
    report = validate_build(discovered)
    assert report["code"] == "REPLAY_VALIDATED"
    assert report["metadata_verification"]["candidate_evidence"] == "STRUCTURE_COUNTS_AND_SOURCE_PROVENANCE_CHECKED"
    assert report["metadata_verification"]["candidate_antecedent_population_counts"] == "NOT_RECOMPUTED"


@pytest.mark.parametrize("change", ["approved", "counts", "family_counts", "relation_table"])
def test_candidate_summary_tampering_is_reported(discovered, change):
    with sqlite3.connect(discovered) as conn:
        rule_id, payload = conn.execute(
            "SELECT rule_id,summary FROM candidate_relations ORDER BY rule_id LIMIT 1"
        ).fetchone()
        summary = json.loads(payload)
        if change == "approved":
            summary["relation"]["approved"] = True
        elif change == "counts":
            summary["evidence_counts"]["support"] += 1
        elif change == "family_counts":
            summary["by_family"]["family"]["support"] += 1
        else:
            summary["relation"]["allowed_rows"] = [[0, 0]]
        conn.execute("UPDATE candidate_relations SET summary=? WHERE rule_id=?", (json.dumps(summary), rule_id))
    assert "MALFORMED_CANDIDATE" in codes(validate_build(discovered))


@pytest.mark.parametrize("change", ["source", "value", "category", "ordinal", "missing"])
def test_candidate_evidence_tampering_is_reported(discovered, change):
    with sqlite3.connect(discovered) as conn:
        rule_id, category, ordinal, payload = conn.execute(
            "SELECT rule_id,category,ordinal,payload FROM candidate_evidence ORDER BY rule_id,category,ordinal LIMIT 1"
        ).fetchone()
        if change in {"source", "value"}:
            receipt = json.loads(payload)
            receipt["observations"][0][change] = (
                "forged"
                if change == "source"
                else -receipt["observations"][0]["value"]
                if receipt["observations"][0]["value"]
                else 1
            )
            conn.execute(
                "UPDATE candidate_evidence SET payload=? WHERE rule_id=? AND category=? AND ordinal=?",
                (json.dumps(receipt), rule_id, category, ordinal),
            )
        elif change == "category":
            conn.execute(
                "UPDATE candidate_evidence SET category=? WHERE rule_id=? AND category=? AND ordinal=?",
                ("unknown", rule_id, category, ordinal),
            )
        elif change == "ordinal":
            conn.execute(
                "UPDATE candidate_evidence SET ordinal=? WHERE rule_id=? AND category=? AND ordinal=?",
                (ordinal + 1, rule_id, category, ordinal),
            )
        else:
            conn.execute(
                "DELETE FROM candidate_evidence WHERE rule_id=? AND category=? AND ordinal=?",
                (rule_id, category, ordinal),
            )
    assert "MALFORMED_CANDIDATE" in codes(validate_build(discovered))


def test_orphan_candidate_evidence_and_metadata_count_are_checked(discovered):
    modify(
        discovered,
        "UPDATE candidate_evidence SET rule_id=? WHERE rowid=(SELECT rowid FROM candidate_evidence LIMIT 1)",
        ("missing:rule",),
    )
    modify(
        discovered,
        "UPDATE builder_metadata SET value=? WHERE key='candidate_relations'",
        (json.dumps({"table": "candidate_relations", "evidence_table": "candidate_evidence", "records": 100000}),),
    )
    assert {"ORPHAN_CANDIDATE_EVIDENCE", "CANDIDATE_METADATA_MISMATCH"} <= codes(validate_build(discovered))


@pytest.mark.parametrize("change", ["code", "ordinal", "delete"])
def test_unresolved_diagnostics_corruption_is_reported(discovered, change):
    if change == "code":
        modify(discovered, "UPDATE unresolved_sources SET code='FORGED'")
    elif change == "ordinal":
        modify(discovered, "UPDATE unresolved_sources SET ordinal=100")
    else:
        modify(discovered, "DELETE FROM unresolved_sources")
    report = validate_build(discovered)
    assert "SOURCE_DIAGNOSTIC_METADATA_MISMATCH" in codes(report) or "MALFORMED_SOURCE_DIAGNOSTIC" in codes(report)


@pytest.mark.parametrize("change", ["coverage", "prime_entries", "delete"])
def test_catalog_metadata_is_recomputed_not_trusted(built, change):
    with sqlite3.connect(built) as conn:
        if change == "coverage":
            record = json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='catalog'").fetchone()[0])
            record["readiness"]["gold"] = "VALIDATED"
            conn.execute("UPDATE builder_metadata SET value=? WHERE key='catalog'", (json.dumps(record),))
        elif change == "prime_entries":
            conn.execute(
                "UPDATE builder_metadata SET value=? WHERE key='prime_entries'",
                (json.dumps({"unknown:unit": ["bank:river"]}),),
            )
        else:
            conn.execute("DELETE FROM builder_metadata WHERE key='catalog'")
    assert codes(validate_build(built)) & {"CATALOG_METADATA_MISMATCH", "CATALOG_METADATA_MISSING"}


def test_oversized_candidate_weight_is_reported_without_numeric_overflow(discovered):
    with sqlite3.connect(discovered) as conn:
        rule_id, category, ordinal, payload = conn.execute(
            "SELECT rule_id,category,ordinal,payload FROM candidate_evidence LIMIT 1"
        ).fetchone()
        record = json.loads(payload)
        record["weight"] = 10**500
        conn.execute(
            "UPDATE candidate_evidence SET payload=? WHERE rule_id=? AND category=? AND ordinal=?",
            (json.dumps(record), rule_id, category, ordinal),
        )
    assert any(item.get("reason") == "INVALID_CANDIDATE_WEIGHT" for item in validate_build(discovered)["mismatches"])


def test_native_source_scope_cannot_be_bypassed_with_matching_provenance(tmp_path):

    from gse.curation.lexicon_builder.foundation import BANKS, projection_relations
    from gse.curation.lexicon_builder.resolution import resolve_dictionary
    from gse.curation.lexicon_builder.storage import store_entry

    definition = Definition("scope:verb", "act", "verb", "synthetic scope tampering fixture")
    observation = Observation(definition.entry_id, "sentiwordnet", "scope:record", "wordnet", {}, "lexical")
    path = tmp_path / "scope.sqlite"
    build_dictionary(EvidenceBundle((definition,), (observation,), (), ()), path)
    assertion = Assertion("DO", 1, observation.source, observation.record_id, observation.family)
    resolution = resolve_dictionary(BANKS, (assertion,), projection_relations(), {"pos": "verb"})
    with sqlite3.connect(path) as conn:
        store_entry(conn, definition, resolution, (assertion,))
    report = validate_build(path)
    assert report["code"] == "REPLAY_MISMATCH"
    assert any(item.get("reason") == "ASSERTION_OUTSIDE_SOURCE_SCOPE" for item in report["mismatches"])
