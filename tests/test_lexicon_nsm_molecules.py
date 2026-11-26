"""NSM molecule inheritance (word_sense_nsm_molecules): computed bindings and components, never typed."""

import pytest

from GSE.curation.lexicon_builder import word_sense_nsm_molecules as m

pytestmark = pytest.mark.skipif(not m.tt.verified_records(), reason="the verified NSM extracts are not on this machine")


def test_the_creature_category_binds_to_the_common_hypernym_of_its_explicated_subkinds():
    binding = m.bindings()["creatures"]
    assert binding["synset"] == "animal.n.01"
    assert {kid[1] for kid in binding["subkinds"]} >= {"birds", "fish", "dogs", "kangaroos"}


def test_its_components_are_the_unquantified_referent_predicates():
    assert m.components()["creatures"] == {"MOVE": 1, "FEEL": 1}


def test_every_kind_of_animal_inherits_them_and_nothing_else_does():
    assert {b: v for b, (v, _w) in m.inherited("dog.n.01").items()} == {"MOVE": 1, "FEEL": 1}
    assert m.inherited("andiron.n.01") == {} and m.inherited("cad.n.01") == {}


def test_a_sense_inherits_only_what_every_wordnet_member_inherits():
    assert set(m.sense_inheritance(["wordnet:dog:dog.n.01"])) == {"MOVE", "FEEL"}
    assert m.sense_inheritance(["wordnet:dog:dog.n.01", "wordnet:dog:andiron.n.01"]) == {}
