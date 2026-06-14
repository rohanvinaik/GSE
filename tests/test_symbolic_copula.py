"""Copula type-assertion tests — "X is a Y" → TypeAssertion.

The copula carries no COMP_* operator (the encoder tags "is" as AUX /
SYN_PRED), so the type assertion is synthesized in ``from_trace`` from the
syntactic-role primitives SYN_SUBJ + SYN_PRED[be] + SYN_COMPL. Verifies the
synthesis, the resolved entity/kind binding, the nominal-only guard, and
that comparatives are unaffected.

The "I is a person" case is the literal sentence that NPEs the Genesis core
(``consciousness.ProblemSolverAuxiliaries:66``,
``translateToEntity("I is a person").getSubject()``) — the reason a copula
type-assertion is the first build step of the Genesis × GSE swap.
"""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    Comparison,
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

    def test_predicative_adjective_is_not_a_type_assertion(self, encoder):
        # "X is cute" is a property, not a type — must NOT fire TYPE_ASSERT.
        preds = predicates(_pipeline(encoder, "The dog is cute"))
        assert not any(isinstance(p, TypeAssertion) for p in preds)

    def test_comparative_unaffected(self, encoder):
        # Regression guard: the copula path must not disturb comparatives.
        preds = predicates(_pipeline(encoder, "The dog is cuter than the cat"))
        assert any(isinstance(p, Comparison) for p in preds)
        assert not any(isinstance(p, TypeAssertion) for p in preds)
