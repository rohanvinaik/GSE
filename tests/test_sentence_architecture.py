"""
Tests for the three-layer sentence architecture.

Tests validate:
1. Informational Zero: "ran" and "run" have cosine=1.0 at word level
2. Operator Resolution: Negation, hierarchy, auxiliaries work correctly
3. Constraint Propagation: Grammar rules prune impossible parses
4. Composition: Sentence vectors preserve expected structure
"""

import numpy as np
import pytest

from gse.composition.composer import SemanticComposer, compose_sentence
from gse.lexicon.similarity import semantic_similarity
from gse.lexicon.word_encoding import (
    PREDEFINED_OPERATORS,
    ComponentType,
    GrammaticalFeatures,
    GramRole,
    LexemeEntry,
    OperatorSpec,
)
from gse.parsing.graph import EdgeType, ParseEdge, ParseGraph, ParseNode
from gse.parsing.operators import OperatorState, apply_operators_to_atomic, resolve_operator
from gse.parsing.parser import SentenceParser
from gse.vectors_v2 import SparseVector

# ============================================================
# FIXTURES
# ============================================================


def make_random_vector(seed: int, dimension: int = 8192, nnz: int = 51) -> SparseVector:
    """Create a random sparse vector for testing."""
    rng = np.random.default_rng(seed=seed)
    indices = rng.choice(dimension, size=nnz, replace=False)
    signs = rng.choice([-1, 1], size=nnz)

    positive = indices[signs > 0].astype(np.uint16)
    negative = indices[signs < 0].astype(np.uint16)

    return SparseVector(
        dimension=dimension,
        positive_indices=positive,
        negative_indices=negative,
    )


def make_lexeme(
    lemma: str,
    surface_form: str,
    roles: set,
    component_type: ComponentType = ComponentType.ATOMIC,
    gram_features: GrammaticalFeatures = None,
    operator_spec: OperatorSpec = None,
    seed: int = None,
) -> LexemeEntry:
    """Create a test lexeme entry."""
    if seed is None:
        seed = hash(lemma) % (2**32)

    return LexemeEntry(
        lemma=lemma,
        surface_form=surface_form,
        semantic_vector=make_random_vector(seed),
        possible_roles=frozenset(roles),
        gram_features=gram_features or GrammaticalFeatures(),
        component_type=component_type,
        operator_spec=operator_spec,
    )


# ============================================================
# TEST: INFORMATIONAL ZERO
# ============================================================


class TestInformationalZero:
    """Tests for the informational zero principle."""

    def test_ran_run_same_semantic_vector(self):
        """
        'ran' and 'run' should have identical semantic vectors.

        The ONLY difference is in gram_features (tense metadata).
        """
        # Same seed = same semantic vector
        base_seed = 42

        run_lexeme = make_lexeme(
            lemma="run",
            surface_form="run",
            roles={GramRole.VERB},
            gram_features=GrammaticalFeatures(),  # Base form
            seed=base_seed,
        )

        ran_lexeme = make_lexeme(
            lemma="run",  # Same lemma!
            surface_form="ran",
            roles={GramRole.VERB},
            gram_features=GrammaticalFeatures(tense="PAST"),  # Tense differs
            seed=base_seed,  # Same seed = same semantic vector
        )

        # Semantic vectors should be identical
        similarity = semantic_similarity(
            run_lexeme.semantic_vector,
            ran_lexeme.semantic_vector,
        )
        assert abs(similarity - 1.0) < 1e-10, f"Expected 1.0, got {similarity}"

        # Gram features should differ
        assert run_lexeme.gram_features.tense is None
        assert ran_lexeme.gram_features.tense == "PAST"

    def test_different_lemmas_different_vectors(self):
        """
        Different lemmas should have different semantic vectors.
        """
        run_lexeme = make_lexeme(
            lemma="run",
            surface_form="run",
            roles={GramRole.VERB},
            seed=42,
        )

        walk_lexeme = make_lexeme(
            lemma="walk",
            surface_form="walk",
            roles={GramRole.VERB},
            seed=43,  # Different seed
        )

        similarity = semantic_similarity(
            run_lexeme.semantic_vector,
            walk_lexeme.semantic_vector,
        )
        # Should be much less than 1.0 (random overlap)
        assert similarity < 0.5, f"Expected < 0.5, got {similarity}"

    def test_gram_features_empty_check(self):
        """GrammaticalFeatures should correctly identify empty state."""
        empty = GrammaticalFeatures()
        assert empty.is_empty()

        with_tense = GrammaticalFeatures(tense="PAST")
        assert not with_tense.is_empty()


# ============================================================
# TEST: OPERATOR RESOLUTION
# ============================================================


class TestOperatorResolution:
    """Tests for the three-component operator model."""

    def test_sign_sets_pending(self):
        """SIGN operator should set pending_sign."""
        not_lexeme = make_lexeme(
            lemma="not",
            surface_form="not",
            roles={GramRole.ADV},
            component_type=ComponentType.OPERATOR,
            operator_spec=PREDEFINED_OPERATORS["not"],
        )

        state = OperatorState()
        new_state = resolve_operator(not_lexeme, state)

        assert new_state.pending_sign == -1
        assert new_state.pending_hierarchy is None

    def test_hierarchy_consumes_sign(self):
        """HIERARCHY should consume pending sign and invert."""
        not_lexeme = make_lexeme(
            lemma="not",
            surface_form="not",
            roles={GramRole.ADV},
            component_type=ComponentType.OPERATOR,
            operator_spec=PREDEFINED_OPERATORS["not"],
        )

        very_lexeme = make_lexeme(
            lemma="very",
            surface_form="very",
            roles={GramRole.ADV},
            component_type=ComponentType.OPERATOR,
            operator_spec=PREDEFINED_OPERATORS["very"],
        )

        # "not very" sequence
        state = OperatorState()
        state = resolve_operator(not_lexeme, state)
        assert state.pending_sign == -1

        state = resolve_operator(very_lexeme, state)
        # Sign should be consumed
        assert state.pending_sign is None
        # Hierarchy should be inverted: -1 * +1 = -1
        assert state.pending_hierarchy == -1

    def test_hierarchy_stacking(self):
        """Multiple hierarchy operators should stack."""
        very_lexeme = make_lexeme(
            lemma="very",
            surface_form="very",
            roles={GramRole.ADV},
            component_type=ComponentType.OPERATOR,
            operator_spec=PREDEFINED_OPERATORS["very"],
        )

        # "very very" sequence
        state = OperatorState()
        state = resolve_operator(very_lexeme, state)
        state = resolve_operator(very_lexeme, state)

        # Should stack: +1 + +1 = +2
        assert state.pending_hierarchy == 2

    def test_auxiliary_lazy_binding(self):
        """AUXILIARY should be pushed to stack (lazy binding)."""
        did_lexeme = make_lexeme(
            lemma="do",
            surface_form="did",
            roles={GramRole.AUX},
            component_type=ComponentType.OPERATOR,
            operator_spec=PREDEFINED_OPERATORS["did"],
            gram_features=GrammaticalFeatures(tense="PAST"),
        )

        state = OperatorState()
        state = resolve_operator(did_lexeme, state)

        assert len(state.pending_auxiliaries) == 1
        assert state.pending_auxiliaries[0].surface_form == "did"

    def test_apply_to_atomic(self):
        """Pending operators should apply to atomic node."""
        # Create "not very happy" scenario
        happy_lexeme = make_lexeme(
            lemma="happy",
            surface_form="happy",
            roles={GramRole.ADJ},
        )

        node = ParseNode(position=2, lexeme=happy_lexeme)
        node.assigned_role = GramRole.ADJ

        # State after "not very"
        state = OperatorState(pending_hierarchy=-1)  # Inverted by "not"

        apply_operators_to_atomic(node, state)

        assert node.hierarchy_level == -1


# ============================================================
# TEST: CONSTRAINT PROPAGATION
# ============================================================


class TestConstraintPropagation:
    """Tests for grammatical constraint propagation."""

    def test_det_noun_sequence(self):
        """DET should only precede NOUN/ADJ."""
        the_lexeme = make_lexeme(
            lemma="the",
            surface_form="the",
            roles={GramRole.DET},
            component_type=ComponentType.OPERATOR,
            operator_spec=PREDEFINED_OPERATORS["the"],
        )

        dog_lexeme = make_lexeme(
            lemma="dog",
            surface_form="dog",
            roles={GramRole.NOUN},
        )

        parser = SentenceParser()
        graph = parser.parse_with_lexemes([the_lexeme, dog_lexeme])

        assert len(graph.nodes) == 2
        assert graph.nodes[0].assigned_role == GramRole.DET
        assert graph.nodes[1].assigned_role == GramRole.NOUN

    def test_subject_verb_object(self):
        """Basic SVO sentence should parse correctly."""
        he_lexeme = make_lexeme(
            lemma="he",
            surface_form="he",
            roles={GramRole.PRON},
        )

        ran_lexeme = make_lexeme(
            lemma="run",
            surface_form="ran",
            roles={GramRole.VERB},
            gram_features=GrammaticalFeatures(tense="PAST"),
        )

        fast_lexeme = make_lexeme(
            lemma="fast",
            surface_form="fast",
            roles={GramRole.ADV},
        )

        parser = SentenceParser()
        graph = parser.parse_with_lexemes([he_lexeme, ran_lexeme, fast_lexeme])

        assert graph.nodes[0].assigned_role == GramRole.PRON
        assert graph.nodes[1].assigned_role == GramRole.VERB
        assert graph.nodes[2].assigned_role == GramRole.ADV

        # Should have SUBJECT edge: he -> ran
        subject_edges = [e for e in graph.edges if e.edge_type == EdgeType.SUBJECT]
        assert len(subject_edges) >= 1


# ============================================================
# TEST: COMPOSITION
# ============================================================


class TestComposition:
    """Tests for HDC composition."""

    def test_compose_simple_sentence(self):
        """Composition should produce non-empty vector."""
        he_lexeme = make_lexeme(
            lemma="he",
            surface_form="he",
            roles={GramRole.PRON},
        )

        ran_lexeme = make_lexeme(
            lemma="run",
            surface_form="ran",
            roles={GramRole.VERB},
        )

        parser = SentenceParser()
        graph = parser.parse_with_lexemes([he_lexeme, ran_lexeme])

        sentence_vec = compose_sentence(graph)

        assert sentence_vec.nnz > 0, "Sentence vector should be non-empty"

    def test_negation_changes_vector(self):
        """Negated sentence should differ from non-negated."""
        he_lexeme = make_lexeme(
            lemma="he",
            surface_form="he",
            roles={GramRole.PRON},
        )

        ran_lexeme = make_lexeme(
            lemma="run",
            surface_form="ran",
            roles={GramRole.VERB},
            seed=100,
        )

        # Non-negated
        parser = SentenceParser()
        graph_positive = parser.parse_with_lexemes([he_lexeme, ran_lexeme])
        vec_positive = compose_sentence(graph_positive)

        # Manually set negation on verb
        graph_negative = parser.parse_with_lexemes([he_lexeme, ran_lexeme])
        graph_negative.nodes[1].pending_sign = -1
        vec_negative = compose_sentence(graph_negative)

        # Vectors should differ
        similarity = semantic_similarity(vec_positive, vec_negative)
        assert similarity < 0.9, f"Expected different vectors, got similarity {similarity}"

    def test_intensity_ordering(self):
        """
        Intensity modifications should create ordered representations.

        happy < very happy (in terms of intensity subspace)
        """
        happy_base = make_lexeme(
            lemma="happy",
            surface_form="happy",
            roles={GramRole.ADJ},
            seed=42,
        )

        # Create nodes with different hierarchy levels
        node_neutral = ParseNode(position=0, lexeme=happy_base, hierarchy_level=0)
        node_intense = ParseNode(position=0, lexeme=happy_base, hierarchy_level=1)
        node_very_intense = ParseNode(position=0, lexeme=happy_base, hierarchy_level=2)

        composer = SemanticComposer()

        vec_neutral = composer._get_modified_vector(node_neutral)
        vec_intense = composer._get_modified_vector(node_intense)
        vec_very_intense = composer._get_modified_vector(node_very_intense)

        # All should be different from each other
        sim_neutral_intense = semantic_similarity(vec_neutral, vec_intense)
        sim_intense_very = semantic_similarity(vec_intense, vec_very_intense)

        # Due to permutation, they should be fairly dissimilar
        assert sim_neutral_intense < 0.8
        assert sim_intense_very < 0.8


# ============================================================
# TEST: SPARSE VECTOR BANK OPERATIONS
# ============================================================


class TestBankOperations:
    """Tests for without_bank() and with_bank_only() methods."""

    def test_without_bank(self):
        """without_bank() should remove dimensions from specified bank."""
        vec = make_random_vector(seed=42, dimension=8192, nnz=100)

        # Remove bank 0 (dims 0-1023)
        filtered = vec.without_bank(0, dims_per_bank=1024)

        # Check no indices in bank 0
        assert all(idx >= 1024 for idx in filtered.positive_indices)
        assert all(idx >= 1024 for idx in filtered.negative_indices)

        # Original should be unchanged
        assert vec.nnz >= filtered.nnz

    def test_with_bank_only(self):
        """with_bank_only() should keep only specified bank dimensions."""
        vec = make_random_vector(seed=42, dimension=8192, nnz=100)

        # Keep only bank 0 (dims 0-1023)
        filtered = vec.with_bank_only(0, dims_per_bank=1024)

        # Check all indices are in bank 0
        assert all(0 <= idx < 1024 for idx in filtered.positive_indices)
        assert all(0 <= idx < 1024 for idx in filtered.negative_indices)


# ============================================================
# TEST: PARSE GRAPH STRUCTURE
# ============================================================


class TestParseGraph:
    """Tests for ParseGraph data structure."""

    def test_graph_accessors(self):
        """ParseGraph should provide convenient accessors."""
        he_lexeme = make_lexeme("he", "he", {GramRole.PRON})
        ran_lexeme = make_lexeme("run", "ran", {GramRole.VERB})

        graph = ParseGraph(
            nodes=[
                ParseNode(position=0, lexeme=he_lexeme, assigned_role=GramRole.PRON),
                ParseNode(position=1, lexeme=ran_lexeme, assigned_role=GramRole.VERB),
            ],
            edges=[
                ParseEdge(source=0, target=1, edge_type=EdgeType.SUBJECT),
            ],
        )

        assert graph.get_subject().word == "he"
        assert graph.get_predicate().word == "ran"

    def test_pretty_print(self):
        """ParseGraph should produce readable output."""
        he_lexeme = make_lexeme("he", "he", {GramRole.PRON})
        ran_lexeme = make_lexeme("run", "ran", {GramRole.VERB})

        graph = ParseGraph(
            nodes=[
                ParseNode(position=0, lexeme=he_lexeme, assigned_role=GramRole.PRON),
                ParseNode(position=1, lexeme=ran_lexeme, assigned_role=GramRole.VERB),
            ],
            edges=[
                ParseEdge(source=0, target=1, edge_type=EdgeType.SUBJECT),
            ],
        )

        output = graph.pretty_print()
        assert "Parse Graph" in output
        assert "he" in output
        assert "ran" in output
        assert "SUBJECT" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
