"""Definition identity evidence preserves alternatives and never assigns signs."""

from copy import deepcopy
from dataclasses import asdict, dataclass
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from GSE.curation.lexicon_builder.evidence import Definition
from GSE.curation.lexicon_builder.wordnet_identity import (
    validate_wordnet_identity,
    wordnet_identity_evidence,
    wordnet_identity_observation,
)


@dataclass
class Synset:
    key: str
    part: str
    gloss: str
    names: list[str]
    lex: str

    def name(self):
        return self.key

    def pos(self):
        return self.part

    def definition(self):
        return self.gloss

    def lemma_names(self):
        return self.names

    def lexname(self):
        return self.lex


@dataclass
class NativeRecord:
    word: str
    pos: str
    synset_name: str
    lexname: str


class WordNet:
    MORPHOLOGICAL_SUBSTITUTIONS = {
        "n": [("s", ""), ("ches", "ch")],
        "v": [("s", "")],
        "a": [],
        "s": [],
        "r": [],
    }

    def __init__(self, synset, candidates, exceptions=None):
        self.selected = synset
        self.candidates = candidates
        self._exception_map = {p: {} for p in self.MORPHOLOGICAL_SUBSTITUTIONS}
        self._exception_map[synset.part] = exceptions or {}

    def get_version(self):
        return "3.0"

    def synset(self, name):
        if name != self.selected.key:
            raise LookupError(name)
        return self.selected

    def _morphy(self, surface, pos):
        assert pos == self.selected.part
        return self.candidates.get(surface, [])


def parser(synset, candidates, exceptions=None):
    pos = {"n": "noun", "v": "verb", "a": "adj", "s": "adj", "r": "adv"}[synset.part]
    return SimpleNamespace(
        _loaded=True,
        _wn=WordNet(synset, candidates, exceptions),
        entries={
            name.casefold().replace("_", " "): [
                NativeRecord(name.casefold().replace("_", " "), pos, synset.key, synset.lex)
            ]
            for name in synset.names
        },
    )


def root(surface, synset):
    return {
        "entry_id": f"wordnet:{quote(surface, safe='')}:{quote(synset.key, safe='')}",
        "lemma": surface,
        "pos": {"n": "noun", "v": "verb", "a": "adj", "s": "adj"}[synset.part],
        "definition": synset.gloss,
    }


@pytest.fixture
def be():
    synset = Synset(
        "embody.v.02", "v", "represent, as of a character on stage", ["embody", "be", "personify"], "verb.stative"
    )
    return synset, parser(synset, {"is": ["be"]}, {"is": ["be"]})


def test_is_has_exception_witness_with_exact_selected_sense(be):
    synset, source = be
    result = wordnet_identity_evidence(source, "is", synset, pos="verb")
    assert result["code"] == "EXCEPTION_DERIVED"
    assert result["source"] == {"name": "wordnet_hierarchy", "version": "3.0"}
    assert result["native_synset"]["definition"] == synset.gloss
    assert result["analyses"] == [
        {
            "base": "be",
            "native_lemmas": ["be"],
            "derivation": {"kind": "EXCEPTION", "exception_bases": ["be"], "substitutions": []},
            "native_records": [{"word": "be", "pos": "verb", "synset_name": "embody.v.02", "lexname": "verb.stative"}],
        }
    ]
    assert result["selects_sense"] is False and result["assigns_banks"] is False
    assert validate_wordnet_identity(result, root("is", synset)) == result


def test_native_membership_does_not_run_morphology(be):
    synset, source = be
    source._wn._morphy = lambda *args: pytest.fail("native spelling must not need a derived candidate")
    result = wordnet_identity_evidence(source, "be", synset)
    assert result["code"] == "NATIVE_LEMMA"
    assert result["analyses"][0]["derivation"]["kind"] == "NATIVE_LEMMA"
    validate_wordnet_identity(result, root("be", synset))


def test_feet_exception_is_separate_from_regular_suffix_authority():
    synset = Synset("foot.n.02", "n", "a linear unit", ["foot", "ft"], "noun.quantity")
    source = parser(synset, {"feet": ["foot"]}, {"feet": ["foot"]})
    result = wordnet_identity_evidence(source, "feet", synset, pos="noun")
    assert result["code"] == "EXCEPTION_DERIVED"
    assert result["analyses"][0]["derivation"]["exception_bases"] == ["foot"]
    validate_wordnet_identity(result, root("feet", synset))


def test_chains_keeps_lexical_alternative_and_matches_selected_sense():
    synset = Synset("chain.n.06", "n", "a unit of length", ["chain"], "noun.quantity")
    source = parser(synset, {"chains": ["chains", "chain"]})
    result = wordnet_identity_evidence(source, "chains", synset)
    assert result["code"] == "REGULAR_RULE_CANDIDATES"
    assert result["authority"] == "CANDIDATE_ONLY"
    assert result["unmatched_candidates"] == ["chains"]
    assert result["analyses"][0]["base"] == "chain"
    assert result["analyses"][0]["derivation"]["substitutions"] == [{"suffix": "s", "replacement": ""}]
    validate_wordnet_identity(result, root("chains", synset))


@pytest.mark.parametrize(
    "surface,base,alternatives",
    [
        ("as", "A", ["as", "a"]),
        ("aus", "AU", ["au"]),
        ("ins", "in", ["ins", "in"]),
        ("ms", "m", ["ms", "m"]),
        ("mis", "mi", ["mi"]),
    ],
)
def test_abbreviation_suffix_candidates_never_become_identity_authority(surface, base, alternatives):
    synset = Synset("unit.n.01", "n", "a unit of length", [base], "noun.quantity")
    result = wordnet_identity_evidence(parser(synset, {surface: alternatives}), surface, synset)
    assert result["code"] == "REGULAR_RULE_CANDIDATES"
    assert result["authority"] == "CANDIDATE_ONLY"
    assert result["analyses"][0]["native_lemmas"] == [base]
    assert result["analyses"][0]["derivation"]["exception_bases"] == []
    validate_wordnet_identity(result, root(surface, synset))


def test_all_matching_exception_alternatives_are_retained():
    synset = Synset("fixture.n.01", "n", "one selected fixture meaning", ["ax", "axis"], "noun.artifact")
    source = parser(synset, {"axes": ["ax", "axis"]}, {"axes": ["ax", "axis"]})
    result = wordnet_identity_evidence(source, "axes", synset)
    assert [item["base"] for item in result["analyses"]] == ["ax", "axis"]
    validate_wordnet_identity(result, root("axes", synset))


def test_exact_native_record_is_selected_instead_of_first_record(be):
    synset, source = be
    source.entries["be"].insert(0, NativeRecord("be", "verb", "exist.v.01", "verb.stative"))
    result = wordnet_identity_evidence(source, "is", synset)
    assert [row["synset_name"] for row in result["analyses"][0]["native_records"]] == ["embody.v.02"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("word", "have"),
        ("pos", "noun"),
        ("pos", []),
        ("lexname", "noun.quantity"),
        ("definition", "unrelated definition"),
    ],
)
def test_wrong_native_record_content_is_malformed(be, field, value):
    synset, source = be
    record = asdict(source.entries["be"][0])
    record[field] = value
    source.entries["be"] = [record]
    result = wordnet_identity_evidence(source, "is", synset)
    assert result["code"] == "MALFORMED" and result["analyses"] == []


@pytest.mark.parametrize("surface", [None, "", " ", " is", 3, [], {}])
def test_invalid_surface_is_named_malformed(be, surface):
    synset, source = be
    result = wordnet_identity_evidence(source, surface, synset)
    assert (result["code"], result["reason"]) == ("MALFORMED", "INVALID_SURFACE")


@pytest.mark.parametrize(
    "pos,reason", [("noun", "EXPECTED_POS_MISMATCH"), ("wrong", "INVALID_EXPECTED_POS"), ([], "INVALID_EXPECTED_POS")]
)
def test_wrong_expected_pos_is_not_a_sense_choice(be, pos, reason):
    synset, source = be
    result = wordnet_identity_evidence(source, "is", synset, pos=pos)
    assert result["code"] == "MALFORMED" and result["reason"] == reason


def test_missing_selected_synset_is_malformed(be):
    _, source = be
    assert wordnet_identity_evidence(source, "is", None)["code"] == "MALFORMED"


def test_supplied_synset_cannot_change_native_definition(be):
    synset, source = be
    altered = deepcopy(synset)
    altered.gloss = "another definition"
    result = wordnet_identity_evidence(source, "is", altered)
    assert (result["code"], result["reason"]) == ("MALFORMED", "SELECTED_SYNSET_MISMATCH")


def test_unloaded_source_abstains_without_loading(be):
    synset, source = be
    source._loaded = False
    source.load = lambda: pytest.fail("must not load")
    result = wordnet_identity_evidence(source, "is", synset)
    assert (result["code"], result["reason"]) == ("UNRESOLVED", "SOURCE_NOT_LOADED")


def test_unmatched_bases_are_not_attached_to_selected_sense(be):
    synset, source = be
    source._wn.candidates["does"] = ["do"]
    result = wordnet_identity_evidence(source, "does", synset)
    assert result["code"] == "UNRESOLVED" and result["reason"] == "NO_MATCHING_NATIVE_BASE"
    assert result["analyses"] == [] and result["unmatched_candidates"] == ["do"]
    validate_wordnet_identity(result, root("does", synset))


def test_observation_is_bound_context_only_and_has_stable_digest(be):
    synset, source = be
    packet = wordnet_identity_evidence(source, "is", synset)
    definition = root("is", synset)
    observation = wordnet_identity_observation(packet, definition)
    assert observation == wordnet_identity_observation(packet, Definition(**definition))
    assert observation.source == "wordnet_hierarchy" and observation.family == "wordnet"
    assert observation.scope == "lexical" and observation.candidate_entry_ids == (definition["entry_id"],)
    assert observation.record_id.startswith("wordnet_identity:")
    assert set(observation.features) == {
        "entry_id",
        "lemma",
        "pos",
        "definition",
        "definition_identity",
        "context_only",
    }
    assert observation.features["context_only"] is True
    assert "hypernym_paths" not in observation.features and "lemma_names" not in observation.features
    packet["analyses"].clear()
    assert observation.features["definition_identity"]["analyses"]


@pytest.mark.parametrize(
    "field,value",
    [("entry_id", "wordnet:is:exist.v.01"), ("lemma", "be"), ("definition", "unrelated definition"), ("pos", "noun")],
)
def test_observation_refuses_different_root(be, field, value):
    synset, source = be
    packet = wordnet_identity_evidence(source, "is", synset)
    definition = root("is", synset)
    definition[field] = value
    with pytest.raises(ValueError):
        wordnet_identity_observation(packet, definition)


@pytest.mark.parametrize(
    "field,value",
    [
        ("format", "wrong"),
        ("assigns_banks", True),
        ("selects_sense", True),
        ("authority", "APPROVED_RULE"),
        ("source", {"name": "wordnet_hierarchy", "version": None}),
        ("analyses", []),
        ("unmatched_candidates", ["be"]),
    ],
)
def test_validator_rejects_altered_authority_or_witness(be, field, value):
    synset, source = be
    packet = wordnet_identity_evidence(source, "is", synset)
    packet[field] = value
    with pytest.raises(ValueError):
        validate_wordnet_identity(packet, root("is", synset))


def test_validator_rejects_other_sense_native_record(be):
    synset, source = be
    packet = wordnet_identity_evidence(source, "is", synset)
    packet["analyses"][0]["native_records"].append(
        {"word": "be", "pos": "verb", "synset_name": "exist.v.01", "lexname": "verb.stative"}
    )
    with pytest.raises(ValueError, match="OTHER_SENSE"):
        validate_wordnet_identity(packet, root("is", synset))


def test_validator_rejects_fake_exception_derivation(be):
    synset, source = be
    packet = wordnet_identity_evidence(source, "is", synset)
    packet["analyses"][0]["derivation"]["exception_bases"] = ["have"]
    with pytest.raises(ValueError, match="EXCEPTION_DERIVATION"):
        validate_wordnet_identity(packet, root("is", synset))


def test_validator_rejects_wrong_regular_transformation():
    synset = Synset("chain.n.06", "n", "a unit", ["chain"], "noun.quantity")
    packet = wordnet_identity_evidence(parser(synset, {"chains": ["chain"]}), "chains", synset)
    packet["analyses"][0]["derivation"]["substitutions"][0]["replacement"] = "x"
    with pytest.raises(ValueError, match="REGULAR_TRANSFORMATION"):
        validate_wordnet_identity(packet, root("chains", synset))


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("_exception_map", {}, "INVALID_EXCEPTION_MAP"),
        ("_exception_map", None, "INVALID_EXCEPTION_MAP"),
        ("MORPHOLOGICAL_SUBSTITUTIONS", {}, "INVALID_MORPHOLOGY_RULES"),
        ("MORPHOLOGICAL_SUBSTITUTIONS", None, "INVALID_MORPHOLOGY_RULES"),
    ],
)
def test_missing_native_morphology_maps_are_malformed(be, field, value, reason):
    synset, source = be
    setattr(source._wn, field, value)
    result = wordnet_identity_evidence(source, "is", synset)
    assert (result["code"], result["reason"]) == ("MALFORMED", reason)


def test_stub_parser_has_named_omission_diagnostic(be):
    synset, _ = be
    result = wordnet_identity_evidence(SimpleNamespace(), "is", synset)
    assert (result["code"], result["reason"]) == ("UNRESOLVED", "SOURCE_NOT_LOADED")
    with pytest.raises(ValueError, match="AUTHORITY_MISMATCH"):
        wordnet_identity_observation(result, root("is", synset))
