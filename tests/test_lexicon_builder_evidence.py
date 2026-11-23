"""Evidence-boundary tests: definition identity, silence and native provenance."""

import sqlite3
from types import SimpleNamespace

import pytest

from GSE.curation.external_sources.wordnet_hierarchy import WordNetHierarchyParser
from GSE.curation.lexicon_builder import evidence
from GSE.curation.lexicon_builder.engine import Assertion
from GSE.curation.lexicon_builder.evidence import (
    Definition,
    Observation,
    collect_evidence,
    load_local_sources,
    validate_assertion_competence,
)


class Synset:
    def __init__(self, name, definition, lexname, ancestors=(), pos="n"):
        self._name = name
        self._definition = definition
        self._lexname = lexname
        self._ancestors = ancestors
        self._pos = pos

    def name(self):
        return self._name

    def definition(self):
        return self._definition

    def lexname(self):
        return self._lexname

    def pos(self):
        return self._pos

    def hypernym_paths(self):
        return [[SimpleNamespace(name=lambda name=name: name) for name in self._ancestors]]

    def examples(self):
        return ["full original example"]

    def lemma_names(self):
        return [self._name.split(".")[0]]


def wordnet(records):
    parser = WordNetHierarchyParser()
    parser._loaded = True
    parser.entries = {word: [] for word in records}
    by_id = {synset.name(): synset for definitions in records.values() for synset in definitions}
    parser._wn = SimpleNamespace(synsets=lambda word: records.get(word, []), synset=lambda name: by_id[name])
    return parser


def native(entries, **kwargs):
    return SimpleNamespace(_loaded=True, entries=entries, **kwargs)


def animal(name="dog"):
    return Synset(
        f"{name}.n.01", f"A complete definition of {name}.", "noun.animal", ("entity.n.01", "living_thing.n.01")
    )


def test_polysemy_remains_separate_and_ratings_are_not_copied():
    parsers = {
        "wordnet_hierarchy": wordnet(
            {"dog": [animal(), Synset("dog.n.02", "A contemptible person.", "noun.person", ("person.n.01",))]}
        ),
        "nrc_vad": native({"dog": {"word": "dog", "valence": 0.9, "arousal": 0.4, "dominance": 0.8}}),
    }
    bundle = collect_evidence(parsers)
    assert len(bundle.definitions) == 2
    rating = next(o for o in bundle.observations if o.source == "nrc_vad")
    assert rating.entry_id is None
    assert len(rating.candidate_entry_ids) == 2
    assert rating.scope == "association"
    assert rating.features["valence"] == 0.9
    assert not any(a.bank == "GOOD" for a in bundle.assertions)
    by_record = {o.record_id: o for o in bundle.observations}
    person = next(d for d in bundle.definitions if d.definition == "A contemptible person.")
    assert any(a.bank == "SOMEONE" and a.record_id == person.entry_id for a in bundle.assertions)
    assert all(by_record[a.record_id].entry_id is not None for a in bundle.assertions)


def test_synonyms_and_identical_geometry_do_not_merge_lexical_objects():
    shared = animal()
    bundle = collect_evidence({"wordnet_hierarchy": wordnet({"dog": [shared], "hound": [shared]})})
    assert len(bundle.definitions) == 2
    assert len({d.entry_id for d in bundle.definitions}) == 2
    assignments = [
        {(a.bank, a.value) for a in bundle.assertions if a.record_id == d.entry_id} for d in bundle.definitions
    ]
    assert assignments[0] == assignments[1]


def test_exact_synset_link_preserves_sentiment_without_asserting_it():
    bundle = collect_evidence(
        {
            "wordnet_hierarchy": wordnet({"dog": [animal()]}),
            "sentiwordnet": native(
                {"dog": [{"word": "dog", "pos": "noun", "synset_id": "dog.n.01", "pos_score": 0.0, "neg_score": 0.75}]}
            ),
        }
    )
    sentiment = next(o for o in bundle.observations if o.source == "sentiwordnet")
    assert sentiment.entry_id == bundle.definitions[0].entry_id
    assert sentiment.record_id in bundle.definitions[0].source_ids
    assert sentiment.features["neg_score"] == 0.75
    assert not any(a.source == "sentiwordnet" for a in bundle.assertions)


def test_argument_records_cannot_create_definitions_or_objecthood():
    bundle = collect_evidence(
        {
            "wordnet_hierarchy": wordnet({"move": [Synset("move.v.01", "Change position.", "verb.motion", pos="v")]}),
            "verbnet": native(
                {
                    "move": [
                        {"word": "move", "verb_class": "move-1", "thematic_roles": ["Agent", "Theme"]},
                        {"word": "move", "verb_class": "move-2", "thematic_roles": ["Agent"]},
                    ]
                }
            ),
        }
    )
    assert len(bundle.definitions) == 1
    roles = [o for o in bundle.observations if o.source == "verbnet"]
    assert len(roles) == 2
    assert all(o.entry_id is None and o.scope == "argument_structure" for o in roles)
    assert bundle.assertions == ()


def test_modifier_does_not_inherit_objecthood_from_external_participants():
    bundle = collect_evidence(
        {
            "wordnet_hierarchy": wordnet(
                {"long": [Synset("long.a.01", "An object is long.", "adj.all", ("entity.n.01",), pos="a")]}
            )
        }
    )
    assert len(bundle.definitions) == 1
    assert bundle.assertions == ()


def test_zero_is_preserved_and_missing_coordinates_are_not_manufactured(monkeypatch):
    monkeypatch.setitem(evidence.ROOT_CONCEPT_PRIMITIVES, "entity.n.01", {"SOMETHING": 0})
    bundle = collect_evidence(
        {
            "wordnet_hierarchy": wordnet(
                {"test": [Synset("test.n.01", "Test definition.", "noun.unknown", ("entity.n.01",))]}
            )
        }
    )
    assert [(a.bank, a.value) for a in bundle.assertions] == [("SOMETHING", 0)]


def test_flock_does_not_become_people_but_old_proposals_are_retained():
    bundle = collect_evidence(
        {
            "wordnet_hierarchy": wordnet(
                {"flock": [Synset("flock.n.01", "A group of birds.", "noun.group", ("entity.n.01", "group.n.01"))]}
            )
        }
    )
    assert not any(a.bank == "PEOPLE" for a in bundle.assertions)
    assert any(a.bank == "SOMETHING" for a in bundle.assertions)
    proposals = bundle.observations[0].features["taxonomy_proposals"]
    assert {p["origin"] for p in proposals if p["primitive"] == "PEOPLE"} == {"noun.group", "group.n.01"}
    assert all(p["status"] == "CANDIDATE" for p in proposals)


def test_food_does_not_become_body_and_abstract_does_not_become_thought():
    bundle = collect_evidence(
        {
            "wordnet_hierarchy": wordnet(
                {
                    "food": [Synset("food.n.01", "Food definition.", "noun.food", ("entity.n.01",))],
                    "abstraction": [
                        Synset(
                            "abstraction.n.06", "An abstraction.", "noun.cognition", ("entity.n.01", "abstraction.n.06")
                        )
                    ],
                }
            )
        }
    )
    assert not any(a.bank in {"BODY", "THINK"} for a in bundle.assertions)
    proposals = [p for o in bundle.observations for p in o.features["taxonomy_proposals"]]
    assert any(p["primitive"] == "BODY" for p in proposals)
    assert any(p["primitive"] == "THINK" for p in proposals)


def test_unknown_source_scope_abstains_even_with_coordinate_shaped_input():
    bundle = collect_evidence({"unknown": native({"unseen": {"GOOD": 1, "SOMETHING": 0}})})
    assert bundle.definitions == bundle.assertions == ()
    assert bundle.observations[0].features["SOMETHING"] == 0
    assert bundle.observations[0].scope == "unscoped"
    assert {item["code"] for item in bundle.unresolved} == {
        "NO_IDENTIFIED_DEFINITION",
        "UNSCOPED_SOURCE",
        "UNRESOLVED_SOURCE_LINK",
    }


def test_record_identity_is_order_independent_and_full_text_survives():
    long_text = "meaning " * 1000
    record = {"lemma": "test", "name": long_text, "roleset_id": "test.01", "roles": {"ARG1": "thing", "ARG0": "person"}}
    first = collect_evidence({"propbank": native({"test": [record, record]})})
    second = collect_evidence({"propbank": native({"test": [dict(reversed(tuple(record.items())))]})})
    assert first.observations == second.observations
    assert first.observations[0].features["name"] == long_text


def test_no_adapter_loading_or_aggregate_mapping_is_called():
    class Adapter:
        _loaded = False
        entries = {"dog": {"word": "dog"}}

        def load(self):
            raise AssertionError("must not load")

        def to_primitives(self, word):
            raise AssertionError("must not aggregate")

    result = collect_evidence({"nrc_vad": Adapter()}, ("dog",))
    assert result.assertions == result.observations == ()
    assert {item["code"] for item in result.unresolved} == {"SOURCE_NOT_LOADED", "NO_IDENTIFIED_DEFINITION"}


def test_invalid_input_and_nonfinite_features_are_explicit():
    with pytest.raises(ValueError, match="INVALID_WORDS"):
        collect_evidence({}, "dog")
    with pytest.raises(ValueError, match="INVALID_PARSERS"):
        collect_evidence({1: object()})
    result = collect_evidence({"nrc_vad": native({"dog": {"valence": float("nan")}})})
    assert result.observations == ()
    assert any(item["code"] == "MALFORMED_NATIVE_RECORD" for item in result.unresolved)


def test_empty_collection_and_unidentified_word():
    assert collect_evidence({}).definitions == ()
    result = collect_evidence({}, ("missing",))
    assert result.unresolved == ({"code": "NO_IDENTIFIED_DEFINITION", "lemma": "missing"},)


def test_conceptnet_reads_all_available_records_without_limit_or_projection():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE edges (relation TEXT,start_word TEXT,end_word TEXT,weight REAL,source TEXT)")
    connection.executemany(
        "INSERT INTO edges VALUES (?,?,?,?,?)", [("IsA", "dog", f"type{i}", 1.0, "native") for i in range(105)]
    )
    bundle = collect_evidence({"conceptnet": native({}, conn=connection)}, ("dog",))
    assert len(bundle.observations) == 105
    assert bundle.assertions == ()
    connection.close()


def test_frame_metadata_is_preserved():
    bundle = collect_evidence(
        {
            "framenet": native(
                {"run": [{"frame_name": "Motion", "pos": "v"}]},
                _frame_cache={"Motion": {"definition": "all available description", "id": 1}},
            )
        }
    )
    assert bundle.observations[0].features["frame_metadata"]["definition"] == "all available description"


def test_local_loader_does_not_enter_missing_file_download_fallback(tmp_path):
    parser = SimpleNamespace(data_path=tmp_path / "absent", load=lambda: pytest.fail("download-capable loader invoked"))
    result = evidence._load_local_source("nrc_vad", parser)
    assert result["code"] == "UNAVAILABLE"
    assert result["reason"] == "MISSING_LOCAL_FILE"


def test_local_loader_does_not_enter_missing_nltk_download_fallback(monkeypatch):
    def missing(source):
        raise LookupError("missing local corpus")

    monkeypatch.setattr(evidence, "_verify_nltk_cache", missing)
    parser = SimpleNamespace(load=lambda: pytest.fail("download-capable loader invoked"))
    assert evidence._load_local_source("verbnet", parser)["code"] == "UNAVAILABLE"


def test_conceptnet_cache_is_readonly_and_never_built(tmp_path):
    path = tmp_path / "cache.sqlite"
    parser = SimpleNamespace(db_path=path, load=lambda: pytest.fail("index builder invoked"))
    assert evidence._load_local_source("conceptnet", parser)["code"] == "UNAVAILABLE"
    assert not path.exists()
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE edges (relation TEXT,start_word TEXT,end_word TEXT,weight REAL,source TEXT)")
    connection.execute("INSERT INTO edges VALUES ('IsA','dog','animal',1.0,'source')")
    connection.commit()
    connection.close()
    diagnostic = evidence._load_local_source("conceptnet", parser)
    assert diagnostic["native_records"] == 1
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        parser.conn.execute("DELETE FROM edges")
    parser.conn.close()


def test_local_loader_rejects_unknown_sources():
    with pytest.raises(ValueError, match="UNKNOWN_LOCAL_SOURCE"):
        load_local_sources(("unknown",))


def test_nominal_feeling_projection_respects_declared_scope(monkeypatch):
    parser = wordnet({"feeling": [Synset("feeling.n.01", "A feeling.", "noun.feeling", ("feeling.n.01",))]})
    result = collect_evidence({"wordnet_hierarchy": parser})
    assert [(a.bank, a.value) for a in result.assertions] == [("FEEL", 1)]
    monkeypatch.setitem(evidence.SOURCE_PRIMITIVE_SCOPE, "wordnet_hierarchy", {"SOMETHING"})
    assert collect_evidence({"wordnet_hierarchy": parser}).assertions == ()


def test_missing_definition_projection_is_explicit():
    parser = wordnet({"dog": [animal()]})
    parser.to_primitives_for_definition = None
    result = collect_evidence({"wordnet_hierarchy": parser})
    assert result.assertions == ()
    assert result.unresolved[0]["code"] == "DEFINITION_PROJECTION_UNAVAILABLE"


def test_lancaster_raw_missingness_survives_collection_without_lexical_claim(tmp_path):
    from GSE.curation.external_sources.lancaster_sensorimotor import LancasterSensorimotorParser

    path = tmp_path / "raw.csv"
    path.write_text("Word,Auditory.mean,Visual.mean,Haptic.mean\ndog,0,\n")
    parser = LancasterSensorimotorParser(data_path=str(path))
    assert parser.load() is True
    result = collect_evidence({"lancaster_sensorimotor": parser, "wordnet_hierarchy": wordnet({"dog": [animal()]})})
    observation = next(o for o in result.observations if o.source == "lancaster_sensorimotor")
    assert observation.features["raw_fields"] == {
        "Word": "dog",
        "Auditory.mean": "0",
        "Visual.mean": "",
        "Haptic.mean": None,
    }
    assert "Gustatory.mean" not in observation.features["raw_fields"]
    assert observation.scope == "association"
    assert observation.entry_id is None
    assert not any(a.source == "lancaster_sensorimotor" for a in result.assertions)


@pytest.mark.parametrize(
    "field,value",
    [
        ("entry_id", ""),
        ("lemma", " "),
        ("pos", None),
        ("definition", None),
        ("source_ids", ["source"]),
        ("source_ids", ("",)),
        ("source_ids", (1,)),
    ],
)
def test_definition_rejects_malformed_fields(field, value):
    fields = {"entry_id": "id", "lemma": "dog", "pos": "noun", "definition": "A dog.", "source_ids": ()}
    fields[field] = value
    with pytest.raises(ValueError, match="INVALID_DEFINITION"):
        Definition(**fields)


def test_definition_allows_explicitly_empty_gloss():
    assert Definition("id", "dog", "noun", "").definition == ""


@pytest.mark.parametrize(
    "field,value",
    [
        ("entry_id", ""),
        ("source", ""),
        ("record_id", 1),
        ("family", None),
        ("scope", " "),
        ("candidate_entry_ids", ["id"]),
        ("candidate_entry_ids", (None,)),
        ("features", []),
        ("features", {1: "bad key"}),
        ("features", {"nested": [float("nan")]}),
        ("features", {"nested": {"value": float("inf")}}),
        ("features", {"set": {1}}),
    ],
)
def test_observation_rejects_malformed_fields(field, value):
    fields = {
        "entry_id": None,
        "source": "source",
        "record_id": "id",
        "family": "source",
        "features": {},
        "scope": "association",
        "candidate_entry_ids": (),
    }
    fields[field] = value
    with pytest.raises(ValueError, match="INVALID_OBSERVATION"):
        Observation(**fields)


def test_observation_preserves_typed_zero_null_and_nested_native_values():
    features = {"value": 0, "missing": None, "nested": [{"flag": False, "text": ""}]}
    observation = Observation(None, "source", "record", "family", features, "association")
    assert observation.features == features


@pytest.mark.parametrize("predicate,bank", [("motion", "MOVE"), ("emotional_state", "FEEL"), ("desire", "WANT")])
def test_verbnet_explicit_sense_links_have_distinct_witnesses_and_no_ambiguous_copy(monkeypatch, predicate, bank):
    from GSE.curation.external_sources.verbnet import VerbNetEntry, VerbNetParser

    synsets = [Synset(f"run.v.0{i}", f"Run definition {i}.", "verb.motion", pos="v") for i in (1, 2, 3)]
    spine = wordnet({"run": synsets})
    by_key = {f"run%2:38:0{i}::": synsets[i - 1] for i in (1, 2)}
    spine._wn.lemma_from_key = lambda key: SimpleNamespace(name=lambda: "run", synset=lambda: by_key[key])
    entry = VerbNetEntry(
        "run",
        "run-class",
        ["Agent", "Theme"],
        wordnet_sense_keys=["run%2:38:01", "run%2:38:02", "?run%2:38:03"],
        class_context=[
            {
                "class_id": "run-class",
                "frames": [
                    {
                        "semantics": [
                            {
                                "predicate_value": predicate,
                                "negated": False,
                                "polarity": "",
                                "arguments": [{"type": "Event", "value": "during(E)"}],
                            }
                        ]
                    }
                ],
            }
        ],
    )
    parser = VerbNetParser()
    parser._loaded = True
    parser.entries = {"run": [entry]}
    result = collect_evidence({"wordnet_hierarchy": spine, "verbnet": parser})
    native_observation = next(
        o for o in result.observations if o.source == "verbnet" and o.scope == "argument_structure"
    )
    witnesses = [o for o in result.observations if o.source == "verbnet" and o.scope == "lexical"]
    assert len(witnesses) == 2
    assert len({o.record_id for o in witnesses}) == 2
    assert all(o.features["native_record_id"] == native_observation.record_id for o in witnesses)
    assert {a.record_id for a in result.assertions} == {o.record_id for o in witnesses}
    assert {(a.bank, a.value, a.source, a.family, a.scope) for a in result.assertions} == {
        (bank, 1, "verbnet", "verb_structure", "lexical")
    }
    assert not any(o.entry_id == "wordnet:run:run.v.03" for o in witnesses)
    assert any(d.get("reason") == "UNCERTAIN_SENSE_KEY" for d in result.unresolved)
    monkeypatch.setitem(evidence.SOURCE_PRIMITIVE_SCOPE, "verbnet", {"CAUSE"})
    assert collect_evidence({"wordnet_hierarchy": spine, "verbnet": parser}).assertions == ()


def test_unresolved_link_diagnostic_references_observation_candidates_once():
    result = collect_evidence(
        {"wordnet_hierarchy": wordnet({"dog": [animal()]}), "usas": native({"dog": {"semantic_tags": ["L2"]}})}
    )
    diagnostic = next(d for d in result.unresolved if d["code"] == "UNRESOLVED_SOURCE_LINK")
    observation = next(o for o in result.observations if o.record_id == diagnostic["record_id"])
    assert observation.candidate_entry_ids == (result.definitions[0].entry_id,)
    assert "candidate_entry_ids" not in diagnostic


@pytest.mark.parametrize("value", [-1, 0, 1])
def test_assertion_competence_accepts_canonical_sentiment_poles(value):
    assertion = Assertion("GOOD", value, "sentiwordnet", "record", "wordnet")
    assert validate_assertion_competence(assertion) is None


def test_assertion_competence_rejects_out_of_scope_imported_fact():
    with pytest.raises(ValueError, match="ASSERTION_OUTSIDE_SOURCE_SCOPE"):
        validate_assertion_competence(Assertion("DO", 1, "sentiwordnet", "record", "wordnet"))
    with pytest.raises(ValueError, match="ASSERTION_OUTSIDE_SOURCE_SCOPE"):
        validate_assertion_competence(Assertion("BAD", 1, "sentiwordnet", "record", "wordnet"))


def test_assertion_competence_normalizes_negative_only_source_scope(monkeypatch):
    monkeypatch.setitem(evidence.SOURCE_PRIMITIVE_SCOPE, "sentiwordnet", {"BAD"})
    assert validate_assertion_competence(Assertion("GOOD", -1, "sentiwordnet", "record", "wordnet")) is None


def test_authored_dictionary_source_has_no_invented_native_scope():
    assert validate_assertion_competence(Assertion("DO", 1, "authored_dictionary", "record", "authored")) is None


def test_assertion_competence_rejects_untyped_input():
    with pytest.raises(ValueError, match="INVALID_ASSERTION"):
        validate_assertion_competence({"bank": "GOOD"})


def test_real_verb_ancestry_reaches_collector_without_polysemy_fanout():
    from nltk.corpus import wordnet as wn

    wn.ensure_loaded()
    parser = WordNetHierarchyParser()
    parser._loaded = True
    parser._wn = wn
    result = collect_evidence({"wordnet_hierarchy": parser}, ("contemplate", "want", "hear", "shake"))
    by_record = {}
    for assertion in result.assertions:
        by_record.setdefault(assertion.record_id, {})[assertion.bank] = assertion.value
    assert by_record["wordnet:contemplate:contemplate.v.02"]["THINK"] == 1
    assert "THINK" not in by_record.get("wordnet:contemplate:contemplate.v.01", {})
    assert by_record["wordnet:want:desire.v.01"]["WANT"] == 1
    assert "WANT" not in by_record.get("wordnet:want:want.v.05", {})
    assert by_record["wordnet:hear:hear.v.01"]["HEAR"] == 1
    assert "HEAR" not in by_record.get("wordnet:hear:hear.v.03", {})
    assert by_record["wordnet:shake:shake.v.02"]["MOVE"] == 1
    observation = next(o for o in result.observations if o.record_id == "wordnet:shake:shake.v.02")
    assert any("move.v.03" in path for path in observation.features["hypernym_paths"])
