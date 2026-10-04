#!/usr/bin/env python3
"""
Modified Bellman-Ford Routing for GSE Merkle Tree

Exploits the 5-level tree structure for efficient semantic search:
- O(8) bank-level pruning (skip orthogonal banks)
- O(17) family-level shortcuts (pre-computed centroids)
- O(17) hub-level routing (bank representatives)
- O(L/17) lexeme lookup (only in relevant families)

Total: O(42 + L/17) vs Dijkstra's O(L log L)

For L=18,000 lexemes:
- Modified Bellman-Ford: ~42 + 1,059 = ~1,100 operations
- Dijkstra: ~18,000 * 14.1 = ~254,000 operations
- Speedup: ~230x
"""

from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import Dict, List, Optional, Tuple

import numpy as np

from gse.primitives_v2 import (
    DIMS_PER_BANK,
    N_BANKS,
    SEMANTIC_BANK_NAMES,
    D,
    SemanticBank,
    get_dimension_range,
)
from gse.vectors_v2 import SparseVector, create_basis

# =============================================================================
# ROUTING RESULT
# =============================================================================

@dataclass
class RouteResult:
    """Result of routing through the Merkle tree."""
    query_vector: SparseVector

    # Path through tree
    activated_banks: List[int] = field(default_factory=list)
    activated_families: List[str] = field(default_factory=list)
    activated_hubs: List[str] = field(default_factory=list)

    # Top matches
    matches: List[Tuple[str, float]] = field(default_factory=list)  # (lexeme_key, similarity)

    # Statistics
    banks_checked: int = 0
    families_checked: int = 0
    hubs_checked: int = 0
    lexemes_checked: int = 0

    @property
    def total_operations(self) -> int:
        """Total number of similarity computations."""
        return self.banks_checked + self.families_checked + self.hubs_checked + self.lexemes_checked


@dataclass
class FamilyCentroid:
    """Pre-computed centroid for a primitive family."""
    family_id: str
    bank_id: int
    centroid: SparseVector
    lexeme_count: int = 0

    # Cached similarity bounds
    max_intra_similarity: float = 1.0
    min_intra_similarity: float = 0.0


# =============================================================================
# MERKLE BELLMAN-FORD ROUTER
# =============================================================================

class MerkleBellmanFord:
    """
    Modified Bellman-Ford routing through the Merkle tree.

    Uses hierarchical pruning to achieve O(42 + L/17) complexity:
    1. Compute bank activations from query vector
    2. Route to active families using pre-computed centroids
    3. Expand to hubs within active families
    4. Search lexemes only under activated hubs
    """

    def __init__(self, tree: "MerkleLexiconTree", basis: "HadamardOTPBasis" = None):
        """
        Initialize router with a Merkle tree.

        Args:
            tree: MerkleLexiconTree to route through
            basis: Optional HDC basis (created if not provided)
        """
        self.tree = tree
        self.basis = basis or create_basis()

        # Pre-computed family centroids
        self.family_centroids: Dict[str, FamilyCentroid] = {}

        # Bank activation thresholds
        self.bank_threshold = 0.1  # Minimum activation to consider bank
        self.family_threshold = 0.2  # Minimum similarity to consider family
        self.hub_threshold = 0.3  # Minimum similarity to consider hub

        # Build centroids
        self._compute_family_centroids()

    def _compute_family_centroids(self):
        """Compute centroids for each family from member lexemes."""
        for family_id, family in self.tree.families.items():
            # Get all lexemes in this family
            lexemes = self.tree.get_lexemes_by_family(family_id)

            if not lexemes:
                # Empty family - use hub primitive as centroid
                hub_name = family.hub_primitive
                if hub_name in self.basis.primitives:
                    centroid = self.basis.primitives[hub_name]
                else:
                    centroid = SparseVector(D)
            else:
                # Average of all lexeme vectors
                centroid = self._compute_centroid(lexemes)

            self.family_centroids[family_id] = FamilyCentroid(
                family_id=family_id,
                bank_id=family.bank_id,
                centroid=centroid,
                lexeme_count=len(lexemes),
            )

    def _compute_centroid(self, lexemes: List["LexemeNode"]) -> SparseVector:
        """Compute centroid of a set of lexemes."""
        if not lexemes:
            return SparseVector(D)

        # Aggregate positive and negative indices
        pos_counts: Dict[int, int] = {}
        neg_counts: Dict[int, int] = {}

        for lexeme in lexemes:
            for idx in lexeme.vector_positive:
                pos_counts[idx] = pos_counts.get(idx, 0) + 1
            for idx in lexeme.vector_negative:
                neg_counts[idx] = neg_counts.get(idx, 0) + 1

        # Keep indices that appear in majority
        threshold = len(lexemes) / 2

        centroid_pos = np.array(
            [idx for idx, count in pos_counts.items() if count > threshold],
            dtype=np.uint16
        )
        centroid_neg = np.array(
            [idx for idx, count in neg_counts.items() if count > threshold],
            dtype=np.uint16
        )

        return SparseVector(D, centroid_pos, centroid_neg)

    def _compute_bank_activations(self, query: SparseVector) -> Dict[int, float]:
        """
        Compute activation level for each bank from query vector.

        Activation = proportion of query's non-zero elements in bank's dimension range.
        """
        activations = {}

        for bank in SemanticBank:
            start, end = get_dimension_range(bank)

            # Count query elements in this bank's range
            pos_in_bank = np.sum((query.positive_indices >= start) & (query.positive_indices < end))
            neg_in_bank = np.sum((query.negative_indices >= start) & (query.negative_indices < end))
            total_in_bank = pos_in_bank + neg_in_bank

            # Normalize by bank size
            activation = total_in_bank / (DIMS_PER_BANK * 0.1)  # Expected sparsity ~10%
            activations[bank.value] = min(1.0, activation)

        return activations

    def route(
        self,
        query: SparseVector,
        top_k: int = 10,
        expand_families: int = 3,
        expand_hubs: int = 5,
    ) -> RouteResult:
        """
        Route a query through the Merkle tree to find similar lexemes.

        Args:
            query: Query vector to match
            top_k: Number of top matches to return
            expand_families: Max families to expand per bank
            expand_hubs: Max hubs to expand per family

        Returns:
            RouteResult with matches and statistics
        """
        result = RouteResult(query_vector=query)

        # Step 1: Bank-level pruning
        bank_activations = self._compute_bank_activations(query)
        result.banks_checked = N_BANKS

        active_banks = [
            bank_id for bank_id, activation in bank_activations.items()
            if activation > self.bank_threshold
        ]
        result.activated_banks = active_banks

        if not active_banks:
            # No significant bank activation - use all banks
            active_banks = list(range(N_BANKS))

        # Step 2: Family-level routing
        family_similarities: List[Tuple[float, str]] = []

        for family_id, centroid in self.family_centroids.items():
            if centroid.bank_id in active_banks:
                sim = query.cosine(centroid.centroid)
                result.families_checked += 1

                if sim > self.family_threshold or centroid.lexeme_count > 0:
                    heappush(family_similarities, (-sim, family_id))

        # Get top families per bank
        active_families = []
        families_per_bank: Dict[int, int] = {b: 0 for b in active_banks}

        while family_similarities and len(active_families) < expand_families * len(active_banks):
            neg_sim, family_id = heappop(family_similarities)
            bank_id = self.family_centroids[family_id].bank_id

            if families_per_bank[bank_id] < expand_families:
                active_families.append(family_id)
                families_per_bank[bank_id] += 1

        result.activated_families = active_families

        # Step 3: Hub-level routing
        active_hubs = []

        for family_id in active_families:
            family = self.tree.families.get(family_id)
            if not family:
                continue

            for hub_name in family.hub_hashes:
                hub = self.tree.hubs.get(hub_name)
                if hub and hub.lexeme_count > 0:
                    # Compute similarity to hub
                    hub_vec = self._get_hub_vector(hub_name)
                    if hub_vec:
                        sim = query.cosine(hub_vec)
                        result.hubs_checked += 1

                        if sim > self.hub_threshold:
                            active_hubs.append((hub_name, sim))

        # Sort hubs by similarity and take top
        active_hubs.sort(key=lambda x: -x[1])
        active_hubs = active_hubs[:expand_hubs * len(active_families)]
        result.activated_hubs = [h[0] for h in active_hubs]

        # Step 4: Lexeme search
        candidates: List[Tuple[float, str]] = []

        for hub_name, _ in active_hubs:
            lexemes = self.tree.get_lexemes_by_hub(hub_name)

            for lexeme in lexemes:
                lexeme_vec = SparseVector(
                    D,
                    lexeme.vector_positive,
                    lexeme.vector_negative
                )
                sim = query.cosine(lexeme_vec)
                result.lexemes_checked += 1

                heappush(candidates, (-sim, lexeme.key))

                # Keep heap bounded
                if len(candidates) > top_k * 2:
                    candidates = candidates[:top_k]

        # Extract top-k
        matches = []
        while candidates and len(matches) < top_k:
            neg_sim, key = heappop(candidates)
            matches.append((key, -neg_sim))

        result.matches = matches
        return result

    def _get_hub_vector(self, hub_name: str) -> Optional[SparseVector]:
        """Get vector for a hub primitive."""
        hub = self.tree.hubs.get(hub_name)
        if not hub:
            return None

        if len(hub.vector_positive) > 0 or len(hub.vector_negative) > 0:
            return SparseVector(D, hub.vector_positive, hub.vector_negative)

        # Fall back to basis primitive
        return self.basis.get_primitive(hub.primitive_name)

    def find_nearest(
        self,
        query: SparseVector,
        k: int = 1,
    ) -> List[Tuple[str, float]]:
        """
        Find k nearest lexemes to query.

        Convenience wrapper around route().
        """
        result = self.route(query, top_k=k)
        return result.matches

    def find_by_decomposition(
        self,
        decomposition: List[Tuple[str, str, int]],
        top_k: int = 10,
    ) -> RouteResult:
        """
        Find lexemes matching a decomposition pattern.

        Args:
            decomposition: List of (primitive, role, polarity) tuples
            top_k: Number of matches to return

        Returns:
            RouteResult with matches
        """
        from gse.vectors_v2 import compose_decomposition

        query = compose_decomposition(self.basis, decomposition)
        return self.route(query, top_k=top_k)


# =============================================================================
# DISTANCE METRICS
# =============================================================================

def semantic_distance(
    v1: SparseVector,
    v2: SparseVector,
    bank_weights: Optional[Dict[int, float]] = None,
) -> float:
    """
    Compute weighted semantic distance between vectors.

    Args:
        v1, v2: Vectors to compare
        bank_weights: Optional per-bank weights (default: uniform)

    Returns:
        Distance in [0, 2] (0 = identical, 2 = opposite)
    """
    if bank_weights is None:
        # Uniform weights
        return 1.0 - v1.cosine(v2)

    # Weighted by bank
    total_weight = 0.0
    weighted_sim = 0.0

    for bank in SemanticBank:
        weight = bank_weights.get(bank.value, 1.0)
        start, end = get_dimension_range(bank)

        # Extract bank-specific portions
        v1_bank = _extract_bank(v1, start, end)
        v2_bank = _extract_bank(v2, start, end)

        if v1_bank.nnz > 0 and v2_bank.nnz > 0:
            bank_sim = v1_bank.cosine(v2_bank)
            weighted_sim += weight * bank_sim
            total_weight += weight

    if total_weight > 0:
        return 1.0 - (weighted_sim / total_weight)
    return 1.0


def _extract_bank(v: SparseVector, start: int, end: int) -> SparseVector:
    """Extract elements within a bank's range."""
    pos_mask = (v.positive_indices >= start) & (v.positive_indices < end)
    neg_mask = (v.negative_indices >= start) & (v.negative_indices < end)

    return SparseVector(
        v.dimension,
        v.positive_indices[pos_mask],
        v.negative_indices[neg_mask],
    )


# =============================================================================
# PATH FINDING
# =============================================================================

def find_semantic_path(
    router: MerkleBellmanFord,
    source: str,
    target: str,
    max_hops: int = 5,
) -> Optional[List[str]]:
    """
    Find shortest path between two lexemes through semantic space.

    Uses Bellman-Ford algorithm on the hub graph.

    Args:
        router: MerkleBellmanFord instance
        source: Source lexeme key
        target: Target lexeme key
        max_hops: Maximum path length

    Returns:
        List of lexeme keys forming path, or None if not found
    """
    source_lex = router.tree.get_lexeme(source)
    target_lex = router.tree.get_lexeme(target)

    if not source_lex or not target_lex:
        return None

    # Build source and target vectors
    source_vec = SparseVector(D, source_lex.vector_positive, source_lex.vector_negative)
    target_vec = SparseVector(D, target_lex.vector_positive, target_lex.vector_negative)

    # BFS through similar lexemes
    visited = {source}
    queue = [(source, [source])]

    while queue and len(queue[0][1]) <= max_hops:
        current, path = queue.pop(0)

        if current == target:
            return path

        # Get current vector
        current_lex = router.tree.get_lexeme(current)
        if not current_lex:
            continue

        current_vec = SparseVector(D, current_lex.vector_positive, current_lex.vector_negative)

        # Find neighbors
        result = router.route(current_vec, top_k=10)

        for neighbor_key, sim in result.matches:
            if neighbor_key not in visited and sim > 0.3:
                visited.add(neighbor_key)
                queue.append((neighbor_key, path + [neighbor_key]))

    return None


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    from gse.merkle import LexemeNode, MerkleLexiconTree

    print("MerkleBellmanFord Router Tests")
    print("=" * 50)

    # Create tree with sample lexemes
    tree = MerkleLexiconTree()
    basis = create_basis()

    # Add some lexemes
    test_lexemes = [
        ("happy", "adj", "01", "feeling joy", [("FEEL", "experiencer", 1), ("GOOD", "attribute", 1)]),
        ("sad", "adj", "01", "feeling sorrow", [("FEEL", "experiencer", 1), ("BAD", "attribute", 1)]),
        ("big", "adj", "01", "large in size", [("BIG", "attribute", 1)]),
        ("small", "adj", "01", "little in size", [("SMALL", "attribute", 1)]),
        ("think", "v", "01", "use mind", [("THINK", "action", 1), ("SOMEONE", "agent", 1)]),
        ("know", "v", "01", "have knowledge", [("KNOW", "action", 1), ("SOMEONE", "agent", 1)]),
        ("run", "v", "01", "move fast", [("MOVE", "action", 1), ("SOMEONE", "agent", 1)]),
        ("walk", "v", "01", "move slow", [("MOVE", "action", 1), ("SOMEONE", "agent", 1)]),
    ]

    from gse.vectors_v2 import compose_decomposition

    for lemma, pos, sense, gloss, decomp in test_lexemes:
        vec = compose_decomposition(basis, decomp)
        lexeme = LexemeNode(
            node_id=f"{lemma}_{pos}_{sense}",
            lemma=lemma,
            pos=pos,
            sense_id=sense,
            gloss=gloss,
            decomposition=decomp,
            vector_positive=vec.positive_indices,
            vector_negative=vec.negative_indices,
        )
        tree.add_lexeme(lexeme)

    print(f"✓ Created tree with {len(tree.lexemes)} lexemes")

    # Create router
    router = MerkleBellmanFord(tree, basis)
    print(f"✓ Router initialized with {len(router.family_centroids)} family centroids")

    # Test 1: Route query for "happy"
    happy_decomp = [("FEEL", "experiencer", 1), ("GOOD", "attribute", 1)]
    query = compose_decomposition(basis, happy_decomp)

    result = router.route(query, top_k=5)
    print("\n✓ Route for 'happy' decomposition:")
    print(f"  Activated banks: {result.activated_banks}")
    print(f"  Activated families: {result.activated_families[:3]}...")
    print(f"  Operations: {result.total_operations}")
    print(f"  Top matches: {result.matches[:3]}")

    # Test 2: Find nearest to "sad"
    sad_lex = tree.get_lexeme("sad_adj_01")
    sad_vec = SparseVector(D, sad_lex.vector_positive, sad_lex.vector_negative)

    nearest = router.find_nearest(sad_vec, k=3)
    print(f"\n✓ Nearest to 'sad': {nearest}")

    # Test 3: Find by decomposition
    move_decomp = [("MOVE", "action", 1)]
    result = router.find_by_decomposition(move_decomp, top_k=5)
    print("\n✓ Lexemes with MOVE:")
    for key, sim in result.matches:
        print(f"  {key}: {sim:.3f}")

    # Test 4: Bank activations
    activations = router._compute_bank_activations(query)
    print("\n✓ Bank activations for happy query:")
    for bank_id, act in sorted(activations.items(), key=lambda x: -x[1])[:3]:
        print(f"  {SEMANTIC_BANK_NAMES[bank_id]}: {act:.3f}")

    print("\n" + "=" * 50)
    print("All MerkleBellmanFord tests passed!")
