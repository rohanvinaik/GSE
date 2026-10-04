"""
Every walker over a predicate tree handles every Predicate type (#3).

The defect: each walker hand-listed the types it knew, and the lists drifted. ClauseCoordination,
Conditional and Temporal were missing from ``queries`` (entities / predicates / clauses / the
swap and logical-equality signatures), Temporal from ``grounding``'s recursion map and
``coherence``'s visit, all three from ``templating``, and ``_structural_signature`` had no Event
case at all. ``grounding`` claimed its map was "kept parallel and asserted by tests"; no test did.

These laws are derived from the ``Predicate`` union itself, so a type added later fails here until
every walker handles it — the drift cannot recur silently.
"""

import dataclasses
import typing
from types import SimpleNamespace

import pytest

from gse.symbolic.coherence import coherence_report
from gse.symbolic.emit import _PRED_SPEC  # the package re-exports a FUNCTION named emit, so import by name
from gse.symbolic.expression import Atom, Phrase
from gse.symbolic.grounding import OPERAND_FIELDS as GROUNDING_OPERAND_FIELDS
from gse.symbolic.grounding import NullGenealogy, _walk_predicates, resolve_references
from gse.symbolic.narrative import _CONTAINER_FIELDS
from gse.symbolic.predicates import OPERAND_FIELDS, Predicate
from gse.symbolic.queries import (
    _structural_signature,
    clauses,
    entities,
    is_argument_swap_of,
    is_logically_equal_to,
    predicates,
)
from gse.symbolic.resolution import Entity
from gse.symbolic.templating import substitute

PREDICATE_TYPES = typing.get_args(Predicate)
CLAUSE_LINKERS = ("Contrast", "ClauseCoordination", "Causation", "Conditional", "Temporal")


def _entity(lemma: str, position: int = 0) -> Entity:
    return Entity(head=Atom(lemma=lemma, position=position, pos="PROPN"))


def _instance(cls, lemma_of=lambda field: field):
    """One instance of ``cls`` whose every operand field holds a distinct Entity."""
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.name in OPERAND_FIELDS[cls.__name__]:
            kwargs[f.name] = _entity(f"{cls.__name__.lower()}_{lemma_of(f.name)}")
        elif f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            kwargs[f.name] = "act"  # a required feature field (Event.verb)
    return cls(**kwargs)


def _operand_lemmas(node) -> set:
    return {getattr(node, f).head.lemma for f in OPERAND_FIELDS[type(node).__name__]}


# ---------------------------------------------------------------------------
# The map itself
# ---------------------------------------------------------------------------


def test_operand_fields_cover_exactly_the_predicate_union():
    assert set(OPERAND_FIELDS) == {cls.__name__ for cls in PREDICATE_TYPES}


@pytest.mark.parametrize("cls", PREDICATE_TYPES, ids=lambda c: c.__name__)
def test_operand_fields_name_every_operand_typed_field(cls):
    typed = {f.name for f in dataclasses.fields(cls) if "Operand" in str(f.type)}
    assert set(OPERAND_FIELDS[cls.__name__]) == typed


def test_emit_contract_spec_matches_the_map():
    assert {k: v[1] for k, v in _PRED_SPEC.items()} == OPERAND_FIELDS


def test_grounding_walks_the_canonical_map():
    assert GROUNDING_OPERAND_FIELDS is OPERAND_FIELDS


def test_narrative_container_fields_agree_with_the_map():
    for kind, fields in _CONTAINER_FIELDS.items():
        if kind in OPERAND_FIELDS:
            assert fields == OPERAND_FIELDS[kind], kind


# ---------------------------------------------------------------------------
# Every walker reaches every operand of every Predicate type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cls", PREDICATE_TYPES, ids=lambda c: c.__name__)
def test_entities_reaches_every_operand(cls):
    node = _instance(cls)
    assert {e.head.lemma for e in entities(node)} == _operand_lemmas(node)


@pytest.mark.parametrize("cls", PREDICATE_TYPES, ids=lambda c: c.__name__)
def test_predicates_returns_the_node(cls):
    node = _instance(cls)
    assert node in predicates(node)


@pytest.mark.parametrize("cls", PREDICATE_TYPES, ids=lambda c: c.__name__)
def test_substitute_reaches_every_operand(cls):
    node = _instance(cls)
    renamed = substitute(node, {lemma: f"{lemma}_x" for lemma in _operand_lemmas(node)})
    assert _operand_lemmas(renamed) == {f"{lemma}_x" for lemma in _operand_lemmas(node)}


@pytest.mark.parametrize("cls", PREDICATE_TYPES, ids=lambda c: c.__name__)
def test_structural_signature_is_structural_for_every_type(cls):
    node = _instance(cls)
    assert _structural_signature(node)[0] == cls.__name__
    # Content-sensitive: changing any operand's lemma changes the signature.
    for field in OPERAND_FIELDS[cls.__name__]:
        other = dataclasses.replace(node, **{field: _entity("someone_else")})
        assert not is_logically_equal_to(node, other), field


@pytest.mark.parametrize("cls", PREDICATE_TYPES, ids=lambda c: c.__name__)
def test_logical_equality_ignores_positions_and_primitives(cls):
    a = _instance(cls)
    b = dataclasses.replace(
        a,
        **{
            f: Entity(head=Atom(lemma=getattr(a, f).head.lemma, position=9, word_primitives={"DO": 1}))
            for f in OPERAND_FIELDS[cls.__name__]
        },
    )
    assert is_logically_equal_to(a, b)


@pytest.mark.parametrize("cls", PREDICATE_TYPES, ids=lambda c: c.__name__)
def test_resolve_references_reaches_every_operand(cls):
    resolved = resolve_references(_instance(cls), NullGenealogy())
    ids = {getattr(resolved, f).entity_id for f in OPERAND_FIELDS[cls.__name__]}
    assert None not in ids and len(ids) == len(OPERAND_FIELDS[cls.__name__])


@pytest.mark.parametrize("cls", PREDICATE_TYPES, ids=lambda c: c.__name__)
def test_grounding_predicate_walk_yields_the_node(cls):
    node = _instance(cls)
    assert node in list(_walk_predicates(node))


@pytest.mark.parametrize("name", CLAUSE_LINKERS)
def test_clause_linkers_are_clauses_and_swap(name):
    cls = next(c for c in PREDICATE_TYPES if c.__name__ == name)
    node = _instance(cls)
    assert clauses(node) == [node]
    left, right = OPERAND_FIELDS[name]
    swapped = dataclasses.replace(node, **{left: getattr(node, right), right: getattr(node, left)})
    assert is_argument_swap_of(node, swapped)


@pytest.mark.parametrize("name", CLAUSE_LINKERS)
def test_coherence_visits_both_clauses_of_every_linker(name):
    # A collapsed clause: a bare Phrase holding a verb-sense token AND a distinct would-be subject.
    tokens = [
        SimpleNamespace(token="Brutus", lemma="brutus", pos="PROPN", position=0),
        SimpleNamespace(token="betrayed", lemma="betray", pos="NOUN", position=1),
        SimpleNamespace(token="Caesar", lemma="caesar", pos="PROPN", position=2),
        SimpleNamespace(token="fled", lemma="flee", pos="NOUN", position=3),
    ]
    trace = SimpleNamespace(tokens=tokens)

    def collapsed(subject: int, verb: int) -> Phrase:
        return Phrase(atoms=[Atom(lemma=tokens[i].lemma, position=i, pos=tokens[i].pos) for i in (subject, verb)])

    cls = next(c for c in PREDICATE_TYPES if c.__name__ == name)
    left, right = OPERAND_FIELDS[name]
    node = cls(**{left: collapsed(0, 1), right: collapsed(2, 3)})
    assert [r["positions"] for r in coherence_report(node, trace)] == [[0, 1], [2, 3]]
