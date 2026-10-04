import json
import sqlite3

import pytest
from gse.primitives import Polarity

from gse.patterns import CooccurrenceMatrix, KLineStore, PrimitivePatternNetwork


class TestPatternNetwork:
    """Test Primitive Pattern Network functionality."""

    @pytest.fixture
    def mock_lexicon(self, tmp_path):
        """Create a temporary lexicon database for testing."""
        db_path = tmp_path / "test_lexicon.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE lexicon (decomposition TEXT)")

        # Add some sample decompositions
        # "happy" -> GOOD, FEEL
        happy = json.dumps([("GOOD", "evaluation"), ("FEEL", "experiencer")])
        # "joy" -> GOOD, FEEL, VERY
        joy = json.dumps([("GOOD", "evaluation"), ("FEEL", "experiencer"), ("VERY", "intensity")])
        # "sad" -> BAD, FEEL (will be canonicalized to GOOD-, FEEL+)
        sad = json.dumps([("BAD", "evaluation"), ("FEEL", "experiencer")])
        # "unknown" -> XYZ (should be ignored)
        unknown = json.dumps([("XYZ", "evaluation")])

        conn.execute("INSERT INTO lexicon VALUES (?)", (happy,))
        conn.execute("INSERT INTO lexicon VALUES (?)", (joy,))
        conn.execute("INSERT INTO lexicon VALUES (?)", (sad,))
        conn.execute("INSERT INTO lexicon VALUES (?)", (unknown,))

        conn.commit()
        conn.close()
        return str(db_path)

    @pytest.fixture
    def primitives(self):
        return ["GOOD", "BAD", "FEEL", "VERY", "BIG", "SMALL"]

    def test_cooccurrence_learning(self, mock_lexicon, primitives):
        """Test that matrix learns co-occurrences correctly."""
        matrix = CooccurrenceMatrix(primitives)
        matrix.learn_from_lexicon(mock_lexicon)

        # GOOD and FEEL should co-occur in happy, joy
        # BAD and FEEL should co-occur in sad
        # Note: logical primitives might be different after canonicalization?
        # CooccurrenceMatrix uses RAW primitives from json, before canonicalization?
        # Check implementation: "Extract primitives from this decomposition... prim = item[0]"
        # Yes, it uses raw primitives.

        p = matrix.get_probability("GOOD", "FEEL")
        assert p > 0.0

        p2 = matrix.get_probability("BAD", "FEEL")
        assert p2 > 0.0

        p3 = matrix.get_probability("GOOD", "BAD")
        assert p3 == 0.0  # They never appear together

    def test_kline_learning(self, mock_lexicon, primitives):
        """Test K-line extraction."""
        # K-lines USE canonicalization
        store = KLineStore(min_pattern_size=2)
        store.learn_from_lexicon(mock_lexicon, primitives)

        # Should have patterns for happy/sad
        assert len(store) >= 2

        # Check for GOOD w/ Polarity.NEGATIVE (from "sad" -> BAD)
        found_sad = False
        for kline in store._klines.values():
            if ("GOOD", int(Polarity.NEGATIVE)) in kline.pattern:
                found_sad = True
        assert found_sad

    def test_prediction(self, mock_lexicon, primitives):
        """Test primitive prediction."""
        network = PrimitivePatternNetwork(primitives)
        network.learn(mock_lexicon)

        # Given GOOD, we expect FEEL
        preds = network.predict_primitives({"GOOD"}, top_k=3)
        pred_prims = [p for p, s in preds]

        assert "FEEL" in pred_prims

    def test_coherence(self, mock_lexicon, primitives):
        """Test coherence scoring."""
        network = PrimitivePatternNetwork(primitives)
        network.learn(mock_lexicon)

        # "happy" decomposition should be coherent
        score_happy = network.score_pattern_coherence([("GOOD", "evaluation"), ("FEEL", "experiencer")])
        assert score_happy > 0.8

        # Random nonsensical decomposition
        score_rand = network.score_pattern_coherence([("GOOD", "evaluation"), ("BIG", "size")])
        assert score_rand < score_happy
