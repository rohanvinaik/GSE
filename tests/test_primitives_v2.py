#!/usr/bin/env python3
"""
Tests for GSE Primitives v2 and Vectors v2

Verifies:
1. Bipolar dimensions have cosine = -1.0 for antonym pairs
2. Within-bank orthogonality for non-antonym primitives
3. Cross-bank orthogonality (exact zero due to disjoint dimensions)
4. Hierarchical modifier encoding
5. HDC operations (bind, bundle, permute)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.primitives_v2 import (
    BIPOLAR_DIMENSIONS,
    DIMS_PER_BANK,
    HUB_PRIMITIVES,
    INTENSITY_HIERARCHY,
    N_BANKS,
    PRIMITIVE_FAMILIES,
    PRIMITIVE_REGISTRY,
    QUANTITY_HIERARCHY,
    D,
    SemanticBank,
    expand_hierarchy_activation,
    get_canonical_pole,
    get_dimension_range,
    get_hierarchy_encoding,
    is_bipolar,
)
from gse.vectors_v2 import (
    SparseVector,
    bank_activity_profile,
    bind,
    bundle,
    compose_decomposition,
    create_basis,
    permute,
    polarity_aware_similarity,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(scope="module")
def basis():
    """Create basis once for all tests."""
    return create_basis()


# =============================================================================
# PRIMITIVE STRUCTURE TESTS
# =============================================================================


class TestPrimitiveStructure:
    """Test primitive definitions and organization."""

    def test_total_primitive_count(self):
        """Should have ~60 primitives (45 unipolar + 10 bipolar dims * 2 poles, minus overlap)."""
        assert 50 <= len(PRIMITIVE_REGISTRY) <= 75  # 72 primitives after adding CAUSE and INFER

    def test_bipolar_dimensions_count(self):
        """Should have exactly 14 bipolar dimensions."""
        assert len(BIPOLAR_DIMENSIONS) == 14

    def test_all_bipolar_poles_in_registry(self):
        """All bipolar poles should be in the primitive registry."""
        for dim in BIPOLAR_DIMENSIONS:
            assert dim.positive in PRIMITIVE_REGISTRY
            assert dim.negative in PRIMITIVE_REGISTRY

    def test_hub_primitives_in_registry(self):
        """All hub primitives should be in the registry."""
        for hub in HUB_PRIMITIVES:
            assert hub in PRIMITIVE_REGISTRY, f"Hub {hub} not in registry"

    def test_primitive_families_cover_all_banks(self):
        """Each bank should have at least one family."""
        banks_covered = set()
        for family_info in PRIMITIVE_FAMILIES.values():
            banks_covered.add(family_info["bank"])
        for bank in SemanticBank:
            assert bank in banks_covered, f"Bank {bank} has no family"

    def test_dimension_range_non_overlapping(self):
        """Bank dimension ranges should not overlap."""
        ranges = [get_dimension_range(bank) for bank in SemanticBank]
        for i, (s1, e1) in enumerate(ranges):
            for j, (s2, e2) in enumerate(ranges):
                if i != j:
                    assert e1 <= s2 or e2 <= s1, f"Banks {i} and {j} overlap"


# =============================================================================
# BIPOLAR DIMENSION TESTS
# =============================================================================


class TestBipolarDimensions:
    """Test antonym pair handling."""

    def test_is_bipolar_detection(self):
        """is_bipolar should correctly identify bipolar primitives."""
        assert is_bipolar("GOOD")
        assert is_bipolar("BAD")
        assert is_bipolar("ABOVE")
        assert is_bipolar("BELOW")
        assert not is_bipolar("THINK")
        assert not is_bipolar("SOMEONE")

    def test_canonical_pole_positive(self):
        """Positive poles should canonicalize to themselves with +1."""
        for dim in BIPOLAR_DIMENSIONS:
            canonical, polarity = get_canonical_pole(dim.positive)
            assert canonical == dim.positive
            assert polarity == 1

    def test_canonical_pole_negative(self):
        """Negative poles should canonicalize to positive pole with -1."""
        for dim in BIPOLAR_DIMENSIONS:
            canonical, polarity = get_canonical_pole(dim.negative)
            assert canonical == dim.positive
            assert polarity == -1

    def test_non_bipolar_canonical_unchanged(self):
        """Non-bipolar primitives should be unchanged."""
        canonical, polarity = get_canonical_pole("THINK")
        assert canonical == "THINK"
        assert polarity == 1


# =============================================================================
# HIERARCHY TESTS
# =============================================================================


class TestHierarchyEncoding:
    """Test hierarchical modifier encoding."""

    def test_quantity_hierarchy_levels(self):
        """Quantity hierarchy should have 7 levels."""
        assert len(QUANTITY_HIERARCHY) == 7

    def test_intensity_hierarchy_levels(self):
        """Intensity hierarchy should have 5 levels."""
        assert len(INTENSITY_HIERARCHY) == 5

    def test_hierarchy_encoding_quantity(self):
        """Quantity modifiers should encode correctly."""
        # NONE = [−][−][−][QUANTITY]
        base, level, markers = get_hierarchy_encoding("NONE")
        assert base == "QUANTITY"
        assert level == -3
        assert markers == 3

        # ALL = [+][+][+][QUANTITY]
        base, level, markers = get_hierarchy_encoding("ALL")
        assert base == "QUANTITY"
        assert level == 3
        assert markers == 3

        # MIDDLE = [QUANTITY]
        base, level, markers = get_hierarchy_encoding("MIDDLE")
        assert base == "QUANTITY"
        assert level == 0
        assert markers == 0

    def test_hierarchy_encoding_intensity(self):
        """Intensity modifiers should encode correctly."""
        # VERY = [+][INTENSITY]
        base, level, markers = get_hierarchy_encoding("VERY")
        assert base == "INTENSITY"
        assert level == 1
        assert markers == 1

        # EXTREMELY = [+][+][INTENSITY]
        base, level, markers = get_hierarchy_encoding("EXTREMELY")
        assert base == "INTENSITY"
        assert level == 2
        assert markers == 2

    def test_expand_hierarchy_activation(self):
        """Expanding hierarchy should produce correct activations."""
        activations = expand_hierarchy_activation("MANY")
        assert len(activations) == 3  # QUANTITY + 2 markers

        # First should be QUANTITY
        assert activations[0].primitive == "QUANTITY"

        # Rest should be HIER_PLUS
        for act in activations[1:]:
            assert act.primitive == "HIER_PLUS"


# =============================================================================
# VECTOR STRUCTURE TESTS
# =============================================================================


class TestSparseVector:
    """Test SparseVector class."""

    def test_zero_vector(self):
        """Zero vector should have no non-zeros."""
        v = SparseVector.zeros(D)
        assert v.nnz == 0
        assert v.sparsity == 0.0

    def test_dense_roundtrip(self):
        """Conversion to/from dense should preserve data."""
        pos = np.array([10, 100, 1000], dtype=np.uint16)
        neg = np.array([50, 500, 5000], dtype=np.uint16)
        v = SparseVector(D, pos, neg)

        dense = v.to_dense()
        v2 = SparseVector.from_dense(dense)

        assert np.array_equal(v.positive_indices, v2.positive_indices)
        assert np.array_equal(v.negative_indices, v2.negative_indices)

    def test_dot_product_same(self):
        """Dot product of identical vectors should equal nnz."""
        pos = np.array([10, 20, 30], dtype=np.uint16)
        neg = np.array([40, 50, 60], dtype=np.uint16)
        v = SparseVector(D, pos, neg)

        assert v.dot(v) == v.nnz

    def test_dot_product_negated(self):
        """Dot product with negation should equal -nnz."""
        pos = np.array([10, 20, 30], dtype=np.uint16)
        neg = np.array([40, 50, 60], dtype=np.uint16)
        v = SparseVector(D, pos, neg)

        assert v.dot(v.negate()) == -v.nnz

    def test_cosine_identical(self):
        """Cosine of identical vectors should be 1.0."""
        pos = np.array([10, 20, 30], dtype=np.uint16)
        v = SparseVector(D, pos, np.array([], dtype=np.uint16))

        assert abs(v.cosine(v) - 1.0) < 0.01

    def test_cosine_negated(self):
        """Cosine with negation should be -1.0."""
        pos = np.array([10, 20, 30], dtype=np.uint16)
        v = SparseVector(D, pos, np.array([], dtype=np.uint16))

        assert abs(v.cosine(v.negate()) - (-1.0)) < 0.01

    def test_serialize_deserialize(self):
        """Serialization should preserve data."""
        pos = np.array([10, 100, 1000], dtype=np.uint16)
        neg = np.array([50, 500, 5000], dtype=np.uint16)
        v = SparseVector(D, pos, neg, bank=3)

        data = v.serialize()
        v2 = SparseVector.deserialize(data)

        assert np.array_equal(v.positive_indices, v2.positive_indices)
        assert np.array_equal(v.negative_indices, v2.negative_indices)
        assert v.dimension == v2.dimension
        assert v.bank == v2.bank


# =============================================================================
# BASIS ORTHOGONALITY TESTS
# =============================================================================


class TestBasisOrthogonality:
    """Test Hadamard-OTP basis orthogonality properties."""

    def test_antonym_cosine_minus_one(self, basis):
        """All antonym pairs should have cosine = -1.0."""
        for dim in BIPOLAR_DIMENSIONS:
            pos_vec = basis.get_primitive(dim.positive)
            neg_vec = basis.get_primitive(dim.negative)

            assert pos_vec is not None, f"Missing {dim.positive}"
            assert neg_vec is not None, f"Missing {dim.negative}"

            cos = pos_vec.cosine(neg_vec)
            assert abs(cos - (-1.0)) < 0.01, f"{dim.positive}/{dim.negative} cosine = {cos}, expected -1.0"

    def test_cross_bank_orthogonality(self, basis):
        """Primitives in different banks should be orthogonal."""
        # Sample one primitive from each bank
        samples = {}
        for prim, vec in basis.primitives.items():
            if vec.bank is not None and vec.bank not in samples:
                samples[vec.bank] = (prim, vec)

        for bank_i, (name_i, vec_i) in samples.items():
            for bank_j, (name_j, vec_j) in samples.items():
                if bank_i != bank_j:
                    cos = vec_i.cosine(vec_j)
                    assert abs(cos) < 0.01, (
                        f"Cross-bank {name_i} (bank {bank_i}) / {name_j} (bank {bank_j}) cosine = {cos}, expected ~0"
                    )

    def test_within_bank_non_antonym_orthogonality(self, basis):
        """Non-antonym primitives in same bank should be approximately orthogonal."""
        for bank in range(N_BANKS):
            bank_prims = [(name, vec) for name, vec in basis.primitives.items() if vec.bank == bank]

            for i, (name_i, vec_i) in enumerate(bank_prims):
                for name_j, vec_j in bank_prims[i + 1 :]:
                    # Skip antonym pairs
                    if basis.bipolar_map.get(name_j) == name_i or basis.bipolar_map.get(name_i) == name_j:
                        continue

                    cos = vec_i.cosine(vec_j)
                    assert abs(cos) < 0.2, f"Within-bank {name_i}/{name_j} cosine = {cos}, expected ~0"

    def test_role_vectors_span_all_banks(self, basis):
        """Role vectors should have support in all banks."""
        for role_name, role_vec in basis.roles.items():
            banks_covered = set()
            for idx in role_vec.support:
                bank = idx // DIMS_PER_BANK
                banks_covered.add(bank)

            assert len(banks_covered) == N_BANKS, f"Role {role_name} only covers banks {banks_covered}"

    def test_role_pairs_exactly_orthogonal(self, basis):
        """Partition-based role generation guarantees cosine = 0.0 exactly."""
        roles = list(basis.roles.items())
        for i, (name_i, vec_i) in enumerate(roles):
            for name_j, vec_j in roles[i + 1 :]:
                cos = vec_i.cosine(vec_j)
                assert cos == 0.0, f"Roles {name_i}/{name_j} cosine = {cos}, expected exact 0.0"


# =============================================================================
# HDC OPERATION TESTS
# =============================================================================


class TestHDCOperations:
    """Test bind, bundle, permute operations."""

    def test_bind_dissimilar_to_inputs(self, basis):
        """Bind result should be dissimilar to both inputs."""
        a = basis.get_primitive("SOMEONE")
        b = basis.get_primitive("THINK")

        result = bind(a, b)

        # Bound result should be dissimilar to inputs
        cos_a = result.cosine(a)
        cos_b = result.cosine(b)

        assert abs(cos_a) < 0.3
        assert abs(cos_b) < 0.3

    def test_bundle_similar_to_inputs(self, basis):
        """Bundle result should be similar to all inputs."""
        a = basis.get_primitive("GOOD")
        b = basis.get_primitive("FEEL")
        c = basis.get_primitive("SOMEONE")  # Use actual primitive, not hierarchy

        result = bundle([a, b, c])

        # Bundle should maintain similarity to inputs
        cos_a = result.cosine(a)
        cos_b = result.cosine(b)
        cos_c = result.cosine(c)

        assert cos_a > 0.2
        assert cos_b > 0.2
        assert cos_c > 0.2

    def test_permute_dissimilar(self, basis):
        """Permuted vector should be dissimilar to original."""
        v = basis.get_primitive("SOMEONE")
        shifted = permute(v, shift=1000)

        cos = v.cosine(shifted)
        assert abs(cos) < 0.2

    def test_permute_reversible(self, basis):
        """Permute should be reversible."""
        v = basis.get_primitive("SOMEONE")
        shifted = permute(v, shift=100)
        restored = permute(shifted, shift=-100)

        # After restoring, should be identical
        assert np.array_equal(np.sort(v.positive_indices), np.sort(restored.positive_indices))
        assert np.array_equal(np.sort(v.negative_indices), np.sort(restored.negative_indices))


# =============================================================================
# COMPOSITION TESTS
# =============================================================================


class TestComposition:
    """Test decomposition composition."""

    def test_compose_simple_decomposition(self, basis):
        """Simple decomposition should compose to non-empty vector."""
        decomp = [
            ("GOOD", "evaluation", 1),
            ("FEEL", "experiencer", 1),
        ]

        result = compose_decomposition(basis, decomp)
        assert result.nnz > 0

    def test_compose_with_negative_polarity(self, basis):
        """Negative polarity should flip the primitive."""
        decomp_pos = [("GOOD", "evaluation", 1)]
        decomp_neg = [("GOOD", "evaluation", -1)]

        result_pos = compose_decomposition(basis, decomp_pos)
        result_neg = compose_decomposition(basis, decomp_neg)

        # They should be opposite
        cos = result_pos.cosine(result_neg)
        assert cos < 0

    def test_antonym_decompositions_opposite(self, basis):
        """Words with opposing primitives should have lower similarity than synonyms."""
        # Test with pure primitives first
        good_vec = basis.get_primitive("GOOD")
        bad_vec = basis.get_primitive("BAD")

        # Direct antonyms should be -1.0
        assert good_vec.cosine(bad_vec) < -0.9

        # Now test compositions where evaluation differs
        # positive_eval = evaluation is GOOD
        positive_eval = compose_decomposition(
            basis,
            [
                ("GOOD", "evaluation", 1),
            ],
        )

        # negative_eval = evaluation is BAD (= GOOD with -1 polarity)
        negative_eval = compose_decomposition(
            basis,
            [
                ("GOOD", "evaluation", -1),
            ],
        )

        cos = positive_eval.cosine(negative_eval)
        # Should be negative (opposite evaluations)
        assert cos < 0, f"GOOD/BAD composition cosine should be negative, got {cos}"

        # When we add shared components, similarity moves toward 0
        # This is expected: happy/sad share "feeling" but differ in "valence"
        # The similarity should be LESS THAN pure synonyms
        synonym_pair = compose_decomposition(
            basis,
            [
                ("GOOD", "evaluation", 1),
                ("FEEL", "experiencer", 1),
            ],
        )
        another_positive = compose_decomposition(
            basis,
            [
                ("GOOD", "evaluation", 1),
                ("FEEL", "state", 1),  # Same components, different role
            ],
        )

        antonym_pair = compose_decomposition(
            basis,
            [
                ("GOOD", "evaluation", -1),
                ("FEEL", "experiencer", 1),
            ],
        )

        # Synonym pair should have higher similarity than antonym
        cos_synonym = synonym_pair.cosine(another_positive)
        cos_antonym = synonym_pair.cosine(antonym_pair)

        assert cos_synonym > cos_antonym, (
            f"Synonyms ({cos_synonym:.3f}) should be more similar than antonyms ({cos_antonym:.3f})"
        )


# =============================================================================
# SIMILARITY ANALYSIS TESTS
# =============================================================================


class TestSimilarityAnalysis:
    """Test polarity-aware similarity."""

    def test_polarity_aware_antonyms(self, basis):
        """Antonym analysis should show high opposition."""
        good = basis.get_primitive("GOOD")
        bad = basis.get_primitive("BAD")

        analysis = polarity_aware_similarity(good, bad)

        assert analysis["cosine"] < -0.9  # Should be -1.0
        assert analysis["opposition"] > 0.9  # High opposition
        assert analysis["alignment"] < 0.1  # Low alignment

    def test_bank_activity_profile(self, basis):
        """Bank activity should be concentrated in primitive's bank."""
        good = basis.get_primitive("GOOD")  # Bank 2: EVALUATORS

        profile = bank_activity_profile(good)

        # Should be active in bank 2
        assert profile[2] > 0.5

        # Should be inactive in other banks
        for bank in range(N_BANKS):
            if bank != 2:
                assert profile[bank] < 0.1


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
