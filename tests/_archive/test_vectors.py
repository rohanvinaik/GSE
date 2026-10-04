import numpy as np
import pytest
from gse.vectors import PrimitiveBasis, SparseVector, bind, bundle, permute


def test_sparse_vector_creation():
    v = SparseVector.random(10000, 1000, seed=42)
    assert v.dimension == 10000
    assert v.nnz == 1000
    assert len(v.positive_indices) == 500
    assert len(v.negative_indices) == 500


def test_sparse_vector_roundtrip():
    v = SparseVector.random(10000, 1000, seed=42)
    dense = v.to_dense()
    v2 = SparseVector.from_dense(dense)
    assert np.array_equal(v.positive_indices, v2.positive_indices)
    assert np.array_equal(v.negative_indices, v2.negative_indices)


def test_dot_product():
    v1 = SparseVector.random(10000, 1000, seed=42)
    v2 = SparseVector.random(10000, 1000, seed=43)

    # Sparse dot should match dense dot
    sparse_dot = v1.dot(v2)
    dense_dot = np.dot(v1.to_dense(), v2.to_dense())
    assert sparse_dot == dense_dot


def test_self_similarity():
    v = SparseVector.random(10000, 1000, seed=42)
    assert v.cosine(v) == pytest.approx(1.0)


def test_random_vectors_nearly_orthogonal():
    v1 = SparseVector.random(10000, 1000, seed=42)
    v2 = SparseVector.random(10000, 1000, seed=43)
    # Random vectors should have low similarity
    assert abs(v1.cosine(v2)) < 0.15


def test_bind_dissimilarity():
    v1 = SparseVector.random(10000, 1000, seed=42)
    v2 = SparseVector.random(10000, 1000, seed=43)
    bound = bind(v1, v2)

    # Bound vector should be dissimilar to both inputs
    assert abs(bound.cosine(v1)) < 0.2
    assert abs(bound.cosine(v2)) < 0.2


def test_bind_self_inverse():
    v1 = SparseVector.random(10000, 1000, seed=42)
    v2 = SparseVector.random(10000, 1000, seed=43)
    bound = bind(v1, v2)

    # v1 ⊗ (v1 ⊗ v2) ≈ v2 (masked by v1)
    # With 10% sparsity and element-wise multiplication, we only recover the intersection.
    # Theoretical cosine is sqrt(sparsity) ≈ sqrt(0.1) ≈ 0.316.
    recovered = bind(v1, bound)
    assert recovered.cosine(v2) > 0.3


def test_bundle_similarity():
    v1 = SparseVector.random(10000, 1000, seed=42)
    v2 = SparseVector.random(10000, 1000, seed=43)
    bundled = bundle([v1, v2])

    # Bundled vector should be similar to both inputs
    assert bundled.cosine(v1) > 0.3
    assert bundled.cosine(v2) > 0.3


def test_permute_dissimilarity():
    v = SparseVector.random(10000, 1000, seed=42)
    permuted = permute(v, 1)

    # Permuted vector should be dissimilar to original
    assert abs(permuted.cosine(v)) < 0.15


def test_permute_inverse():
    v = SparseVector.random(10000, 1000, seed=42)
    permuted = permute(v, 5)
    recovered = permute(permuted, -5)

    # Should recover original
    assert recovered.cosine(v) == pytest.approx(1.0)


def test_primitive_basis_orthogonality():
    from gse.primitives import PRIMITIVES, ROLES
    from gse.vectors import ANTONYM_PAIRS

    # Use new Hadamard-OTP architecture
    basis = PrimitiveBasis.generate(PRIMITIVES, ROLES)

    # Build set of antonym pairs for exclusion
    antonym_set = set()
    for pos, neg in ANTONYM_PAIRS:
        antonym_set.add((pos, neg))
        antonym_set.add((neg, pos))

    # Get all primitive and role names
    prim_names = list(basis.primitives.keys())
    role_names = list(basis.roles.keys())

    # Check primitive orthogonality (excluding antonyms which should be -1)
    for i, n1 in enumerate(prim_names):
        for j, n2 in enumerate(prim_names):
            if i < j:
                v1, v2 = basis.primitives[n1], basis.primitives[n2]
                sim = v1.cosine(v2)
                if (n1, n2) in antonym_set:
                    # Antonyms should be exactly -1
                    assert sim < -0.9, f"Antonym pair {n1},{n2} should be ~-1, got {sim}"
                else:
                    # Non-antonyms should be orthogonal or near-zero
                    assert abs(sim) < 0.15, f"Primitive pair {n1},{n2} too similar: {sim}"

    # Check role orthogonality
    for i, n1 in enumerate(role_names):
        for j, n2 in enumerate(role_names):
            if i < j:
                v1, v2 = basis.roles[n1], basis.roles[n2]
                sim = abs(v1.cosine(v2))
                assert sim < 0.15, f"Role pair {n1},{n2} too similar: {sim}"


def test_serialization_roundtrip():
    v = SparseVector.random(10000, 1000, seed=42)
    serialized = v.serialize()
    recovered = SparseVector.deserialize(serialized)

    assert v.dimension == recovered.dimension
    assert np.array_equal(v.positive_indices, recovered.positive_indices)
    assert np.array_equal(v.negative_indices, recovered.negative_indices)
