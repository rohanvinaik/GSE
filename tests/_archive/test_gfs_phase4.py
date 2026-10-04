from unittest.mock import MagicMock

from gse.graph.semantic_graph import SemanticGraph
from gse.patterns.pattern_network import PrimitivePatternNetwork
from gse.vectors import SparseVector

from gse.cache import MerkleNavigator
from gse.orchestration import AmbiguityHandler, CollisionClassifier, CollisionType, Coordinator


class TestOrchestration:
    """Test Orchestration Layer."""

    def test_collision_classification(self):
        classifier = CollisionClassifier()

        # Novel Sense: Pattern Network > Lexicon with high confidence
        c_type = classifier.classify(
            mechanism_a="pattern_network",
            prediction_a="X",
            mechanism_b="lexicon",
            prediction_b=None,
            context={"score_a": 0.9},
        )
        assert c_type == CollisionType.NOVEL_SENSE

        # False Positive: Low confidence pattern network
        c_type = classifier.classify(
            mechanism_a="pattern_network",
            prediction_a="X",
            mechanism_b="lexicon",
            prediction_b=None,
            context={"score_a": 0.6},
        )
        assert c_type == CollisionType.FALSE_POSITIVE

    def test_ambiguity_handler(self):
        handler = AmbiguityHandler(confidence_threshold=0.5)

        # Ambiguous: low confidence
        assert handler.check_ambiguity([("dog", 0.4)])

        # Ambiguous: close margin
        assert handler.check_ambiguity([("dog", 0.8), ("cat", 0.75)])

        # Clear
        assert not handler.check_ambiguity([("dog", 0.9), ("cat", 0.4)])

        # Resolution
        res = handler.resolve([("dog", 0.4)], "ctx")
        assert res["status"] == "ambiguous"


class TestCoordinator:
    """Test Coordinator."""

    def test_process_text(self):
        # Mock components
        graph = MagicMock(spec=SemanticGraph)
        network = MagicMock(spec=PrimitivePatternNetwork)

        lex_scale = MagicMock()
        lex_scale.encode.return_value = SparseVector.zeros(8192)

        scales = {"lexical": lex_scale}

        coord = Coordinator(graph, network, scales)

        # Test word mode
        res = coord.process_text("happy", mode="word")
        assert res["status"] == "ok"
        lex_scale.encode.assert_called_with("happy")

    def test_verify_concept(self):
        # Mock pattern network
        network = MagicMock()
        network.score_pattern_coherence.return_value = 0.9

        coord = Coordinator(MagicMock(), network, {})

        res = coord.verify_concept(["GOOD", "FEEL"])
        assert res["valid"]
        assert res["score"] == 0.9


class TestCache:
    """Test Merkle Navigator."""

    def test_hashing(self):
        cache = MerkleNavigator()

        obj1 = {"a": 1, "b": 2}
        obj2 = {"b": 2, "a": 1}  # Same content, diff order

        h1 = cache.put(obj1)
        h2 = cache.put(obj2)

        assert h1 == h2  # Deterministic hashing for JSON
        assert cache.get(h1) == obj1
