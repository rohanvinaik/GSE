"""Manual contract tests for gse.patterns.networks_v2."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.patterns.networks_v2 import (
    PARAGRAPH_PRIMITIVES,
    SENTENCE_PRIMITIVES,
    TEXT_PRIMITIVES,
    WORD_PRIMITIVES,
    LearningNetwork,
    ParagraphScaleNetwork,
    ScaleNetworkCollection,
    SentenceScaleNetwork,
    TextScaleNetwork,
    WordScaleNetwork,
)


class TestLearningNetworkInit:
    def test_default_init(self):
        net = LearningNetwork(name="test", node_names=["A", "B", "C"])
        assert net.n_nodes == 3
        assert net.weights.shape == (3, 3)
        assert net.update_count == 0

    def test_diagonal_zero(self):
        net = LearningNetwork(name="test", node_names=["A", "B"])
        for i in range(net.n_nodes):
            assert net.weights[i, i] == 0.0

    def test_get_index_known_name(self):
        net = LearningNetwork(name="test", node_names=["A", "B", "C"])
        assert net.get_index("A") == 0
        assert net.get_index("B") == 1
        assert net.get_index("C") == 2

    def test_get_index_unknown_returns_negative(self):
        net = LearningNetwork(name="test", node_names=["A"])
        assert net.get_index("XYZZY") == -1


class TestActivate:
    def test_returns_dict(self):
        net = LearningNetwork(name="t", node_names=["A", "B"])
        result = net.activate({"A": 1.0})
        assert isinstance(result, dict)

    def test_unknown_input_ignored(self):
        net = LearningNetwork(name="t", node_names=["A", "B"])
        # XYZZY is not a node, should be ignored without error
        result = net.activate({"XYZZY": 1.0})
        assert isinstance(result, dict)

    def test_threshold_filters_low_activations(self):
        net = LearningNetwork(name="t", node_names=["A", "B"], activation_threshold=0.9)
        # With threshold=0.9, weak activations should be filtered out
        result = net.activate({"A": 0.1})
        # A's activation is small; should likely be filtered
        for v in result.values():
            assert abs(v) > 0.9

    def test_increments_total_activations(self):
        net = LearningNetwork(name="t", node_names=["A", "B"])
        initial = net.total_activations
        net.activate({"A": 1.0})
        assert net.total_activations == initial + 1


class TestLearn:
    def test_increments_update_count(self):
        net = LearningNetwork(name="t", node_names=["A", "B"])
        initial = net.update_count
        net.learn({"A": 1.0, "B": 1.0})
        assert net.update_count == initial + 1

    def test_strengthens_coactivated_pair(self):
        net = LearningNetwork(name="t", node_names=["A", "B"], learning_rate=0.5)
        # Repeatedly co-activate A and B
        for _ in range(10):
            net.learn({"A": 1.0, "B": 1.0})
        # Weight A→B should be positive
        assert net.weights[0, 1] > 0
        assert net.weights[1, 0] > 0

    def test_diagonal_stays_zero(self):
        net = LearningNetwork(name="t", node_names=["A", "B"])
        net.learn({"A": 1.0, "B": 1.0})
        for i in range(net.n_nodes):
            assert net.weights[i, i] == 0.0

    def test_unknown_nodes_ignored(self):
        net = LearningNetwork(name="t", node_names=["A"])
        # Should not raise
        net.learn({"XYZZY": 1.0, "A": 1.0})
        assert net.update_count == 1


class TestGetAssociations:
    def test_known_node_returns_associations(self):
        net = LearningNetwork(name="t", node_names=["A", "B", "C"], learning_rate=0.5)
        for _ in range(5):
            net.learn({"A": 1.0, "B": 1.0})
        assocs = net.get_associations("A", top_k=3)
        assert len(assocs) > 0
        # Self should NOT be in associations
        for name, _ in assocs:
            assert name != "A"

    def test_unknown_node_returns_empty(self):
        net = LearningNetwork(name="t", node_names=["A"])
        assert net.get_associations("XYZZY") == []

    def test_top_k_limits(self):
        net = LearningNetwork(name="t", node_names=["A", "B", "C", "D", "E"])
        assocs = net.get_associations("A", top_k=2)
        assert len(assocs) <= 2


class TestGetWeight:
    def test_known_pair(self):
        net = LearningNetwork(name="t", node_names=["A", "B"])
        net.weights[0, 1] = 0.7
        assert net.get_weight("A", "B") == pytest.approx(0.7)

    def test_unknown_name_returns_zero(self):
        net = LearningNetwork(name="t", node_names=["A"])
        assert net.get_weight("XYZZY", "A") == 0.0
        assert net.get_weight("A", "XYZZY") == 0.0


class TestSaveLoad:
    def test_roundtrip(self):
        net = LearningNetwork(name="t", node_names=["A", "B"], learning_rate=0.5)
        net.learn({"A": 1.0, "B": 1.0})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp = f.name

        try:
            net.save(tmp)
            loaded = LearningNetwork.load(tmp)
            assert loaded.name == net.name
            assert loaded.node_names == net.node_names
            assert np.allclose(loaded.weights, net.weights)
            assert loaded.update_count == net.update_count
        finally:
            Path(tmp).unlink(missing_ok=True)


class TestSubclasses:
    def test_text_scale_network_uses_text_primitives(self):
        net = TextScaleNetwork()
        assert net.node_names == TEXT_PRIMITIVES

    def test_paragraph_scale_network_uses_paragraph_primitives(self):
        net = ParagraphScaleNetwork()
        assert net.node_names == PARAGRAPH_PRIMITIVES

    def test_sentence_scale_network_uses_sentence_primitives(self):
        net = SentenceScaleNetwork()
        assert net.node_names == SENTENCE_PRIMITIVES

    def test_word_scale_network_uses_word_primitives(self):
        net = WordScaleNetwork()
        assert net.node_names == WORD_PRIMITIVES


class TestTextScaleClassify:
    def test_classify_returns_dict(self):
        net = TextScaleNetwork()
        result = net.classify_text({"FORMAL": 0.8})
        assert isinstance(result, dict)


class TestWordScaleLearnFromDecomposition:
    def test_learn_with_polarity(self):
        net = WordScaleNetwork()
        # All primitives in WORD_PRIMITIVES
        decomp = [
            ("FEEL", "experiencer", 1),
            ("GOOD", "evaluation", 1),
        ]
        # Should not raise
        net.learn_from_decomposition(decomp)
        assert net.update_count == 1

    def test_single_primitive_no_learn(self):
        net = WordScaleNetwork()
        # Only one primitive — no co-occurrence to learn
        net.learn_from_decomposition([("FEEL", "experiencer", 1)])
        assert net.update_count == 0

    def test_unknown_primitive_filtered(self):
        net = WordScaleNetwork()
        # XYZZY is not in WORD_PRIMITIVES
        net.learn_from_decomposition([
            ("XYZZY", "x", 1),
            ("FEEL", "experiencer", 1),
        ])
        # Only 1 known primitive after filtering → no learn
        assert net.update_count == 0


class TestWordScalePredictPrimitives:
    def test_returns_tuples(self):
        net = WordScaleNetwork()
        # Train a co-occurrence
        for _ in range(5):
            net.learn_from_decomposition([
                ("FEEL", "exp", 1),
                ("GOOD", "eval", 1),
            ])
        result = net.predict_primitives(["FEEL"], top_k=3)
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_excludes_seeds(self):
        net = WordScaleNetwork()
        for _ in range(5):
            net.learn_from_decomposition([
                ("FEEL", "exp", 1),
                ("GOOD", "eval", 1),
            ])
        result = net.predict_primitives(["FEEL"], top_k=10)
        for name, _ in result:
            assert name != "FEEL"


class TestScaleNetworkCollection:
    def test_default_init(self):
        coll = ScaleNetworkCollection()
        assert isinstance(coll.text, TextScaleNetwork)
        assert isinstance(coll.paragraph, ParagraphScaleNetwork)
        assert isinstance(coll.sentence, SentenceScaleNetwork)
        assert isinstance(coll.word, WordScaleNetwork)

    def test_get_network_by_name(self):
        coll = ScaleNetworkCollection()
        assert coll.get_network("text") is coll.text
        assert coll.get_network("paragraph") is coll.paragraph
        assert coll.get_network("sentence") is coll.sentence
        assert coll.get_network("word") is coll.word

    def test_unknown_scale_returns_none(self):
        coll = ScaleNetworkCollection()
        assert coll.get_network("xyzzy") is None

    def test_learn_from_document_text(self):
        coll = ScaleNetworkCollection()
        coll.learn_from_document(text_features={"FORMAL": 1.0, "TECHNICAL": 0.8})
        assert coll.text.update_count == 1

    def test_learn_from_document_paragraph(self):
        coll = ScaleNetworkCollection()
        coll.learn_from_document(paragraph_relations=["CAUSE", "EFFECT", "CONTRAST"])
        # Two transitions: CAUSE→EFFECT, EFFECT→CONTRAST
        assert coll.paragraph.update_count == 2

    def test_learn_from_document_sentence(self):
        coll = ScaleNetworkCollection()
        coll.learn_from_document(sentence_structures=[{"SYN_SUBJ": 1.0, "SYN_PRED": 1.0}])
        assert coll.sentence.update_count == 1

    def test_learn_from_document_word(self):
        coll = ScaleNetworkCollection()
        coll.learn_from_document(word_decompositions=[[
            ("FEEL", "exp", 1),
            ("GOOD", "eval", 1),
        ]])
        assert coll.word.update_count == 1

    def test_get_statistics(self):
        coll = ScaleNetworkCollection()
        stats = coll.get_statistics()
        assert "text" in stats
        assert "paragraph" in stats
        assert "sentence" in stats
        assert "word" in stats
        for scale_stats in stats.values():
            assert "nodes" in scale_stats
            assert "updates" in scale_stats
            assert "weight_norm" in scale_stats

    def test_save_load_collection(self):
        coll = ScaleNetworkCollection()
        coll.learn_from_document(text_features={"FORMAL": 1.0, "ACADEMIC": 0.9})

        with tempfile.TemporaryDirectory() as tmp:
            coll.save(tmp)
            loaded = ScaleNetworkCollection.load(tmp)
            assert loaded.text.update_count == coll.text.update_count
            assert np.allclose(loaded.text.weights, coll.text.weights)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
