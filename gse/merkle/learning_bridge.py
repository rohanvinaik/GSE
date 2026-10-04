#!/usr/bin/env python3
"""
Merkle ↔ Learning Network Bridge for GSE

Maps the Merkle tree structure to learning networks:
- Level 1 (Banks) → OrchestratorNetwork routing
- Level 2 (Families) → Cross-family affinity matrix
- Level 3 (Hubs) → WordScaleNetwork nodes
- Level 4 (Lexemes) → K-Line patterns

This bridge enables:
1. Training networks from lexicon structure
2. Using network activations to guide tree navigation
3. Bi-directional updates between tree and networks
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from gse.merkle.nodes import LexemeNode
from gse.merkle.router import MerkleBellmanFord
from gse.merkle.tree import MerkleLexiconTree
from gse.patterns.networks_v2 import (
    ScaleNetworkCollection,
)
from gse.patterns.orchestrator import OrchestratorNetwork, OrchestratorNode
from gse.primitives_v2 import PRIMITIVE_FAMILIES

# =============================================================================
# FAMILY AFFINITY MATRIX
# =============================================================================


class FamilyAffinityMatrix:
    """
    Cross-family affinity matrix learned from lexicon.

    Tracks how often primitives from different families
    co-occur in word decompositions.
    """

    def __init__(self, family_ids: List[str]):
        """
        Initialize affinity matrix.

        Args:
            family_ids: List of family identifiers
        """
        self.family_ids = family_ids
        self.n_families = len(family_ids)
        self._family_to_idx = {fid: i for i, fid in enumerate(family_ids)}

        # Affinity matrix: how often families co-occur
        self.affinity = np.zeros((self.n_families, self.n_families), dtype=np.float32)

        # Transition counts for normalization
        self.counts = np.zeros((self.n_families, self.n_families), dtype=np.int32)

    def get_index(self, family_id: str) -> int:
        """Get index for family ID."""
        return self._family_to_idx.get(family_id, -1)

    def update_from_decomposition(
        self,
        primitives: List[str],
        family_lookup: Dict[str, str],
    ):
        """
        Update affinity from a word's decomposition.

        Args:
            primitives: List of primitives in decomposition
            family_lookup: Mapping from primitive to family ID
        """
        # Get families for each primitive
        families = []
        for prim in primitives:
            fam = family_lookup.get(prim)
            if fam and fam in self._family_to_idx:
                families.append(fam)

        # Update pairwise affinities
        for i, fam1 in enumerate(families):
            idx1 = self.get_index(fam1)
            for j, fam2 in enumerate(families):
                if i != j:
                    idx2 = self.get_index(fam2)
                    self.counts[idx1, idx2] += 1

        # Normalize to get affinities
        row_sums = self.counts.sum(axis=1, keepdims=True)
        row_sums = np.maximum(row_sums, 1)  # Avoid division by zero
        self.affinity = self.counts / row_sums

    def get_affinity(self, family1: str, family2: str) -> float:
        """Get affinity between two families."""
        idx1 = self.get_index(family1)
        idx2 = self.get_index(family2)
        if idx1 >= 0 and idx2 >= 0:
            return float(self.affinity[idx1, idx2])
        return 0.0

    def get_top_affinities(self, family_id: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Get families with highest affinity to given family."""
        idx = self.get_index(family_id)
        if idx < 0:
            return []

        affinities = self.affinity[idx]
        top_indices = np.argsort(affinities)[::-1][:top_k]

        return [(self.family_ids[i], float(affinities[i])) for i in top_indices if i != idx]


# =============================================================================
# K-LINE PATTERNS
# =============================================================================


@dataclass
class KLinePattern:
    """
    A K-line pattern extracted from similar lexemes.

    Captures recurring primitive combinations with roles.
    """

    pattern_id: str
    primitives: List[str]
    roles: List[str]
    polarities: List[int]
    frequency: int = 1
    exemplars: List[str] = field(default_factory=list)

    @property
    def signature(self) -> str:
        """Canonical signature for this pattern."""
        parts = sorted(zip(self.primitives, self.roles, self.polarities))
        return "|".join(f"{p}:{r}:{pol}" for p, r, pol in parts)


class KLineStore:
    """
    Store of K-line patterns extracted from lexicon.

    Patterns are indexed by:
    - Primary primitive
    - Role configuration
    - Polarity pattern
    """

    def __init__(self):
        """Initialize empty K-line store."""
        # Pattern signature → KLinePattern
        self.patterns: Dict[str, KLinePattern] = {}

        # Primary primitive → list of pattern signatures
        self.by_primitive: Dict[str, List[str]] = {}

        # Role → list of pattern signatures
        self.by_role: Dict[str, List[str]] = {}

    def add_pattern(self, pattern: KLinePattern):
        """Add or update a pattern."""
        sig = pattern.signature

        if sig in self.patterns:
            # Update frequency
            self.patterns[sig].frequency += 1
            self.patterns[sig].exemplars.extend(pattern.exemplars)
        else:
            # New pattern
            self.patterns[sig] = pattern

            # Index by primitive
            for prim in pattern.primitives:
                if prim not in self.by_primitive:
                    self.by_primitive[prim] = []
                self.by_primitive[prim].append(sig)

            # Index by role
            for role in pattern.roles:
                if role not in self.by_role:
                    self.by_role[role] = []
                self.by_role[role].append(sig)

    def extract_from_lexeme(self, lexeme: LexemeNode) -> Optional[KLinePattern]:
        """Extract K-line pattern from a lexeme."""
        if not lexeme.decomposition:
            return None

        primitives = [p for p, r, pol in lexeme.decomposition]
        roles = [r for p, r, pol in lexeme.decomposition]
        polarities = [pol for p, r, pol in lexeme.decomposition]

        return KLinePattern(
            pattern_id=lexeme.key,
            primitives=primitives,
            roles=roles,
            polarities=polarities,
            exemplars=[lexeme.lemma],
        )

    def find_similar_patterns(
        self,
        primitives: List[str],
        top_k: int = 5,
    ) -> List[Tuple[KLinePattern, float]]:
        """
        Find patterns similar to given primitives.

        Args:
            primitives: Query primitives
            top_k: Number of patterns to return

        Returns:
            List of (pattern, similarity) tuples
        """
        query_set = set(primitives)

        scored = []
        for sig, pattern in self.patterns.items():
            pattern_set = set(pattern.primitives)
            intersection = len(query_set & pattern_set)
            union = len(query_set | pattern_set)
            if union > 0:
                jaccard = intersection / union
                scored.append((pattern, jaccard))

        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    def get_patterns_for_primitive(self, primitive: str) -> List[KLinePattern]:
        """Get all patterns containing a primitive."""
        sigs = self.by_primitive.get(primitive, [])
        return [self.patterns[sig] for sig in sigs if sig in self.patterns]


# =============================================================================
# LEARNING BRIDGE
# =============================================================================


class MerkleLearningBridge:
    """
    Bridge between Merkle tree and learning networks.

    Provides:
    1. Training networks from tree structure
    2. Network-guided tree navigation
    3. Bi-directional pattern propagation
    """

    def __init__(
        self,
        tree: MerkleLexiconTree,
        networks: ScaleNetworkCollection = None,
        orchestrator: OrchestratorNetwork = None,
    ):
        """
        Initialize bridge.

        Args:
            tree: Merkle lexicon tree
            networks: Scale-specific networks (created if None)
            orchestrator: Orchestrator network (created if None)
        """
        self.tree = tree
        self.networks = networks or ScaleNetworkCollection()
        self.orchestrator = orchestrator or OrchestratorNetwork(self.networks)

        # Build lookup tables
        self._primitive_to_family = self._build_primitive_family_map()

        # Family affinity matrix
        family_ids = list(PRIMITIVE_FAMILIES.keys())
        self.family_affinity = FamilyAffinityMatrix(family_ids)

        # K-line store
        self.klines = KLineStore()

        # Router for tree navigation
        from gse.vectors_v2 import create_basis

        self.basis = create_basis()
        self.router = MerkleBellmanFord(tree, self.basis)

    def _build_primitive_family_map(self) -> Dict[str, str]:
        """Build mapping from primitives to families."""
        mapping = {}
        for family_id, family_def in PRIMITIVE_FAMILIES.items():
            for prim in family_def["primitives"]:
                mapping[prim] = family_id
        return mapping

    def train_from_tree(self):
        """
        Train all networks from the Merkle tree.

        Extracts patterns at each level and updates corresponding networks.
        """
        # Train word-scale network from lexeme decompositions
        self._train_word_network()

        # Build family affinity from co-occurrences
        self._build_family_affinity()

        # Extract K-line patterns
        self._extract_klines()

        # Train orchestrator routing from tree structure
        self._train_orchestrator_routing()

    def _train_word_network(self):
        """Train word-scale network from lexeme decompositions."""
        for lexeme in self.tree.iter_lexemes():
            self.networks.word.learn_from_decomposition(lexeme.decomposition)

    def _build_family_affinity(self):
        """Build family affinity matrix from lexemes."""
        for lexeme in self.tree.iter_lexemes():
            primitives = [p for p, r, pol in lexeme.decomposition]
            self.family_affinity.update_from_decomposition(
                primitives,
                self._primitive_to_family,
            )

    def _extract_klines(self):
        """Extract K-line patterns from all lexemes."""
        for lexeme in self.tree.iter_lexemes():
            pattern = self.klines.extract_from_lexeme(lexeme)
            if pattern:
                self.klines.add_pattern(pattern)

    def _train_orchestrator_routing(self):
        """Train orchestrator on bank → family → hub routing."""
        for bank_id, bank in self.tree.banks.items():
            # Associate bank with routing
            scale_node = {
                0: OrchestratorNode.ROUTE_WORD,  # SUBSTANTIVES
                1: OrchestratorNode.ROUTE_WORD,  # QUANTITY
                2: OrchestratorNode.ROUTE_WORD,  # EVALUATORS
                3: OrchestratorNode.ROUTE_SENT,  # MENTAL
                4: OrchestratorNode.ROUTE_SENT,  # ACTION
                5: OrchestratorNode.ROUTE_PARA,  # TEMPORAL
                6: OrchestratorNode.ROUTE_SENT,  # SPATIAL
                7: OrchestratorNode.ROUTE_TEXT,  # LOGICAL
            }.get(bank_id, OrchestratorNode.ROUTE_WORD)

            # Learn association
            self.orchestrator.learn(
                {
                    scale_node.name: 1.0,
                    OrchestratorNode.TASK_DECOMPOSE.name: 0.5,
                }
            )

    def navigate_with_network(
        self,
        query_activations: Dict[str, float],
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        """
        Navigate tree using network activations.

        Args:
            query_activations: Word-scale network activations
            top_k: Number of results

        Returns:
            List of (lexeme_key, score) tuples
        """
        # Propagate through word network
        output = self.networks.word.activate(query_activations)

        # Use activated primitives to guide routing
        active_prims = [p for p, v in output.items() if abs(v) > 0.1]

        # Build query vector from active primitives
        from gse.vectors_v2 import compose_decomposition

        decomp = [(p, "attribute", 1 if output.get(p, 0) > 0 else -1) for p in active_prims]

        if not decomp:
            return []

        query = compose_decomposition(self.basis, decomp)

        # Route through tree
        result = self.router.route(query, top_k=top_k)
        return result.matches

    def update_network_from_lexeme(self, lexeme: LexemeNode):
        """
        Update networks when a lexeme is added/modified.

        Args:
            lexeme: The new or modified lexeme
        """
        # Update word network
        self.networks.word.learn_from_decomposition(lexeme.decomposition)

        # Update family affinity
        primitives = [p for p, r, pol in lexeme.decomposition]
        self.family_affinity.update_from_decomposition(
            primitives,
            self._primitive_to_family,
        )

        # Extract and store K-line
        pattern = self.klines.extract_from_lexeme(lexeme)
        if pattern:
            self.klines.add_pattern(pattern)

    def get_family_suggestions(
        self,
        current_family: str,
        top_k: int = 3,
    ) -> List[Tuple[str, float]]:
        """
        Get suggested families based on affinity.

        Args:
            current_family: Current family being considered
            top_k: Number of suggestions

        Returns:
            List of (family_id, affinity) tuples
        """
        return self.family_affinity.get_top_affinities(current_family, top_k)

    def get_pattern_suggestions(
        self,
        seed_primitives: List[str],
        top_k: int = 5,
    ) -> List[Tuple[KLinePattern, float]]:
        """
        Get K-line pattern suggestions.

        Args:
            seed_primitives: Starting primitives
            top_k: Number of suggestions

        Returns:
            List of (pattern, similarity) tuples
        """
        return self.klines.find_similar_patterns(seed_primitives, top_k)

    def get_statistics(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        return {
            "tree": {
                "lexemes": len(self.tree.lexemes),
                "families": len(self.tree.families),
                "hubs": len(self.tree.hubs),
            },
            "networks": self.networks.get_statistics(),
            "orchestrator": {
                "updates": self.orchestrator.update_count,
            },
            "klines": {
                "patterns": len(self.klines.patterns),
                "by_primitive": len(self.klines.by_primitive),
            },
            "family_affinity": {
                "families": self.family_affinity.n_families,
                "total_counts": int(self.family_affinity.counts.sum()),
            },
        }


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    from gse.merkle import LexemeNode, MerkleLexiconTree
    from gse.vectors_v2 import compose_decomposition, create_basis

    print("MerkleLearningBridge Tests")
    print("=" * 50)

    # Create tree with sample lexemes
    tree = MerkleLexiconTree()
    basis = create_basis()

    test_lexemes = [
        ("happy", "adj", [("FEEL", "experiencer", 1), ("GOOD", "attribute", 1)]),
        ("sad", "adj", [("FEEL", "experiencer", 1), ("BAD", "attribute", 1)]),
        ("ecstatic", "adj", [("FEEL", "experiencer", 1), ("GOOD", "attribute", 1), ("INTENSITY", "degree", 1)]),
        ("think", "v", [("THINK", "action", 1), ("SOMEONE", "agent", 1)]),
        ("know", "v", [("KNOW", "action", 1), ("SOMEONE", "agent", 1)]),
        ("believe", "v", [("THINK", "action", 1), ("MAYBE", "modifier", 1)]),
        ("run", "v", [("MOVE", "action", 1), ("SOMEONE", "agent", 1)]),
        ("walk", "v", [("MOVE", "action", 1), ("SOMEONE", "agent", 1)]),
    ]

    for lemma, pos, decomp in test_lexemes:
        vec = compose_decomposition(basis, decomp)
        lexeme = LexemeNode(
            node_id=f"{lemma}_{pos}_01",
            lemma=lemma,
            pos=pos,
            sense_id="01",
            gloss=f"test {lemma}",
            decomposition=decomp,
            vector_positive=vec.positive_indices,
            vector_negative=vec.negative_indices,
        )
        tree.add_lexeme(lexeme)

    print(f"✓ Created tree with {len(tree.lexemes)} lexemes")

    # Create bridge
    bridge = MerkleLearningBridge(tree)
    print("✓ Created MerkleLearningBridge")

    # Train from tree
    bridge.train_from_tree()
    print("✓ Trained networks from tree")

    # Check statistics
    stats = bridge.get_statistics()
    print(f"  K-line patterns: {stats['klines']['patterns']}")
    print(f"  Word network updates: {stats['networks']['word']['updates']}")

    # Test family affinity
    suggestions = bridge.get_family_suggestions("mental_affective")
    print(f"✓ Family suggestions for mental_affective: {suggestions[:2]}")

    # Test K-line suggestions
    patterns = bridge.get_pattern_suggestions(["FEEL", "GOOD"])
    print(f"✓ Pattern suggestions for FEEL+GOOD: {len(patterns)} found")
    if patterns:
        print(f"  Best: {patterns[0][0].exemplars[:2]}")

    # Test network navigation
    matches = bridge.navigate_with_network({"FEEL": 1.0, "GOOD": 0.8})
    print(f"✓ Network navigation: {matches[:3]}")

    # Test incremental update
    new_lexeme = LexemeNode(
        node_id="joyful_adj_01",
        lemma="joyful",
        pos="adj",
        sense_id="01",
        gloss="full of joy",
        decomposition=[("FEEL", "experiencer", 1), ("GOOD", "attribute", 1)],
        vector_positive=np.array([1, 2, 3], dtype=np.uint16),
        vector_negative=np.array([], dtype=np.uint16),
    )
    tree.add_lexeme(new_lexeme)
    bridge.update_network_from_lexeme(new_lexeme)
    print("✓ Incremental update completed")

    print("\n" + "=" * 50)
    print("All MerkleLearningBridge tests passed!")
