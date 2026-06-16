"""
Stage-2 (M2.1) reference-resolution tests — docs/RESOLVED_STRUCTURE_DESIGN.md.

Assert stable within-sentence entity ids (coreference by id), the v2 entity-ref
emit contract, and that an injected GenealogyProvider populates type threads —
all DB-free (NullGenealogy / a fake provider).
"""

import json

import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    NullGenealogy,
    emit,
    emit_contract,
    evaluate_tree,
    from_dict,
    from_trace,
    resolve,
    resolve_references,
    to_dict,
)
from gse.symbolic.expression import Atom
from gse.symbolic.predicates import Comparison, TypeAssertion
from gse.symbolic.resolution import Entity


@pytest.fixture(scope="module")
def encoder():
    with GSEEncoder() as enc:
        yield enc


def _resolved(encoder, sentence, genealogy=None):
    tree = evaluate_tree(resolve(from_trace(encoder.encode(sentence))))
    return resolve_references(tree, genealogy)


# --- DB-free unit tests on hand-built trees (no encoder) --------------------


def test_coreferent_mentions_share_one_id():
    # Two mentions of the same referent → same entity_id.
    macbeth_a = Entity(head=Atom(lemma="macbeth", pos="PROPN", position=0))
    macbeth_b = Entity(head=Atom(lemma="macbeth", pos="PROPN", position=5))
    tree = Comparison(lhs=macbeth_a, rhs=macbeth_b)
    out = resolve_references(tree, NullGenealogy())
    assert out.lhs.entity_id == out.rhs.entity_id  # same referent, same id


def test_distinct_referents_get_distinct_ids():
    dog = Entity(head=Atom(lemma="dog", pos="NOUN", position=1))
    cat = Entity(head=Atom(lemma="cat", pos="NOUN", position=4))
    tree = Comparison(lhs=dog, rhs=cat)
    out = resolve_references(tree, NullGenealogy())
    assert out.lhs.entity_id != out.rhs.entity_id


def test_ids_are_first_occurrence_by_position():
    cat = Entity(head=Atom(lemma="cat", pos="NOUN", position=4))
    dog = Entity(head=Atom(lemma="dog", pos="NOUN", position=1))
    # lhs is the later token; id minting is by position, not tree order.
    tree = Comparison(lhs=cat, rhs=dog)
    out = resolve_references(tree, NullGenealogy())
    assert out.rhs.entity_id == "e0"  # dog, position 1, minted first
    assert out.lhs.entity_id == "e1"  # cat, position 4


def test_provider_populates_type_thread():
    class FakeGenealogy:
        def thread(self, lemma, pos, is_proper):
            return ("thing", "person", lemma) if lemma == "thane" else ()

    thane = Entity(head=Atom(lemma="thane", pos="NOUN", position=2))
    macbeth = Entity(head=Atom(lemma="macbeth", pos="PROPN", position=0))
    tree = TypeAssertion(entity=macbeth, kind=thane)
    out = resolve_references(tree, FakeGenealogy())
    assert out.kind.type_thread == ("thing", "person", "thane")
    assert out.entity.type_thread == ()  # provider returned nothing for macbeth


def test_resolution_is_deterministic():
    def build():
        return Comparison(
            lhs=Entity(head=Atom(lemma="dog", pos="NOUN", position=1)),
            rhs=Entity(head=Atom(lemma="cat", pos="NOUN", position=4)),
        )

    a = resolve_references(build(), NullGenealogy())
    b = resolve_references(build(), NullGenealogy())
    assert (a.lhs.entity_id, a.rhs.entity_id) == (b.lhs.entity_id, b.rhs.entity_id)


# --- Emit contract v2 (with the real encoder) -------------------------------


def test_emit_v2_entity_refs(encoder):
    node = emit(_resolved(encoder, "Spot is a dog"))
    assert node["op"] == "TYPE_ASSERT"
    # Both args are now entity-refs, not bare strings.
    for arg in node["args"]:
        assert isinstance(arg, dict)
        assert set(arg) == {"entity_id", "lemma", "type_thread"}
    assert node["args"][0]["lemma"] == "spot"
    assert node["args"][1]["lemma"] == "dog"


def test_contract_version_is_inferred_v2_when_resolved(encoder):
    contract = emit_contract(_resolved(encoder, "Spot is a dog"))
    assert contract["contract_version"] == "2.0"


def test_unresolved_tree_stays_v1(encoder):
    # No resolve_references → bare-string args → v1.
    tree = evaluate_tree(resolve(from_trace(encoder.encode("Spot is a dog"))))
    contract = emit_contract(tree)
    assert contract["contract_version"] == "1.0"
    assert all(isinstance(a, str) for a in emit(tree)["args"])


def test_v2_contract_is_json_safe(encoder):
    for s in ["The dog is cuter than the cat", "Spot and Rex are dogs",
              "Rex barks because the dog is cuter than the cat"]:
        json.dumps(emit_contract(_resolved(encoder, s)))


def test_entity_ref_fields_round_trip_serialization():
    e = Entity(
        head=Atom(lemma="macbeth", pos="PROPN", position=0),
        entity_id="e0",
        type_thread=("thing", "person", "thane"),
    )
    back = from_dict(to_dict(e))
    assert back.entity_id == "e0"
    assert back.type_thread == ("thing", "person", "thane")
