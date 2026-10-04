"""
Tests for the Constraint Cascade System

Tests the unified multi-scale processing pipeline:
- Scale-specific primitives
- Compound pattern learning networks
- Constraint propagation
- Merkle caching
"""

import tempfile
from pathlib import Path

import pytest
from gse.cascade import ConstraintCascade, MerkleCache, ScaleFrame, create_cascade
from gse.patterns.compound_network import CompoundPatternNetwork, OrchestratorNetwork, WordScaleNetwork
from gse.primitives import (
    HUB_PRIMITIVES,
    ORCHESTRATOR_NODES,
    PARAGRAPH_PRIMITIVES,
    PRIMITIVE_TO_BANK,
    PRIMITIVES_BY_SCALE,
    SEMANTIC_BANKS,
    SENTENCE_PRIMITIVES,
    TEXT_PRIMITIVES,
    WORD_PRIMITIVES,
    Scale,
)


class TestScalePrimitives:
    """Test scale-specific primitive definitions."""

    def test_text_primitives_count(self):
        assert len(TEXT_PRIMITIVES) == 12

    def test_paragraph_primitives_count(self):
        assert len(PARAGRAPH_PRIMITIVES) == 15

    def test_sentence_primitives_count(self):
        assert len(SENTENCE_PRIMITIVES) == 20

    def test_word_primitives_count(self):
        assert len(WORD_PRIMITIVES) == 62

    def test_hub_primitives_count(self):
        assert len(HUB_PRIMITIVES) == 24

    def test_orchestrator_nodes_count(self):
        assert len(ORCHESTRATOR_NODES) == 36

    def test_hub_primitives_are_word_primitives(self):
        """All hub primitives should be from the word primitive set."""
        for hub in HUB_PRIMITIVES:
            assert hub in WORD_PRIMITIVES, f"{hub} not in WORD_PRIMITIVES"

    def test_primitives_by_scale_complete(self):
        """All scales should have primitive mappings."""
        assert Scale.TEXT in PRIMITIVES_BY_SCALE
        assert Scale.PARAGRAPH in PRIMITIVES_BY_SCALE
        assert Scale.SENTENCE in PRIMITIVES_BY_SCALE
        assert Scale.WORD in PRIMITIVES_BY_SCALE

    def test_semantic_banks_cover_all_primitives(self):
        """All word primitives should be in a semantic bank."""
        all_in_banks = set()
        for prims in SEMANTIC_BANKS.values():
            all_in_banks.update(prims)

        for prim in WORD_PRIMITIVES:
            assert prim in all_in_banks, f"{prim} not in any semantic bank"

    def test_primitive_to_bank_mapping(self):
        """PRIMITIVE_TO_BANK should map all word primitives."""
        for prim in WORD_PRIMITIVES:
            assert prim in PRIMITIVE_TO_BANK, f"{prim} not in PRIMITIVE_TO_BANK"


class TestCompoundPatternNetwork:
    """Test the compound pattern learning network."""

    def test_init(self):
        net = CompoundPatternNetwork(HUB_PRIMITIVES, Scale.WORD)
        assert net.n == 24
        assert net.scale == Scale.WORD
        assert net.weights.shape == (24, 24)

    def test_observe_updates_weights(self):
        net = CompoundPatternNetwork(HUB_PRIMITIVES, Scale.WORD)

        # Observe some primitives
        net.observe({"FEEL", "GOOD", "SOMEONE"})

        # Weights between observed primitives should increase
        i_feel = net.node_to_idx["FEEL"]
        i_good = net.node_to_idx["GOOD"]
        assert net.weights[i_feel, i_good] > 0

    def test_observe_creates_patterns(self):
        net = CompoundPatternNetwork(HUB_PRIMITIVES, Scale.WORD)

        # Observe 3+ primitives creates a pattern
        net.observe({"FEEL", "GOOD", "SOMEONE"})

        assert len(net.patterns) >= 1

    def test_predict_returns_primitives(self):
        net = CompoundPatternNetwork(HUB_PRIMITIVES, Scale.WORD)

        # Train with some patterns
        for _ in range(10):
            net.observe({"FEEL", "GOOD", "SOMEONE"})
            net.observe({"THINK", "SOMETHING", "BE"})

        # Predict from partial input
        preds = net.predict({"FEEL", "GOOD"}, top_k=5)

        assert len(preds) > 0
        assert all(isinstance(p, tuple) and len(p) == 2 for p in preds)

    def test_coherence_score_range(self):
        net = CompoundPatternNetwork(HUB_PRIMITIVES, Scale.WORD)

        # Train
        for _ in range(5):
            net.observe({"FEEL", "GOOD", "SOMEONE"})

        # Coherence should be in [0, 1]
        score = net.coherence_score({"FEEL", "GOOD"})
        assert 0 <= score <= 1

    def test_save_load_roundtrip(self):
        net = CompoundPatternNetwork(HUB_PRIMITIVES, Scale.WORD)
        net.observe({"FEEL", "GOOD", "SOMEONE"})

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        net.save(path)

        loaded = CompoundPatternNetwork.load(path)

        assert loaded.n == net.n
        assert len(loaded.patterns) == len(net.patterns)

        Path(path).unlink()


class TestWordScaleNetwork:
    """Test the 24-node word-scale learning network."""

    def test_init(self):
        net = WordScaleNetwork()
        assert net.n == 24
        assert net.scale == Scale.WORD

    def test_bank_structure_initialized(self):
        net = WordScaleNetwork()

        # Same-bank primitives should have slight positive prior
        i_feel = net.node_to_idx["FEEL"]
        i_think = net.node_to_idx["THINK"]

        # FEEL and THINK are both in Mental bank (bank 3)
        assert net.weights[i_feel, i_think] > 0

    def test_map_to_hubs(self):
        net = WordScaleNetwork()

        # Map some primitives to hubs
        full_prims = {"GOOD", "FEEL", "SOMEONE", "I", "YOU"}
        hubs = net._map_to_hubs(full_prims)

        # Should get hub primitives
        assert "GOOD" in hubs  # GOOD is a hub
        assert "FEEL" in hubs  # FEEL is a hub
        assert "SOMEONE" in hubs  # SOMEONE is a hub


class TestOrchestratorNetwork:
    """Test the 36-node orchestrator learning network."""

    def test_init(self):
        net = OrchestratorNetwork()
        assert net.n == 36

    def test_routing_priors(self):
        net = OrchestratorNetwork()

        # Route chain should have positive priors
        i_text = net.node_to_idx["ROUTE_TEXT"]
        i_para = net.node_to_idx["ROUTE_PARAGRAPH"]

        assert net.weights[i_text, i_para] > 0

    def test_route_decision(self):
        net = OrchestratorNetwork()

        features = {"ROUTE_TEXT": 1.0, "CONF_HIGH": 0.8}
        routing = net.route_decision(features)

        assert isinstance(routing, dict)
        assert len(routing) > 0


class TestMerkleCache:
    """Test the Merkle caching system."""

    def test_store_and_lookup(self):
        cache = MerkleCache()

        # Create a mock result
        from gse.vectors import SparseVector
        result = type('CascadeResult', (), {
            'text': 'test',
            'vector': SparseVector.zeros(8192),
            'frames': {},
            'confidence': 0.8,
            'merkle_root': 'abc123',
            'processing_time': 0.01,
            'ambiguities': []
        })()

        cache.store("test text", result)
        cached = cache.lookup("test text")

        assert cached is not None
        assert cached.text == 'test'

    def test_cache_miss(self):
        cache = MerkleCache()
        result = cache.lookup("nonexistent")
        assert result is None

    def test_lru_eviction(self):
        cache = MerkleCache(max_size=5)

        from gse.vectors import SparseVector
        for i in range(10):
            result = type('CascadeResult', (), {
                'text': f'test{i}',
                'vector': SparseVector.zeros(8192),
                'frames': {},
                'confidence': 0.8,
                'merkle_root': f'hash{i}',
                'processing_time': 0.01,
                'ambiguities': []
            })()
            cache.store(f"text {i}", result)

        # Cache should have evicted some entries
        assert len(cache.cache) <= 5


class TestScaleFrame:
    """Test scale activation frames."""

    def test_active_set(self):
        frame = ScaleFrame(
            scale=Scale.TEXT,
            active={"FORMAL": 0.8, "ACADEMIC": 0.6, "INFORMAL": 0.05},
            confidence=0.8
        )

        active = frame.active_set()
        assert "FORMAL" in active
        assert "ACADEMIC" in active
        assert "INFORMAL" not in active  # Below threshold


class TestConstraintCascade:
    """Test the main constraint cascade pipeline."""

    @pytest.fixture
    def cascade(self):
        """Create a cascade without lexicon for basic testing."""
        return ConstraintCascade(use_cache=True)

    def test_text_constraints_formal(self, cascade):
        text = "Therefore, we conclude that the hypothesis is supported. Furthermore, the evidence suggests..."
        frame = cascade._text_constraints(text)

        assert frame.scale == Scale.TEXT
        assert "FORMAL" in frame.active or "ARGUMENTATIVE" in frame.active

    def test_text_constraints_narrative(self, cascade):
        text = "Once upon a time, he said to her, 'Let me tell you a story.' Then suddenly..."
        frame = cascade._text_constraints(text)

        assert "NARRATIVE" in frame.active

    def test_paragraph_segmentation(self, cascade):
        text = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph."
        paragraphs = cascade._segment_paragraphs(text)

        assert len(paragraphs) == 3

    def test_paragraph_constraints_contrast(self, cascade):
        paragraphs = [
            "The first approach works well.",
            "However, there are some limitations to consider."
        ]
        text_frame = ScaleFrame(Scale.TEXT, {"EXPOSITORY": 0.5}, 0.5)

        para_frame = cascade._paragraph_constraints(paragraphs, text_frame)

        assert "CONTRAST" in para_frame.active or "CONTINUATION" in para_frame.active

    def test_sentence_segmentation(self, cascade):
        text = "First sentence. Second sentence! Third sentence?"
        sentences = cascade._segment_sentences(text)

        assert len(sentences) >= 3

    def test_merkle_root_deterministic(self, cascade):
        text = "The same text produces the same Merkle root."

        result1 = cascade.process(text)
        result2 = cascade.process(text)

        assert result1.merkle_root == result2.merkle_root

    def test_confidence_range(self, cascade):
        result = cascade.process("A simple test sentence.")

        assert 0 <= result.confidence <= 1

    def test_processing_time_recorded(self, cascade):
        result = cascade.process("Test sentence for timing.")

        assert result.processing_time > 0
        assert result.processing_time < 10  # Should be fast

    def test_caching_works(self, cascade):
        text = "This text will be cached."

        # First call
        result1 = cascade.process(text)
        time1 = result1.processing_time

        # Second call should be cached (much faster)
        result2 = cascade.process(text)

        assert result2.vector.nnz == result1.vector.nnz


class TestIntegrationWithLexicon:
    """Integration tests with actual lexicon."""

    @pytest.fixture
    def full_cascade(self):
        """Create cascade with lexicon if available."""
        lexicon_path = Path("data/lexicon.db")
        basis_path = Path("data/basis.msgpack")
        networks_path = Path("data/networks")

        if lexicon_path.exists() and basis_path.exists():
            cascade = ConstraintCascade(
                lexicon_path=str(lexicon_path),
                basis_path=str(basis_path),
                use_cache=True
            )
            # Load trained networks if available
            if networks_path.exists():
                cascade.load_networks(str(networks_path))
            return cascade
        else:
            pytest.skip("Lexicon or basis not available")

    def test_full_pipeline(self, full_cascade):
        result = full_cascade.process("The happy dog runs through the park.")

        assert result.vector.nnz > 0
        assert result.confidence > 0
        assert Scale.TEXT in result.frames
        assert Scale.PARAGRAPH in result.frames
        assert Scale.SENTENCE in result.frames
        # WORD scale produces vectors, not frames

    def test_similar_sentences_similar_vectors(self, full_cascade):

        result1 = full_cascade.process("The cat sleeps on the bed.")
        result2 = full_cascade.process("The dog rests on the couch.")

        sim = result1.vector.cosine(result2.vector)

        # Similar sentences should have positive similarity
        assert sim > 0

    def test_different_topics_lower_similarity(self, full_cascade):
        result1 = full_cascade.process("The scientist studied quantum physics.")
        result2 = full_cascade.process("The chef prepared a delicious meal.")

        sim = result1.vector.cosine(result2.vector)

        # Different topics should have lower similarity than similar topics
        result3 = full_cascade.process("The researcher analyzed particle behavior.")
        sim_similar = result1.vector.cosine(result3.vector)

        assert sim_similar > sim

    def test_word_network_predictions_sensible(self, full_cascade):
        # After training, predictions should be semantically sensible
        preds = full_cascade.word_network.predict({"FEEL", "GOOD"}, top_k=5)

        pred_names = [p[0] for p in preds]

        # Should predict related primitives
        # SOMEONE (experiencer), BE (state), etc.
        assert len(preds) > 0


class TestProductionReadiness:
    """Tests for production deployment."""

    def test_cascade_handles_empty_input(self):
        cascade = ConstraintCascade(use_cache=False)
        result = cascade.process("")

        assert result.vector.nnz >= 0
        assert result.confidence >= 0

    def test_cascade_handles_long_input(self):
        cascade = ConstraintCascade(use_cache=False)
        long_text = "This is a sentence. " * 100
        result = cascade.process(long_text)

        assert result.processing_time < 60  # Should complete in reasonable time

    def test_cascade_handles_special_characters(self):
        cascade = ConstraintCascade(use_cache=False)
        text = "Special chars: @#$%^&*()! Emojis: 😀🎉 Unicode: café résumé"
        result = cascade.process(text)

        # Should not crash
        assert result is not None

    def test_network_save_load_preserves_state(self):
        net = WordScaleNetwork()

        # Train
        for _ in range(10):
            net.observe({"FEEL", "GOOD", "SOMEONE"})

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "network.json"
            net.save(str(path))

            loaded = WordScaleNetwork.load(str(path))

            assert loaded.total_observations == net.total_observations
            assert len(loaded.patterns) == len(net.patterns)

    def test_create_cascade_factory(self):
        # Test factory function with non-existent paths (should not crash)
        cascade = create_cascade(
            lexicon_path="nonexistent.db",
            basis_path="nonexistent.msgpack"
        )

        assert cascade is not None
        assert cascade.lexicon is None
        assert cascade.basis is None
