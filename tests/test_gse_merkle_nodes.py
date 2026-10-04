"""Manual contract tests for gse.merkle.nodes."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest

from gse.merkle.hash_chain import MerkleHashChain
from gse.merkle.nodes import (
    BankNode,
    FamilyNode,
    HubNode,
    LexemeNode,
    MerkleNode,
    RootNode,
    create_bank_node,
    create_family_node,
)
from gse.primitives_v2 import SemanticBank


class TestMerkleNodeUpdateCombinedHash:
    def test_combines_content_and_children(self):
        node = MerkleNode(node_id="x", node_type="test", content_hash="abc", children_hash="def")
        node.update_combined_hash()
        expected = MerkleHashChain.combine_hashes("abc", "def")
        assert node.combined_hash == expected


class TestRootNode:
    def test_default_type(self):
        node = RootNode(node_id="root")
        assert node.node_type == "root"
        assert node.version == "2.0.0"

    def test_compute_content_hash_returns_string(self):
        node = RootNode(node_id="root", total_lexemes=100, total_primitives=50)
        h = node.compute_content_hash()
        assert isinstance(h, str)
        assert len(h) == 32

    def test_content_hash_changes_with_metadata(self):
        n1 = RootNode(node_id="root", total_lexemes=100)
        n2 = RootNode(node_id="root", total_lexemes=200)
        assert n1.compute_content_hash() != n2.compute_content_hash()

    def test_children_hash_orders_banks(self):
        node = RootNode(node_id="root")
        node.bank_hashes = {2: "h2", 1: "h1", 3: "h3"}
        h1 = node.compute_children_hash()
        # Same bank_hashes in different insertion order — should produce same hash
        node2 = RootNode(node_id="root")
        node2.bank_hashes = {3: "h3", 1: "h1", 2: "h2"}
        h2 = node2.compute_children_hash()
        assert h1 == h2

    def test_children_hash_empty_dict(self):
        node = RootNode(node_id="root")
        h = node.compute_children_hash()
        assert len(h) == 32


class TestBankNode:
    def test_default_type(self):
        node = BankNode(node_id="b")
        assert node.node_type == "bank"

    def test_compute_content_hash(self):
        node = BankNode(
            node_id="b",
            bank_id=0,
            bank_name="SUBSTANTIVES",
            dim_start=0,
            dim_end=1024,
            primitive_count=10,
            lexeme_count=100,
        )
        h = node.compute_content_hash()
        assert len(h) == 32

    def test_different_bank_id_different_hash(self):
        n1 = BankNode(node_id="x", bank_id=0)
        n2 = BankNode(node_id="x", bank_id=1)
        assert n1.compute_content_hash() != n2.compute_content_hash()

    def test_children_hash_orders_families(self):
        node = BankNode(node_id="b")
        node.family_hashes = {"f2": "h2", "f1": "h1"}
        h = node.compute_children_hash()
        assert len(h) == 32


class TestFamilyNode:
    def test_default_type(self):
        node = FamilyNode(node_id="f")
        assert node.node_type == "family"

    def test_compute_content_hash(self):
        node = FamilyNode(
            node_id="f",
            family_id="entity_animate",
            bank_id=0,
            member_primitives=["SOMEONE", "PEOPLE"],
            hub_primitive="SOMEONE",
            lexeme_count=50,
        )
        h = node.compute_content_hash()
        assert len(h) == 32

    def test_primitives_sorted_in_hash(self):
        """Primitives sorted alphabetically for deterministic hash."""
        n1 = FamilyNode(node_id="f", family_id="x", bank_id=0, member_primitives=["B", "A", "C"])
        n2 = FamilyNode(node_id="f", family_id="x", bank_id=0, member_primitives=["A", "C", "B"])
        assert n1.compute_content_hash() == n2.compute_content_hash()

    def test_children_hash(self):
        node = FamilyNode(node_id="f")
        node.hub_hashes = {"hub1": "h1"}
        h = node.compute_children_hash()
        assert len(h) == 32


class TestHubNode:
    def test_default_type(self):
        node = HubNode(node_id="h")
        assert node.node_type == "hub"

    def test_compute_content_hash_includes_vector_sig(self):
        node = HubNode(
            node_id="h",
            primitive_name="SOMEONE",
            bank_id=0,
            family_id="entity",
            vector_positive=np.array([1, 2, 3], dtype=np.uint16),
            vector_negative=np.array([4, 5], dtype=np.uint16),
        )
        h = node.compute_content_hash()
        assert len(h) == 32

    def test_different_vector_lengths_different_hash(self):
        n1 = HubNode(node_id="h", primitive_name="X", vector_positive=np.array([1, 2], dtype=np.uint16))
        n2 = HubNode(node_id="h", primitive_name="X", vector_positive=np.array([1, 2, 3], dtype=np.uint16))
        assert n1.compute_content_hash() != n2.compute_content_hash()

    def test_children_hash_orders_lexemes(self):
        node = HubNode(node_id="h")
        node.lexeme_hashes = {"b": "h2", "a": "h1"}
        h1 = node.compute_children_hash()
        node2 = HubNode(node_id="h")
        node2.lexeme_hashes = {"a": "h1", "b": "h2"}
        h2 = node2.compute_children_hash()
        assert h1 == h2


class TestLexemeNode:
    def test_default_type(self):
        node = LexemeNode(node_id="lex")
        assert node.node_type == "lexeme"

    def test_compute_content_hash(self):
        node = LexemeNode(
            node_id="happy_adj_01",
            lemma="happy",
            pos="adj",
            sense_id="01",
            gloss="feeling pleasure",
            decomposition=[("GOOD", "evaluation", 1), ("FEEL", "state", 1)],
            source="manual",
            confidence=0.9,
        )
        h = node.compute_content_hash()
        assert len(h) == 32

    def test_different_decomposition_different_hash(self):
        n1 = LexemeNode(node_id="x", lemma="x", decomposition=[("A", "r1", 1)])
        n2 = LexemeNode(node_id="x", lemma="x", decomposition=[("B", "r1", 1)])
        assert n1.compute_content_hash() != n2.compute_content_hash()

    def test_compute_children_hash_empty(self):
        node = LexemeNode(node_id="lex", lemma="x")
        h = node.compute_children_hash()
        # children_hash for lexemes is hash of empty bytes
        expected = MerkleHashChain.compute_hash(b"")
        assert h == expected

    def test_key_property(self):
        node = LexemeNode(node_id="x", lemma="happy", pos="adj", sense_id="01")
        assert node.key == "happy_adj_01"

    def test_to_dict_includes_all_fields(self):
        node = LexemeNode(
            node_id="x",
            lemma="happy",
            pos="adj",
            sense_id="01",
            gloss="g",
            decomposition=[("A", "r", 1)],
            vector_positive=np.array([1, 2], dtype=np.uint16),
            vector_negative=np.array([3], dtype=np.uint16),
            parent_hub="HUB",
            frequency=2.0,
            source="llm",
            confidence=0.8,
        )
        d = node.to_dict()
        assert d["lemma"] == "happy"
        assert d["pos"] == "adj"
        assert d["sense_id"] == "01"
        assert d["gloss"] == "g"
        assert d["decomposition"] == [("A", "r", 1)]
        assert d["vector_positive"] == [1, 2]
        assert d["vector_negative"] == [3]
        assert d["parent_hub"] == "HUB"
        assert d["frequency"] == 2.0
        assert d["source"] == "llm"
        assert d["confidence"] == 0.8

    def test_from_dict_roundtrip(self):
        original = LexemeNode(
            node_id="x",
            lemma="happy",
            pos="adj",
            sense_id="01",
            decomposition=[("A", "r", 1)],
            vector_positive=np.array([1, 2], dtype=np.uint16),
            source="llm",
        )
        original.content_hash = original.compute_content_hash()
        d = original.to_dict()
        restored = LexemeNode.from_dict(d)
        assert restored.lemma == original.lemma
        assert restored.pos == original.pos
        assert restored.decomposition == original.decomposition
        assert restored.source == original.source

    def test_from_dict_defaults(self):
        d = {"lemma": "x", "pos": "n"}
        node = LexemeNode.from_dict(d)
        assert node.lemma == "x"
        assert node.sense_id == "01"  # default
        assert node.source == "manual"
        assert node.frequency == 1.0
        assert node.confidence == 1.0

    def test_from_dict_decomposition_tuples(self):
        d = {"lemma": "x", "pos": "n", "decomposition": [["A", "r", 1]]}
        node = LexemeNode.from_dict(d)
        assert node.decomposition == [("A", "r", 1)]


class TestCreateBankNode:
    def test_creates_node_with_correct_id(self):
        node = create_bank_node(SemanticBank.SUBSTANTIVES)
        assert node.bank_id == SemanticBank.SUBSTANTIVES.value
        assert node.bank_name == "SUBSTANTIVES"

    def test_dim_range_populated(self):
        node = create_bank_node(SemanticBank.SUBSTANTIVES)
        # SUBSTANTIVES is bank 0 → dims 0-1024
        assert node.dim_start == 0
        assert node.dim_end == 1024

    def test_node_id_format(self):
        node = create_bank_node(SemanticBank.QUANTITY)
        assert node.node_id == f"bank_{SemanticBank.QUANTITY.value}"


class TestCreateFamilyNode:
    def test_creates_node(self):
        node = create_family_node(
            family_id="entity_animate",
            bank=SemanticBank.SUBSTANTIVES,
            primitives=["SOMEONE", "PEOPLE"],
            hub="SOMEONE",
        )
        assert node.family_id == "entity_animate"
        assert node.bank_id == SemanticBank.SUBSTANTIVES.value
        assert node.member_primitives == ["SOMEONE", "PEOPLE"]
        assert node.hub_primitive == "SOMEONE"

    def test_node_id_format(self):
        node = create_family_node("ent", SemanticBank.SUBSTANTIVES, [], "")
        assert node.node_id == "family_ent"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
