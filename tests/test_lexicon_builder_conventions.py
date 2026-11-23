"""Approved conventions retain evidence guards through build, storage, and replay."""

import json
import sqlite3
from dataclasses import asdict

import pytest

from GSE.curation.lexicon_builder.engine import Assertion, Relation
from GSE.curation.lexicon_builder.evidence import Definition, EvidenceBundle, Observation
from GSE.curation.lexicon_builder.foundation import BANKS, load_manifest, projection_relations
from GSE.curation.lexicon_builder.pipeline import build_dictionary
from GSE.curation.lexicon_builder.storage import read_entries
from GSE.curation.lexicon_builder.validation import validate_build


def classified(*banks):
    return {"bank_relevance": {"code": "CLASSIFIED", "banks": list(banks), "provenance": ["fixture:reviewed-scope"]}}


def build_case(
    tmp_path,
    values,
    *,
    features=None,
    pos="adjective",
    extra_observations=(),
    manifest=None,
    transport=None,
    max_model_calls=0,
):
    definition = Definition("fixture:definition", "example", pos, "the designated test meaning")
    observation = Observation(
        definition.entry_id,
        "fixture-dictionary",
        "fixture:record",
        "fixture-family",
        {} if features is None else features,
        "lexical",
    )
    assertions = tuple(
        Assertion(bank, value, observation.source, observation.record_id, observation.family)
        for bank, value in values.items()
    )
    bundle = EvidenceBundle((definition,), (observation,) + extra_observations, assertions, ())
    path = tmp_path / "conventions.sqlite"
    report = build_dictionary(bundle, path, manifest=manifest, transport=transport, max_model_calls=max_model_calls)
    with sqlite3.connect(path) as conn:
        entry = read_entries(conn)[0]
    return path, report, entry


def guard(entry, rule_id="founder:absence:good-big"):
    return next(
        record for record in entry["trace"] if record["kind"] == "EVIDENCE_GUARD" and record["rule_id"] == rule_id
    )


def assert_replays(path):
    result = validate_build(path)
    assert result["code"] == "REPLAY_VALIDATED", result["mismatches"]


CATEGORY_CASES = (
    ("I", 1, "SOMEONE", "pronoun"),
    ("YOU", 1, "SOMEONE", "pronoun"),
    ("BODY", 1, "SOMETHING", "noun"),
    ("ONE", 1, "QUANTITY", "numeral"),
    ("TWO", 1, "QUANTITY", "numeral"),
    ("MOVE", 1, "HAPPEN", "verb"),
    ("DO", 1, "HAPPEN", "verb"),
    ("CAUSE", 1, "HAPPEN", "verb"),
    ("THEN", -1, "WHEN", "adverb"),
    ("BEFORE", -1, "WHEN", "adverb"),
    ("LONG_TIME", -1, "WHEN", "adverb"),
    ("MOMENT", 1, "WHEN", "noun"),
    ("ABOVE", -1, "WHERE", "adverb"),
    ("FAR", -1, "WHERE", "adverb"),
    ("OUTSIDE", -1, "WHERE", "adverb"),
    ("TOWARD", -1, "WHERE", "adverb"),
    ("HERE", 1, "WHERE", "adverb"),
    ("SIDE", 1, "WHERE", "noun"),
)


@pytest.mark.parametrize("specific,value,general,pos", CATEGORY_CASES)
def test_all_eighteen_category_relations_build_and_replay(tmp_path, specific, value, general, pos):
    path, _, entry = build_case(tmp_path, {specific: value}, features=classified(specific), pos=pos)
    assert entry["assignments"][specific] == value
    assert entry["assignments"][general] == 1
    assert any(
        record["kind"] == "RELATION"
        and record.get("rule_id") == f"founder:category:{specific.lower()}-{general.lower()}"
        for record in entry["trace"]
    )
    assert_replays(path)


def test_category_content_is_ordinary_information_not_an_absence_default():
    categories = [rule for rule in projection_relations() if rule.rule_id.startswith("founder:category:")]
    assert len(categories) == 18
    assert all(rule.approved and not rule.absent_evidence for rule in categories)


@pytest.mark.parametrize("value", [-1, 1])
def test_evaluative_size_default_with_reviewed_scope_builds_and_replays(tmp_path, value):
    path, _, entry = build_case(tmp_path, {"GOOD": value}, features=classified("GOOD"))
    assert entry["assignments"]["GOOD"] == value
    assert entry["assignments"]["BIG"] == 0
    assert guard(entry)["status"] == "ELIGIBLE"
    assert guard(entry)["relation"]["absent_evidence"] == ["BIG"]
    assert_replays(path)


def test_unclassified_native_encoding_blocks_absence_even_without_size_sign(tmp_path):
    path, _, entry = build_case(tmp_path, {"GOOD": 1})
    assert "BIG" not in entry["assignments"]
    assert guard(entry)["reason"] == "RELEVANT_EVIDENCE"
    assert guard(entry)["witnesses"][0]["supplied_evidence"] is True
    assert_replays(path)


def test_classified_unknown_size_blocks_absence_without_inventing_value(tmp_path):
    path, _, entry = build_case(tmp_path, {"GOOD": 1}, features=classified("GOOD", "BIG"))
    assert "BIG" not in entry["assignments"]
    assert entry["domains"]["BIG"] == [-1, 0, 1]
    assert guard(entry)["status"] == "BLOCKED"
    assert_replays(path)


@pytest.mark.parametrize("value", [-1, 0, 1])
def test_known_size_is_preserved_without_default_fallback_exception(tmp_path, value):
    path, _, entry = build_case(tmp_path, {"GOOD": 1, "BIG": value}, features=classified("GOOD"))
    assert entry["assignments"]["BIG"] == value
    assert entry["assignments"]["GOOD"] == 1
    assert guard(entry)["status"] == "BLOCKED"
    assert not any(record["kind"] == "CONDITIONAL_EXCEPTION" for record in entry["trace"])
    assert_replays(path)


def test_candidate_definition_link_retains_relevant_unknown_encoding(tmp_path):
    candidate = Observation(
        None,
        "other-dictionary",
        "candidate:record",
        "other-family",
        classified("BIG"),
        "source_structure",
        ("fixture:definition",),
    )
    path, _, entry = build_case(tmp_path, {"GOOD": 1}, features=classified("GOOD"), extra_observations=(candidate,))
    assert "BIG" not in entry["assignments"]
    assert guard(entry)["reason"] == "RELEVANT_EVIDENCE"
    assert_replays(path)


def test_independent_ordinary_size_rule_blocks_default_before_firing(tmp_path):
    relation = Relation("fixture:size", ("BIG",), ((1,),), ("fixture:size-evidence",), "foundational", True)
    manifest = tmp_path / "rules.json"
    manifest.write_text(json.dumps({"format": "GSE.lexicon-rules/1", "relations": [asdict(relation)]}))
    path, _, entry = build_case(tmp_path, {"GOOD": 1}, features=classified("GOOD"), manifest=manifest)
    assert entry["assignments"]["GOOD"] == entry["assignments"]["BIG"] == 1
    assert guard(entry)["witnesses"][0]["baseline_rule_ids"] == ["fixture:size"]
    assert not any(record["kind"] == "CONDITIONAL_EXCEPTION" for record in entry["trace"])
    assert_replays(path)


def test_noun_scope_does_not_apply_adjective_default(tmp_path):
    path, _, entry = build_case(tmp_path, {}, features=classified(), pos="noun")
    assert entry["assignments"]["GOOD"] == 0
    assert "BIG" not in entry["assignments"]
    assert guard(entry)["reason"] == "GUARD_MISMATCH"
    assert_replays(path)


def test_older_relation_manifest_and_serialized_record_omit_absence_field(tmp_path):
    legacy = {
        "rule_id": "fixture:legacy",
        "banks": ["THINK"],
        "allowed_rows": [[1]],
        "provenance": ["fixture:legacy"],
        "approved": True,
    }
    manifest = tmp_path / "legacy.json"
    manifest.write_text(json.dumps({"format": "GSE.lexicon-rules/1", "relations": [legacy]}))
    assert load_manifest(manifest)[0][0].absent_evidence == ()
    path, _, entry = build_case(tmp_path, {}, features=classified(), manifest=manifest)
    assert entry["assignments"]["THINK"] == 1
    with sqlite3.connect(path) as conn:
        records = json.loads(conn.execute("SELECT value FROM builder_metadata WHERE key='relations'").fetchone()[0])
        for record in records:
            if not record["absent_evidence"]:
                del record["absent_evidence"]
        conn.execute("UPDATE builder_metadata SET value=? WHERE key='relations'", (json.dumps(records),))
    assert_replays(path)


@pytest.mark.parametrize(
    "annotation",
    [
        None,
        {},
        {"code": "CLASSIFIED", "banks": ["BIG"], "provenance": []},
        {"code": "CLASSIFIED", "banks": ["BIG", "BIG"], "provenance": ["fixture"]},
        {"code": "CLASSIFIED", "banks": ["SMALL"], "provenance": ["fixture"]},
        {"code": "CLASSIFIED", "banks": ["NO_SUCH_BANK"], "provenance": ["fixture"]},
    ],
)
def test_malformed_relevance_fails_before_creating_build(tmp_path, annotation):
    with pytest.raises(ValueError, match="BANK_RELEVANCE"):
        build_case(tmp_path, {"GOOD": 1}, features={"bank_relevance": annotation})
    assert not (tmp_path / "conventions.sqlite").exists()


def test_saved_relevance_change_is_detected_by_replay(tmp_path):
    path, _, _ = build_case(tmp_path, {"GOOD": 1}, features=classified("GOOD", "BIG"))
    with sqlite3.connect(path) as conn:
        record = json.loads(conn.execute("SELECT payload FROM source_observations").fetchone()[0])
        record["features"] = classified("GOOD")
        conn.execute("UPDATE source_observations SET payload=?", (json.dumps(record),))
    result = validate_build(path)
    assert result["code"] == "REPLAY_MISMATCH"
    assert {"DOMAIN_MISMATCH", "TRACE_MISMATCH", "PUBLISHED_ASSIGNMENT_MISMATCH"} <= {
        r["code"] for r in result["mismatches"]
    }


def test_model_can_fill_relevant_unknown_size_without_touching_known_evaluation(tmp_path):
    def transport(payload, schema):
        assert set(schema["properties"]) == {payload["bank"]}
        return json.dumps({payload["bank"]: 1 if payload["bank"] == "BIG" else None})

    path, report, entry = build_case(
        tmp_path, {"GOOD": 1}, features=classified("GOOD", "BIG"), transport=transport, max_model_calls=len(BANKS)
    )
    assert report["model_outcomes"]["ASSIGNED"] == 1
    assert entry["assignments"]["GOOD"] == entry["assignments"]["BIG"] == 1
    assert_replays(path)


def test_model_cannot_remove_known_default_when_new_evidence_blocks_its_guard(tmp_path):
    default = Relation("fixture:default", ("BIG",), ((0,),), ("fixture:scope",), "conditional", True, (), ("FEEL",))
    manifest = tmp_path / "default.json"
    manifest.write_text(json.dumps({"format": "GSE.lexicon-rules/1", "relations": [asdict(default)]}))

    def transport(payload, schema):
        return json.dumps({payload["bank"]: 1 if payload["bank"] == "FEEL" else None})

    path, report, entry = build_case(
        tmp_path, {}, features=classified(), manifest=manifest, transport=transport, max_model_calls=len(BANKS)
    )
    assert report["model_outcomes"]["CONTRADICTION"] == 1
    assert entry["assignments"]["BIG"] == 0
    assert "FEEL" not in entry["assignments"]
    assert_replays(path)
