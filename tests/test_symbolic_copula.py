"""Copula type-assertion tests — "X is a Y" → TypeAssertion.

The copula carries no COMP_* operator (the encoder tags "is" as AUX /
SYN_PRED), so the type assertion is synthesized in ``from_trace`` from the
syntactic-role primitives SYN_SUBJ + SYN_PRED[be] + SYN_COMPL. Verifies the
synthesis, the resolved entity/kind binding, that a predicate adjective binds
the same way (decision A — "X is ADJ" is a TYPE_ASSERT, negation preserved),
and that comparatives are unaffected.

The "I is a person" case is the literal sentence that NPEs the Genesis core
(``consciousness.ProblemSolverAuxiliaries:66``,
``translateToEntity("I is a person").getSubject()``) — the reason a copula
type-assertion is the first build step of the Genesis × GSE swap.
"""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    Causation,
    Comparison,
    Event,
    TypeAssertion,
    evaluate_tree,
    from_trace,
    predicates,
    resolve,
)
from gse.symbolic.resolution import Entity


@pytest.fixture(scope="module")
def encoder():
    return GSEEncoder()


def _pipeline(encoder, sentence):
    return evaluate_tree(resolve(from_trace(encoder.encode(sentence))))


def _head(node):
    """The head Atom of an Entity, or the node itself if already an Atom."""
    return node.head if isinstance(node, Entity) else node


class TestCopulaTypeAssertion:
    def test_spot_is_a_dog_yields_one_type_assertion(self, encoder):
        preds = predicates(_pipeline(encoder, "Spot is a dog"))
        assert len(preds) == 1
        assert isinstance(preds[0], TypeAssertion)

    def test_spot_is_a_dog_binds_entity_and_kind(self, encoder):
        ta = predicates(_pipeline(encoder, "Spot is a dog"))[0]
        assert _head(ta.entity).lemma == "spot"
        assert _head(ta.kind).lemma == "dog"

    def test_genesis_blocker_sentence_resolves(self, encoder):
        # The literal sentence that NPEs Genesis core.
        ta = predicates(_pipeline(encoder, "I is a person"))[0]
        assert isinstance(ta, TypeAssertion)
        # "I" is a pronoun with no antecedent — it stays as the subject.
        assert _head(ta.entity).pos == "PRON"
        assert _head(ta.kind).lemma == "person"

    def test_predicative_adjective_is_a_type_assertion(self, encoder):
        # Design decision A (flywheel worklist #2): a predicate adjective binds the
        # same way as a predicate nominal — the entity takes on the complement's
        # primitive decomposition — so "X is ADJ" fires TYPE_ASSERT. Previously it
        # collapsed to a bare nominal (a degraded clause) and dropped negation.
        ta = predicates(_pipeline(encoder, "The dog is cute"))[0]
        assert isinstance(ta, TypeAssertion)
        assert _head(ta.entity).lemma == "dog"
        assert _head(ta.kind).lemma == "cute"

    def test_negated_predicative_adjective_preserves_negation(self, encoder):
        # The #2 correctness fix: "X is not ADJ" must NOT invert to "X is ADJ".
        # The predication forms, and the existing clause-negation wrapper applies.
        tree = _pipeline(encoder, "The dog is not cute")
        assert type(tree).__name__ == "Negation"
        assert isinstance(tree.operand, TypeAssertion)

    def test_comparative_unaffected(self, encoder):
        # Regression guard: the copula path must not disturb comparatives.
        preds = predicates(_pipeline(encoder, "The dog is cuter than the cat"))
        assert any(isinstance(p, Comparison) for p in preds)
        assert not any(isinstance(p, TypeAssertion) for p in preds)


class TestRelationalPredicateAdjective:
    """A predicate adjective with a PP complement ("X is loyal to Y") is a
    RELATION between X and the PP's object, not bare property attribution: it
    must become an Event keyed on the adjective so both arguments survive.
    Folding "loyal to Corwin" into one kind nominal dropped the preposition and
    the object, and (as a `because` cause clause) silently defeated learning.
    """

    def test_relational_adjective_is_an_event(self, encoder):
        ev = predicates(_pipeline(encoder, "Maeve is loyal to Corwin"))[0]
        assert isinstance(ev, Event)
        assert ev.verb == "loyal"
        assert _head(ev.agent).lemma == "maeve"
        assert _head(ev.patient).lemma == "corwin"

    def test_bare_predicate_adjective_stays_type_assertion(self, encoder):
        # Guard the decision-A path: no PP complement → still a TypeAssertion.
        ta = predicates(_pipeline(encoder, "Maeve is loyal"))[0]
        assert isinstance(ta, TypeAssertion)
        assert _head(ta.kind).lemma == "loyal"

    def test_relational_adjective_in_because_clause_learns_a_clean_event(self, encoder):
        # The silent-learning bug: the encoder tags the subordinate-clause
        # subject SYN_OBJ, so the copula path bailed and the cause collapsed to a
        # demi-word nominal ("doran maeve"), dropping "loyal". The cause must now
        # be an Event(loyal, doran, maeve) the rule learner can generalize.
        tree = _pipeline(encoder, "Doran protects Maeve because Doran is loyal to Maeve")
        assert isinstance(tree, Causation)
        assert isinstance(tree.cause, Event)
        assert tree.cause.verb == "loyal"
        assert _head(tree.cause.agent).lemma == "doran"
        assert _head(tree.cause.patient).lemma == "maeve"
