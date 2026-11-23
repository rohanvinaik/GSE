"""Own-target noun projection and native-adapter boundary specifications."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from gse.lexicon_builder.build import build
from gse.lexicon_builder.nouns import noun_head_claim, noun_readings, noun_record_status
from gse.lexicon_builder.registry import load_rulebook
from gse.lexicon_builder.sources import NativeSources, sha256
from tests.lexicon_sources import NLTK, SOURCES, requires_lexicon_sources


@pytest.fixture
def native_fixture(tmp_path):
    """A complete small native source, including non-target frame participants."""
    external = tmp_path / "external"
    external.mkdir()
    corpus = tmp_path / "corpora"
    frame = corpus / "framenet_v17"
    (frame / "frame").mkdir(parents=True)
    (frame / "lu").mkdir()
    (frame / "luIndex.xml").write_text(
        '<luIndex><lu ID="1" name="crate.n" frameName="Containers" frameID="78"/></luIndex>'
    )
    (frame / "semTypes.xml").write_text(
        '<semTypes><semType ID="15" name="Container"><definition>Container type</definition>'
        '<superType supID="68" superTypeName="Physical_object"/></semType></semTypes>'
    )
    (frame / "frame/Containers.xml").write_text(
        '<frame ID="78" name="Containers">'
        "<definition>Entities conventionally used as containers.</definition>"
        '<semType ID="61" name="Artifact"/>'
        '<FE ID="367" name="Container" coreType="Core"><definition>The target object.</definition>'
        '<semType ID="15" name="Container"/></FE>'
        '<FE ID="368" name="Contents" coreType="Peripheral"><definition>What is contained.</definition></FE>'
        '<FE ID="2096" name="Part" coreType="Peripheral"><definition>A part of the container.</definition></FE>'
        '<lexUnit ID="1" name="crate.n" POS="N" incorporatedFE="Container">'
        '<definition>A container.</definition><semType ID="15" name="Container"/></lexUnit></frame>'
    )
    (frame / "lu/lu1.xml").write_text(
        '<lexUnit><valences><FERealization><pattern><valenceUnit FE="Container" PT="DEN" GF=""/>'
        "</pattern></FERealization></valences></lexUnit>"
    )
    vn = corpus / "verbnet"
    vn.mkdir()
    (vn / "test.xml").write_text(
        '<VNCLASS ID="parent-1"><MEMBERS><MEMBER name="parent" wn="parent%2"/></MEMBERS>'
        '<THEMROLES><THEMROLE type="Agent"><SELRESTRS><SELRESTR Value="+" type="animate"/>'
        '</SELRESTRS></THEMROLE><THEMROLE type="Theme"><SELRESTRS logic="or">'
        '<SELRESTR Value="+" type="concrete"/><SELRESTR Value="-" type="animate"/>'
        "</SELRESTRS></THEMROLE></THEMROLES>"
        '<FRAMES><FRAME><DESCRIPTION primary="NP V NP"/><EXAMPLES><EXAMPLE>Native example.</EXAMPLE></EXAMPLES>'
        '<SYNTAX><NP value="Agent"/><VERB/><NP value="Theme"><SYNRESTRS><SYNRESTR Value="+" type="refl"/>'
        '</SYNRESTRS></NP></SYNTAX><SEMANTICS><PRED value="motion"><ARGS>'
        '<ARG type="Event" value="during(E)"/><ARG type="ThemRole" value="Theme"/>'
        "</ARGS></PRED></SEMANTICS></FRAME></FRAMES>"
        '<SUBCLASSES><VNSUBCLASS ID="child-1"><MEMBERS><MEMBER name="child"/></MEMBERS>'
        '<THEMROLES><THEMROLE type="Theme"><SELRESTRS><SELRESTR Value="+" type="body_part"/>'
        "</SELRESTRS></THEMROLE></THEMROLES><FRAMES/><SUBCLASSES/></VNSUBCLASS></SUBCLASSES></VNCLASS>"
    )
    return NativeSources(["crate", "parent", "child"], external, corpus)


@pytest.fixture(scope="module")
def noun_sources():
    return NativeSources(
        [
            "box",
            "dog",
            "cat",
            "head",
            "hand",
            "glove",
            "wheel",
            "handle",
            "body",
            "people",
            "teacher",
            "child",
            "person",
            "kind",
            "type",
            "species",
            "family",
            "group",
            "love",
            "water",
        ],
        SOURCES,
        NLTK,
    )


def test_adapter_keeps_lu_types_incorporation_target_evidence_and_pins(native_fixture):
    record = native_fixture.for_word("crate")["framenet"]["records"][0]
    value = record["values"]
    assert value["semantic_types"][0]["name"] == "Container"
    assert value["semantic_types"][0]["definition"] == "Container type"
    assert value["incorporated_fes"] == ["Container"]
    assert {e["kind"] for e in value["target_role_evidence"]} == {"DEN_VALENCE", "INCORPORATED_FE"}
    assert {fe["name"] for fe in value["frame_elements"]} == {"Container", "Contents", "Part"}
    pinned = next(m for m in native_fixture.manifest if m["source"] == "framenet")["files"]
    assert {p["id"] for p in pinned} == {
        "nltk:framenet_v17/luIndex.xml",
        "nltk:framenet_v17/semTypes.xml",
        "nltk:framenet_v17/frame/Containers.xml",
        "nltk:framenet_v17/lu/lu1.xml",
    }
    assert all(p["sha256"] == sha256(Path(p["path"])) for p in pinned)


def test_adapter_keeps_origin_frame_and_nearest_inherited_role_restrictions(native_fixture):
    parent = native_fixture.for_word("parent")["verbnet"]["records"][0]["values"]
    child = native_fixture.for_word("child")["verbnet"]["records"][0]["values"]
    assert parent["frames"] == child["frames"]
    frame = child["frames"][0]
    assert frame["description"] == [{"primary": "NP V NP"}]
    assert frame["examples"] == ["Native example."]
    assert frame["syntax"][0]["children"][2]["attributes"]["value"] == "Theme"
    assert frame["syntax"][0]["children"][2]["children"][0]["children"][0]["attributes"] == {
        "Value": "+",
        "type": "refl",
    }
    inherited = {r["role"]: r for r in child["effective_role_restrictions"]}
    assert inherited["Agent"]["defined_in"] == "parent-1"
    assert inherited["Theme"]["defined_in"] == "child-1"
    assert inherited["Theme"]["restrictions"][0]["children"][0]["attributes"]["type"] == "body_part"
    origin_theme = next(r for r in frame["role_restrictions"] if r["role"] == "Theme")
    assert origin_theme["restrictions"][0]["attributes"] == {"logic": "or"}
    assert origin_theme["restrictions"][0]["children"][1]["attributes"] == {"Value": "-", "type": "animate"}


def test_container_participants_do_not_become_own_components(native_fixture):
    readings = noun_readings("crate", native_fixture.for_word("crate"), load_rulebook())
    assert len(readings) == 1
    assert readings[0]["symbolic_before"]["forced"] == {"SOMETHING": "+1", "KIND": "0"}
    assert readings[0]["model_calls"] == []
    assert readings[0]["candidate_vector"] is None
    assert readings[0]["production_eligible"] is False
    assert readings[0]["source_scope"] == "FRAMENET_NOUN_TARGET"
    assert all("PRIME" not in r for r in readings[0]["symbolic_before"]["fired_rules"])


def test_removed_target_definition_reopens_every_head_cell(native_fixture):
    native = native_fixture.for_word("crate")
    changed = deepcopy(native)
    value = changed["framenet"]["records"][0]["values"]
    value["frame_elements"] = [fe for fe in value["frame_elements"] if fe["name"] != "Container"]
    readings = noun_readings("crate", changed, load_rulebook())
    assert readings[0]["head_claim"]["code"] == "NOUN_TARGET_DEFINITION_UNAVAILABLE"
    assert readings[0]["symbolic_before"]["forced"] == {}


def test_generic_entity_typing_does_not_supply_a_noun_head(native_fixture):
    native = deepcopy(native_fixture.for_word("crate"))
    value = native["framenet"]["records"][0]["values"]
    value["frame"] = "Unreviewed_frame"
    value["semantic_types"] = [{"name": "Physical_entity"}]
    readings = noun_readings("crate", native, load_rulebook())
    assert readings[0]["unmapped"] == [{"code": "NO_NOUN_HEAD_RULE"}]
    assert readings[0]["symbolic_before"]["forced"] == {}


def test_empty_sources_do_not_create_a_default_noun_reading():
    assert noun_readings("unknown", {}, load_rulebook()) == []


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("frame", [], "INVALID_NATIVE_NOUN_FIELD"),
        ("lu_id", {}, "INVALID_NATIVE_NOUN_FIELD"),
        ("source_record_ids", {}, "INVALID_NATIVE_NOUN_PROVENANCE"),
        ("frame_elements", {}, "INVALID_NATIVE_NOUN_ELEMENTS"),
        ("target_role_evidence", [None], "INVALID_NATIVE_NOUN_BINDINGS"),
    ],
)
def test_malformed_native_fields_return_named_refusals(native_fixture, field, value, expected):
    record = deepcopy(native_fixture.for_word("crate")["framenet"]["records"][0])
    record["values"][field] = value
    assert noun_record_status(record) == expected
    assert noun_head_claim(record) == {"code": expected}
    with pytest.raises(ValueError, match=expected):
        noun_readings("crate", {"framenet": {"records": [record]}}, load_rulebook())


@pytest.mark.parametrize("word", [None, "", " \t"])
def test_invalid_word_has_a_named_refusal(word):
    with pytest.raises(ValueError, match="INVALID_NOUN_WORD"):
        noun_readings(word, {}, load_rulebook())


@pytest.mark.parametrize("native", [None, {"framenet": []}, {"framenet": {"records": {}}}])
def test_invalid_native_envelope_has_a_named_refusal(native):
    with pytest.raises(ValueError, match="INVALID_NATIVE_NOUN"):
        noun_readings("crate", native, load_rulebook())


@requires_lexicon_sources
def test_real_builder_warrants_box_and_dog_but_preserves_box_measure_sense(noun_sources):
    records = list(build(["box", "dog"], noun_sources, load_rulebook(), None, include_foundation=False))
    nouns = {r["word"]: [s for s in r["readings"] if s.get("source_scope") == "FRAMENET_NOUN_TARGET"] for r in records}
    box = {r["annotation_origin"]["frame"]: r for r in nouns["box"]}
    assert box["Containers"]["symbolic_before"]["forced"] == {"SOMETHING": "+1", "KIND": "0"}
    assert box["Measure_volume"]["head_claim"]["code"] == "NO_NOUN_HEAD_RULE"
    assert box["Measure_volume"]["symbolic_before"]["forced"] == {}
    assert nouns["dog"][0]["symbolic_before"]["forced"] == {"SOMETHING": "+1", "KIND": "0"}
    assert all(r["model_calls"] == [] for rows in nouns.values() for r in rows)


@requires_lexicon_sources
def test_real_body_parts_never_inherit_the_whole_or_thing_head(noun_sources):
    for word in ("hand", "handle"):
        readings = noun_readings(word, noun_sources.for_word(word), load_rulebook())
        assert readings[0]["symbolic_before"]["forced"] == {"PART": "+1", "KIND": "0"}
        assert readings[0]["relations"][0]["binding"] == "UNBOUND_ARGUMENT"
        assert readings[0]["relations"][0]["writes_whole_head"] is False
        assert "BODY" not in readings[0]["symbolic_before"]["forced"]
        assert "SOMETHING" not in readings[0]["symbolic_before"]["forced"]
    glove = noun_readings("glove", noun_sources.for_word("glove"), load_rulebook())[0]
    assert glove["symbolic_before"]["forced"] == {"SOMETHING": "+1", "KIND": "0"}
    wheel = noun_readings("wheel", noun_sources.for_word("wheel"), load_rulebook())
    assert {r["head_claim"]["head"] for r in wheel} == {"SOMETHING", "PART"}


@requires_lexicon_sources
def test_real_head_and_kind_keep_corpus_den_alternatives_without_source_vote(noun_sources):
    readings = noun_readings("head", noun_sources.for_word("head"), load_rulebook())
    leadership = next(r for r in readings if r["annotation_origin"]["frame"] == "Leadership")
    assert leadership["symbolic_before"]["forced"] == {"SOMEONE": "+1", "KIND": "0"}
    assert leadership["head_claim"]["binding_scope"]["denoted_roles"] == ["Leader", "Role"]
    anatomy = next(r for r in readings if r["annotation_origin"]["frame"] == "Body_parts")
    assert anatomy["symbolic_before"]["forced"] == {"PART": "+1", "KIND": "0"}
    kind = noun_readings("kind", noun_sources.for_word("kind"), load_rulebook())[0]
    assert kind["symbolic_before"]["forced"] == {"KIND": "+1"}
    assert kind["head_claim"]["binding_scope"]["denoted_roles"] == ["Category", "Subtype"]


@requires_lexicon_sources
def test_real_whole_body_collective_and_person_are_distinct(noun_sources):
    body = noun_readings("body", noun_sources.for_word("body"), load_rulebook())
    assert {r["head_claim"]["head"] for r in body} == {"BODY", "PEOPLE"}
    for word in ("teacher", "person"):
        rows = noun_readings(word, noun_sources.for_word(word), load_rulebook())
        assert all(r["symbolic_before"]["forced"] == {"SOMEONE": "+1", "KIND": "0"} for r in rows)
    child = noun_readings("child", noun_sources.for_word("child"), load_rulebook())
    age = next(r for r in child if r["annotation_origin"]["frame"] == "People_by_age")
    assert age["head_claim"]["head"] == "SOMEONE"
    assert age["symbolic_before"]["forced"] == {"SOMEONE": "+1", "KIND": "0"}
    group = noun_readings("group", noun_sources.for_word("group"), load_rulebook())
    assert any(r["head_claim"]["code"] == "NO_NOUN_HEAD_RULE" for r in group)
    assert any(r["symbolic_before"]["forced"].get("PEOPLE") == "+1" for r in group)


@requires_lexicon_sources
def test_authored_lu_claim_reopens_when_native_definition_changes(noun_sources):
    native = deepcopy(noun_sources.for_word("head"))
    leadership = next(r for r in native["framenet"]["records"] if r["values"]["frame"] == "Leadership")
    leadership["values"]["definition"] = "A different meaning requiring review."
    readings = noun_readings("head", native, load_rulebook())
    row = next(r for r in readings if r["annotation_origin"]["frame"] == "Leadership")
    assert row["head_claim"]["code"] == "NOUN_AUTHORED_CLAIM_SOURCE_CHANGED"
    assert row["symbolic_before"]["forced"] == {}


@requires_lexicon_sources
def test_usas_and_norm_alternatives_never_cross_join_onto_a_noun_lu(noun_sources):
    native = deepcopy(noun_sources.for_word("hand"))
    native["usas"]["records"].append({"record_id": "unrelated", "values": {"pos": "NOUN", "alternatives": ["E2+"]}})
    rows = noun_readings("hand", native, load_rulebook())
    assert rows[0]["symbolic_before"]["forced"] == {"PART": "+1", "KIND": "0"}
    assert "unrelated" not in rows[0]["premise_record_ids"]
    love = noun_readings("love", noun_sources.for_word("love"), load_rulebook())
    assert love == []
