"""Manual contract tests for gse.encoders.paragraph_structure_encoder."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

import gse.encoders.paragraph_structure_encoder as psem
from gse.encoders.paragraph_structure_encoder import (
    RELATION_TO_PRIMITIVE,
    CoherenceRelation,
    GestaltCodebook,
    GestaltType,
    IntensityTrajectory,
    ParagraphEncoding,
    ParagraphStructureEncoder,
    RelationCodebook,
    SentenceInfo,
    encode_paragraph,
    get_paragraph_encoder,
)

# ---------- Enums and mapping ----------

class TestRelationMapping:
    def test_contrast_mapped(self):
        assert RELATION_TO_PRIMITIVE[CoherenceRelation.CONTRAST] == "CONTRAST"

    def test_cause_mapped(self):
        assert RELATION_TO_PRIMITIVE[CoherenceRelation.CAUSE] == "CAUSE"


# ---------- IntensityTrajectory ----------

class TestIntensityTrajectory:
    def test_empty_values(self):
        t = IntensityTrajectory.from_values([])
        assert t.values == []
        assert t.peak_index == 0
        assert t.trajectory_type == "stable"

    def test_single_value_stable(self):
        t = IntensityTrajectory.from_values([0.5])
        assert t.trajectory_type == "stable"

    def test_building(self):
        t = IntensityTrajectory.from_values([0.1, 0.3, 0.6, 0.9])
        assert t.trajectory_type == "building"

    def test_declining(self):
        t = IntensityTrajectory.from_values([0.9, 0.6, 0.3, 0.1])
        assert t.trajectory_type == "declining"

    def test_oscillating(self):
        # 5 values with diffs averaging to 0 but large range
        t = IntensityTrajectory.from_values([0.1, 0.9, 0.1, 0.9, 0.1])
        assert t.trajectory_type == "oscillating"

    def test_stable(self):
        t = IntensityTrajectory.from_values([0.5, 0.5, 0.5])
        assert t.trajectory_type == "stable"

    def test_peak_index(self):
        t = IntensityTrajectory.from_values([0.2, 0.8, 0.5])
        assert t.peak_index == 1

    def test_boundary_avg_diff_exactly_at_threshold(self):
        # diffs = [0.1, 0.1] → avg = 0.1 (NOT > 0.1) → fall through to next check
        # range = 0.2 (NOT > 0.4) → stable
        t = IntensityTrajectory.from_values([0.5, 0.6, 0.7])
        assert t.trajectory_type == "stable"

    def test_just_over_building_threshold(self):
        # diffs = [0.15, 0.15] → avg = 0.15 > 0.1 → building
        t = IntensityTrajectory.from_values([0.4, 0.55, 0.7])
        assert t.trajectory_type == "building"

    def test_boundary_neg_avg_diff_at_threshold(self):
        # diffs = [-0.1, -0.1] → avg = -0.1 (NOT < -0.1) → fall through
        # range = 0.2 → stable
        t = IntensityTrajectory.from_values([0.7, 0.6, 0.5])
        assert t.trajectory_type == "stable"

    def test_just_over_declining_threshold(self):
        # diffs = [-0.15, -0.15] → avg = -0.15 < -0.1 → declining
        t = IntensityTrajectory.from_values([0.7, 0.55, 0.4])
        assert t.trajectory_type == "declining"

    def test_range_exactly_at_oscillating_threshold(self):
        # avg_diff = 0, range = 0.4 (NOT > 0.4) → stable
        t = IntensityTrajectory.from_values([0.3, 0.7, 0.3, 0.7])
        # diffs = [0.4, -0.4, 0.4] → avg = 0.133, > 0.1 → building (not the case we want)
        # Use values where avg_diff = 0 AND range = exactly 0.4
        # [0.3, 0.7, 0.3] → diffs = [0.4, -0.4], avg=0, range=0.4 (not > 0.4) → stable
        t = IntensityTrajectory.from_values([0.3, 0.7, 0.3])
        assert t.trajectory_type == "stable"

    def test_range_just_over_oscillating_threshold(self):
        # avg_diff = 0, range = 0.5 > 0.4 → oscillating
        t = IntensityTrajectory.from_values([0.25, 0.75, 0.25])
        assert t.trajectory_type == "oscillating"

    def test_peak_with_ties_takes_first(self):
        # max() with duplicates → values.index(max) returns first occurrence
        t = IntensityTrajectory.from_values([0.5, 0.9, 0.9, 0.5])
        assert t.peak_index == 1

    def test_two_values_building(self):
        # len=2 with avg_diff > 0.1 → 'building', not 'stable'
        # Kills BOUNDARY mutant: `len(values) < 2` → `<= 2`
        t = IntensityTrajectory.from_values([0.0, 1.0])
        assert t.trajectory_type == "building"

    def test_two_values_declining(self):
        t = IntensityTrajectory.from_values([1.0, 0.0])
        assert t.trajectory_type == "declining"

    def test_constants_021_not_001(self):
        # Range = 0.21 NOT > 0.4 → stable
        # If oscillating threshold mutated 0.4 → 0.0, would return "oscillating"
        # avg_diff=0.105 > 0.1 → "building" → kills threshold mutants too
        t = IntensityTrajectory.from_values([0.4, 0.505, 0.61])
        assert t.trajectory_type == "building"

    def test_range_just_under_oscillating(self):
        # avg_diff = 0, range = 0.3 (< 0.4) → stable
        # If 0.4 mutated to 0.2, range > 0.2 → oscillating (differs)
        t = IntensityTrajectory.from_values([0.4, 0.7, 0.4])
        assert t.trajectory_type == "stable"


# ---------- Codebooks ----------

class TestRelationCodebook:
    def test_all_relations_have_vectors(self):
        cb = RelationCodebook(dim=64)
        for rel in CoherenceRelation:
            v = cb.get(rel)
            assert isinstance(v, np.ndarray)
            assert v.shape == (64,)

    def test_deterministic_seed(self):
        cb1 = RelationCodebook(dim=64, seed=7)
        cb2 = RelationCodebook(dim=64, seed=7)
        np.testing.assert_array_equal(
            cb1.get(CoherenceRelation.CAUSE),
            cb2.get(CoherenceRelation.CAUSE),
        )

    def test_different_seeds_differ(self):
        cb1 = RelationCodebook(dim=64, seed=1)
        cb2 = RelationCodebook(dim=64, seed=2)
        v1 = cb1.get(CoherenceRelation.CAUSE)
        v2 = cb2.get(CoherenceRelation.CAUSE)
        assert not np.array_equal(v1, v2)


class TestGestaltCodebook:
    def test_all_types_have_vectors(self):
        cb = GestaltCodebook(dim=64)
        for gt in GestaltType:
            assert cb.get(gt).shape == (64,)


# ---------- Encoder ----------

@pytest.fixture
def encoder():
    return ParagraphStructureEncoder(dim=2048)


class TestEncoderInit:
    def test_uses_provided_codebooks(self):
        rc = RelationCodebook(dim=64)
        gc = GestaltCodebook(dim=64)
        enc = ParagraphStructureEncoder(dim=64, relation_codebook=rc, gestalt_codebook=gc)
        assert enc.relations is rc
        assert enc.gestalts is gc

    def test_creates_default_codebooks(self):
        enc = ParagraphStructureEncoder(dim=128)
        assert isinstance(enc.relations, RelationCodebook)
        assert isinstance(enc.gestalts, GestaltCodebook)


class TestSegment:
    def test_splits_on_period(self, encoder):
        result = encoder._segment("First. Second. Third.")
        assert len(result) == 3

    def test_strips_whitespace(self, encoder):
        result = encoder._segment("  First.  Second.  ")
        assert all(not s.startswith(" ") for s in result)

    def test_empty_string(self, encoder):
        assert encoder._segment("") == []

    def test_filters_empty_after_split(self, encoder):
        result = encoder._segment("First.   ")
        assert "" not in result


class TestHashVector:
    def test_deterministic(self, encoder):
        v1 = encoder._hash_vector("test")
        v2 = encoder._hash_vector("test")
        np.testing.assert_array_equal(v1, v2)

    def test_different_text_different_vector(self, encoder):
        v1 = encoder._hash_vector("foo")
        v2 = encoder._hash_vector("bar")
        assert not np.array_equal(v1, v2)

    def test_uses_ternary_values(self, encoder):
        v = encoder._hash_vector("hello world")
        unique = set(v.tolist())
        # Values should be from {0, 1, -1}
        assert unique.issubset({0.0, 1.0, -1.0})


class TestComputeIntensity:
    def test_base_intensity(self, encoder):
        assert encoder._compute_intensity("hello") == 0.5

    def test_marker_increases_intensity(self, encoder):
        assert encoder._compute_intensity("very fast") > 0.5

    def test_exclamation_increases_intensity(self, encoder):
        assert encoder._compute_intensity("Wow!") > 0.5

    def test_capped_at_one(self, encoder):
        # Many markers
        s = "very extremely incredibly absolutely totally !!! really truly completely"
        assert encoder._compute_intensity(s) <= 1.0


class TestHasAnalogy:
    def test_like_triggers(self, encoder):
        assert encoder._has_analogy("It is like a dog") is True

    def test_as_if_triggers(self, encoder):
        assert encoder._has_analogy("As if running away") is True

    def test_no_marker(self, encoder):
        assert encoder._has_analogy("Just a sentence") is False


class TestHasMeta:
    def test_what_i_mean_triggers(self, encoder):
        assert encoder._has_meta("What I mean is clear") is True

    def test_no_marker(self, encoder):
        assert encoder._has_meta("Just text") is False


class TestDetectRelationPair:
    def test_contrast_marker(self, encoder):
        result = encoder._detect_relation_pair("A is good.", "But B is bad.")
        assert result == CoherenceRelation.CONTRAST

    def test_cause_marker(self, encoder):
        result = encoder._detect_relation_pair("A.", "Because B.")
        assert result == CoherenceRelation.CAUSE

    def test_no_marker_returns_continuation(self, encoder):
        result = encoder._detect_relation_pair("A.", "Just B.")
        assert result == CoherenceRelation.CONTINUATION


class TestDetectRelations:
    def test_escalation(self, encoder):
        info_list = [
            SentenceInfo(text="a", vector=np.zeros(128, dtype=np.float32), intensity_score=0.3),
            SentenceInfo(text="b", vector=np.zeros(128, dtype=np.float32), intensity_score=0.7),
        ]
        result = encoder._detect_relations(["a.", "b."], info_list)
        assert result[0][2] == CoherenceRelation.ESCALATION

    def test_de_escalation(self, encoder):
        info_list = [
            SentenceInfo(text="a", vector=np.zeros(128, dtype=np.float32), intensity_score=0.8),
            SentenceInfo(text="b", vector=np.zeros(128, dtype=np.float32), intensity_score=0.3),
        ]
        result = encoder._detect_relations(["a.", "b."], info_list)
        assert result[0][2] == CoherenceRelation.DE_ESCALATION

    def test_uses_marker_for_close_intensity(self, encoder):
        info_list = [
            SentenceInfo(text="a", vector=np.zeros(128, dtype=np.float32), intensity_score=0.5),
            SentenceInfo(text="b", vector=np.zeros(128, dtype=np.float32), intensity_score=0.5),
        ]
        result = encoder._detect_relations(["a.", "But b."], info_list)
        assert result[0][2] == CoherenceRelation.CONTRAST


class TestExtractTopicChain:
    def test_capitalizes_persist(self, encoder):
        sentences = ["Alice met Bob.", "Alice talked to Bob."]
        result = encoder._extract_topic_chain(sentences)
        assert "Alice" in result
        assert "Bob" in result

    def test_no_capitalized_words_empty(self, encoder):
        result = encoder._extract_topic_chain(["lower case", "lower text"])
        assert result == []

    def test_single_occurrence_excluded(self, encoder):
        result = encoder._extract_topic_chain(["Alice ran.", "Bob ran."])
        # Each appears once → not in chain
        assert "Alice" not in result


class TestIdentifyMainClaim:
    def test_empty_returns_zero(self, encoder):
        assert encoder._identify_main_claim([], [], []) == 0

    def test_thesis_marker(self, encoder):
        sentences = ["Hi.", "The point is X."]
        info_list = [
            SentenceInfo(text=s, vector=np.zeros(128, dtype=np.float32))
            for s in sentences
        ]
        idx = encoder._identify_main_claim(sentences, [], info_list)
        assert idx == 1

    def test_falls_back_to_intensity(self, encoder):
        sentences = ["a.", "b!"]
        info_list = [
            SentenceInfo(text="a.", vector=np.zeros(128, dtype=np.float32), intensity_score=0.3),
            SentenceInfo(text="b!", vector=np.zeros(128, dtype=np.float32), intensity_score=0.9),
        ]
        idx = encoder._identify_main_claim(sentences, [], info_list)
        assert idx == 1


class TestDetectGestaltPoints:
    def test_thesis_detected(self, encoder):
        sents = ["The point is X."]
        info_list = [SentenceInfo(text=s, vector=np.zeros(128, dtype=np.float32),
                                  intensity_score=1.0) for s in sents]
        gps = encoder._detect_gestalt_points(sents, info_list)
        types = [g.gestalt_type for g in gps]
        assert GestaltType.THESIS in types

    def test_first_sentence_higher_weight(self, encoder):
        sents = ["Consider this."]
        info_list = [SentenceInfo(text=s, vector=np.zeros(128, dtype=np.float32),
                                  intensity_score=1.0) for s in sents]
        gps = encoder._detect_gestalt_points(sents, info_list)
        # First-position weight starts at 0.8 (vs 0.5)
        assert any(g.weight > 0.5 for g in gps)


class TestBindBundle:
    def test_bind_elementwise(self, encoder):
        a = np.array([1, -1, 1], dtype=np.float32)
        b = np.array([1, 1, -1], dtype=np.float32)
        result = encoder._bind(a, b)
        np.testing.assert_array_equal(result, [1, -1, -1])

    def test_bundle_empty_returns_zeros(self, encoder):
        result = encoder._bundle([])
        assert result.shape == (2048,)
        assert np.all(result == 0)

    def test_bundle_thresholding(self, encoder):
        v = np.ones(2048, dtype=np.float32)
        result = encoder._bundle([v, v])
        # Two vectors of all 1s: summed = 2.0, threshold = 2*0.3 = 0.6 → all should be 1
        assert np.all(result == 1.0)


class TestComputeBankActivations:
    def test_normalizes(self, encoder):
        relations = [
            (0, 1, CoherenceRelation.CAUSE),
            (1, 2, CoherenceRelation.CONTRAST),
        ]
        a = encoder._compute_bank_activations(relations)
        # Sum should be very close to 1.0 (with eps)
        assert abs(sum(a.values()) - 1.0) < 1e-3

    def test_unmapped_relation_ignored(self, encoder):
        # ESCALATION isn't in the bank_mapping
        a = encoder._compute_bank_activations([(0, 1, CoherenceRelation.ESCALATION)])
        # All activations should be ~0 (only the eps in denominator)
        assert all(v < 0.1 for v in a.values())


class TestComputeCoherence:
    def test_less_than_two_returns_one(self, encoder):
        assert encoder._compute_coherence([]) == 1.0
        assert encoder._compute_coherence([np.ones(128, dtype=np.float32)]) == 1.0

    def test_identical_vectors_high_coherence(self, encoder):
        v = np.ones(128, dtype=np.float32)
        result = encoder._compute_coherence([v, v])
        assert result == pytest.approx(1.0)

    def test_zero_vectors_skipped(self, encoder):
        # zero-norm vectors are skipped, leaving only non-zero pairs
        z = np.zeros(128, dtype=np.float32)
        result = encoder._compute_coherence([z, z])
        # No valid pairs → fallback to 1.0
        assert result == 1.0


class TestSimilarity:
    def test_identical_returns_one(self, encoder):
        v = np.ones(128, dtype=np.float32)
        e1 = ParagraphEncoding(
            vector=v, structure=None, sentence_vectors=[], bank_activations={}, coherence_score=0.0
        )
        assert encoder.similarity(e1, e1) == pytest.approx(1.0)

    def test_zero_vectors_zero(self, encoder):
        v = np.zeros(128, dtype=np.float32)
        e1 = ParagraphEncoding(
            vector=v, structure=None, sentence_vectors=[], bank_activations={}, coherence_score=0.0
        )
        assert encoder.similarity(e1, e1) == 0.0


class TestEncode:
    def test_empty_paragraph(self, encoder):
        result = encoder.encode("")
        assert result.coherence_score == 0.0
        assert result.structure.sentences == []
        assert np.all(result.vector == 0)

    def test_single_sentence(self, encoder):
        result = encoder.encode("Hello world.")
        assert len(result.structure.sentences) == 1

    def test_multiple_sentences(self, encoder):
        result = encoder.encode("Alice ran. But Bob walked. Therefore they met.")
        assert len(result.structure.sentences) == 3
        # Relations should be detected
        assert len(result.structure.relations) == 2

    def test_uses_provided_sentence_vectors(self, encoder):
        sent_vecs = [np.ones(2048, dtype=np.float32), np.ones(2048, dtype=np.float32) * -1]
        result = encoder.encode("First. Second.", sentence_vectors=sent_vecs)
        # The first sentence vector should match what we passed
        np.testing.assert_array_equal(result.sentence_vectors[0], sent_vecs[0])


# ---------- Singleton ----------

class TestSingleton:
    def test_get_paragraph_encoder_cached(self):
        # Reset module-level singleton for isolation
        psem._paragraph_encoder = None
        a = get_paragraph_encoder()
        b = get_paragraph_encoder()
        assert a is b

    def test_encode_paragraph_convenience(self):
        result = encode_paragraph("Hi.")
        assert isinstance(result, ParagraphEncoding)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
