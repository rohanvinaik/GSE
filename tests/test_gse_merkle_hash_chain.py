"""Manual contract tests for gse.merkle.hash_chain."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.merkle.hash_chain import (
    DifferenceProof,
    MembershipProof,
    MerkleHashChain,
    compute_tree_root_from_leaves,
    verify_hash_chain,
)


class TestComputeHash:
    def test_returns_string(self):
        h = MerkleHashChain.compute_hash(b"x")
        assert isinstance(h, str)

    def test_truncated_to_32_chars(self):
        h = MerkleHashChain.compute_hash(b"any data")
        assert len(h) == 32

    def test_deterministic(self):
        h1 = MerkleHashChain.compute_hash(b"hello")
        h2 = MerkleHashChain.compute_hash(b"hello")
        assert h1 == h2

    def test_different_input_different_hash(self):
        h1 = MerkleHashChain.compute_hash(b"hello")
        h2 = MerkleHashChain.compute_hash(b"world")
        assert h1 != h2

    def test_empty_bytes(self):
        h = MerkleHashChain.compute_hash(b"")
        assert len(h) == 32


class TestCombineHashes:
    def test_returns_32_char_hash(self):
        h = MerkleHashChain.combine_hashes("abc", "def")
        assert len(h) == 32

    def test_order_matters(self):
        h1 = MerkleHashChain.combine_hashes("a", "b")
        h2 = MerkleHashChain.combine_hashes("b", "a")
        assert h1 != h2

    def test_deterministic(self):
        h1 = MerkleHashChain.combine_hashes("a", "b")
        h2 = MerkleHashChain.combine_hashes("a", "b")
        assert h1 == h2


class TestHashList:
    def test_returns_32_char_hash(self):
        h = MerkleHashChain.hash_list(["a", "b", "c"])
        assert len(h) == 32

    def test_order_matters(self):
        h1 = MerkleHashChain.hash_list(["a", "b"])
        h2 = MerkleHashChain.hash_list(["b", "a"])
        assert h1 != h2

    def test_custom_separator(self):
        h1 = MerkleHashChain.hash_list(["a", "b"], separator="|")
        h2 = MerkleHashChain.hash_list(["a", "b"], separator=",")
        assert h1 != h2

    def test_empty_list(self):
        h = MerkleHashChain.hash_list([])
        assert len(h) == 32


class TestHashSortedDict:
    def test_returns_32_char_hash(self):
        h = MerkleHashChain.hash_sorted_dict({"a": 1, "b": 2})
        assert len(h) == 32

    def test_key_order_independent(self):
        """Sorted-dict hash should be same regardless of insertion order."""
        h1 = MerkleHashChain.hash_sorted_dict({"a": 1, "b": 2})
        h2 = MerkleHashChain.hash_sorted_dict({"b": 2, "a": 1})
        assert h1 == h2

    def test_different_values_different_hash(self):
        h1 = MerkleHashChain.hash_sorted_dict({"a": 1})
        h2 = MerkleHashChain.hash_sorted_dict({"a": 2})
        assert h1 != h2


class TestMembershipProof:
    def test_valid_proof_verifies(self):
        leaf = MerkleHashChain.compute_hash(b"lexeme")
        sibling = MerkleHashChain.compute_hash(b"sibling")
        # Manual chain
        level1 = MerkleHashChain.compute_hash(f"{leaf}|{sibling}".encode())
        proof = MembershipProof(
            lexeme_hash=leaf,
            sibling_hashes=[(sibling, False)],
            root_hash=level1,
        )
        assert proof.verify()

    def test_invalid_root_fails(self):
        leaf = MerkleHashChain.compute_hash(b"lexeme")
        sibling = MerkleHashChain.compute_hash(b"sibling")
        proof = MembershipProof(
            lexeme_hash=leaf,
            sibling_hashes=[(sibling, False)],
            root_hash="wrong_hash_wrong_hash_wrong_has",
        )
        assert not proof.verify()

    def test_left_sibling_position(self):
        """Verify is_left=True positions sibling on left."""
        leaf = MerkleHashChain.compute_hash(b"lexeme")
        sibling = MerkleHashChain.compute_hash(b"sibling")
        # If sibling is on left, root = hash(sibling | leaf)
        level1 = MerkleHashChain.compute_hash(f"{sibling}|{leaf}".encode())
        proof = MembershipProof(
            lexeme_hash=leaf,
            sibling_hashes=[(sibling, True)],
            root_hash=level1,
        )
        assert proof.verify()

    def test_right_sibling_position(self):
        leaf = MerkleHashChain.compute_hash(b"lexeme")
        sibling = MerkleHashChain.compute_hash(b"sibling")
        # If sibling is on right, root = hash(leaf | sibling)
        level1 = MerkleHashChain.compute_hash(f"{leaf}|{sibling}".encode())
        proof = MembershipProof(
            lexeme_hash=leaf,
            sibling_hashes=[(sibling, False)],
            root_hash=level1,
        )
        assert proof.verify()

    def test_to_dict_serializes_fields(self):
        p = MembershipProof("a", [("b", True)], "c")
        d = p.to_dict()
        assert d["lexeme_hash"] == "a"
        assert d["sibling_hashes"] == [("b", True)]
        assert d["root_hash"] == "c"

    def test_from_dict_roundtrip(self):
        original = MembershipProof("a", [("b", False), ("c", True)], "root")
        d = original.to_dict()
        restored = MembershipProof.from_dict(d)
        assert restored.lexeme_hash == "a"
        assert restored.root_hash == "root"
        # Tuples may serialize as lists; from_dict converts back to tuples
        assert all(isinstance(s, tuple) for s in restored.sibling_hashes)


class TestDifferenceProof:
    def test_total_changes_sums_correctly(self):
        p = DifferenceProof(
            old_root_hash="old",
            new_root_hash="new",
            changed_paths=[],
            added_lexemes=["a", "b"],
            removed_lexemes=["c"],
            modified_lexemes=["d", "e", "f"],
        )
        assert p.total_changes == 6

    def test_empty_changes(self):
        p = DifferenceProof(
            old_root_hash="x",
            new_root_hash="x",
            changed_paths=[],
            added_lexemes=[],
            removed_lexemes=[],
            modified_lexemes=[],
        )
        assert p.total_changes == 0

    def test_to_dict_serializes_fields(self):
        p = DifferenceProof(
            old_root_hash="old",
            new_root_hash="new",
            changed_paths=[["root", "node"]],
            added_lexemes=["a"],
            removed_lexemes=["b"],
            modified_lexemes=["c"],
        )
        d = p.to_dict()
        assert d["old_root_hash"] == "old"
        assert d["new_root_hash"] == "new"
        assert d["added_lexemes"] == ["a"]
        assert d["removed_lexemes"] == ["b"]
        assert d["modified_lexemes"] == ["c"]
        assert d["changed_paths"] == [["root", "node"]]

    def test_from_dict_roundtrip(self):
        original = DifferenceProof(
            old_root_hash="o",
            new_root_hash="n",
            changed_paths=[["p1"]],
            added_lexemes=["a"],
            removed_lexemes=[],
            modified_lexemes=["m"],
        )
        d = original.to_dict()
        restored = DifferenceProof.from_dict(d)
        assert restored.old_root_hash == original.old_root_hash
        assert restored.added_lexemes == original.added_lexemes
        assert restored.modified_lexemes == original.modified_lexemes


class TestVerifyHashChain:
    def test_valid_chain(self):
        content = "node_content"
        children = ["c1", "c2", "c3"]
        content_hash = MerkleHashChain.compute_hash(content.encode())
        children_hash = MerkleHashChain.hash_list(children)
        combined = MerkleHashChain.combine_hashes(content_hash, children_hash)
        assert verify_hash_chain(combined, content, children)

    def test_wrong_node_hash_fails(self):
        assert not verify_hash_chain("wrong_hash", "content", ["c1"])

    def test_different_content_fails(self):
        content = "real_content"
        children = ["c1"]
        content_hash = MerkleHashChain.compute_hash(content.encode())
        children_hash = MerkleHashChain.hash_list(children)
        node_hash = MerkleHashChain.combine_hashes(content_hash, children_hash)
        assert not verify_hash_chain(node_hash, "wrong_content", children)


class TestComputeTreeRoot:
    def test_empty_returns_empty_hash(self):
        root = compute_tree_root_from_leaves([])
        expected = MerkleHashChain.compute_hash(b"empty")
        assert root == expected

    def test_single_leaf_is_root(self):
        leaf = MerkleHashChain.compute_hash(b"only")
        root = compute_tree_root_from_leaves([leaf])
        assert root == leaf

    def test_two_leaves_combined(self):
        l1 = MerkleHashChain.compute_hash(b"a")
        l2 = MerkleHashChain.compute_hash(b"b")
        root = compute_tree_root_from_leaves([l1, l2])
        expected = MerkleHashChain.compute_hash(f"{l1}|{l2}".encode())
        assert root == expected

    def test_deterministic(self):
        leaves = [MerkleHashChain.compute_hash(f"l{i}".encode()) for i in range(8)]
        r1 = compute_tree_root_from_leaves(leaves)
        r2 = compute_tree_root_from_leaves(leaves)
        assert r1 == r2

    def test_returns_32_char_hash(self):
        leaves = [MerkleHashChain.compute_hash(f"l{i}".encode()) for i in range(4)]
        root = compute_tree_root_from_leaves(leaves)
        assert len(root) == 32

    def test_odd_number_of_leaves_handled(self):
        # 3 leaves — last is duplicated for pairing
        leaves = [MerkleHashChain.compute_hash(f"l{i}".encode()) for i in range(3)]
        root = compute_tree_root_from_leaves(leaves)
        assert len(root) == 32

    def test_different_leaves_different_root(self):
        leaves1 = [MerkleHashChain.compute_hash(f"a{i}".encode()) for i in range(4)]
        leaves2 = [MerkleHashChain.compute_hash(f"b{i}".encode()) for i in range(4)]
        assert compute_tree_root_from_leaves(leaves1) != compute_tree_root_from_leaves(leaves2)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
