"""Phase B3 tests — query interface.

Verifies entities(), predicates(), axis_of_comparison(),
is_logically_equal_to(), and is_argument_swap_of() on representative
evaluated trees from real encoder output.
"""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    Atom,
    Causation,
    Comparison,
    axis_of_comparison,
    entity_lemmas,
    evaluate_tree,
    from_trace,
    is_argument_swap_of,
    is_logically_equal_to,
    predicates,
    resolve,
)


@pytest.fixture(scope="module")
def encoder():
    return GSEEncoder()


def _pipeline(encoder, sentence):
    """Encode → AST → resolve → evaluate. Returns the evaluated tree."""
    return evaluate_tree(resolve(from_trace(encoder.encode(sentence))))


# ---------------------------------------------------------------------------
# entities()
# ---------------------------------------------------------------------------


class TestEntities:
    def test_finds_two_entities_in_comparison(self, encoder):
        tree = _pipeline(encoder, "Mike is taller than Rex")
        lemmas = entity_lemmas(tree)
        assert "mike" in lemmas
        assert "rex" in lemmas

    def test_finds_possessor_too(self, encoder):
        tree = _pipeline(encoder, "Mike's dog ran fast")
        lemmas = entity_lemmas(tree)
        assert "mike" in lemmas
        assert "dog" in lemmas

    def test_no_duplicates_for_same_entity(self, encoder):
        tree = _pipeline(encoder, "Mike is taller than Rex")
        lemmas = entity_lemmas(tree)
        # No lemma appears more than once
        assert len(lemmas) == len(set(lemmas))

    def test_entities_in_causation_recovered(self, encoder):
        tree = _pipeline(encoder, "Mike sang so Rex left")
        lemmas = entity_lemmas(tree)
        assert "mike" in lemmas
        assert "rex" in lemmas


# ---------------------------------------------------------------------------
# predicates()
# ---------------------------------------------------------------------------


class TestPredicates:
    def test_comparison_returned(self, encoder):
        tree = _pipeline(encoder, "Mike is taller than Rex")
        preds = predicates(tree)
        assert len(preds) >= 1
        assert any(isinstance(p, Comparison) for p in preds)

    def test_causation_returned(self, encoder):
        tree = _pipeline(encoder, "Mike sang so Rex left")
        preds = predicates(tree)
        assert any(isinstance(p, Causation) for p in preds)

    def test_verb_clause_has_event_predicate(self, encoder):
        tree = _pipeline(encoder, "the dog ran")
        preds = predicates(tree)
        # A plain verb clause is now an Event roleframe (the base-case predicate).
        assert len(preds) == 1 and type(preds[0]).__name__ == "Event"
        assert preds[0].verb == "run"


# ---------------------------------------------------------------------------
# axis_of_comparison()
# ---------------------------------------------------------------------------


class TestAxisOfComparison:
    def test_axis_recovered_post_resolution(self, encoder):
        # v2 fix: Entity.modifier preserves the source Phrase's ADJ/ADV
        # through resolution, so axis_of_comparison recovers the axis
        # lemma after resolve() has run. Previously returned None.
        tree = _pipeline(encoder, "Mike is taller than Rex")
        preds = [p for p in predicates(tree) if isinstance(p, Comparison)]
        assert preds
        axis = axis_of_comparison(preds[0])
        assert axis is not None
        # spaCy lemmatizes "taller" to a root — accept the family
        assert axis in ("tall", "taller")

    def test_axis_extraction_works_on_unresolved_phrase(self, encoder):
        # Even if the resolved Predicate loses the axis, the *raw* AST
        # (no resolve) still contains it. Verifies the extractor works
        # when given content that has ADJ/ADV atoms.
        from gse.symbolic import Phrase
        phrase = Phrase(atoms=[
            Atom(lemma="the", word_primitives={}, position=0, pos="DET"),
            Atom(lemma="dog", word_primitives={}, position=1, pos="NOUN"),
            Atom(lemma="tall", word_primitives={}, position=2, pos="ADJ"),
        ])
        comp = Comparison(lhs=phrase, rhs=phrase, sign=+1)
        axis = axis_of_comparison(comp)
        assert axis == "tall"

    def test_no_axis_for_atom_input(self):
        a = Atom(lemma="dog", word_primitives={}, position=0, pos="NOUN")
        # axis_of_comparison only meaningful on Predicate inputs
        assert axis_of_comparison(a) is None


# ---------------------------------------------------------------------------
# is_logically_equal_to / is_argument_swap_of
# ---------------------------------------------------------------------------


class TestLogicalEquality:
    def test_same_sentence_logically_equal_to_itself(self, encoder):
        tree_a = _pipeline(encoder, "Mike is taller than Rex")
        tree_b = _pipeline(encoder, "Mike is taller than Rex")
        assert is_logically_equal_to(tree_a, tree_b)

    def test_argument_swap_NOT_logically_equal(self, encoder):
        # The headline architecture distinction: "dog cuter than cat" vs
        # "cat cuter than dog" should be DIFFERENT symbolically even though
        # they're similar in HDC space.
        tree_a = _pipeline(encoder, "The dog is cuter than the cat")
        tree_b = _pipeline(encoder, "The cat is cuter than the dog")
        assert not is_logically_equal_to(tree_a, tree_b)


class TestArgumentSwap:
    def test_swap_pair_detected(self, encoder):
        tree_a = _pipeline(encoder, "The dog is cuter than the cat")
        tree_b = _pipeline(encoder, "The cat is cuter than the dog")
        # B3's payoff: detects that one is the argument-swap of the other
        assert is_argument_swap_of(tree_a, tree_b)

    def test_non_swap_not_detected(self, encoder):
        tree_a = _pipeline(encoder, "Mike is taller than Rex")
        tree_b = _pipeline(encoder, "Mike sang so Rex left")
        # Completely different operations → not a swap
        assert not is_argument_swap_of(tree_a, tree_b)
