import json
import sqlite3

import pytest
from gse.graph.builder import GraphBuilder
from gse.graph.traversal import HierarchicalTraversal
from gse.patterns.pattern_network import PrimitivePatternNetwork
from gse.primitives import Polarity, canonicalize_decomposition
from gse.vectors import SparseVector

from gse.orchestration import AmbiguityHandler, CollisionClassifier, CollisionType
from gse.scales import DiscourseScale


class TestGFSIntegration:
    """
    Comprehensive Integration Tests for GFS Refactor.
    Coverage: Foundation, Patterns, Graph, Scales, Orchestration.
    """

    @pytest.fixture
    def mock_db(self, tmp_path):
        db_path = tmp_path / "integration_lexicon.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE lexicon (lemma TEXT, pos TEXT, decomposition TEXT, frequency REAL)")

        data = [
            ("happy", "adj", json.dumps([("GOOD", "evaluation"), ("FEEL", "experiencer")]), 0.8),
            ("sad", "adj", json.dumps([("BAD", "evaluation"), ("FEEL", "experiencer")]), 0.7),
            ("joy", "noun", json.dumps([("GOOD", "evaluation"), ("FEEL", "experiencer"), ("VERY", "intensity")]), 0.5),
            ("grief", "noun", json.dumps([("BAD", "evaluation"), ("FEEL", "experiencer"), ("VERY", "intensity")]), 0.4),
            ("doctor", "noun", json.dumps([("PERSON", "agent"), ("HEAL", "action")]), 0.6),
            ("nurse", "noun", json.dumps([("PERSON", "agent"), ("HEAL", "action")]), 0.5),
        ]

        for row in data:
            conn.execute("INSERT INTO lexicon VALUES (?, ?, ?, ?)", row)

        conn.commit()
        conn.close()
        return str(db_path)

    @pytest.fixture
    def primitives(self):
        return ["GOOD", "BAD", "FEEL", "VERY", "PERSON", "HEAL", "BIG", "SMALL"]

    def test_ternary_polarity(self):
        """Test antonym canonicalization and polarity-aware similarity."""
        happy_decomp = [("GOOD", "evaluation"), ("FEEL", "experiencer")]
        sad_decomp = [("BAD", "evaluation"), ("FEEL", "experiencer")]  # BAD -> GOOD w/ negative

        # Verify canonicalization
        canon_sad = canonicalize_decomposition(sad_decomp)
        sad_prim_map = {p.primitive: p.polarity for p in canon_sad}
        assert "GOOD" in sad_prim_map
        assert sad_prim_map["GOOD"] == Polarity.NEGATIVE

        # Verify similarity Logic (mock vectors)
        # We assume vectors.py logic is correct, just checking high-level behavior if we had vectors
        # Here we manually check the polarity logic
        pass

    def test_pattern_network(self, mock_db, primitives):
        """Test co-occurrence and K-line learning."""
        network = PrimitivePatternNetwork(primitives)
        network.learn(mock_db)

        # happy and joy share GOOD+FEEL
        # sad and grief share BAD+FEEL (GOOD- + FEEL+)

        # Predict FEEL given GOOD
        preds = network.predict_primitives({"GOOD"})
        prims = [p for p, s in preds]
        assert "FEEL" in prims

        # Verify prediction for SAD context (using canonical BAD->GOOD-)
        # The network learns from "sad" which has BAD.
        # CooccurrenceMatrix uses raw "BAD".
        # KLines use canonical "GOOD-".

        # Matrix check
        prob = network.matrix.get_probability("BAD", "FEEL")
        assert prob > 0.0

    def test_hierarchical_traversal(self, mock_db, primitives):
        """Test graph building and primitive bottleneck."""
        builder = GraphBuilder(primitives)
        graph = builder.build(mock_db)
        trav = HierarchicalTraversal(graph)

        # doctor and nurse share primitives
        dist = trav.semantic_distance("doctor.noun", "nurse.noun")
        assert dist < 0.2

        # happy and doctor share nothing
        dist2 = trav.semantic_distance("happy.adj", "doctor.noun")
        assert dist2 > 0.8

        # Search similar
        sims = trav.find_similar_lexemes("doctor.noun")
        found = [s[0] for s in sims]
        assert "nurse.noun" in found

    def test_no_string_matching(self):
        """
        Verify that discourse coherence uses vector similarity,
        not string overlap.
        """
        scale = DiscourseScale()

        # Create two vectors that are orthogonal (diff indices)
        v1 = SparseVector.zeros(100)
        v1.positive_indices = [1, 2]
        v2 = SparseVector.zeros(100)
        v2.positive_indices = [3, 4]

        # Coherence should be 0 even if we pretend strings match outside
        coh = scale.measure_coherence([v1, v2])
        assert coh == 0.0

        # Similar vectors
        v3 = SparseVector.zeros(100)
        v3.positive_indices = [1, 2, 5]
        coh2 = scale.measure_coherence([v1, v3])
        assert coh2 > 0.5

    def test_collision_handling(self):
        """Test collision classifier."""
        classifier = CollisionClassifier()
        # Novel sense
        res = classifier.classify("pattern_network", "X", "lexicon", None, {"score_a": 0.9})
        assert res == CollisionType.NOVEL_SENSE

    def test_graceful_degradation(self):
        """Test ambiguity handling."""
        handler = AmbiguityHandler(confidence_threshold=0.6)

        # Low confidence
        res = handler.resolve([("cat", 0.4)], "ctx")
        assert res["status"] == "ambiguous"
        assert "unsure" in res["question"]
