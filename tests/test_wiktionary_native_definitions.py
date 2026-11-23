"""Native sense identity is evidence, never a first-gloss bank assignment."""

import copy
import hashlib
import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from gse.curation.external_sources.wiktionary import WiktionaryParser, native_anatomy_witness
from gse.curation.lexicon_builder.engine import Assertion
from gse.curation.lexicon_builder.evidence import collect_evidence, load_local_sources, validate_assertion_competence
from gse.curation.lexicon_builder.model_evidence import evidence_view


def native(word="example", senses=None, **extra):
    return {
        "word": word,
        "pos": "noun",
        "lang": "English",
        "lang_code": "en",
        "senses": senses if senses is not None else [{"id": f"en-{word}-one", "glosses": ["Something good."]}],
        **extra,
    }


def parser_for(tmp_path, *records):
    path = tmp_path / "native.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    parser = WiktionaryParser(data_path=path)
    assert parser.load()
    return parser


def test_person_genus_projection_requires_single_native_noun_definition(tmp_path):
    import sqlite3
    from contextlib import closing

    from gse.curation.lexicon_builder.engine import Assertion
    from gse.curation.lexicon_builder.evidence import collect_evidence
    from gse.curation.lexicon_builder.foundation import BANKS
    from gse.curation.lexicon_builder.pipeline import build_dictionary
    from gse.curation.lexicon_builder.resolution import resolve_dictionary
    from gse.curation.lexicon_builder.storage import store_entry
    from gse.curation.lexicon_builder.validation import validate_build

    senses = [
        {"id": "sense:person", "glosses": ["A person who writes for a living."]},
        {"id": "sense:alternate", "glosses": ["A person who writes."], "alt_of": [{"word": "writer"}]},
        {"id": "sense:alternative", "glosses": ["A person who writes or an organization that publishes."]},
        {"id": "sense:nested", "glosses": ["A person who writes.", "An organization that publishes."]},
        {"id": "sense:mentioned", "glosses": ["A work by a person who writes."]},
    ]
    parser = parser_for(tmp_path, native(senses=senses, pos="noun"))
    entries = list(parser.get_definition_entries(("example",)))
    assert [parser.to_primitives_for_entry(entry) for entry in entries] == [{"SOMEONE": 1}, {}, {}, {}, {}]
    assert parser.to_primitives("example") == {}
    bundle = collect_evidence({"wiktionary": parser}, ("example",))
    assert [(a.source, a.bank, a.value) for a in bundle.assertions] == [("wiktionary", "SOMEONE", 1)]
    output = tmp_path / "candidate.db"
    build_dictionary(bundle, output)
    assert validate_build(output)["code"] == "REPLAY_VALIDATED"

    ambiguous = next(definition for definition in bundle.definitions if "an organization" in definition.definition)
    assertion = Assertion("SOMEONE", 1, "wiktionary", ambiguous.source_ids[0], "wiktionary")
    state = resolve_dictionary(BANKS, (assertion,), ())
    with closing(sqlite3.connect(output)) as conn, conn:
        store_entry(conn, ambiguous, state, (assertion,))
    report = validate_build(output)
    assert report["code"] == "REPLAY_MISMATCH"
    assert any("WIKTIONARY_PERSON_PROJECTION_WITNESS_MISMATCH" in str(row) for row in report["mismatches"])


def test_all_senses_and_context_survive_without_regex_assignments(tmp_path):
    senses = [
        {"id": "sense:a", "glosses": ["To move.", "A large good thing."], "examples": [{"text": "Example."}]},
        {"id": "sense:b", "glosses": ["Not a movement."], "form_of": [{"word": "other"}]},
    ]
    source = native(senses=senses, etymology_text="A negative prefix", extra_field={"keep": 0})
    original = copy.deepcopy(source)
    parser = parser_for(tmp_path, source)
    entries = list(parser.get_definition_entries(("example",)))
    assert len(entries) == 2
    assert entries[0].definition == "To move.\nA large good thing."
    assert [entry.native_sense for entry in entries] == senses
    assert entries[1].record_context == {k: v for k, v in source.items() if k != "senses"}
    assert [entry.sense_index for entry in entries] == [0, 1]
    assert all(entry.sense_count == 2 for entry in entries)
    assert entries[0].source_sha256 == hashlib.sha256(parser.data_path.read_bytes()).hexdigest()
    assert parser.to_primitives("example") == {}
    assert all(parser.to_primitives_for_entry(entry) == {} for entry in entries)
    assert source == original
    assert parser.conn is None and parser.entries == {}


def test_anatomy_genus_projects_own_body_content_and_replays_exact_witness(tmp_path):
    import sqlite3
    from contextlib import closing

    from gse.curation.lexicon_builder.foundation import BANKS
    from gse.curation.lexicon_builder.pipeline import build_dictionary
    from gse.curation.lexicon_builder.resolution import resolve_dictionary
    from gse.curation.lexicon_builder.storage import read_entries, store_entry
    from gse.curation.lexicon_builder.validation import validate_build

    senses = [
        {"id": "bone", "glosses": ["A small bone in the wrist."], "topics": ["anatomy"]},
        {"id": "tendon", "glosses": ["The distal tendon of a muscle."], "topics": ["anatomy"]},
        {"id": "modifier", "glosses": ["An involuntary muscle twitch."], "topics": ["anatomy"]},
        {"id": "coordinate", "glosses": ["A muscle, or a device."], "topics": ["anatomy"]},
        {"id": "reference", "glosses": ["A muscle."], "topics": ["anatomy"], "alt_of": [{"word": "other"}]},
        {"id": "multiple", "glosses": ["A muscle.", "A device."], "topics": ["anatomy"]},
        {"id": "figurative", "glosses": ["A muscle."], "topics": ["anatomy"], "tags": ["figuratively"]},
        {"id": "other", "glosses": ["An organ of government."], "topics": ["politics"]},
    ]
    parser = parser_for(tmp_path, native(senses=senses))
    entries = list(parser.get_definition_entries(("example",)))
    assert [parser.to_primitives_for_entry(entry) for entry in entries] == [{"BODY": 1}, {"BODY": 1}] + [{}] * 6
    assert parser.to_primitives("example") == {}
    bundle = collect_evidence({"wiktionary": parser}, ("example",))
    assert [(assertion.bank, assertion.value) for assertion in bundle.assertions] == [("BODY", 1), ("BODY", 1)]
    path = tmp_path / "anatomy.db"
    build_dictionary(bundle, path)
    assert validate_build(path)["code"] == "REPLAY_VALIDATED"

    supported = next(definition for definition in bundle.definitions if definition.definition == "A small bone in the wrist.")
    excluded = next(definition for definition in bundle.definitions if definition.definition == "An involuntary muscle twitch.")
    with closing(sqlite3.connect(path)) as conn, conn:
        [entry] = read_entries(conn, entry_id=supported.entry_id)
        assert entry["assignments"] == {"BODY": 1, "GOOD": 0, "SOMETHING": 1}
        assert entry["domains"]["WANT"] == [-1, 0, 1]
        forged = Assertion("BODY", 1, "wiktionary", excluded.source_ids[0], "wiktionary")
        state = resolve_dictionary(BANKS, (forged,), (), {"pos": "noun"})
        store_entry(conn, excluded, state, (forged,))
    report = validate_build(path)
    assert report["code"] == "REPLAY_MISMATCH"
    assert any("WIKTIONARY_ANATOMY_PROJECTION_WITNESS_MISMATCH" in str(row) for row in report["mismatches"])


@pytest.mark.parametrize(
    ("gloss", "witness"),
    [
        ("The lunate bone, or semilunar bone.", ("bone", "disjunction")),
        ("A central vein or nerve, especially the median vein.", ("vein", "disjunction")),
        ("A small bone (or bony structure), especially one of the three of the middle ear.", ("bone", "disjunction")),
        ("A muscle having four heads.", ("muscle", "participle")),
        ("The smooth muscle forming the wall of the uterus.", ("muscle", "participle")),
        ("The white nerve tissue of the cerebellum.", ("nerve", "compound")),
        ("A nerve ending that is sensitive to pressure.", ("nerve", "compound")),
        ("A modified muscle fibre in the form of a flattened discoid.", ("muscle", "compound")),
        ("The nerve-dense, retractable fold of skin which covers the glans.", ("skin", "material_fold")),
        ("A bone, or a nerve, or a device.", None),
        ("A bone (or bony structure) or a device.", None),
        ("An involuntary muscle twitch.", None),
        ("A muscle-like structure.", None),
        ("The tendons or other structures resembling cords.", None),
        ("A fold of skin-like material.", None),
    ],
)
def test_anatomy_attachment_requires_anatomical_head_in_each_supported_construction(gloss, witness):
    assert native_anatomy_witness(gloss, "noun", {"glosses": [gloss], "topics": ["anatomy"]}) == witness


def test_case_variants_and_every_requested_word_are_distinct(tmp_path):
    parser = parser_for(tmp_path, native("name"), native("Name"), native("other"))
    entries = list(parser.get_definition_entries(("name", "other")))
    assert len(entries) == 3 and len({entry.entry_id for entry in entries}) == 3
    assert {entry.word for entry in entries} == {"name", "Name", "other"}
    assert {entry.lemma for entry in entries} == {"name", "other"}
    assert parser.get_all_words() == ["name", "other"]


def test_unrequested_space_punctuation_record_does_not_abort_lexical_cohort(tmp_path):
    parser = parser_for(tmp_path, native(" ", pos="punct", original_title="Unsupported titles/Space"), native())
    assert parser.get_all_words() == ["example"]
    assert len(list(parser.get_definition_entries(("example",)))) == 1


def test_parent_ids_do_not_merge_leaves_and_identical_duplicates_keep_witnesses(tmp_path):
    source = native()
    parser = parser_for(tmp_path, source, source)
    entries = list(parser.get_definition_entries(("example",)))
    assert len(entries) == 2 and entries[0].entry_id == entries[1].entry_id
    assert entries[0].source_line != entries[1].source_line
    assert parser.native_statistics["identical_duplicate_senses"] == 1
    changed = copy.deepcopy(source)
    changed["senses"][0]["glosses"] = ["Another definition."]
    parser = parser_for(tmp_path, source, changed)
    entries = list(parser.get_definition_entries(("example",)))
    assert len({entry.entry_id for entry in entries}) == 2
    assert len({entry.native_id for entry in entries}) == 1
    original_ids = {entry.entry_id for entry in entries}
    parser = parser_for(tmp_path, changed, source)
    assert {entry.entry_id for entry in parser.get_definition_entries(("example",))} == original_ids
    parser = parser_for(tmp_path, source, source)
    evidence = collect_evidence({"wiktionary": parser}, ("example",))
    assert len(evidence.definitions) == 1
    assert len(evidence.observations) == 2
    assert len(evidence.definitions[0].source_ids) == 2


@pytest.mark.parametrize(
    "sense,code",
    [
        ({"glosses": ["missing id"]}, "MISSING_WIKTIONARY_SENSE_ID"),
        ({"id": ""}, "MISSING_WIKTIONARY_SENSE_ID"),
        ({"id": "x", "glosses": None}, "MALFORMED_WIKTIONARY_GLOSSES"),
        ({"id": "x", "glosses": [None]}, "MALFORMED_WIKTIONARY_GLOSSES"),
        (None, "MALFORMED_WIKTIONARY_SENSE"),
    ],
)
def test_malformed_senses_refuse_with_named_codes(tmp_path, sense, code):
    parser = parser_for(tmp_path, native(senses=[sense]))
    with pytest.raises(ValueError, match=code):
        list(parser.get_definition_entries(("example",)))


def test_no_gloss_preserves_identity_and_named_gap_without_values(tmp_path):
    parser = parser_for(tmp_path, native(senses=[{"id": "no-gloss", "tags": ["no-gloss"]}]))
    evidence = collect_evidence({"wiktionary": parser}, ("example",))
    assert len(evidence.definitions) == 1
    assert evidence.definitions[0].definition == ""
    assert not evidence.assertions
    assert any(item["code"] == "MISSING_DEFINITION" for item in evidence.unresolved)


def test_collector_links_candidates_to_new_definitions_without_resolving_ratings(tmp_path):
    parser = parser_for(
        tmp_path, native(senses=[{"id": "one", "glosses": ["First."]}, {"id": "two", "glosses": ["Second."]}])
    )
    rating = SimpleNamespace(_loaded=True, entries={"example": [{"word": "example", "valence": 0.0}]})
    evidence = collect_evidence({"wiktionary": parser, "nrc_vad": rating}, ("example", "missing"))
    assert len(evidence.definitions) == 2 and not evidence.assertions
    observation = next(item for item in evidence.observations if item.source == "nrc_vad")
    assert observation.entry_id is None
    assert set(observation.candidate_entry_ids) == {definition.entry_id for definition in evidence.definitions}
    assert [item["lemma"] for item in evidence.unresolved if item["code"] == "NO_IDENTIFIED_DEFINITION"] == ["missing"]


def test_view_keeps_native_relations_and_names_every_omission_without_mutation(tmp_path):
    parser = parser_for(
        tmp_path,
        native(
            senses=[
                {
                    "id": "one",
                    "glosses": ["Plural of other."],
                    "form_of": [{"word": "other"}],
                    "tags": ["plural", "form-of"],
                    "examples": [{"text": "Usage."}],
                    "future": {"x": 1},
                }
            ],
            forms=[{"form": "examples", "tags": ["plural"]}],
        ),
    )
    evidence = collect_evidence({"wiktionary": parser}, ("example",))
    raw = asdict(evidence.observations[0])
    original = copy.deepcopy(raw)
    summary = evidence_view([raw], "GOOD")["records"][0]
    assert summary["features"]["native_sense"]["form_of"] == [{"word": "other"}]
    assert summary["features"]["record_context"]["forms"] == [{"form": "examples", "tags": ["plural"]}]
    assert {item["field"] for item in summary["omitted_fields"]} == {
        "/features/native_sense/examples",
        "/features/native_sense/future",
    }
    assert raw == original


def test_native_input_never_downloads_or_writes_and_detects_mutation(tmp_path):
    missing = WiktionaryParser(data_path=tmp_path / "absent")
    assert not missing.load()
    assert not missing.data_path.exists()
    parser = parser_for(tmp_path, native())
    parser.data_path.write_text("{}\n")
    with pytest.raises(ValueError, match="WIKTIONARY_SOURCE_CHANGED"):
        list(parser.get_definition_entries(("example",)))


def test_native_mode_required_for_definition_stream(tmp_path):
    parser = WiktionaryParser(db_path=tmp_path / "legacy.sqlite")
    with pytest.raises(ValueError, match="WIKTIONARY_NATIVE_INPUT_REQUIRED"):
        list(parser.get_definition_entries(("example",)))


def test_registered_local_loader_selects_native_cache_and_source_has_no_assertion_authority(tmp_path, monkeypatch):
    from gse.curation.external_sources import wiktionary

    fixture = parser_for(tmp_path, native())
    monkeypatch.setattr(wiktionary, "WIKTIONARY_DUMP", fixture.data_path)
    parsers, diagnostics = load_local_sources(("wiktionary",))
    assert diagnostics[0]["code"] == "LOADED"
    assert diagnostics[0]["mode"] == "STREAMED_NATIVE_DEFINITIONS"
    assert parsers["wiktionary"].conn is None
    evidence = collect_evidence(parsers, ("example",))
    assert len(evidence.definitions) == 1 and not evidence.assertions
    with pytest.raises(ValueError, match="ASSERTION_OUTSIDE_SOURCE_SCOPE"):
        validate_assertion_competence(Assertion("GOOD", 1, "wiktionary", "record", "wiktionary", "lexical"))


def test_native_first_sense_getters_refuse_instead_of_picking_or_crashing(tmp_path):
    parser = parser_for(tmp_path, native())
    for getter in (parser.get_definition, parser.get_synonyms, parser.get_antonyms, parser.get_etymology):
        with pytest.raises(ValueError, match="WIKTIONARY_NATIVE_REQUIRES_DEFINITION_ID"):
            getter("example")


def test_compact_view_exclusions_are_named_and_full_hash_keeps_omitted_evidence(tmp_path):
    parser = parser_for(
        tmp_path,
        native(
            senses=[
                {
                    "id": "sense",
                    "glosses": ["Definition."],
                    "raw_glosses": ["(rare) Definition."],
                    "tags": ["rare"],
                    "translations": [{"word": "x"}],
                    "categories": [{"name": "Editorial"}],
                }
            ],
            derived=[{"word": "examplelike"}],
            etymology_templates=[{"name": "markup"}],
            etymology_text="Recorded etymology.",
        ),
    )
    bundle = collect_evidence({"wiktionary": parser}, ("example",))
    raw = asdict(bundle.observations[0])
    original = copy.deepcopy(raw)
    view = evidence_view([raw], "WANT")["records"][0]
    assert view["features"]["native_sense"]["raw_glosses"] == ["(rare) Definition."]
    assert view["features"]["record_context"]["etymology_text"] == "Recorded etymology."
    assert {item["field"] for item in view["omitted_fields"]} == {
        "/features/native_sense/translations",
        "/features/native_sense/categories",
        "/features/record_context/derived",
        "/features/record_context/etymology_templates",
    }
    raw["features"]["record_context"]["derived"].append({"word": "another"})
    modified = evidence_view([raw], "WANT")["records"][0]
    assert modified["features"] == view["features"]
    assert modified["full_record_sha256"] != view["full_record_sha256"]
    assert original["features"]["record_context"]["derived"] == [{"word": "examplelike"}]
