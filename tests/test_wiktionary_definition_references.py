"""One native reference hop preserves evidence and abstains on identity gaps."""

import copy
import json
from dataclasses import asdict, replace

import pytest

from gse.curation.external_sources.wiktionary import WiktionaryParser


def native(word, *, pos="noun", senses=None, **context):
    return {
        "word": word,
        "pos": pos,
        "lang": "English",
        "lang_code": "en",
        "senses": senses if senses is not None else [{"id": "en-" + word, "glosses": ["Meaning of " + word]}],
        **context,
    }


def linked(word="alias", target="target", *, relation="alt_of", **sense):
    return {"id": "en-" + word, "glosses": ["Reference to " + target], relation: [{"word": target}], **sense}


def parser_for(tmp_path, *records):
    path = tmp_path / "native.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    parser = WiktionaryParser(data_path=path)
    assert parser.load()
    return parser


def entries(parser, *words):
    return tuple(parser.get_definition_entries(words))


def test_existing_parser_returns_complete_target_and_original_without_signs(tmp_path):
    parser = parser_for(
        tmp_path,
        native("IT", pos="adj", senses=[linked("IT", "intrathecal", tags=["initialism"])]),
        native("intrathecal", pos="adj", etymology_text="Complete original context."),
        native("intrathecal", pos="noun"),
    )
    original = entries(parser, "IT")
    targets = entries(parser, "intrathecal")
    packet, = parser.get_definition_references(original)
    assert packet == {
        "format": "gse.wiktionary-definition-reference/1",
        "code": "TARGET_DEFINITIONS_AVAILABLE",
        "source_entry": json.loads(json.dumps(asdict(original[0]))),
        "relation": "alt_of",
        "link": {"word": "intrathecal"},
        "target_word": "intrathecal",
        "target_lookup": "intrathecal",
        "target_entries": [json.loads(json.dumps(asdict(targets[0])))],
        "other_pos_entries": [json.loads(json.dumps(asdict(targets[1])))],
        "source_sha256": parser.source_sha256,
    }
    assert parser.to_primitives_for_entry(original[0]) == {}
    assert parser.to_primitives_for_entry(targets[0]) == {}
    assert parser.conn is None


@pytest.mark.parametrize("relation", ["alt_of", "form_of"])
def test_target_missing_is_distinct_from_wrong_pos(tmp_path, relation):
    parser = parser_for(
        tmp_path,
        native("alias", senses=[linked(relation=relation)]),
        native("target", pos="verb"),
    )
    packet, = parser.get_definition_references(entries(parser, "alias"))
    assert packet["code"] == "TARGET_HAS_ONLY_OTHER_POS"
    assert packet["target_entries"] == []
    assert [record["pos"] for record in packet["other_pos_entries"]] == ["verb"]
    parser = parser_for(tmp_path, native("alias", senses=[linked(target="absent", relation=relation)]))
    packet, = parser.get_definition_references(entries(parser, "alias"))
    assert packet["code"] == "TARGET_NOT_FOUND"
    assert packet["target_entries"] == packet["other_pos_entries"] == []


def test_multiple_senses_preserved_even_when_native_parent_id_is_shared(tmp_path):
    parser = parser_for(
        tmp_path,
        native("alias", senses=[linked()]),
        native("target", senses=[{"id": "parent", "glosses": ["First"]}, {"id": "parent", "glosses": ["Second"]}]),
    )
    packet, = parser.get_definition_references(entries(parser, "alias"))
    assert packet["code"] == "AMBIGUOUS_TARGET_SENSES"
    assert {record["definition"] for record in packet["target_entries"]} == {"First", "Second"}
    assert len({record["entry_id"] for record in packet["target_entries"]}) == 2


@pytest.mark.parametrize("target", ["alias", "third"])
def test_chain_and_cycle_are_reported_without_recursing(tmp_path, target):
    parser = parser_for(
        tmp_path,
        native("alias", senses=[linked()]),
        native("target", senses=[linked("target", target, relation="form_of")]),
        native("third"),
    )
    packet, = parser.get_definition_references(entries(parser, "alias"))
    assert packet["code"] == "TARGET_IS_REFERENCE"
    assert [record["word"] for record in packet["target_entries"]] == ["target"]
    assert packet["target_entries"][0]["native_sense"]["form_of"] == [{"word": target}]


def test_self_reference_is_not_terminal(tmp_path):
    parser = parser_for(tmp_path, native("alias", senses=[linked(target="alias")]))
    packet, = parser.get_definition_references(entries(parser, "alias"))
    assert packet["code"] == "TARGET_IS_REFERENCE"
    assert packet["target_entries"][0]["entry_id"] == packet["source_entry"]["entry_id"]


def test_ambiguous_targets_do_not_choose_a_terminal_leaf_over_a_reference(tmp_path):
    parser = parser_for(
        tmp_path, native("alias", senses=[linked()]),
        native("target", senses=[linked("target", "third"), {"id": "terminal", "glosses": ["Terminal"]}]),
    )
    packet, = parser.get_definition_references(entries(parser, "alias"))
    assert packet["code"] == "AMBIGUOUS_TARGET_SENSES"
    assert len(packet["target_entries"]) == 2


def test_exact_normalization_preserves_original_spelling_and_link_metadata(tmp_path):
    link = {"word": " Target_Name ", "extra": {"qualifier": "native"}}
    parser = parser_for(
        tmp_path,
        native("ALIAS", senses=[linked(alt_of=[link])]),
        native("Target name"), native("target names"), native("target-name"),
    )
    packet, = parser.get_definition_references(entries(parser, "alias"))
    assert packet["target_word"] == " Target_Name "
    assert packet["target_lookup"] == "target name"
    assert packet["link"] == link
    assert [record["word"] for record in packet["target_entries"]] == ["Target name"]
    assert packet["source_entry"]["word"] == "ALIAS"


def test_duplicate_locations_are_preserved_without_false_ambiguity(tmp_path):
    source = native("alias", senses=[linked(alt_of=[{"word": "target"}, {"word": "target"}])])
    target = native("target")
    parser = parser_for(tmp_path, source, source, target, target)
    original = entries(parser, "alias")
    packets = parser.get_definition_references(original + original)
    assert len(packets) == 2
    assert {packet["source_entry"]["source_line"] for packet in packets} == {1, 2}
    for packet in packets:
        assert packet["code"] == "TARGET_DEFINITIONS_AVAILABLE"
        assert {record["source_line"] for record in packet["target_entries"]} == {3, 4}
        assert len({record["entry_id"] for record in packet["target_entries"]}) == 1


def test_distinct_link_metadata_and_relation_types_remain_separate(tmp_path):
    parser = parser_for(tmp_path, native("alias", senses=[linked(
        alt_of=[{"word": "target"}, {"word": "target", "note": "different"}],
        form_of=[{"word": "target"}],
    )]), native("target"))
    packets = parser.get_definition_references(entries(parser, "alias"))
    assert len(packets) == 3
    assert sorted(packet["relation"] for packet in packets) == ["alt_of", "alt_of", "form_of"]
    assert any(packet["link"].get("note") == "different" for packet in packets)


def test_one_scan_for_all_targets_preserves_original_statistics(tmp_path, monkeypatch):
    parser = parser_for(
        tmp_path, native("one", senses=[linked("one", "first")]),
        native("two", senses=[linked("two", "second")]), native("first"), native("second"),
    )
    original = entries(parser, "one", "two")
    statistics = copy.deepcopy(parser.native_statistics)
    scans = []
    real = parser.get_definition_entries

    def counted(words):
        scans.append(words)
        yield from real(words)

    monkeypatch.setattr(parser, "get_definition_entries", counted)
    first = parser.get_definition_references(original)
    assert scans == [("first", "second")]
    assert parser.native_statistics == statistics
    assert parser.get_definition_references(tuple(reversed(original))) == first


def test_original_entries_and_source_bytes_are_not_mutated(tmp_path):
    parser = parser_for(tmp_path, native("alias", senses=[linked()]), native("target"))
    original = entries(parser, "alias")
    before = copy.deepcopy(original)
    source_bytes = parser.data_path.read_bytes()
    packet, = parser.get_definition_references(original)
    packet["source_entry"]["native_sense"]["alt_of"][0]["word"] = "changed"
    packet["link"]["word"] = "changed"
    packet["target_entries"][0]["native_sense"]["glosses"].append("changed")
    assert original == before
    assert parser.data_path.read_bytes() == source_bytes
    assert parser.get_definition_references(original)[0]["target_word"] == "target"


def test_empty_and_no_explicit_references_do_not_scan_targets(tmp_path, monkeypatch):
    parser = parser_for(tmp_path, native("plain", senses=[{
        "id": "plain", "glosses": ["Alternative of target."], "links": [["target", "target"]],
        "synonyms": [{"word": "target"}], "alt_of": [], "form_of": [],
    }]))
    original = entries(parser, "plain")

    def unexpected(words):
        pytest.fail("A gloss/link/synonym must not invent an explicit native reference")

    monkeypatch.setattr(parser, "get_definition_entries", unexpected)
    assert parser.get_definition_references(()) == ()
    assert parser.get_definition_references(original) == ()


@pytest.mark.parametrize("value", [None, [], {}, "alias", (None,)])
def test_invalid_input_container_or_entry_is_named(tmp_path, value):
    parser = parser_for(tmp_path, native("alias"))
    with pytest.raises(ValueError, match="INVALID_WIKTIONARY_REFERENCE_ENTRIES"):
        parser.get_definition_references(value)


@pytest.mark.parametrize("relation", ["alt_of", "form_of"])
@pytest.mark.parametrize("value", [None, {}, "target", 1])
def test_malformed_link_lists_are_not_treated_as_absence(tmp_path, relation, value):
    parser = parser_for(tmp_path, native("alias", senses=[linked(**{relation: value})]))
    with pytest.raises(ValueError, match="MALFORMED_WIKTIONARY_REFERENCE_LINKS"):
        parser.get_definition_references(entries(parser, "alias"))


@pytest.mark.parametrize("value", [None, "target", 1, []])
def test_malformed_link_objects_are_named(tmp_path, value):
    parser = parser_for(tmp_path, native("alias", senses=[linked(alt_of=[value])]))
    with pytest.raises(ValueError, match="MALFORMED_WIKTIONARY_REFERENCE_LINK:"):
        parser.get_definition_references(entries(parser, "alias"))


@pytest.mark.parametrize("value", [None, "", " ", "_", 1, [], {}])
def test_malformed_target_words_are_named(tmp_path, value):
    parser = parser_for(tmp_path, native("alias", senses=[linked(alt_of=[{"word": value}])]))
    with pytest.raises(ValueError, match="MALFORMED_WIKTIONARY_REFERENCE_TARGET"):
        parser.get_definition_references(entries(parser, "alias"))


def test_missing_target_word_is_named(tmp_path):
    parser = parser_for(tmp_path, native("alias", senses=[linked(alt_of=[{"sense": "target"}])]))
    with pytest.raises(ValueError, match="MALFORMED_WIKTIONARY_REFERENCE_TARGET"):
        parser.get_definition_references(entries(parser, "alias"))


def test_malformed_links_on_target_do_not_pass_as_terminal(tmp_path):
    parser = parser_for(tmp_path, native("alias", senses=[linked()]), native("target", senses=[linked("target", alt_of=None)]))
    with pytest.raises(ValueError, match="MALFORMED_WIKTIONARY_REFERENCE_LINKS"):
        parser.get_definition_references(entries(parser, "alias"))


def test_foreign_snapshot_entries_are_rejected(tmp_path):
    parser = parser_for(tmp_path, native("alias", senses=[linked()]))
    entry, = entries(parser, "alias")
    with pytest.raises(ValueError, match="WIKTIONARY_REFERENCE_SOURCE_MISMATCH"):
        parser.get_definition_references((replace(entry, source_sha256="0" * 64),))


@pytest.mark.parametrize("field,value", [
    ("entry_id", "wrong"), ("definition", "changed"), ("pos", "verb"),
    ("source_line", 0), ("source_line", True), ("sense_index", 1),
    ("record_sha256", None), ("identity_scheme", "unknown"),
])
def test_incomplete_or_inconsistent_entries_are_named(tmp_path, field, value):
    parser = parser_for(tmp_path, native("alias", senses=[linked()]))
    entry, = entries(parser, "alias")
    with pytest.raises(ValueError, match="INVALID_WIKTIONARY_REFERENCE_ENTRY"):
        parser.get_definition_references((replace(entry, **{field: value}),))


def test_changed_source_refuses_even_when_original_has_no_references(tmp_path):
    parser = parser_for(tmp_path, native("plain"))
    original = entries(parser, "plain")
    parser.data_path.write_text("{}\n")
    with pytest.raises(ValueError, match="WIKTIONARY_SOURCE_CHANGED"):
        parser.get_definition_references(original)


def test_change_during_no_reference_validation_is_detected(tmp_path, monkeypatch):
    from gse.curation.external_sources import wiktionary

    parser = parser_for(tmp_path, native("plain"))
    original = entries(parser, "plain")
    real = wiktionary._native_reference_record

    def mutate_after_validation(entry, source_hash):
        record = real(entry, source_hash)
        with parser.data_path.open("a") as stream:
            stream.write("\n")
        return record

    monkeypatch.setattr(wiktionary, "_native_reference_record", mutate_after_validation)
    with pytest.raises(ValueError, match="WIKTIONARY_SOURCE_CHANGED"):
        parser.get_definition_references(original)


def test_change_during_target_scan_is_detected_and_statistics_restored(tmp_path, monkeypatch):
    parser = parser_for(tmp_path, native("alias", senses=[linked()]), native("target"))
    original = entries(parser, "alias")
    statistics = copy.deepcopy(parser.native_statistics)
    real = parser.get_definition_entries

    def mutate_after_scan(words):
        yield from real(words)
        with parser.data_path.open("a") as stream:
            stream.write("\n")

    monkeypatch.setattr(parser, "get_definition_entries", mutate_after_scan)
    with pytest.raises(ValueError, match="WIKTIONARY_SOURCE_CHANGED"):
        parser.get_definition_references(original)
    assert parser.native_statistics == statistics


def test_native_mode_is_required_for_nonempty_entries(tmp_path):
    parser = parser_for(tmp_path, native("alias", senses=[linked()]))
    original = entries(parser, "alias")
    legacy = WiktionaryParser(db_path=tmp_path / "absent.sqlite")
    with pytest.raises(ValueError, match="WIKTIONARY_NATIVE_INPUT_REQUIRED"):
        legacy.get_definition_references(original)
    assert legacy.get_definition_references(()) == ()
    assert not legacy.db_path.exists()
