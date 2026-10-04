"""Manual contract tests for gse.merkle.learning_bridge."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.merkle.learning_bridge import (
    FamilyAffinityMatrix,
    KLinePattern,
    KLineStore,
    MerkleLearningBridge,
)
from gse.merkle.nodes import LexemeNode
from gse.merkle.tree import MerkleLexiconTree


def make_lexeme(lemma="happy", decomposition=None):
    if decomposition is None:
        decomposition = [("GOOD", "evaluation", 1), ("FEEL", "state", 1)]
    return LexemeNode(
        node_id=f"{lemma}_adj_01",
        lemma=lemma,
        pos="adj",
        sense_id="01",
        decomposition=decomposition,
        vector_positive=np.array([], dtype=np.uint16),
        vector_negative=np.array([], dtype=np.uint16),
    )


class TestFamilyAffinityMatrixInit:
    def test_basic_init(self):
        m = FamilyAffinityMatrix(["fam1", "fam2", "fam3"])
        assert m.n_families == 3
        assert m.affinity.shape == (3, 3)
        assert m.counts.shape == (3, 3)
        # All zeros initially
        assert m.affinity.sum() == 0
        assert m.counts.sum() == 0


class TestGetIndex:
    def test_known_family(self):
        m = FamilyAffinityMatrix(["a", "b", "c"])
        assert m.get_index("a") == 0
        assert m.get_index("c") == 2

    def test_unknown_family(self):
        m = FamilyAffinityMatrix(["a", "b"])
        assert m.get_index("xyzzy") == -1


class TestUpdateFromDecomposition:
    def test_increments_counts(self):
        m = FamilyAffinityMatrix(["fam1", "fam2"])
        lookup = {"P1": "fam1", "P2": "fam2"}
        m.update_from_decomposition(["P1", "P2"], lookup)
        # P1→fam1, P2→fam2: pair count (0,1) and (1,0) → 1 each
        assert m.counts[0, 1] == 1
        assert m.counts[1, 0] == 1

    def test_unknown_family_skipped(self):
        m = FamilyAffinityMatrix(["fam1"])
        lookup = {"P1": "fam1", "P2": "unknown_fam"}
        m.update_from_decomposition(["P1", "P2"], lookup)
        # Only fam1 indexed, no pairs
        assert m.counts.sum() == 0

    def test_same_position_excluded(self):
        """The i != j filter excludes pairing a primitive with itself
        (by list position), but two distinct primitives in the same family
        WILL increment the diagonal."""
        m = FamilyAffinityMatrix(["fam1"])
        lookup = {"P1": "fam1"}
        # Single primitive — no pairs
        m.update_from_decomposition(["P1"], lookup)
        assert m.counts[0, 0] == 0

    def test_affinity_normalized_to_row_sum(self):
        m = FamilyAffinityMatrix(["fam1", "fam2"])
        lookup = {"P1": "fam1", "P2": "fam2"}
        m.update_from_decomposition(["P1", "P2"], lookup)
        # Each row should sum to 1 (normalized)
        for i in range(m.n_families):
            row_sum = m.affinity[i].sum()
            assert row_sum == pytest.approx(1.0)


class TestGetAffinity:
    def test_known_pair(self):
        m = FamilyAffinityMatrix(["fam1", "fam2"])
        m.affinity[0, 1] = 0.7
        assert m.get_affinity("fam1", "fam2") == pytest.approx(0.7)

    def test_unknown_family_returns_zero(self):
        m = FamilyAffinityMatrix(["fam1"])
        assert m.get_affinity("xyzzy", "fam1") == 0.0
        assert m.get_affinity("fam1", "xyzzy") == 0.0


class TestGetTopAffinities:
    def test_returns_sorted_descending(self):
        m = FamilyAffinityMatrix(["A", "B", "C", "D"])
        m.affinity[0, 1] = 0.3
        m.affinity[0, 2] = 0.7
        m.affinity[0, 3] = 0.5
        top = m.get_top_affinities("A", top_k=3)
        # Expect [(C, 0.7), (D, 0.5), (B, 0.3)] (excluding self A)
        assert top[0][0] == "C"
        assert top[0][1] == pytest.approx(0.7)
        assert top[1][0] == "D"

    def test_excludes_self(self):
        m = FamilyAffinityMatrix(["A", "B"])
        m.affinity[0, 0] = 0.9
        m.affinity[0, 1] = 0.5
        top = m.get_top_affinities("A", top_k=5)
        for name, _ in top:
            assert name != "A"

    def test_unknown_family_returns_empty(self):
        m = FamilyAffinityMatrix(["A"])
        assert m.get_top_affinities("xyzzy") == []


class TestKLinePatternSignature:
    def test_canonical_signature(self):
        p = KLinePattern(
            pattern_id="x",
            primitives=["FEEL", "GOOD"],
            roles=["state", "eval"],
            polarities=[1, 1],
        )
        sig = p.signature
        # Should be sorted, deterministic
        assert isinstance(sig, str)
        # Same content in different order should give same sig
        p2 = KLinePattern(
            pattern_id="y",
            primitives=["GOOD", "FEEL"],
            roles=["eval", "state"],
            polarities=[1, 1],
        )
        assert p.signature == p2.signature


class TestKLineStore:
    def test_empty_store(self):
        s = KLineStore()
        assert s.patterns == {}
        assert s.by_primitive == {}
        assert s.by_role == {}

    def test_add_new_pattern(self):
        s = KLineStore()
        p = KLinePattern(pattern_id="x", primitives=["A"], roles=["r"], polarities=[1])
        s.add_pattern(p)
        assert p.signature in s.patterns

    def test_add_duplicate_increments_frequency(self):
        s = KLineStore()
        p1 = KLinePattern(pattern_id="x", primitives=["A"], roles=["r"], polarities=[1])
        p2 = KLinePattern(pattern_id="y", primitives=["A"], roles=["r"], polarities=[1])
        s.add_pattern(p1)
        s.add_pattern(p2)
        # Same signature → frequency increments
        assert s.patterns[p1.signature].frequency == 2

    def test_index_by_primitive(self):
        s = KLineStore()
        p = KLinePattern(pattern_id="x", primitives=["A", "B"], roles=["r1", "r2"], polarities=[1, 1])
        s.add_pattern(p)
        assert p.signature in s.by_primitive["A"]
        assert p.signature in s.by_primitive["B"]

    def test_index_by_role(self):
        s = KLineStore()
        p = KLinePattern(pattern_id="x", primitives=["A"], roles=["role1"], polarities=[1])
        s.add_pattern(p)
        assert p.signature in s.by_role["role1"]


class TestExtractFromLexeme:
    def test_extracts_pattern(self):
        s = KLineStore()
        lex = make_lexeme()
        p = s.extract_from_lexeme(lex)
        assert p is not None
        assert "FEEL" in p.primitives
        assert "GOOD" in p.primitives
        assert lex.lemma in p.exemplars

    def test_empty_decomposition_returns_none(self):
        s = KLineStore()
        lex = make_lexeme(decomposition=[])
        assert s.extract_from_lexeme(lex) is None


class TestFindSimilarPatterns:
    def test_jaccard_similarity(self):
        s = KLineStore()
        # Add patterns with overlapping primitives
        s.add_pattern(KLinePattern("p1", primitives=["A", "B"], roles=["r", "r"], polarities=[1, 1]))
        s.add_pattern(KLinePattern("p2", primitives=["B", "C"], roles=["r", "r"], polarities=[1, 1]))
        s.add_pattern(KLinePattern("p3", primitives=["X", "Y"], roles=["r", "r"], polarities=[1, 1]))

        # Query {A, B}: p1 matches 2/2, p2 matches 1/3, p3 matches 0/4
        results = s.find_similar_patterns(["A", "B"], top_k=10)
        sigs = [(r[0].pattern_id, r[1]) for r in results]
        # p1 should be top
        assert sigs[0][0] == "p1"

    def test_top_k_limits(self):
        s = KLineStore()
        for i in range(5):
            s.add_pattern(KLinePattern(f"p{i}", primitives=[f"P{i}"], roles=["r"], polarities=[1]))
        results = s.find_similar_patterns(["P0"], top_k=2)
        assert len(results) <= 2

    def test_empty_query(self):
        s = KLineStore()
        s.add_pattern(KLinePattern("p1", primitives=["A"], roles=["r"], polarities=[1]))
        # Empty query → some result with low similarity
        results = s.find_similar_patterns([], top_k=5)
        # Could be empty or low-jaccard results
        assert isinstance(results, list)


class TestGetPatternsForPrimitive:
    def test_returns_patterns(self):
        s = KLineStore()
        p1 = KLinePattern("p1", primitives=["A", "B"], roles=["r", "r"], polarities=[1, 1])
        s.add_pattern(p1)
        result = s.get_patterns_for_primitive("A")
        assert p1 in result

    def test_unknown_primitive_empty(self):
        s = KLineStore()
        assert s.get_patterns_for_primitive("XYZZY") == []


class TestMerkleLearningBridgeInit:
    def test_default_init(self):
        tree = MerkleLexiconTree()
        bridge = MerkleLearningBridge(tree)
        assert bridge.tree is tree
        assert bridge.networks is not None
        assert bridge.orchestrator is not None
        assert isinstance(bridge.family_affinity, FamilyAffinityMatrix)
        assert isinstance(bridge.klines, KLineStore)

    def test_primitive_family_map_populated(self):
        tree = MerkleLexiconTree()
        bridge = MerkleLearningBridge(tree)
        assert len(bridge._primitive_to_family) > 0


class TestTrainFromTree:
    def test_no_lexemes_no_crash(self):
        tree = MerkleLexiconTree()
        bridge = MerkleLearningBridge(tree)
        # Should not raise with empty tree
        bridge.train_from_tree()

    def test_with_lexemes_updates_networks(self):
        tree = MerkleLexiconTree()
        lex = make_lexeme()
        lex.compute_content_hash()
        tree.add_lexeme(lex)
        bridge = MerkleLearningBridge(tree)

        word_updates_before = bridge.networks.word.update_count
        bridge.train_from_tree()
        word_updates_after = bridge.networks.word.update_count
        # word network was updated by the lexeme decomposition
        assert word_updates_after > word_updates_before


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
