"""
substitute() changes only what it substitutes (#5).

The defect: ``templating._walk`` rebuilt each node by hand-listing its fields, and the lists fell
behind the dataclasses. Substituting inside a possessor rebuilt the parent Entity with only
head/possessor/role — dropping its modifier (the comparison axis), entity_id, type_thread, span and
apposition_thread; the Event branch dropped ``themes`` and never substituted inside them; a
string-substituted Atom lost number / graded / apposition. The walker now rebuilds with
``dataclasses.replace`` over ``predicates.OPERAND_FIELDS``, so untouched fields survive by
construction. These laws hold every node type to that, and the real-pipeline tests replay the
issue's repro.
"""

import dataclasses
import typing

import pytest

from gse.symbolic.expression import Atom
from gse.symbolic.predicates import OPERAND_FIELDS, Event, Predicate
from gse.symbolic.resolution import Entity
from gse.symbolic.templating import substitute


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
        type_thread=("thing", lemma),
        span=("lady", lemma),
        apposition_thread=("thing", "warrior"),
    )


_FEATURES = {
    "verb": "give",
    "conjunction": "after",
    "sign": -1,
    "axis": "tall",
    "note": "probe",
    "themes": (_entity("letter"),),
}


def _predicate(cls):
    kwargs = {f: _entity(f"{cls.__name__.lower()}_{f}") for f in OPERAND_FIELDS[cls.__name__]}
    for f in dataclasses.fields(cls):
        if f.name not in kwargs:
            kwargs[f.name] = _FEATURES[f.name]
    return cls(**kwargs)


PREDICATES = [_predicate(cls) for cls in typing.get_args(Predicate)]


@pytest.mark.parametrize("node", PREDICATES, ids=lambda n: type(n).__name__)
def test_substituting_one_operand_leaves_every_other_field_intact(node):
    for field in OPERAND_FIELDS[type(node).__name__]:
        target = getattr(node, field)
        out = substitute(node, {target.head.lemma: "zorble"})
        for f in dataclasses.fields(node):
            if f.name != field:
                assert getattr(out, f.name) == getattr(node, f.name), f"{field} → {f.name}"
        hit = getattr(out, field)
        assert hit.head.lemma == "zorble"
        assert (hit.possessor, hit.role, hit.modifier) == (target.possessor, target.role, target.modifier)


@pytest.mark.parametrize("node", PREDICATES, ids=lambda n: type(n).__name__)
def test_substituting_inside_a_possessor_keeps_the_parent_entity_whole(node):
    for field in OPERAND_FIELDS[type(node).__name__]:
        parent = getattr(node, field)
        out = getattr(substitute(node, {parent.possessor.head.lemma: "zorble"}), field)
        assert out.possessor.head.lemma == "zorble"
        assert dataclasses.replace(out, possessor=parent.possessor) == parent


def test_event_themes_are_kept_and_substituted():
    ev = _predicate(Event)
    assert substitute(ev, {"event_agent": "zorble"}).themes == ev.themes
    assert [t.head.lemma for t in substitute(ev, {"letter": "sword"}).themes] == ["sword"]


def test_string_substituted_atom_keeps_its_slot_fields():
    atom = _atom("fattest")
    out = substitute(atom, {"fattest": "cutest"})
    assert out.lemma == "cutest"
    assert dataclasses.replace(out, lemma=atom.lemma) == atom


@pytest.mark.parametrize("replacement", ["zorble", Atom(lemma="zorble", position=9, pos="PROPN")], ids=["str", "Atom"])
def test_head_substitution_keeps_the_slot_and_clears_the_old_heads_grounding(replacement):
    # Rohan's ruling (2026-10-04): the slot — possessor, role, modifier, entity_id — survives a head
    # substitution; the grounding computed for the OLD head (type_thread, span, apposition_thread)
    # does not describe the new word, so it is cleared for re-resolution.
    entity = _entity("macbeth")
    out = substitute(entity, {"macbeth": replacement})
    assert out.head.lemma == "zorble"
    assert (out.possessor, out.role, out.modifier, out.entity_id) == (
        entity.possessor,
        entity.role,
        entity.modifier,
        entity.entity_id,
    )
    assert (out.type_thread, out.span, out.apposition_thread) == ((), (), ())


def test_string_head_substitution_keeps_the_heads_grammatical_attributes():
    entity = _entity("macbeth")
    out = substitute(entity, {"macbeth": "zorble"})
    assert dataclasses.replace(out.head, lemma="macbeth") == entity.head


@pytest.fixture(scope="module")
def encoder():
    from gse.api import GSEEncoder

    with GSEEncoder() as enc:
        yield enc


def _tree(encoder, sentence):
    from gse.symbolic import evaluate_tree, from_trace, resolve

    return evaluate_tree(resolve(from_trace(encoder.encode(sentence))))


def test_possessed_entity_keeps_its_modifier_through_the_real_pipeline(encoder):
    tree = _tree(encoder, "Mike's big dog is cuter than the cat")
    dog = tree.lhs
    assert (dog.head.lemma, dog.possessor.head.lemma, dog.modifier.lemma) == ("dog", "mike", "big")
    out = substitute(tree, {"mike": "alice"}).lhs
    assert (out.head.lemma, out.possessor.head.lemma, out.modifier.lemma) == ("dog", "alice", "big")


def test_ditransitive_themes_survive_substitution_through_the_real_pipeline(encoder):
    tree = _tree(encoder, "Macbeth gave Duncan a letter")
    assert [t.head.lemma for t in substitute(tree, {"duncan": "banquo"}).themes] == ["letter"]
    assert [t.head.lemma for t in substitute(tree, {"letter": "sword"}).themes] == ["sword"]
