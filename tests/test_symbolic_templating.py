"""Phase B6 tests — structural templating / entity substitution."""

import pytest

from gse.api import GSEEncoder
from gse.symbolic import (
    Atom,
    Entity,
    entity_lemmas,
    evaluate_tree,
    from_trace,
    is_logically_equal_to,
    resolve,
    substitute,
)


@pytest.fixture(scope="module")
def encoder():
    return GSEEncoder()


def _pipeline(encoder, sentence):
    return evaluate_tree(resolve(from_trace(encoder.encode(sentence))))


class TestStringSubstitution:
    def test_swap_one_entity_by_string(self, encoder):
        tree = _pipeline(encoder, "Mike is taller than Rex")
        templated = substitute(tree, {"mike": "alice"})
        lemmas = entity_lemmas(templated)
        assert "alice" in lemmas
        assert "mike" not in lemmas
        assert "rex" in lemmas  # unchanged

    def test_swap_both_entities(self, encoder):
        tree = _pipeline(encoder, "Mike is taller than Rex")
        templated = substitute(tree, {"mike": "alice", "rex": "bob"})
        lemmas = entity_lemmas(templated)
        assert "alice" in lemmas
        assert "bob" in lemmas
        assert "mike" not in lemmas
        assert "rex" not in lemmas


class TestAtomSubstitution:
    def test_swap_with_atom_replaces_entity_head(self):
        original = Entity(head=Atom(lemma="dog", word_primitives={"ALIVE": 1}, position=0, pos="NOUN"))
        new_head = Atom(lemma="cat", word_primitives={"ALIVE": 1, "BODY": 1}, position=0, pos="NOUN")
        result = substitute(original, {"dog": new_head})
        assert isinstance(result, Entity)
        assert result.head.lemma == "cat"
        # word_primitives from the substitute Atom carry through
        assert result.head.word_primitives.get("BODY") == 1


class TestEntitySubstitution:
    def test_swap_with_entity_replaces_wholesale(self):
        original = Entity(head=Atom(lemma="dog", word_primitives={}, position=0, pos="NOUN"))
        new_entity = Entity(
            head=Atom(lemma="hound", word_primitives={}, position=0, pos="NOUN"),
            possessor=Entity(head=Atom(lemma="alice", word_primitives={}, position=0, pos="PROPN")),
        )
        result = substitute(original, {"dog": new_entity})
        assert result.head.lemma == "hound"
        assert result.possessor is not None
        assert result.possessor.head.lemma == "alice"


class TestStructurePreservation:
    def test_substitution_preserves_logical_shape(self, encoder):
        # Substitute every entity in "dog cuter than cat" — the resulting
        # template should be logically isomorphic to the original (same
        # operation, swapped content). Verifies B6 + B3 working together.
        tree_a = _pipeline(encoder, "The dog is cuter than the cat")
        tree_b = substitute(tree_a, {"dog": "rabbit", "cat": "mouse"})
        # Same structure, different content → logically equal w.r.t.
        # operations but with different entity lemmas
        # Since lemmas differ, NOT logically equal:
        assert not is_logically_equal_to(tree_a, tree_b)
        # Same swap performed on a back-substitution recovers the
        # original structure
        tree_back = substitute(tree_b, {"rabbit": "dog", "mouse": "cat"})
        assert is_logically_equal_to(tree_a, tree_back)

    def test_swap_produces_argument_swap_when_args_are_swapped(self, encoder):
        # "dog cuter than cat" with {dog→cat, cat→dog} should be logically
        # equivalent to "cat cuter than dog" — the argument-swap pair.
        tree_orig = _pipeline(encoder, "The dog is cuter than the cat")
        tree_swap_template = substitute(tree_orig, {"dog": "cat", "cat": "dog"})
        tree_actually_swapped = _pipeline(encoder, "The cat is cuter than the dog")
        # Both should be logically equal (same operations on same entities)
        assert is_logically_equal_to(tree_swap_template, tree_actually_swapped)

    def test_substitution_is_pure(self, encoder):
        # Input tree is not mutated
        tree = _pipeline(encoder, "Mike is taller than Rex")
        original_lemmas = sorted(entity_lemmas(tree))
        substitute(tree, {"mike": "alice"})
        # Same tree object — original entities unchanged
        assert sorted(entity_lemmas(tree)) == original_lemmas


class TestEdgeCases:
    def test_no_match_returns_equivalent_tree(self, encoder):
        tree = _pipeline(encoder, "Mike is taller than Rex")
        result = substitute(tree, {"alice": "bob"})  # no key matches
        assert is_logically_equal_to(tree, result)

    def test_empty_mapping_no_op(self, encoder):
        tree = _pipeline(encoder, "Mike is taller than Rex")
        result = substitute(tree, {})
        assert is_logically_equal_to(tree, result)

    def test_invalid_mapping_value_raises(self, encoder):
        tree = _pipeline(encoder, "Mike is taller than Rex")
        with pytest.raises(TypeError, match="must be str, Atom, or Entity"):
            substitute(tree, {"mike": 42})  # type: ignore
