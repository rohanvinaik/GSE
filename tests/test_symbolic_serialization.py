"""Phase B4 tests — JSON serialization round-trip.

Verifies every node type's ``to_dict``/``from_dict`` are inverses,
plus the JSON wrappers ``to_json``/``from_json``, plus full-tree
round-trips for representative encoded sentences.
"""

import json

import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    Atom,
    BoundaryCase,
    Causation,
    Comparison,
    Contrast,
    DegreeQuery,
    Entity,
    Equality,
    MinimalSufficiency,
    Negation,
    Op,
    Phrase,
    SerializationError,
    SetRestriction,
    TypeQuery,
    evaluate_tree,
    from_dict,
    from_json,
    from_trace,
    resolve,
    to_dict,
    to_json,
)


@pytest.fixture(scope="module")
def encoder():
    return GSEEncoder()


def _atom(lemma="x", pos="NOUN", role=None):
    return Atom(lemma=lemma, word_primitives={"GOOD": 1}, role=role, position=0, pos=pos)


# ---------------------------------------------------------------------------
# Per-node-type round-trip
# ---------------------------------------------------------------------------


class TestAstNodeRoundTrip:
    def test_atom_round_trip(self):
        a = _atom("dog", "NOUN", role="subject")
        assert from_dict(to_dict(a)) == a

    def test_phrase_round_trip(self):
        p = Phrase(atoms=[_atom("a"), _atom("b")])
        restored = from_dict(to_dict(p))
        assert isinstance(restored, Phrase)
        assert [x.lemma for x in restored.atoms] == ["a", "b"]

    def test_negation_round_trip(self):
        n = Negation(operand=_atom("good"))
        restored = from_dict(to_dict(n))
        assert isinstance(restored, Negation)
        assert restored.operand.lemma == "good"

    def test_op_round_trip(self):
        op = Op(primitive="COMP_THAN", operation="SET_DIFF", arity=2,
                args=[_atom("a"), _atom("b")])
        restored = from_dict(to_dict(op))
        assert isinstance(restored, Op)
        assert restored.primitive == "COMP_THAN"
        assert len(restored.args) == 2

    def test_entity_round_trip(self):
        e = Entity(head=_atom("dog"), possessor=Entity(head=_atom("mike")))
        restored = from_dict(to_dict(e))
        assert isinstance(restored, Entity)
        assert restored.head.lemma == "dog"
        assert restored.possessor.head.lemma == "mike"

    def test_entity_with_modifier_round_trip(self):
        # v2 fix: modifier survives serialization
        modifier_atom = Atom(lemma="tall", word_primitives={}, position=2, pos="ADJ")
        e = Entity(head=_atom("dog"), modifier=modifier_atom)
        restored = from_dict(to_dict(e))
        assert isinstance(restored, Entity)
        assert restored.modifier is not None
        assert restored.modifier.lemma == "tall"
        assert restored.modifier.pos == "ADJ"


class TestPredicateRoundTrip:
    @pytest.mark.parametrize("pred", [
        Comparison(lhs=_atom("a"), rhs=_atom("b"), sign=+1),
        Equality(lhs=_atom("a"), rhs=_atom("b")),
        TypeQuery(entity=_atom("a")),
        DegreeQuery(entity=_atom("a")),
        MinimalSufficiency(threshold=_atom("food"), purpose=_atom("ben")),
        SetRestriction(member=_atom("mike"), predicate=_atom("sings")),
        BoundaryCase(entity=_atom("mike"), predicate=_atom("sings")),
        Contrast(left=_atom("sings"), right=_atom("runs")),
        Causation(cause=_atom("sang"), effect=_atom("left"), conjunction="so"),
        Causation(cause=_atom("sang"), effect=_atom("left"), conjunction="because"),
    ])
    def test_predicate_round_trip(self, pred):
        restored = from_dict(to_dict(pred))
        assert type(restored) is type(pred)
        assert restored == pred


class TestJsonWrappers:
    def test_to_json_returns_valid_json_string(self):
        a = _atom("dog")
        s = to_json(a)
        # Round-trip through json.loads then from_dict
        d = json.loads(s)
        assert d["_kind"] == "Atom"
        assert d["lemma"] == "dog"

    def test_from_json_inverts_to_json(self):
        a = _atom("dog", "NOUN")
        s = to_json(a)
        restored = from_json(s)
        assert restored == a


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TestErrors:
    def test_missing_kind_raises(self):
        with pytest.raises(SerializationError, match="_kind"):
            from_dict({"lemma": "x"})

    def test_unknown_kind_raises(self):
        with pytest.raises(SerializationError, match="Unknown"):
            from_dict({"_kind": "Nonsense"})


# ---------------------------------------------------------------------------
# Full-tree round-trip on encoded sentences
# ---------------------------------------------------------------------------


class TestEndToEndRoundTrip:
    @pytest.mark.parametrize("sentence", [
        "Mike is taller than Rex",
        "Mike sang so Rex left",
        "Mike left because Rex sang",
        "Only Mike sings",
        "Even Mike sings",
        "Mike's dog ran fast",
    ])
    def test_evaluated_tree_round_trips(self, encoder, sentence):
        # Encode → AST → resolve → evaluate → serialize → deserialize
        trace = encoder.encode(sentence)
        expr = resolve(from_trace(trace))
        pred = evaluate_tree(expr)
        as_json = to_json(pred)
        restored = from_json(as_json)
        assert type(restored) is type(pred)

    def test_resolved_ast_round_trips(self, encoder):
        # The pre-evaluation AST also round-trips (Entity nodes included)
        trace = encoder.encode("Mike's dog ran fast")
        expr = resolve(from_trace(trace))
        as_json = to_json(expr)
        restored = from_json(as_json)
        # Same shape — possessive entity should survive
        assert _contains_possessive(restored, "dog", "mike")


def _contains_possessive(expr, head, possessor):
    if isinstance(expr, Entity):
        if (expr.head.lemma == head and expr.possessor is not None
                and expr.possessor.head.lemma == possessor):
            return True
        if expr.possessor is not None:
            return _contains_possessive(expr.possessor, head, possessor)
        return False
    if isinstance(expr, Op):
        return any(_contains_possessive(a, head, possessor) for a in expr.args)
    return False
