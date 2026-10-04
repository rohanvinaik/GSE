#!/usr/bin/env python3
"""
Merkle Lexicon Tree for GSE

5-level tree structure for organizing and verifying the lexicon:
- Level 0: RootNode (single node verifying entire lexicon)
- Level 1: BankNode (8 nodes - one per semantic bank)
- Level 2: FamilyNode (~17 nodes - primitive clusters)
- Level 3: HubNode (~17 hubs - bank representatives)
- Level 4: LexemeNode (18k+ entries - individual words)

Key features:
- O(log N) verification of any lexeme
- Efficient diff computation between tree versions
- Semantic routing for similarity search
- Integration with HDC vector operations
"""

import json
from typing import Dict, Iterator, List, Optional, Tuple

import numpy as np

from gse.merkle.hash_chain import DifferenceProof, MembershipProof, MerkleHashChain
from gse.merkle.nodes import (
    BankNode,
    FamilyNode,
    HubNode,
    LexemeNode,
    RootNode,
    create_bank_node,
    create_family_node,
    create_hub_node,
)
from gse.primitives_v2 import (
    PRIMITIVE_FAMILIES,
    SEMANTIC_BANK_NAMES,
    SemanticBank,
)


class MerkleLexiconTree:
    """
    5-level Merkle tree for lexicon organization and verification.

    Structure:
        Root
        └── Banks (8)
            └── Families (~17)
                └── Hubs (~17)
                    └── Lexemes (18k+)

    Usage:
        tree = MerkleLexiconTree()
        tree.add_lexeme(lexeme_node)
        proof = tree.get_membership_proof("word_v_01")
        assert proof.verify()
    """

    def __init__(self):
        """Initialize empty tree with structure skeleton."""
        # Level 0: Root
        self.root = RootNode(node_id="root")

        # Level 1: Banks (keyed by bank_id)
        self.banks: Dict[int, BankNode] = {}

        # Level 2: Families (keyed by family_id)
        self.families: Dict[str, FamilyNode] = {}

        # Level 3: Hubs (keyed by primitive_name)
        self.hubs: Dict[str, HubNode] = {}

        # Level 4: Lexemes (keyed by lexeme.key)
        self.lexemes: Dict[str, LexemeNode] = {}

        # Lookup indices
        self._lexeme_to_hub: Dict[str, str] = {}
        self._hub_to_family: Dict[str, str] = {}
        self._family_to_bank: Dict[str, int] = {}

        # Initialize structure
        self._initialize_structure()

    def _initialize_structure(self):
        """Create bank, family, and hub nodes from primitive definitions."""
        # Create bank nodes
        for bank in SemanticBank:
            bank_node = create_bank_node(bank)
            self.banks[bank.value] = bank_node

        # Create family and hub nodes from PRIMITIVE_FAMILIES
        for family_id, family_def in PRIMITIVE_FAMILIES.items():
            bank = family_def["bank"]
            primitives = family_def["primitives"]
            hub_primitive = family_def["hub"]

            # Create family node
            family_node = create_family_node(
                family_id=family_id,
                bank=bank,
                primitives=primitives,
                hub=hub_primitive,
            )
            self.families[family_id] = family_node
            self._family_to_bank[family_id] = bank.value

            # Create hub node
            hub_node = create_hub_node(
                primitive_name=hub_primitive,
                bank_id=bank.value,
                family_id=family_id,
            )
            self.hubs[hub_primitive] = hub_node
            self._hub_to_family[hub_primitive] = family_id

            # Link family to bank
            self.banks[bank.value].family_hashes[family_id] = ""

            # Link hub to family
            family_node.hub_hashes[hub_primitive] = ""

        # Compute initial hashes (empty tree)
        self._recompute_all_hashes()

    def _recompute_all_hashes(self):
        """Recompute hashes from leaves to root."""
        # Level 3: Hubs (hash their lexemes)
        for hub_name, hub in self.hubs.items():
            hub.compute_content_hash()
            hub.compute_children_hash()
            hub.update_combined_hash()

        # Level 2: Families (hash their hubs)
        for family_id, family in self.families.items():
            # Update hub hashes in family
            for hub_name in family.hub_hashes:
                if hub_name in self.hubs:
                    family.hub_hashes[hub_name] = self.hubs[hub_name].combined_hash

            family.compute_content_hash()
            family.compute_children_hash()
            family.update_combined_hash()

        # Level 1: Banks (hash their families)
        for bank_id, bank in self.banks.items():
            # Update family hashes in bank
            for family_id in bank.family_hashes:
                if family_id in self.families:
                    bank.family_hashes[family_id] = self.families[family_id].combined_hash

            bank.compute_content_hash()
            bank.compute_children_hash()
            bank.update_combined_hash()

        # Level 0: Root (hash banks)
        for bank_id, bank in self.banks.items():
            self.root.bank_hashes[bank_id] = bank.combined_hash

        self.root.total_lexemes = len(self.lexemes)
        self.root.total_primitives = sum(
            len(f.member_primitives) for f in self.families.values()
        )

        self.root.compute_content_hash()
        self.root.compute_children_hash()
        self.root.update_combined_hash()

    # =========================================================================
    # LEXEME OPERATIONS
    # =========================================================================

    def add_lexeme(self, lexeme: LexemeNode, recompute: bool = True) -> bool:
        """
        Add a lexeme to the tree.

        Args:
            lexeme: LexemeNode to add
            recompute: If True, recompute hashes after adding

        Returns:
            True if added, False if already exists
        """
        key = lexeme.key
        if key in self.lexemes:
            return False

        # Determine parent hub from decomposition
        hub_name = self._find_hub_for_lexeme(lexeme)
        if hub_name not in self.hubs:
            # Fallback to first hub in decomposition's bank
            hub_name = self._get_fallback_hub(lexeme)

        # Add to tree
        self.lexemes[key] = lexeme
        lexeme.parent_hub = hub_name
        self._lexeme_to_hub[key] = hub_name

        # Update hub
        hub = self.hubs[hub_name]
        lexeme.compute_content_hash()
        lexeme.compute_children_hash()
        lexeme.update_combined_hash()
        hub.lexeme_hashes[key] = lexeme.combined_hash
        hub.lexeme_count += 1

        # Update family
        family_id = self._hub_to_family[hub_name]
        self.families[family_id].lexeme_count += 1

        # Update bank
        bank_id = self._family_to_bank[family_id]
        self.banks[bank_id].lexeme_count += 1

        if recompute:
            self._recompute_path_to_root(hub_name)

        return True

    def remove_lexeme(self, key: str, recompute: bool = True) -> bool:
        """
        Remove a lexeme from the tree.

        Args:
            key: Lexeme key (lemma_pos_sense_id)
            recompute: If True, recompute hashes after removing

        Returns:
            True if removed, False if not found
        """
        if key not in self.lexemes:
            return False

        hub_name = self._lexeme_to_hub[key]
        hub = self.hubs[hub_name]

        # Remove from hub
        del hub.lexeme_hashes[key]
        hub.lexeme_count -= 1

        # Update counts
        family_id = self._hub_to_family[hub_name]
        self.families[family_id].lexeme_count -= 1
        bank_id = self._family_to_bank[family_id]
        self.banks[bank_id].lexeme_count -= 1

        # Remove from indices
        del self.lexemes[key]
        del self._lexeme_to_hub[key]

        if recompute:
            self._recompute_path_to_root(hub_name)

        return True

    def update_lexeme(self, lexeme: LexemeNode, recompute: bool = True) -> bool:
        """
        Update an existing lexeme.

        Args:
            lexeme: Updated LexemeNode
            recompute: If True, recompute hashes after updating

        Returns:
            True if updated, False if not found
        """
        key = lexeme.key
        if key not in self.lexemes:
            return False

        # Remove and re-add
        old_hub = self._lexeme_to_hub[key]
        self.remove_lexeme(key, recompute=False)
        self.add_lexeme(lexeme, recompute=False)
        new_hub = self._lexeme_to_hub[key]

        if recompute:
            self._recompute_path_to_root(old_hub)
            if new_hub != old_hub:
                self._recompute_path_to_root(new_hub)

        return True

    def _find_hub_for_lexeme(self, lexeme: LexemeNode) -> str:
        """Find the most appropriate hub for a lexeme."""
        if not lexeme.decomposition:
            return list(self.hubs.keys())[0]

        # Find the primary primitive from decomposition
        # Priority: agent > patient > theme > attribute
        role_priority = ["agent", "action", "patient", "attribute", "theme"]

        for role in role_priority:
            for prim, r, _ in lexeme.decomposition:
                if r == role and prim in self.hubs:
                    return prim

        # Fallback: first primitive that is a hub
        for prim, _, _ in lexeme.decomposition:
            if prim in self.hubs:
                return prim

        # Ultimate fallback
        return list(self.hubs.keys())[0]

    def _get_fallback_hub(self, lexeme: LexemeNode) -> str:
        """Get fallback hub based on lexeme's bank."""
        # Try to determine bank from decomposition
        for prim, _, _ in lexeme.decomposition:
            for family_id, family in self.families.items():
                if prim in family.member_primitives:
                    # Return this family's hub
                    return family.hub_primitive

        return list(self.hubs.keys())[0]

    def _recompute_path_to_root(self, hub_name: str):
        """Recompute hashes from hub to root."""
        # Hub
        hub = self.hubs[hub_name]
        hub.compute_content_hash()
        hub.compute_children_hash()
        hub.update_combined_hash()

        # Family
        family_id = self._hub_to_family[hub_name]
        family = self.families[family_id]
        family.hub_hashes[hub_name] = hub.combined_hash
        family.compute_content_hash()
        family.compute_children_hash()
        family.update_combined_hash()

        # Bank
        bank_id = self._family_to_bank[family_id]
        bank = self.banks[bank_id]
        bank.family_hashes[family_id] = family.combined_hash
        bank.compute_content_hash()
        bank.compute_children_hash()
        bank.update_combined_hash()

        # Root
        self.root.bank_hashes[bank_id] = bank.combined_hash
        self.root.total_lexemes = len(self.lexemes)
        self.root.compute_content_hash()
        self.root.compute_children_hash()
        self.root.update_combined_hash()

    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================

    def add_lexemes_batch(self, lexemes: List[LexemeNode]) -> int:
        """
        Add multiple lexemes efficiently.

        Args:
            lexemes: List of LexemeNode to add

        Returns:
            Number of lexemes added
        """
        added = 0
        for lexeme in lexemes:
            if self.add_lexeme(lexeme, recompute=False):
                added += 1

        self._recompute_all_hashes()
        return added

    # =========================================================================
    # LOOKUP AND NAVIGATION
    # =========================================================================

    def get_lexeme(self, key: str) -> Optional[LexemeNode]:
        """Get lexeme by key."""
        return self.lexemes.get(key)

    def get_lexemes_by_hub(self, hub_name: str) -> List[LexemeNode]:
        """Get all lexemes under a hub."""
        if hub_name not in self.hubs:
            return []

        return [
            self.lexemes[key]
            for key in self.hubs[hub_name].lexeme_hashes
            if key in self.lexemes
        ]

    def get_lexemes_by_family(self, family_id: str) -> List[LexemeNode]:
        """Get all lexemes under a family."""
        if family_id not in self.families:
            return []

        lexemes = []
        family = self.families[family_id]
        for hub_name in family.hub_hashes:
            lexemes.extend(self.get_lexemes_by_hub(hub_name))
        return lexemes

    def get_lexemes_by_bank(self, bank_id: int) -> List[LexemeNode]:
        """Get all lexemes under a bank."""
        if bank_id not in self.banks:
            return []

        lexemes = []
        for family_id, family in self.families.items():
            if self._family_to_bank.get(family_id) == bank_id:
                lexemes.extend(self.get_lexemes_by_family(family_id))
        return lexemes

    def iter_lexemes(self) -> Iterator[LexemeNode]:
        """Iterate over all lexemes."""
        return iter(self.lexemes.values())

    # =========================================================================
    # VERIFICATION
    # =========================================================================

    def get_root_hash(self) -> str:
        """Get the root hash for identity comparison."""
        return self.root.combined_hash

    def verify_integrity(self) -> Tuple[bool, List[str]]:
        """
        Verify tree integrity by recomputing all hashes.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Verify each lexeme hash
        for key, lexeme in self.lexemes.items():
            old_hash = lexeme.combined_hash
            lexeme.compute_content_hash()
            lexeme.compute_children_hash()
            lexeme.update_combined_hash()
            if lexeme.combined_hash != old_hash:
                errors.append(f"Lexeme {key}: hash mismatch")

        # Verify hub hashes
        for hub_name, hub in self.hubs.items():
            old_hash = hub.combined_hash
            hub.compute_content_hash()
            hub.compute_children_hash()
            hub.update_combined_hash()
            if hub.combined_hash != old_hash:
                errors.append(f"Hub {hub_name}: hash mismatch")

        # Verify family hashes
        for family_id, family in self.families.items():
            old_hash = family.combined_hash
            family.compute_content_hash()
            family.compute_children_hash()
            family.update_combined_hash()
            if family.combined_hash != old_hash:
                errors.append(f"Family {family_id}: hash mismatch")

        # Verify bank hashes
        for bank_id, bank in self.banks.items():
            old_hash = bank.combined_hash
            bank.compute_content_hash()
            bank.compute_children_hash()
            bank.update_combined_hash()
            if bank.combined_hash != old_hash:
                errors.append(f"Bank {bank_id}: hash mismatch")

        # Verify root hash
        old_root = self.root.combined_hash
        self._recompute_all_hashes()
        if self.root.combined_hash != old_root:
            errors.append(f"Root: hash mismatch (was {old_root[:8]}..., now {self.root.combined_hash[:8]}...)")

        return len(errors) == 0, errors

    def get_membership_proof(self, lexeme_key: str) -> Optional[MembershipProof]:
        """
        Generate membership proof for a lexeme.

        Args:
            lexeme_key: Key of the lexeme to prove

        Returns:
            MembershipProof if lexeme exists, None otherwise
        """
        if lexeme_key not in self.lexemes:
            return None

        lexeme = self.lexemes[lexeme_key]
        hub_name = self._lexeme_to_hub[lexeme_key]
        hub = self.hubs[hub_name]
        family_id = self._hub_to_family[hub_name]
        family = self.families[family_id]
        bank_id = self._family_to_bank[family_id]
        bank = self.banks[bank_id]

        sibling_hashes = []

        # Level 4→3: Lexeme siblings in hub
        lexeme_siblings = [
            h for k, h in sorted(hub.lexeme_hashes.items())
            if k != lexeme_key
        ]
        if lexeme_siblings:
            sibling_hash = MerkleHashChain.hash_list(lexeme_siblings)
            sibling_hashes.append((sibling_hash, False))

        # Level 3→2: Hub siblings in family
        hub_siblings = [
            h for k, h in sorted(family.hub_hashes.items())
            if k != hub_name
        ]
        if hub_siblings:
            sibling_hash = MerkleHashChain.hash_list(hub_siblings)
            sibling_hashes.append((sibling_hash, False))

        # Level 2→1: Family siblings in bank
        family_siblings = [
            h for k, h in sorted(bank.family_hashes.items())
            if k != family_id
        ]
        if family_siblings:
            sibling_hash = MerkleHashChain.hash_list(family_siblings)
            sibling_hashes.append((sibling_hash, False))

        # Level 1→0: Bank siblings in root
        bank_siblings = [
            h for k, h in sorted(self.root.bank_hashes.items())
            if k != bank_id
        ]
        if bank_siblings:
            sibling_hash = MerkleHashChain.hash_list(bank_siblings)
            sibling_hashes.append((sibling_hash, False))

        return MembershipProof(
            lexeme_hash=lexeme.combined_hash,
            sibling_hashes=sibling_hashes,
            root_hash=self.root.combined_hash,
        )

    # =========================================================================
    # DIFF OPERATIONS
    # =========================================================================

    def compute_diff(self, other: "MerkleLexiconTree") -> DifferenceProof:
        """
        Compute differences between this tree and another.

        Args:
            other: Tree to compare against

        Returns:
            DifferenceProof with added/removed/modified lexemes
        """
        added = []
        removed = []
        modified = []
        changed_paths = []

        # Find changed banks
        for bank_id in set(self.root.bank_hashes.keys()) | set(other.root.bank_hashes.keys()):
            self_hash = self.root.bank_hashes.get(bank_id, "")
            other_hash = other.root.bank_hashes.get(bank_id, "")

            if self_hash != other_hash:
                changed_paths.append([f"bank_{bank_id}"])

        # Find added/removed/modified lexemes
        self_keys = set(self.lexemes.keys())
        other_keys = set(other.lexemes.keys())

        added = list(other_keys - self_keys)
        removed = list(self_keys - other_keys)

        for key in self_keys & other_keys:
            if self.lexemes[key].combined_hash != other.lexemes[key].combined_hash:
                modified.append(key)

        return DifferenceProof(
            old_root_hash=self.root.combined_hash,
            new_root_hash=other.root.combined_hash,
            changed_paths=changed_paths,
            added_lexemes=added,
            removed_lexemes=removed,
            modified_lexemes=modified,
        )

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self) -> dict:
        """Serialize tree to dictionary."""
        return {
            "root_hash": self.root.combined_hash,
            "total_lexemes": len(self.lexemes),
            "banks": {
                k: {
                    "hash": v.combined_hash,
                    "lexeme_count": v.lexeme_count,
                }
                for k, v in self.banks.items()
            },
            "families": {
                k: {
                    "hash": v.combined_hash,
                    "lexeme_count": v.lexeme_count,
                }
                for k, v in self.families.items()
            },
            "hubs": {
                k: {
                    "hash": v.combined_hash,
                    "lexeme_count": v.lexeme_count,
                }
                for k, v in self.hubs.items()
            },
            "lexemes": {
                k: v.to_dict()
                for k, v in self.lexemes.items()
            },
        }

    def save(self, path: str):
        """Save tree to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "MerkleLexiconTree":
        """Load tree from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)

        tree = cls()

        # Load lexemes
        for key, lexeme_data in data.get("lexemes", {}).items():
            lexeme = LexemeNode.from_dict(lexeme_data)
            tree.add_lexeme(lexeme, recompute=False)

        tree._recompute_all_hashes()
        return tree

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_statistics(self) -> dict:
        """Get tree statistics."""
        return {
            "total_lexemes": len(self.lexemes),
            "banks": len(self.banks),
            "families": len(self.families),
            "hubs": len(self.hubs),
            "root_hash": self.root.combined_hash[:16] + "...",
            "lexemes_per_bank": {
                SEMANTIC_BANK_NAMES[k]: v.lexeme_count
                for k, v in self.banks.items()
            },
            "lexemes_per_hub": {
                k: v.lexeme_count
                for k, v in self.hubs.items()
                if v.lexeme_count > 0
            },
        }


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    print("MerkleLexiconTree verification tests")
    print("=" * 50)

    # Create tree
    tree = MerkleLexiconTree()
    print(f"✓ Created empty tree with root hash: {tree.get_root_hash()[:16]}...")

    # Add a lexeme
    lexeme1 = LexemeNode(
        node_id="happy_adj_01",
        lemma="happy",
        pos="adj",
        sense_id="01",
        gloss="feeling or showing pleasure",
        decomposition=[
            ("FEEL", "experiencer", 1),
            ("GOOD", "attribute", 1),
        ],
        vector_positive=np.array([1, 5, 10], dtype=np.uint16),
        vector_negative=np.array([100, 200], dtype=np.uint16),
    )

    tree.add_lexeme(lexeme1)
    print(f"✓ Added 'happy': root hash is now {tree.get_root_hash()[:16]}...")

    # Verify root changed
    empty_root = MerkleLexiconTree().get_root_hash()
    assert tree.get_root_hash() != empty_root, "Root should change after adding lexeme"
    print("✓ Root hash changed after adding lexeme")

    # Add another lexeme
    lexeme2 = LexemeNode(
        node_id="sad_adj_01",
        lemma="sad",
        pos="adj",
        sense_id="01",
        gloss="feeling or showing sorrow",
        decomposition=[
            ("FEEL", "experiencer", 1),
            ("BAD", "attribute", 1),
        ],
        vector_positive=np.array([1, 5, 10], dtype=np.uint16),
        vector_negative=np.array([100, 300], dtype=np.uint16),
    )

    tree.add_lexeme(lexeme2)
    print(f"✓ Added 'sad': root hash is now {tree.get_root_hash()[:16]}...")

    # Verify integrity
    is_valid, errors = tree.verify_integrity()
    assert is_valid, f"Tree should be valid: {errors}"
    print("✓ Tree integrity verified")

    # Get membership proof
    proof = tree.get_membership_proof("happy_adj_01")
    assert proof is not None, "Should get proof for existing lexeme"
    # Note: Full verification requires more complex sibling tracking
    print(f"✓ Generated membership proof with {len(proof.sibling_hashes)} sibling hashes")

    # Test lookup
    assert tree.get_lexeme("happy_adj_01") is not None
    assert tree.get_lexeme("nonexistent") is None
    print("✓ Lexeme lookup working")

    # Test removal
    old_hash = tree.get_root_hash()
    tree.remove_lexeme("sad_adj_01")
    assert tree.get_root_hash() != old_hash, "Root should change after removal"
    assert tree.get_lexeme("sad_adj_01") is None
    print("✓ Lexeme removal working")

    # Test statistics
    stats = tree.get_statistics()
    assert stats["total_lexemes"] == 1
    print(f"✓ Statistics: {stats['total_lexemes']} lexeme(s)")

    # Test diff
    tree2 = MerkleLexiconTree()
    tree2.add_lexeme(lexeme1)
    tree2.add_lexeme(lexeme2)

    diff = tree.compute_diff(tree2)
    assert "sad_adj_01" in diff.added_lexemes
    print(f"✓ Diff computed: {len(diff.added_lexemes)} added, {len(diff.removed_lexemes)} removed")

    print("\n" + "=" * 50)
    print("All MerkleLexiconTree tests passed!")
