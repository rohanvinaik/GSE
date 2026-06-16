"""
M3a — the abstention signal (grounding_flags), closing the proof
COMPLEX_SENTENCE_DESIGN.md M3 deferred ("abstention under ambiguity").

Hand-built trees test the two fidelity-tier checks in isolation; the end-to-end
proof (store-gated) shows GSE flags low-confidence grounding while *still*
deriving the structure — "clean structure + a catalogued residual".
"""

from pathlib import Path

import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    GenealogyStore,
    evaluate_tree,
    from_trace,
    grounding_flags,
    predicates,
    resolve,
    resolve_references,
)
from gse.symbolic.expression import Atom
from gse.symbolic.predicates import Comparison, TypeAssertion
from gse.symbolic.resolution import Entity


def _ent(lemma, pos, position, prims, eid, thread):
    return Entity(head=Atom(lemma=lemma, word_primitives=prims, role=None,
                            position=position, pos=pos),
                  entity_id=eid, type_thread=thread)


# -- Tier 2: ungrounded -----------------------------------------------------


def test_ungrounded_entity_flags():
    zorble = _ent("zorble", "NOUN", 1, {}, "e0", ())          # OOV both strands
    thing = _ent("thing", "NOUN", 3, {"X": 1}, "e1", ("entity", "thing"))
    flags = grounding_flags(TypeAssertion(entity=zorble, kind=thing))
    assert any(f.kind == "ungrounded" and f.lemma == "zorble" and f.tier == 2
               for f in flags)


def test_grounded_entity_not_flagged():
    # Grounded by the lexicon alone (word_primitives) even with no thread.
    e = _ent("dog", "NOUN", 1, {"ALIVE": 1}, "e0", ())
    assert not any(f.kind == "ungrounded"
                   for f in grounding_flags(TypeAssertion(entity=e, kind=e)))


# -- Tier 1: incomparable ---------------------------------------------------


_DOG = ("entity", "physical_entity", "object", "whole", "living_thing",
        "organism", "animal", "dog")
_CAT = ("entity", "physical_entity", "object", "whole", "living_thing",
        "organism", "animal", "cat")
_IDEA = ("entity", "abstraction", "psychological_feature", "cognition", "idea")
_PARIS = ("Thing", "Place", "PopulatedPlace", "City")  # world strand


def test_incomparable_animal_vs_abstraction():
    dog = _ent("dog", "NOUN", 1, {"x": 1}, "e0", _DOG)
    idea = _ent("idea", "NOUN", 4, {"y": 1}, "e1", _IDEA)
    flags = grounding_flags(Comparison(lhs=dog, rhs=idea))
    assert any(f.kind == "incomparable" and f.tier == 1 for f in flags)


def test_comparable_animals_not_flagged():
    dog = _ent("dog", "NOUN", 1, {"x": 1}, "e0", _DOG)
    cat = _ent("cat", "NOUN", 4, {"y": 1}, "e1", _CAT)
    assert not any(f.kind == "incomparable"
                   for f in grounding_flags(Comparison(lhs=dog, rhs=cat)))


def test_cross_vocab_not_compared():
    # word-thread vs world-thread: different vocabulary → not our call to flag.
    dog = _ent("dog", "NOUN", 1, {"x": 1}, "e0", _DOG)
    paris = _ent("paris", "PROPN", 4, {"y": 1}, "e1", _PARIS)
    assert not any(f.kind == "incomparable"
                   for f in grounding_flags(Comparison(lhs=dog, rhs=paris)))


# -- End-to-end: the abstention proof ---------------------------------------

_DB = Path("data/genealogy.db")


@pytest.mark.skipif(not _DB.exists(), reason="genealogy.db not built")
class TestAbstentionProof:
    @pytest.fixture(scope="class")
    def encoder(self):
        with GSEEncoder() as enc:
            yield enc

    @pytest.fixture(scope="class")
    def store(self):
        s = GenealogyStore()
        yield s
        s.close()

    def _resolved(self, encoder, store, sentence):
        return resolve_references(
            evaluate_tree(resolve(from_trace(encoder.encode(sentence)))), store)

    def test_clean_sentence_has_no_flags(self, encoder, store):
        tree = self._resolved(encoder, store, "The dog is cuter than the cat")
        assert grounding_flags(tree) == []

    def test_ungrounded_flags_yet_structure_survives(self, encoder, store):
        # The argument-swap jewel on OOV tokens: structure derived, grounding
        # abstained. clean structure + catalogued residual, in one tree.
        tree = self._resolved(encoder, store, "The zorble is bigger than the florp")
        assert predicates(tree), "structure is still derived on OOV input"
        flags = grounding_flags(tree)
        assert any(f.kind == "ungrounded" for f in flags)
        assert {f.lemma for f in flags} >= {"zorble", "florp"}
