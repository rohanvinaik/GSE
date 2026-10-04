from gse.primitives import Polarity, canonicalize_decomposition
from gse.vectors import SparseVector, cross_bank_surprise, polarity_aware_similarity


class TestTernaryPolarity:
    """Test ternary polarity encoding."""

    def test_antonym_canonicalization(self):
        """Antonyms should share primitive with opposite polarity."""
        happy = [("GOOD", "evaluation"), ("FEEL", "experiencer")]
        sad = [("BAD", "evaluation"), ("FEEL", "experiencer")]

        happy_canon = canonicalize_decomposition(happy)
        sad_canon = canonicalize_decomposition(sad)

        # Both should have GOOD primitive
        happy_prims = {a.primitive for a in happy_canon}
        sad_prims = {a.primitive for a in sad_canon}

        assert "GOOD" in happy_prims
        assert "GOOD" in sad_prims  # BAD → GOOD with negative polarity

        # But with opposite polarity
        happy_pol = [a.polarity for a in happy_canon if a.primitive == "GOOD"][0]
        sad_pol = [a.polarity for a in sad_canon if a.primitive == "GOOD"][0]

        assert happy_pol == Polarity.POSITIVE
        assert sad_pol == Polarity.NEGATIVE

    def test_polarity_aware_similarity(self):
        """Test polarity-aware similarity analysis."""
        # Create test vectors
        v1 = SparseVector.zeros(8192)
        v1.positive_indices = [100, 200, 300]
        v1.negative_indices = []

        v2 = SparseVector.zeros(8192)
        v2.positive_indices = [100, 200]  # Overlap with same sign
        v2.negative_indices = [300]  # Overlap with opposite sign

        result = polarity_aware_similarity(v1, v2)

        assert 'alignment' in result
        assert 'opposition' in result
        assert result['alignment'] > 0  # Some same-sign overlap
        assert result['opposition'] > 0  # Some opposite-sign overlap

    def test_cross_bank_surprise(self):
        """Test cross-bank surprise calculation."""
        # Create a test vector active in bank 0 and bank 7
        vec = SparseVector.zeros(8192)
        # Bank 0: 0-1024, Bank 7: 7168-8192
        vec.positive_indices = list(range(100, 200)) + list(range(7200, 7300))

        surprise = cross_bank_surprise(vec)

        assert 'active_banks' in surprise
        assert 0 in surprise['active_banks']
        assert 7 in surprise['active_banks']
        assert surprise['surprise_score'] > 0.45  # Should be surprising (distant banks)

    def test_canonicalize_stability(self):
        """Test that canonical decomposition is stable."""
        decomp = [("GOOD", "evaluation"), ("FELL", "experiencer")] # Typo intended to test non-antonyms
        canon = canonicalize_decomposition(decomp)
        assert len(canon) == 2
        assert canon[0].primitive == "GOOD"
        assert canon[0].polarity == Polarity.POSITIVE
