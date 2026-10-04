"""Manual contract tests for gse.encoders.sentence_structure_encoder."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.encoders.sentence_structure_encoder import (
    ALL_SYNTACTIC_PRIMITIVES,
    BANK_ALLOCATIONS,
    CORE_STRUCTURE_PRIMITIVES,
    MODIFICATION_PRIMITIVES,
    TAM_FEATURE_PRIMITIVES,
    SentenceStructureEncoder,
    SentenceVectorMetadata,
    WordPosition,
    compute_word_boundaries,
    encode_simple_sentence,
    gaussian_weight,
    stretch_to_dimensions,
)

# ---------- Constants ----------

class TestConstants:
    def test_all_primitives_union(self):
        assert ALL_SYNTACTIC_PRIMITIVES == (
            CORE_STRUCTURE_PRIMITIVES + MODIFICATION_PRIMITIVES + TAM_FEATURE_PRIMITIVES
        )

    def test_bank_allocations_sum_to_one(self):
        total = sum(BANK_ALLOCATIONS.values())
        assert abs(total - 1.0) < 1e-9

    def test_core_has_subj_pred_obj(self):
        for p in ["SYN_SUBJ", "SYN_PRED", "SYN_OBJ"]:
            assert p in CORE_STRUCTURE_PRIMITIVES


# ---------- Dataclass metadata ----------

class TestSentenceVectorMetadata:
    def test_post_init_computes_dims_per_word(self):
        m = SentenceVectorMetadata(word_count=4, total_dimensions=8192)
        assert m.dims_per_word == 2048.0

    def test_zero_words_no_division(self):
        m = SentenceVectorMetadata(word_count=0, total_dimensions=8192)
        assert m.dims_per_word == 0.0

    def test_default_lists(self):
        m = SentenceVectorMetadata(word_count=1)
        assert m.word_boundaries == []
        assert m.per_position_magnitude == []
        assert m.bank_magnitudes == {}
        assert m.syntactic_roles == []


# ---------- Gaussian weight ----------

class TestGaussianWeight:
    def test_zero_distance_is_one(self):
        assert gaussian_weight(0.0) == pytest.approx(1.0)

    def test_symmetric(self):
        assert gaussian_weight(0.3) == pytest.approx(gaussian_weight(-0.3))

    def test_decays_with_distance(self):
        assert gaussian_weight(0.0) > gaussian_weight(0.5) > gaussian_weight(1.0)

    def test_sigma_affects_spread(self):
        # Larger sigma → wider spread → higher weight at same distance
        assert gaussian_weight(1.0, sigma=1.0) > gaussian_weight(1.0, sigma=0.5)


# ---------- stretch_to_dimensions ----------

class TestStretchToDimensions:
    def test_empty_signal_returns_zeros(self):
        result = stretch_to_dimensions(np.array([], dtype=np.float32), 0, 10, total_dims=100)
        assert result.shape == (100,)
        assert np.all(result == 0)

    def test_zero_signal_returns_zeros(self):
        # All-zero signal — the `if val == 0: continue` short-circuits
        result = stretch_to_dimensions(np.zeros(5, dtype=np.float32), 0, 5, total_dims=10)
        assert np.all(result == 0)

    def test_signal_lands_in_target_window(self):
        signal = np.ones(5, dtype=np.float32)
        result = stretch_to_dimensions(signal, target_start=10, target_end=20, total_dims=100)
        # Magnitude should be concentrated in dims 10-20
        assert np.sum(np.abs(result[10:21])) > 0
        # Magnitude outside window should be small (Gaussian falloff at boundary)
        assert np.sum(np.abs(result[:5])) < 1e-3

    def test_negative_values_preserved(self):
        signal = np.array([-1.0, -1.0, -1.0], dtype=np.float32)
        result = stretch_to_dimensions(signal, 0, 10, total_dims=20)
        # Should produce negative values
        assert result.min() < 0

    def test_out_of_bounds_boundary_safe(self):
        # target_start near edge — boundary checks should prevent crash
        signal = np.array([1.0], dtype=np.float32)
        result = stretch_to_dimensions(signal, total_dims=10, target_start=9, target_end=10)
        # Right boundary at 10 is out of bounds for dims 0..9 — should not crash
        assert result.shape == (10,)


# ---------- compute_word_boundaries ----------

class TestComputeWordBoundaries:
    def test_even_split(self):
        b = compute_word_boundaries(4, total_dims=8)
        assert b == [(0, 2), (2, 4), (4, 6), (6, 8)]

    def test_fractional_split(self):
        b = compute_word_boundaries(3, total_dims=10)
        assert b[0] == (0, 10 / 3)
        assert b[2][1] == 10.0

    def test_single_word(self):
        b = compute_word_boundaries(1, total_dims=100)
        assert b == [(0, 100)]


# ---------- SentenceStructureEncoder ----------

@pytest.fixture
def encoder():
    return SentenceStructureEncoder(total_dims=1024)


class TestEncoderInit:
    def test_default_dims(self):
        from gse.primitives_v2 import D
        e = SentenceStructureEncoder()
        assert e.total_dims == D

    def test_custom_dims(self):
        e = SentenceStructureEncoder(total_dims=256)
        assert e.total_dims == 256

    def test_syntactic_vectors_populated(self, encoder):
        # All primitives should have generated vectors
        for prim in ALL_SYNTACTIC_PRIMITIVES:
            assert prim in encoder._syntactic_vectors
            vec = encoder._syntactic_vectors[prim]
            assert isinstance(vec, np.ndarray)
            assert len(vec) == 64

    def test_syntactic_vectors_are_distinct(self, encoder):
        # First two primitives should differ
        v0 = encoder._syntactic_vectors[ALL_SYNTACTIC_PRIMITIVES[0]]
        v1 = encoder._syntactic_vectors[ALL_SYNTACTIC_PRIMITIVES[1]]
        assert not np.array_equal(v0, v1)


class TestEncodeSentence:
    def test_empty_returns_zero_vector(self, encoder):
        vec, meta = encoder.encode_sentence([])
        assert vec.shape == (1024,)
        assert np.all(vec == 0)
        assert meta.word_count == 0

    def test_single_word(self, encoder):
        wp = WordPosition(
            position=0, word="dog", syntactic_role="SYN_SUBJ",
            semantic_vector=np.array([], dtype=np.float32),
        )
        vec, meta = encoder.encode_sentence([wp])
        assert vec.shape == (1024,)
        assert meta.word_count == 1
        # CORE_STRUCTURE bank should have non-zero magnitude
        assert meta.bank_magnitudes["core"] > 0

    def test_multiple_words(self, encoder):
        words = [
            WordPosition(position=i, word=f"w{i}", syntactic_role="SYN_SUBJ",
                         semantic_vector=np.array([], dtype=np.float32))
            for i in range(3)
        ]
        vec, meta = encoder.encode_sentence(words)
        assert meta.word_count == 3
        assert len(meta.word_boundaries) == 3
        assert len(meta.syntactic_roles) == 3

    def test_semantic_vector_encoded(self, encoder):
        sem = np.array([1.0, -1.0, 1.0, -1.0], dtype=np.float32)
        wp = WordPosition(position=0, word="x", syntactic_role="SYN_SUBJ", semantic_vector=sem)
        vec, meta = encoder.encode_sentence([wp])
        # MODIFICATION bank receives semantic content
        assert meta.bank_magnitudes["mod"] > 0

    def test_tam_features_encoded(self, encoder):
        wp = WordPosition(
            position=0, word="ran", syntactic_role="SYN_PRED",
            semantic_vector=np.array([], dtype=np.float32),
            tam_features=["SYN_TENSE_PAST"],
        )
        vec, meta = encoder.encode_sentence([wp])
        assert meta.bank_magnitudes["tam"] > 0

    def test_unknown_role_no_core_bank(self, encoder):
        # Unknown role → no core encoding
        wp = WordPosition(
            position=0, word="x", syntactic_role="UNKNOWN_ROLE",
            semantic_vector=np.array([], dtype=np.float32),
        )
        _, meta = encoder.encode_sentence([wp])
        assert meta.bank_magnitudes["core"] == 0


class TestDecodePositions:
    def test_returns_one_entry_per_word(self, encoder):
        wps = [
            WordPosition(position=i, word=f"w{i}", syntactic_role="SYN_SUBJ",
                         semantic_vector=np.array([], dtype=np.float32))
            for i in range(3)
        ]
        vec, meta = encoder.encode_sentence(wps)
        positions = encoder.decode_positions(vec, meta)
        assert len(positions) == 3
        # Each entry is (index, magnitude)
        for i, (idx, mag) in enumerate(positions):
            assert idx == i
            assert mag >= 0


class TestCompareStructure:
    def test_identical_vectors_high_cosine(self, encoder):
        wp = WordPosition(position=0, word="x", syntactic_role="SYN_SUBJ",
                          semantic_vector=np.array([], dtype=np.float32))
        v1, m1 = encoder.encode_sentence([wp])
        result = encoder.compare_structure(v1, m1, v1, m1)
        assert result["cosine_similarity"] == pytest.approx(1.0)

    def test_zero_vector_zero_cosine(self, encoder):
        v1 = np.zeros(1024, dtype=np.float32)
        m1 = SentenceVectorMetadata(word_count=1)
        result = encoder.compare_structure(v1, m1, v1, m1)
        assert result["cosine_similarity"] == 0.0

    def test_length_ratio_computed(self, encoder):
        m1 = SentenceVectorMetadata(word_count=2)
        m2 = SentenceVectorMetadata(word_count=4)
        v1 = np.zeros(1024, dtype=np.float32)
        v2 = np.zeros(1024, dtype=np.float32)
        result = encoder.compare_structure(v1, m1, v2, m2)
        assert result["length_ratio"] == pytest.approx(0.5)

    def test_bank_similarity_for_equal_mags(self, encoder):
        v1 = np.zeros(1024, dtype=np.float32)
        m1 = SentenceVectorMetadata(word_count=1)
        m1.bank_magnitudes = {"core": 5.0, "mod": 5.0, "tam": 5.0}
        m2 = SentenceVectorMetadata(word_count=1)
        m2.bank_magnitudes = {"core": 5.0, "mod": 5.0, "tam": 5.0}
        result = encoder.compare_structure(v1, m1, v1, m2)
        # 2 * min / (a+b) where a==b → 1.0
        for bank in ["core", "mod", "tam"]:
            assert result["bank_similarity"][bank] == pytest.approx(1.0)

    def test_bank_similarity_zero_for_empty(self, encoder):
        v1 = np.zeros(1024, dtype=np.float32)
        m1 = SentenceVectorMetadata(word_count=1)
        m1.bank_magnitudes = {"core": 0.0, "mod": 0.0, "tam": 0.0}
        result = encoder.compare_structure(v1, m1, v1, m1)
        for bank in ["core", "mod", "tam"]:
            assert result["bank_similarity"][bank] == 0.0


# ---------- encode_simple_sentence ----------

class TestEncodeSimpleSentence:
    def test_basic_usage(self):
        vec, meta = encode_simple_sentence(["The", "dog"], ["SYN_DET", "SYN_SUBJ"])
        assert meta.word_count == 2

    def test_creates_encoder_if_none(self):
        # No encoder passed in → creates one
        vec, meta = encode_simple_sentence(["x"], ["SYN_SUBJ"])
        assert isinstance(vec, np.ndarray)

    def test_uses_passed_encoder(self):
        enc = SentenceStructureEncoder(total_dims=256)
        vec, meta = encode_simple_sentence(["x"], ["SYN_SUBJ"], encoder=enc)
        assert vec.shape == (256,)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
