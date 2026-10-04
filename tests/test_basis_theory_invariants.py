"""Canonical theory contract for the GSE basis vectors.

Consolidates every basis-level geometric guarantee in one place. The
basis (word-scale + sentence-scale) must satisfy these invariants for
the encoder's downstream geometry to be sound. Breaking any of these
breaks GSE.

This file is intentionally redundant with smaller assertions scattered
across ``test_primitives_v2.py`` and others — the redundancy is the
point. A future change that erodes basis geometry will fail here
regardless of which scattered test was missed.

Anchors:

* ``sentence_architecture.md`` — bipolar primitives are perfect
  antonyms in their bank (cos = −1).
* The May 2026 partition-based Hadamard rewrite — primitives in the
  same bank have disjoint index supports → exact orthogonality.
* The May 2026 role-orthogonality rewrite — roles get disjoint slices
  in every bank → cos(role_i, role_j) = 0 exactly.
"""

import itertools
import math

import pytest

from gse.api import GSEEncoder
from gse.primitives_v2 import (
    BIPOLAR_DIMENSIONS,
    DIMS_PER_BANK,
    PRIMITIVE_REGISTRY,
    SEMANTIC_ROLES,
    SemanticBank,
)


@pytest.fixture(scope="module")
def word_basis():
    return GSEEncoder().word_basis


@pytest.fixture(scope="module")
def sent_basis():
    return GSEEncoder().sent_basis


class TestBipolarOpposition:
    """For every BIPOLAR_DIMENSION, cos(positive, negative) = −1 exactly."""

    @pytest.mark.parametrize("dim", BIPOLAR_DIMENSIONS, ids=lambda d: d.name)
    def test_bipolar_cos_minus_one(self, word_basis, dim):
        # Theoretical contract: cos = exactly -1. In practice the cosine
        # involves dividing by floating-point norms, so the result lands
        # at -1 ± 1e-16. The `isclose` tolerance is tight enough to fail
        # if the partition design ever breaks but loose enough for FP.
        pos_vec = word_basis.get_primitive(dim.positive)
        neg_vec = word_basis.get_primitive(dim.negative)
        assert pos_vec is not None, f"{dim.positive} missing from basis"
        assert neg_vec is not None, f"{dim.negative} missing from basis"
        cos = pos_vec.cosine(neg_vec)
        assert math.isclose(cos, -1.0, abs_tol=1e-9), (
            f"{dim.positive}/{dim.negative} cos={cos:.12f}, expected -1 ± 1e-9"
        )

    def test_all_14_bipolar_pairs_present(self, word_basis):
        # Theory anchor: there are exactly 14 bipolar dimensions.
        assert len(BIPOLAR_DIMENSIONS) == 14


class TestWithinBankPrimitiveOrthogonality:
    """Non-antonym primitives in the same bank have exactly disjoint supports.

    Partition-based Hadamard gives each primitive a disjoint slice of
    the bank's dim range → cos = 0 exactly for any two non-antonyms.
    """

    @pytest.mark.parametrize("bank", list(SemanticBank), ids=lambda b: b.name)
    def test_within_bank_disjoint_supports(self, word_basis, bank):
        bank_idx = bank.value
        # Collect all primitives in this bank's basis
        prims_in_bank = []
        for name in PRIMITIVE_REGISTRY:
            vec = word_basis.get_primitive(name)
            if vec is None:
                continue
            if vec.bank == bank_idx:
                prims_in_bank.append((name, vec))

        # Bipolar partners have overlapping supports by design (one is
        # the negation of the other). Skip those pairs.
        bipolar_partners = {}
        for dim in BIPOLAR_DIMENSIONS:
            bipolar_partners[dim.positive] = dim.negative
            bipolar_partners[dim.negative] = dim.positive

        for (n1, v1), (n2, v2) in itertools.combinations(prims_in_bank, 2):
            if bipolar_partners.get(n1) == n2:
                continue  # antonym pair — has cos=-1, not 0
            cos = v1.cosine(v2)
            assert abs(cos) < 1e-9, (
                f"Bank {bank.name}: {n1}/{n2} cos={cos:.6e}, expected exact 0 from partition-based Hadamard"
            )


class TestCrossBankOrthogonality:
    """Primitives in different banks live in disjoint dim ranges.

    cos = 0 regardless of primitive content because the dim slices
    don't overlap.
    """

    def test_sampled_cross_bank_pairs_orthogonal(self, word_basis):
        # One primitive from each bank, all pairs
        samples = []
        for bank in SemanticBank:
            for name, info in PRIMITIVE_REGISTRY.items():
                if info.bank == bank:
                    vec = word_basis.get_primitive(name)
                    if vec is not None:
                        samples.append((bank.name, name, vec))
                        break
        for (b1, n1, v1), (b2, n2, v2) in itertools.combinations(samples, 2):
            assert b1 != b2
            cos = v1.cosine(v2)
            assert cos == 0.0, f"Cross-bank {b1}/{n1} vs {b2}/{n2} cos={cos:.6f}, expected 0"


class TestRoleOrthogonality:
    """Every role-pair is exactly orthogonal (May 2026 partition rewrite)."""

    def test_all_role_pairs_exact_zero(self, word_basis):
        role_vecs = list(word_basis.roles.items())
        for (n1, v1), (n2, v2) in itertools.combinations(role_vecs, 2):
            cos = v1.cosine(v2)
            assert cos == 0.0, f"Roles {n1}/{n2} cos={cos:.6f}, expected exact 0"

    def test_role_count_matches_semantic_roles_list(self, word_basis):
        assert len(word_basis.roles) == len(SEMANTIC_ROLES)


class TestPartitionDisjointness:
    """Each bank's dim range is exactly DIMS_PER_BANK wide and disjoint."""

    @pytest.mark.parametrize("bank", list(SemanticBank), ids=lambda b: b.name)
    def test_bank_dim_range_correct(self, bank):
        start = bank.value * DIMS_PER_BANK
        end = start + DIMS_PER_BANK
        # Sample a primitive in this bank, confirm its support is inside
        word_basis = GSEEncoder().word_basis
        for name, info in PRIMITIVE_REGISTRY.items():
            if info.bank != bank:
                continue
            vec = word_basis.get_primitive(name)
            if vec is None:
                continue
            support = vec.support
            assert all(start <= idx < end for idx in support), (
                f"Bank {bank.name}: primitive {name} has support outside [{start}, {end})"
            )
            break

    def test_dims_per_bank_is_8192_over_8(self):
        # Theory anchor: 8192 / 8 = 1024
        assert DIMS_PER_BANK == 1024


class TestSentenceScaleBasisShareStructure:
    """Sentence-scale primitives also use partition-based Hadamard.

    Same orthogonality contract as word-scale, just for the SYN_/COMP_
    primitives. Verifies the SentenceScaleBasis refactor in May 2026.
    """

    def test_two_sentence_primitives_in_same_bank_orthogonal(self, sent_basis):
        # Sample CORE_STRUCTURE bank primitives — they should be exactly orthogonal
        prims = [sent_basis.get_primitive(name) for name in ("SYN_SUBJ", "SYN_PRED", "SYN_OBJ")]
        prims = [p for p in prims if p is not None]
        assert len(prims) >= 2, "Need at least 2 sentence primitives to test"
        for i, p1 in enumerate(prims):
            for p2 in prims[i + 1 :]:
                cos = p1.cosine(p2)
                assert cos == 0.0, f"Same-bank sentence-scale primitive cos={cos}, expected 0"

    def test_comp_than_present(self, sent_basis):
        # The architecture's set-theory operators must be present
        vec = sent_basis.get_primitive("COMP_THAN")
        assert vec is not None, "COMP_THAN missing — set-theory layer broken"
