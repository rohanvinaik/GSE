#!/usr/bin/env python3
"""
Merkle Hash Chain Utilities for GSE Lexicon

Provides SHA-256 based hashing for Merkle tree nodes:
- Content hashing: Hash node's own data
- Children hashing: Hash child node references
- Combined hashing: Combine content + children hashes
- Membership proofs: Verify lexeme inclusion

Hash format: SHA-256 truncated to 32 hex chars (128 bits)
for storage efficiency while maintaining collision resistance.
"""

import hashlib
from typing import List, Tuple


class MerkleHashChain:
    """
    SHA-256 hash chain utilities for Merkle tree.

    All hashes are truncated to 128 bits (32 hex chars) for efficiency.
    This provides 2^64 collision resistance, sufficient for lexicon verification.
    """

    HASH_LENGTH = 32  # 128 bits = 32 hex chars

    @classmethod
    def compute_hash(cls, data: bytes) -> str:
        """
        Compute SHA-256 hash of data, truncated to 128 bits.

        Args:
            data: Raw bytes to hash

        Returns:
            32-character hex string (128 bits)
        """
        full_hash = hashlib.sha256(data).hexdigest()
        return full_hash[: cls.HASH_LENGTH]

    @classmethod
    def combine_hashes(cls, content_hash: str, children_hash: str) -> str:
        """
        Combine content and children hashes into a single combined hash.

        Formula: hash(content_hash || children_hash)

        Args:
            content_hash: Hash of node's own data
            children_hash: Hash of child node hashes

        Returns:
            Combined hash string
        """
        combined = f"{content_hash}|{children_hash}"
        return cls.compute_hash(combined.encode())

    @classmethod
    def hash_list(cls, items: List[str], separator: str = "|") -> str:
        """
        Hash a list of strings in deterministic order.

        Args:
            items: List of strings to hash
            separator: Separator between items

        Returns:
            Hash of concatenated items
        """
        combined = separator.join(items)
        return cls.compute_hash(combined.encode())

    @classmethod
    def hash_sorted_dict(cls, d: dict, separator: str = "|") -> str:
        """
        Hash a dictionary in key-sorted order.

        Args:
            d: Dictionary to hash
            separator: Separator between key:value pairs

        Returns:
            Hash of sorted key:value pairs
        """
        pairs = [f"{k}:{v}" for k, v in sorted(d.items())]
        combined = separator.join(pairs)
        return cls.compute_hash(combined.encode())


class MembershipProof:
    """
    Merkle membership proof for a lexeme.

    Proves that a lexeme exists in the tree without revealing
    sibling data, only sibling hashes.
    """

    def __init__(
        self,
        lexeme_hash: str,
        sibling_hashes: List[Tuple[str, bool]],  # (hash, is_left)
        root_hash: str,
    ):
        """
        Initialize membership proof.

        Args:
            lexeme_hash: Hash of the lexeme being proved
            sibling_hashes: List of (sibling_hash, is_left) tuples
                           from leaf to root. is_left indicates if
                           sibling is on the left side.
            root_hash: Expected root hash for verification
        """
        self.lexeme_hash = lexeme_hash
        self.sibling_hashes = sibling_hashes
        self.root_hash = root_hash

    def verify(self) -> bool:
        """
        Verify the membership proof.

        Returns:
            True if proof is valid, False otherwise
        """
        current_hash = self.lexeme_hash

        for sibling_hash, is_left in self.sibling_hashes:
            if is_left:
                # Sibling is on left, so current is on right
                combined = f"{sibling_hash}|{current_hash}"
            else:
                # Sibling is on right, so current is on left
                combined = f"{current_hash}|{sibling_hash}"

            current_hash = MerkleHashChain.compute_hash(combined.encode())

        return current_hash == self.root_hash

    def to_dict(self) -> dict:
        """Serialize proof to dictionary."""
        return {
            "lexeme_hash": self.lexeme_hash,
            "sibling_hashes": self.sibling_hashes,
            "root_hash": self.root_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MembershipProof":
        """Deserialize proof from dictionary."""
        return cls(
            lexeme_hash=data["lexeme_hash"],
            sibling_hashes=[tuple(s) for s in data["sibling_hashes"]],
            root_hash=data["root_hash"],
        )


class DifferenceProof:
    """
    Proof of differences between two Merkle trees.

    Used to efficiently sync lexicons by identifying only
    the changed subtrees.
    """

    def __init__(
        self,
        old_root_hash: str,
        new_root_hash: str,
        changed_paths: List[List[str]],  # Paths from root to changed nodes
        added_lexemes: List[str],
        removed_lexemes: List[str],
        modified_lexemes: List[str],
    ):
        """
        Initialize difference proof.

        Args:
            old_root_hash: Root hash of old tree
            new_root_hash: Root hash of new tree
            changed_paths: Paths from root to changed subtrees
            added_lexemes: Keys of newly added lexemes
            removed_lexemes: Keys of removed lexemes
            modified_lexemes: Keys of modified lexemes
        """
        self.old_root_hash = old_root_hash
        self.new_root_hash = new_root_hash
        self.changed_paths = changed_paths
        self.added_lexemes = added_lexemes
        self.removed_lexemes = removed_lexemes
        self.modified_lexemes = modified_lexemes

    @property
    def total_changes(self) -> int:
        """Total number of lexeme changes."""
        return len(self.added_lexemes) + len(self.removed_lexemes) + len(self.modified_lexemes)

    def to_dict(self) -> dict:
        """Serialize proof to dictionary."""
        return {
            "old_root_hash": self.old_root_hash,
            "new_root_hash": self.new_root_hash,
            "changed_paths": self.changed_paths,
            "added_lexemes": self.added_lexemes,
            "removed_lexemes": self.removed_lexemes,
            "modified_lexemes": self.modified_lexemes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DifferenceProof":
        """Deserialize proof from dictionary."""
        return cls(
            old_root_hash=data["old_root_hash"],
            new_root_hash=data["new_root_hash"],
            changed_paths=data["changed_paths"],
            added_lexemes=data["added_lexemes"],
            removed_lexemes=data["removed_lexemes"],
            modified_lexemes=data["modified_lexemes"],
        )


# =============================================================================
# VERIFICATION UTILITIES
# =============================================================================


def verify_hash_chain(
    node_hash: str,
    content: str,
    children_hashes: List[str],
) -> bool:
    """
    Verify a node's hash chain is consistent.

    Args:
        node_hash: The node's combined hash
        content: String content for content hash
        children_hashes: List of child hashes

    Returns:
        True if hash chain is valid
    """
    content_hash = MerkleHashChain.compute_hash(content.encode())
    children_hash = MerkleHashChain.hash_list(children_hashes)
    expected = MerkleHashChain.combine_hashes(content_hash, children_hash)
    return expected == node_hash


def compute_tree_root_from_leaves(leaf_hashes: List[str]) -> str:
    """
    Compute root hash from leaf hashes using binary Merkle tree.

    Note: This is for testing/verification. The actual GSE tree
    uses a 5-level structure, not a binary tree.

    Args:
        leaf_hashes: List of leaf node hashes

    Returns:
        Root hash
    """
    if not leaf_hashes:
        return MerkleHashChain.compute_hash(b"empty")

    if len(leaf_hashes) == 1:
        return leaf_hashes[0]

    # Build tree bottom-up
    current_level = leaf_hashes

    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            # Handle odd number of nodes by duplicating last
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            combined = f"{left}|{right}"
            parent_hash = MerkleHashChain.compute_hash(combined.encode())
            next_level.append(parent_hash)
        current_level = next_level

    return current_level[0]


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    # Quick verification tests
    print("MerkleHashChain verification tests")
    print("=" * 50)

    # Test basic hashing
    h1 = MerkleHashChain.compute_hash(b"hello")
    h2 = MerkleHashChain.compute_hash(b"hello")
    h3 = MerkleHashChain.compute_hash(b"world")

    assert h1 == h2, "Same input should give same hash"
    assert h1 != h3, "Different input should give different hash"
    assert len(h1) == 32, f"Hash should be 32 chars, got {len(h1)}"
    print(f"✓ Basic hashing: {h1}")

    # Test hash combination
    combined = MerkleHashChain.combine_hashes(h1, h3)
    assert len(combined) == 32, "Combined hash should be 32 chars"
    assert combined != h1 and combined != h3, "Combined should differ from inputs"
    print(f"✓ Hash combination: {combined}")

    # Test membership proof
    leaf = MerkleHashChain.compute_hash(b"lexeme_data")
    sibling1 = MerkleHashChain.compute_hash(b"sibling1")
    sibling2 = MerkleHashChain.compute_hash(b"sibling2")

    # Build path to root manually
    level1 = MerkleHashChain.compute_hash(f"{leaf}|{sibling1}".encode())
    root = MerkleHashChain.compute_hash(f"{level1}|{sibling2}".encode())

    proof = MembershipProof(
        lexeme_hash=leaf,
        sibling_hashes=[(sibling1, False), (sibling2, False)],
        root_hash=root,
    )

    assert proof.verify(), "Valid proof should verify"
    print("✓ Membership proof verification")

    # Test invalid proof
    invalid_proof = MembershipProof(
        lexeme_hash=leaf,
        sibling_hashes=[(sibling1, False), (sibling2, False)],
        root_hash="wrong_hash_wrong_hash_wrong_has",
    )
    assert not invalid_proof.verify(), "Invalid proof should not verify"
    print("✓ Invalid proof rejection")

    # Test tree root computation
    leaves = [MerkleHashChain.compute_hash(f"leaf{i}".encode()) for i in range(8)]
    root = compute_tree_root_from_leaves(leaves)
    assert len(root) == 32, "Root should be 32 chars"
    print(f"✓ Tree root computation: {root}")

    # Verify determinism
    root2 = compute_tree_root_from_leaves(leaves)
    assert root == root2, "Same leaves should give same root"
    print("✓ Deterministic root computation")

    print("\n" + "=" * 50)
    print("All hash chain tests passed!")
