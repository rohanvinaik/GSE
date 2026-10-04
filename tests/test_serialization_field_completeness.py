"""
Serialization round-trips every field of every node type (#4).

The defect: ``to_dict``/``from_dict`` claim to be symmetric, but fields added to the dataclasses
after the serializer was written never reached the dict — ``Event.themes`` (documented as
"PRESERVED … never destroying the dropped constituents"), ``Atom.number``/``graded``/``apposition``
and ``Entity.apposition_thread`` — so a round trip silently dropped them. The existing tests only
round-tripped instances that left those fields at their defaults.

The law here builds each node type with EVERY field away from its default (asserted, so a field
added later fails until this file — and the serializer — cover it) and requires an exact round
trip through both the dict and the JSON forms.
"""

import dataclasses
import typing

import pytest

from gse.symbolic.expression import Atom, Negation, Op, Phrase
from gse.symbolic.predicates import OPERAND_FIELDS, Event, Predicate
from gse.symbolic.resolution import Coordination, Entity
from gse.symbolic.serialization import from_dict, from_json, to_dict, to_json


def _atom(lemma: str, position: int = 3) -> Atom:
    return Atom(
        lemma=lemma,
        word_primitives={"DO": 1},
        role="subject",
        position=position,
        pos="NOUN",
        number="plur",
        graded=True,
        apposition="warrior",
    )


def _entity(lemma: str) -> Entity:
    return Entity(
        head=_atom(lemma),
        possessor=Entity(head=_atom(f"{lemma}_owner", 1)),
        role="subject",
        modifier=_atom("big", 2),
        entity_id=f"e_{lemma}",
        type_thread=("thing", "person", lemma),
        span=("lady", lemma),
        apposition_thread=("thing", "person", "warrior"),
    )


# Non-default values for every non-operand field a Predicate type declares.
_FEATURES = {
    "verb": "give",
    "conjunction": "after",
    "sign": -1,
    "axis": "tall",
    "note": "probe",
    "themes": (Entity(head=_atom("letter")),),
}


def _predicate(cls):
    kwargs = {f: _entity(f"{cls.__name__.lower()}_{f}") for f in OPERAND_FIELDS[cls.__name__]}
    for f in dataclasses.fields(cls):
        if f.name not in kwargs:
            kwargs[f.name] = _FEATURES[f.name]
    return cls(**kwargs)


NODES = [
    _atom("hens"),
    Phrase(atoms=[_atom("mike", 4), _atom("dog", 5)]),
    Negation(operand=_atom("leave")),
    Op(primitive="COMP_THAN", operation="SET_DIFF", arity=2, args=[_atom("dog"), _atom("cat")]),
    _entity("macbeth"),
    Coordination(members=(_entity("spot"), _entity("rex")), conjunction="or", modifier=_atom("cute")),
] + [_predicate(cls) for cls in typing.get_args(Predicate)]


def _ids(node):
    return type(node).__name__


def test_every_node_type_is_covered():
    kinds = {type(n) for n in NODES}
    assert kinds == {Atom, Phrase, Negation, Op, Entity, Coordination, *typing.get_args(Predicate)}


@pytest.mark.parametrize("node", NODES, ids=_ids)
def test_every_field_is_exercised(node):
    """Guard: the round-trip law only means something if no field of the node sits at its default.
    (Nested nodes may keep defaults — each type is exercised in full as its own top-level node.)"""
    for f in dataclasses.fields(node):
        value = getattr(node, f.name)
        if f.default is not dataclasses.MISSING:
            assert value != f.default, f"{type(node).__name__}.{f.name} left at its default"
        if f.default_factory is not dataclasses.MISSING:
            assert value != f.default_factory(), f"{type(node).__name__}.{f.name} left at its default"


@pytest.mark.parametrize("node", NODES, ids=_ids)
def test_dict_round_trip_is_exact(node):
    assert from_dict(to_dict(node)) == node


@pytest.mark.parametrize("node", NODES, ids=_ids)
def test_json_round_trip_is_exact(node):
    assert from_json(to_json(node)) == node


def test_ditransitive_themes_survive_the_real_pipeline():
    # The issue's own repro, end to end: the secondary argument must survive JSON.
    from gse.api import GSEEncoder
    from gse.symbolic import evaluate_tree, from_trace, resolve

    with GSEEncoder() as enc:
        tree = evaluate_tree(resolve(from_trace(enc.encode("Macbeth gave Duncan a letter"))))
    assert isinstance(tree, Event) and [t.head.lemma for t in tree.themes] == ["letter"]
    assert from_json(to_json(tree)) == tree


def test_fields_at_their_defaults_are_not_emitted():
    # Older payloads stay byte-identical: a field is written only when it is set.
    d = to_dict(Entity(head=Atom(lemma="dog")))
    assert "apposition_thread" not in d
    assert not {"number", "graded", "apposition"} & set(d["head"])
    assert "themes" not in to_dict(Event(verb="run", agent=Atom(lemma="rex")))
