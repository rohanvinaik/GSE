"""Exact native expansion context reaches bounded questions without sign transfer."""

import copy
import hashlib
import json
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from gse.curation.external_sources.wiktionary import WiktionaryParser
from gse.curation.lexicon_builder.evidence import (
    collect_evidence,
    native_reference_observation,
    native_reference_observations,
)
from gse.curation.lexicon_builder.model_evidence import evidence_view, restore_candidate_links
from gse.curation.lexicon_builder.model_protocol import model_input, protocol_contract
from gse.curation.lexicon_builder.residual import build_request
from gse.curation.lexicon_builder.resolution import resolve_dictionary


def native(word, pos="adj", senses=None):
    return {
        "word": word, "pos": pos, "lang": "English", "lang_code": "en",
        "senses": senses if senses is not None else [{"id": word, "glosses": ["Spinal canal delivery."]}],
    }


def parser_for(tmp_path, *targets, links=None):
    sense = {"id": "IT-adj", "glosses": ["Abbreviation of intrathecal."], "tags": ["abbreviation"],
             "alt_of": [{"word": "intrathecal", "extra": "original link"}] if links is None else links}
    path = tmp_path / "native.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in (native("IT", senses=[sense]), *targets)) + "\n")
    parser = WiktionaryParser(data_path=path)
    assert parser.load()
    return parser


def packet_for(parser):
    return parser.get_definition_references(tuple(parser.get_definition_entries(("IT",))))[0]


def test_collect_to_actual_model_input_preserves_native_ids_and_unknown_banks(tmp_path):
    parser = parser_for(tmp_path, native("intrathecal", senses=[{
        "id": "intrathecal-adj", "glosses": ["Spinal canal delivery."],
        "examples": [{"text": "An example."}],
    }]), native("intrathecal", "noun"))
    originals = tuple(parser.get_definition_entries(("IT",)))
    before = copy.deepcopy(asdict(originals[0]))
    bundle = collect_evidence({"wiktionary": parser}, ("IT",))
    assert len(bundle.definitions) == 1
    definition, = bundle.definitions
    original, expansion = bundle.observations
    assert definition.entry_id == original.entry_id == expansion.entry_id == originals[0].entry_id
    assert original.features == json.loads(json.dumps(before))
    assert definition.source_ids == (original.record_id,)
    assert expansion.record_id.startswith("wiktionary_reference:IT:")
    assert bundle.assertions == ()
    state = resolve_dictionary(("BODY", "BE"), (), ())
    request = build_request(definition.entry_id, "BODY", state,
                            tuple(asdict(item) for item in bundle.observations), definition=definition)
    before_request = copy.deepcopy(request.payload())
    wire = model_input(request.payload())
    view = restore_candidate_links(wire["input"]["evidence"])
    record = view["records"][1]
    packet = record["features"]["native_reference"]
    assert packet["source_entry"]["entry_id"] == definition.entry_id
    assert packet["link"] == {"word": "intrathecal", "extra": "original link"}
    assert packet["target_entries"][0]["definition"] == "Spinal canal delivery."
    assert packet["other_pos_entries"][0]["pos"] == "noun"
    assert wire["input"]["definition"] == {**before_request["definition"], "definition": "Spinal canal delivery."}
    assert wire["input"]["definition_content"] == {
        "code": "UNIQUE_TERMINAL_NATIVE_ABBREVIATION",
        "definition": "Spinal canal delivery.",
        "surface_definition": before_request["definition"]["definition"],
        "target_entry_id": packet["target_entries"][0]["entry_id"],
        "source_sha256": parser.source_sha256,
    }
    assert packet["source_sha256"] == parser.source_sha256
    assert packet["target_entries"][0]["record_sha256"]
    assert {item["field"] for item in record["omitted_fields"]} == {
        "/features/native_reference/target_entries/0/native_sense/examples"}
    assert record["full_record_sha256"] == hashlib.sha256(json.dumps(
        asdict(expansion), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()).hexdigest()
    assert request.known == state.assignments == {}
    assert request.allowed_values == (-1, 0, 1)
    assert request.payload() == before_request
    assert asdict(originals[0]) == before
    assert protocol_contract()["evidence_view"] == "gse.model-evidence/5"


@pytest.mark.parametrize("targets,code,count", [
    ([], "TARGET_NOT_FOUND", 0),
    ([native("intrathecal", "noun")], "TARGET_HAS_ONLY_OTHER_POS", 0),
    ([native("intrathecal", senses=[{"id": "one", "glosses": ["First."]},
                                    {"id": "two", "glosses": ["Second."]}])], "AMBIGUOUS_TARGET_SENSES", 2),
    ([native("intrathecal", senses=[{"id": "chain", "glosses": ["Reference."],
                                    "form_of": [{"word": "IT"}]}])], "TARGET_IS_REFERENCE", 1),
])
def test_diagnostics_preserve_all_senses_without_assignments(tmp_path, targets, code, count):
    parser = parser_for(tmp_path, *targets)
    bundle = collect_evidence({"wiktionary": parser}, ("IT",))
    assert bundle.assertions == ()
    expansion = next(item for item in bundle.observations if "native_reference" in item.features)
    view = evidence_view([asdict(expansion)], "BODY")["records"][0]
    packet = view["features"]["native_reference"]
    assert packet["code"] == code
    assert len(packet["target_entries"]) == count
    assert "ONE_HOP" in view["features"]["reference_semantics"]
    definition, = bundle.definitions
    request = build_request(definition.entry_id, "BODY", resolve_dictionary(("BODY",), (), ()),
                            tuple(asdict(item) for item in bundle.observations), definition=definition)
    assert "definition_content" not in model_input(request.payload())["input"]


def test_alternative_links_and_forged_definition_content_do_not_select_an_expansion(tmp_path):
    parser = parser_for(tmp_path, native("intrathecal"), links=[{"word": "intrathecal"}, {"word": "missing"}])
    bundle = collect_evidence({"wiktionary": parser}, ("IT",))
    definition, = bundle.definitions
    request = build_request(definition.entry_id, "BODY", resolve_dictionary(("BODY",), (), ()),
                            tuple(asdict(item) for item in bundle.observations), definition=definition)
    payload = request.payload()
    payload["definition_content"] = {"definition": "forged expansion"}
    assert "definition_content" not in model_input(payload)["input"]


@pytest.mark.parametrize("change,code", [
    (lambda p: p.update(code="TARGET_NOT_FOUND"), "NATIVE_REFERENCE_STATUS_MISMATCH"),
    (lambda p: p.update(target_lookup="other"), "NATIVE_REFERENCE_TARGET_WORD_MISMATCH"),
    (lambda p: p.update(link={"word": "other"}), "NATIVE_REFERENCE_LINK_NOT_IN_SOURCE"),
    (lambda p: p.update(target_entries=None), "INVALID_NATIVE_REFERENCE_TARGET_LIST"),
    (lambda p: p["source_entry"].update(entry_id="wrong"), "INVALID_WIKTIONARY_REFERENCE_ENTRY"),
])
def test_invalid_packet_rejected_before_model_view(tmp_path, change, code):
    parser = parser_for(tmp_path, native("intrathecal"))
    packet = copy.deepcopy(packet_for(parser))
    change(packet)
    with pytest.raises(ValueError, match=code):
        native_reference_observation(packet)


@pytest.mark.parametrize("field,value", [("entry_id", "wrong"), ("record_id", "forged"),
                                          ("candidate_entry_ids", ("wrong",)), ("source", "nrc_emotion")])
def test_envelope_and_digest_cannot_be_detached_from_source(tmp_path, field, value):
    observation = native_reference_observation(packet_for(parser_for(tmp_path, native("intrathecal"))))
    with pytest.raises(ValueError, match="NATIVE_REFERENCE_OBSERVATION_MISMATCH"):
        replace(observation, **{field: value})
    raw = asdict(observation)
    raw[field] = value
    with pytest.raises(ValueError, match="NATIVE_REFERENCE_OBSERVATION_MISMATCH"):
        evidence_view([raw], "BODY")


def test_empty_links_and_empty_inputs_produce_no_context(tmp_path):
    assert native_reference_observations(None, ()) == ()
    parser = parser_for(tmp_path, links=[])
    bundle = collect_evidence({"wiktionary": parser}, ("IT",))
    assert len(bundle.observations) == 1
    assert bundle.assertions == ()


@pytest.mark.parametrize("links", [None, {}, "intrathecal", [None], [{}]])
def test_malformed_links_are_not_silent_absence(tmp_path, links):
    parser = parser_for(tmp_path)
    path = parser.data_path
    record = native("IT", senses=[{"id": "IT-adj", "glosses": ["Reference."], "alt_of": links}])
    path.write_text(json.dumps(record) + "\n")
    parser = WiktionaryParser(data_path=path)
    assert parser.load()
    with pytest.raises(ValueError, match="MALFORMED_WIKTIONARY_REFERENCE"):
        collect_evidence({"wiktionary": parser}, ("IT",))


def test_wrong_source_witness_and_source_mutation_refuse(tmp_path, monkeypatch):
    parser = parser_for(tmp_path, native("intrathecal"))
    originals = tuple(parser.get_definition_entries(("IT",)))
    packet = packet_for(parser)
    targets = tuple(parser.get_definition_entries(("intrathecal",)))
    monkeypatch.setattr(parser, "get_definition_references", lambda _: (packet,))
    with pytest.raises(ValueError, match="NATIVE_REFERENCE_WRONG_SOURCE_WITNESS"):
        native_reference_observations(parser, targets)
    monkeypatch.undo()
    parser.data_path.write_text(parser.data_path.read_text() + "\n")
    with pytest.raises(ValueError, match="WIKTIONARY_SOURCE_CHANGED"):
        native_reference_observations(parser, originals)


def wordnet_parser(surface="is", base="be", exceptional=True, loaded=True):
    selected = SimpleNamespace(name=lambda: "be.v.01", pos=lambda: "v",
                               definition=lambda: "have the quality of being",
                               lemma_names=lambda: [base], lexname=lambda: "verb.stative",
                               hypernym_paths=lambda: [], examples=lambda: [])
    wordnet = SimpleNamespace(
        get_version=lambda: "3.0", synsets=lambda _: [selected], synset=lambda _: selected,
        _exception_map={"v": {surface: [base]} if exceptional else {}},
        MORPHOLOGICAL_SUBSTITUTIONS={"v": [("s", "")]}, _morphy=lambda *_: [base],
    )
    return SimpleNamespace(_loaded=loaded, _wn=wordnet, entries={base: [
        {"word": base, "synset_name": "be.v.01", "pos": "v", "lexname": "verb.stative"}
    ]}, to_primitives_for_definition=lambda _: {})


@pytest.mark.parametrize("surface,base,exceptional,code,authority", [
    ("is", "be", True, "EXCEPTION_DERIVED", "IDENTITY_EVIDENCE_WITHIN_SELECTED_SENSE"),
    ("acts", "act", False, "REGULAR_RULE_CANDIDATES", "CANDIDATE_ONLY"),
])
def test_derived_identity_reaches_actual_request_without_original_changes(surface, base, exceptional, code, authority):
    parser = wordnet_parser(surface, base, exceptional)
    bundle = collect_evidence({"wordnet_hierarchy": parser}, (surface,))
    definition, = bundle.definitions
    original, identity = bundle.observations
    assert definition.source_ids == (original.record_id,)
    assert "definition_identity" not in original.features
    assert original.features["native_records"] == []
    assert identity.record_id.startswith("wordnet_identity:")
    assert bundle.assertions == ()
    state = resolve_dictionary(("BODY", "BE"), (), ())
    request = build_request(definition.entry_id, "BODY", state,
                            tuple(asdict(item) for item in bundle.observations), definition=definition)
    view = restore_candidate_links(model_input(request.payload())["input"]["evidence"])
    packet = view["records"][1]["features"]["definition_identity"]
    assert packet == identity.features["definition_identity"]
    assert packet["code"] == code
    assert packet["authority"] == authority
    assert packet["analyses"][0]["native_records"] == parser.entries[base]
    assert packet["assigns_banks"] is packet["selects_sense"] is False
    assert request.known == state.assignments == {}
    assert request.allowed_values == (-1, 0, 1)


def test_native_lemma_gets_no_redundant_derived_context():
    bundle = collect_evidence({"wordnet_hierarchy": wordnet_parser("be", "be")}, ("be",))
    assert len(bundle.observations) == 1
    assert "definition_identity" not in bundle.observations[0].features


def test_malformed_derived_interface_is_diagnostic_not_identity():
    parser = wordnet_parser()
    parser._wn._exception_map = None
    bundle = collect_evidence({"wordnet_hierarchy": parser}, ("is",))
    assert len(bundle.observations) == 1
    diagnostic, = bundle.unresolved
    assert diagnostic["code"] == "WORDNET_IDENTITY_CONTEXT_UNAVAILABLE"
    assert diagnostic["identity"]["code"] == "MALFORMED"
    assert diagnostic["identity"]["reason"] == "INVALID_EXCEPTION_MAP"
    assert bundle.assertions == ()


@pytest.mark.parametrize("field,value", [("entry_id", "wrong"), ("record_id", "forged"),
                                          ("candidate_entry_ids", ("wrong",)), ("source", "nrc_emotion")])
def test_derived_identity_envelope_validated_during_replay_and_model_view(field, value):
    bundle = collect_evidence({"wordnet_hierarchy": wordnet_parser()}, ("is",))
    identity = bundle.observations[1]
    with pytest.raises(ValueError, match="WORDNET_IDENTITY_OBSERVATION_MISMATCH"):
        replace(identity, **{field: value})
    raw = asdict(identity)
    raw[field] = value
    with pytest.raises(ValueError, match="WORDNET_IDENTITY_OBSERVATION_MISMATCH"):
        evidence_view([raw], "BODY")
