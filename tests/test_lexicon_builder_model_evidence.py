"""Model context compression must not change evidence or fabricate absence."""

import copy
import hashlib
import json

import pytest

from gse.curation.lexicon_builder.model_evidence import evidence_view


def record(source="wordnet_hierarchy", features=None, **kwargs):
    return {
        "entry_id": "definition:a",
        "source": source,
        "record_id": "native:one",
        "family": "fixture",
        "scope": "source_structure",
        "candidate_entry_ids": ["definition:a", "definition:b"],
        "features": {} if features is None else features,
        **kwargs,
    }


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def test_empty_and_tiny_views_are_explicitly_partial_without_filling():
    empty = evidence_view([], "WANT")
    assert empty["records"] == empty["excluded_sources"] == []
    assert empty["record_count"] == 0
    raw = record(features={"definition": "not wanting to do something", "lemma": "reluctant"})
    view = evidence_view([raw], "WANT")
    summary = view["records"][0]
    assert view["code"] == "PARTIAL_TYPED_VIEW"
    assert view["omission_semantics"] == "OMITTED_IS_NOT_ZERO"
    assert summary["features"] == raw["features"]
    assert summary["full_record_sha256"] == digest(raw)
    assert summary["candidate_entry_ids"] == raw["candidate_entry_ids"]
    assert summary["omitted_fields"] == []
    assert not {"fill", "assignments", "allowed_values"} & view.keys()


def test_omitted_fields_are_named_and_full_digest_covers_omissions():
    raw = record(
        features={
            "definition": "a long exact definition" * 100,
            "examples": ["usage"],
            "native_records": [{"word": "reluctant"}],
            "future/field~": {"data": "not yet recognized"},
        },
        new_envelope_field=9,
    )
    summary = evidence_view([raw], "WANT")["records"][0]
    omitted = {item["field"]: item["code"] for item in summary["omitted_fields"]}
    assert summary["features"] == {"definition": raw["features"]["definition"]}
    assert omitted == {
        "/features/examples": "USAGE_EXAMPLES_NOT_INCLUDED_IN_DEFINITION_VIEW",
        "/features/native_records": "DUPLICATED_NATIVE_RECORDS_NOT_INCLUDED",
        "/features/future~1field~0": "UNKNOWN_FIELD_NOT_IN_MODEL_VIEW_SCHEMA",
        "/new_envelope_field": "UNKNOWN_FIELD_NOT_IN_MODEL_VIEW_SCHEMA",
    }
    altered = copy.deepcopy(raw)
    altered["features"]["examples"] = ["different"]
    assert evidence_view([altered], "WANT")["records"][0]["full_record_sha256"] != summary["full_record_sha256"]


@pytest.mark.parametrize(
    "source,features",
    [
        (
            "sentiwordnet",
            {"word": "a", "pos": "adj", "pos_score": 0.4, "neg_score": 0.5, "obj_score": 0.1, "synset_id": "a.a.01"},
        ),
        ("nrc_emotion", {"word": "a", "emotions": {"joy": 1, "sadness": 1, "fear": 0}}),
        (
            "nrc_vad",
            {
                "word": "a",
                "valence": -0.6,
                "arousal": 0.2,
                "dominance": -0.1,
                "native_version": "2",
                "native_scale": [-1, 1],
                "native_header": ["term", "valence", "arousal", "dominance"],
            },
        ),
        ("usas", {"lemma": "a", "pos": None, "semantic_tags": ["A1", "B2"]}),
        ("concreteness", {"word": "a", "concreteness": 1.3, "known_percent": 0.9, "n_ratings": 20}),
        (
            "lancaster_sensorimotor",
            {
                "word": "a",
                "visual": 0.0,
                "raw_fields": {"Visual.mean": "", "Auditory.mean": "0", "Haptic.mean": None},
                "raw_extra_fields": ["extra"],
            },
        ),
        (
            "propbank",
            {
                "lemma": "a",
                "roleset_id": "a.01",
                "name": "a",
                "roles": {"ARG0": "actor"},
                "role_mappings": {"ARG0": [{"vnrole": "Agent"}]},
                "verbnet_classes": ["act-1"],
                "native_attributes": {"id": "a.01"},
            },
        ),
    ],
)
def test_native_values_and_cross_bank_candidates_survive_without_winners_or_zero(source, features):
    candidates = [
        {
            "bank": "GOOD",
            "suggested_values": [-1, 1],
            "mapping_provenance": ["negative evidence", "positive evidence"],
            "evidence_disposition": "ASSOCIATION_OWN_DEFINITION_UNESTABLISHED",
        }
    ]
    features = {**features, "projection_candidates": candidates}
    raw = record(source, features, entry_id=None)
    original = copy.deepcopy(raw)
    view = evidence_view([raw], "WANT")
    summary = view["records"][0]
    assert summary["features"] == features
    assert summary["entry_id"] is None
    assert summary["omitted_fields"] == []
    assert raw == original
    summary["features"]["projection_candidates"][0]["suggested_values"].append(0)
    assert raw == original  # No output alias can modify the replay request.


def test_framenet_keeps_lu_definition_and_roles_without_frame_expansion():
    raw = record(
        "framenet",
        {
            "frame_id": 1,
            "frame_name": "Desiring",
            "pos": "v",
            "core_fes": ["Experiencer", "Event"],
            "native_lu": {
                "ID": 2,
                "name": "want.v",
                "POS": "V",
                "definition": "desire " * 200,
                "frame": {"many": "fields"},
            },
            "frame_metadata": {"frame_elements": {"Experiencer": {"description": "a person"}}},
        },
    )
    view = evidence_view([raw], "SOMEONE")
    summary = view["records"][0]
    assert summary["features"]["core_fes"] == ["Experiencer", "Event"]
    assert summary["features"]["native_lu"]["definition"] == raw["features"]["native_lu"]["definition"]
    assert {item["field"] for item in summary["omitted_fields"]} == {
        "/features/frame_metadata",
        "/features/native_lu/frame",
    }
    assert view["role_semantics"] == "ARGUMENT_ROLES_ARE_NOT_OWN_WORD_BANK_ASSIGNMENTS"
    assert "SOMEONE" not in summary["features"]


def test_verbnet_preserves_all_frames_negation_nested_arguments_and_exact_witness():
    semantics = [
        {"predicate_value": "desire", "negated": False, "polarity": "", "arguments": [{"type": "Event", "value": "E"}]},
        {
            "predicate_value": "cause",
            "negated": True,
            "polarity": "!",
            "arguments": [{"type": "ThemRole", "value": "Agent"}],
        },
    ]
    native = {
        "word": "want",
        "verb_class": "desire-32",
        "wordnet_sense_keys": ["want%2:37:00"],
        "member_attributes": {"wn": "want%2:37:00"},
        "thematic_roles": ["Experiencer"],
        "class_context": [
            {
                "class_id": "desire-32",
                "thematic_roles": [{"native": "XML"}],
                "frames": [
                    {"semantics": semantics, "native": {"xml": "large"}},
                    {"semantics": [], "native": {"xml": "large"}},
                    {"native": {"xml": "large"}},
                ],
            }
        ],
    }
    raw = record(
        "verbnet",
        {
            "native_record_id": "original",
            "native": native,
            "definition_links": [{"code": "LINKED", "synset_name": "desire.v.01", "sense_key": "want%2:37:00"}],
            "projection": {"WANT": 1},
        },
    )
    summary = evidence_view([raw], "CAUSE")["records"][0]
    compact = summary["features"]["native"]
    assert compact["class_context"][0]["frames"] == [{"semantics": semantics}, {"semantics": []}, {}]
    assert summary["features"]["definition_links"] == raw["features"]["definition_links"]
    assert summary["features"]["projection"] == {"WANT": 1}
    assert len(summary["omitted_fields"]) == 4
    assert summary["full_record_sha256"] == digest(raw)


def test_world_associations_are_counted_and_hashed_without_individual_ids_or_votes():
    first = record("conceptnet", {"relation": "UsedFor", "start_word": "table", "end_word": "eat", "weight": 10})
    second = record(
        "conceptnet",
        {"relation": "RelatedTo", "start_word": "table", "end_word": "wood", "weight": 1},
        record_id="native:two",
    )
    view = evidence_view([first, second], "WANT")
    exclusion = view["excluded_sources"][0]
    assert view["records"] == []
    assert exclusion["record_count"] == 2
    assert exclusion["code"] == "WORLD_ASSOCIATION_NOT_LEXICAL_EVIDENCE"
    assert exclusion["full_records_sha256"] == digest(sorted([digest(first), digest(second)]))
    assert evidence_view([second, first], "WANT")["excluded_sources"] == view["excluded_sources"]
    assert (
        evidence_view([first, first, second], "WANT")["excluded_sources"][0]["full_records_sha256"]
        != exclusion["full_records_sha256"]
    )
    assert "native:one" not in json.dumps(view) and "native:two" not in json.dumps(view)
    assert "/features/relation" in exclusion["omitted_fields"]


@pytest.mark.parametrize(
    "observations,bank,code",
    [
        (None, "WANT", "INVALID_MODEL_EVIDENCE_OBSERVATIONS"),
        ([None], "WANT", "INVALID_MODEL_EVIDENCE_RECORD"),
        ([], "BAD", "INVALID_MODEL_EVIDENCE_BANK"),
        ([record("new-source")], "WANT", "UNKNOWN_MODEL_EVIDENCE_SOURCE"),
        ([record(features={"definition": float("nan")})], "WANT", "INVALID_MODEL_EVIDENCE_JSON"),
        ([record(features={1: "not JSON"})], "WANT", "INVALID_MODEL_EVIDENCE_JSON"),
        ([record(features=[])], "WANT", "INVALID_MODEL_EVIDENCE_FEATURES"),
        ([record(source="")], "WANT", "INVALID_MODEL_EVIDENCE_IDENTITY"),
        ([record(candidate_entry_ids=[None])], "WANT", "INVALID_MODEL_EVIDENCE_CANDIDATE_IDS"),
        ([record("verbnet", {"class_context": {}})], "WANT", "INVALID_MODEL_EVIDENCE_VERBNET_CONTEXT"),
        ([record("verbnet", {"native": []})], "WANT", "INVALID_MODEL_EVIDENCE_VERBNET_NATIVE"),
        ([record("framenet", {"native_lu": []})], "WANT", "INVALID_MODEL_EVIDENCE_FRAMENET_LU"),
    ],
)
def test_malformed_or_unknown_records_refuse_with_named_code(observations, bank, code):
    original = copy.deepcopy(observations)
    with pytest.raises(ValueError, match=code):
        evidence_view(observations, bank)
    assert repr(observations) == repr(original)


def test_wordnet_native_relations_are_preserved_as_evidence_without_sign_inheritance():
    relations = {
        "wordnet_version": "3.0",
        "source_synset": "loath.s.01",
        "antonyms": [
            {
                "source_lemma": "reluctant",
                "source_key": "reluctant%5:00:00:willing:00",
                "target": {
                    "synset_name": "willing.a.01",
                    "pos": "a",
                    "definition": "disposed or inclined toward",
                    "lemma_names": ["willing"],
                },
                "target_lemma": "willing",
                "target_key": "willing%3:00:00::",
            }
        ],
        "similar_to": [],
        "attributes": [],
    }
    raw = record(features={"synset_name": "loath.s.01", "native_relations": relations})
    summary = evidence_view([raw], "WANT")["records"][0]
    assert summary["features"]["native_relations"] == relations
    assert summary["omitted_fields"] == []
    assert "/features/native_relations" in summary["selected_fields"]
    assert "WANT" not in summary["features"]
