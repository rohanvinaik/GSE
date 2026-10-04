"""
Compose HDC vectors from parsed semantic graph.

Design principles:
- Graph structure determines composition order
- Role binding uses HDC binding operation
- Operators modify vectors before composition
- Output: single sentence vector encoding full semantics

The composition process:
1. Get semantic vector for each node (from lexeme)
2. Apply operator modifications (negation, hierarchy)
3. Bind each node to its syntactic role
4. Bundle all bound vectors into sentence vector
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List

import numpy as np

if TYPE_CHECKING:
    from ..parsing.graph import ParseGraph, ParseNode

from ..parsing.graph import EdgeType
from ..vectors_v2 import SparseVector, bind, bundle, permute

# ============================================================
# ROLE VECTORS
# ============================================================


def _generate_role_vector(seed: int, dimension: int = 8192) -> SparseVector:
    """
    Generate a random role vector for binding.

    Role vectors span all banks to ensure binding produces
    non-empty results regardless of which bank the primitive is in.
    """
    rng = np.random.default_rng(seed=seed)

    # ~48 non-zeros spanning all banks (6 per bank)
    dims_per_bank = dimension // 8
    positive_indices = []
    negative_indices = []

    for bank in range(8):
        bank_offset = bank * dims_per_bank
        positions = rng.choice(dims_per_bank, size=6, replace=False)

        for i, pos in enumerate(positions):
            global_pos = bank_offset + pos
            if (bank + i) % 2 == 0:
                positive_indices.append(global_pos)
            else:
                negative_indices.append(global_pos)

    return SparseVector(
        dimension=dimension,
        positive_indices=np.array(positive_indices, dtype=np.uint16),
        negative_indices=np.array(negative_indices, dtype=np.uint16),
        bank=None,
    )


# Pre-computed role vectors for binding
ROLE_VECTORS: Dict[EdgeType, SparseVector] = {
    EdgeType.SUBJECT: _generate_role_vector(seed=1001),
    EdgeType.OBJECT: _generate_role_vector(seed=1002),
    EdgeType.INDIRECT_OBJECT: _generate_role_vector(seed=1003),
    EdgeType.MODIFIER: _generate_role_vector(seed=1004),
    EdgeType.DETERMINER: _generate_role_vector(seed=1005),
    EdgeType.AUXILIARY: _generate_role_vector(seed=1006),
    EdgeType.NEGATION: _generate_role_vector(seed=1007),
    EdgeType.DEGREE: _generate_role_vector(seed=1008),
    EdgeType.PREP_OBJ: _generate_role_vector(seed=1009),
    EdgeType.PREP_ATTACH: _generate_role_vector(seed=1010),
    EdgeType.COORDINATION: _generate_role_vector(seed=1011),
    EdgeType.COMPLEMENT: _generate_role_vector(seed=1012),
    EdgeType.RELATIVE: _generate_role_vector(seed=1013),
}

# Special vectors for operator effects
NEGATION_VECTOR = _generate_role_vector(seed=2001)
INTENSIFY_PERMUTATION = 100  # Shift amount for intensification
ATTENUATE_PERMUTATION = -100  # Shift amount for attenuation


# ============================================================
# SEMANTIC COMPOSER
# ============================================================


@dataclass
class SemanticComposer:
    """
    Composes sentence-level HDC vectors from parse graphs.

    Takes a ParseGraph from Layer 3 and produces a single
    SparseVector representing the sentence's meaning.

    The composition strategy:
    1. Get modified vectors for each node (with operator effects)
    2. Bind each node to its syntactic role
    3. Bundle all bound vectors into sentence vector
    """

    dimension: int = 8192
    include_unbound: bool = True  # Include raw word vectors too

    def compose(self, graph: "ParseGraph") -> SparseVector:
        """
        Main composition algorithm.

        Strategy:
        1. Apply operator modifications to atomic vectors
        2. Bind each node to its syntactic role
        3. Bundle all bound vectors into sentence vector

        Args:
            graph: Parsed graph from Layer 3

        Returns:
            Sentence-level HDC vector
        """
        if not graph.nodes:
            return SparseVector.zeros(self.dimension)

        # Step 1: Get modified vectors for each node
        node_vectors: Dict[int, SparseVector] = {}
        for node in graph.nodes:
            vec = self._get_modified_vector(node)
            node_vectors[node.position] = vec

        # Step 2: Bind to roles based on edges
        bound_vectors: List[SparseVector] = []
        nodes_with_edges = set()

        for edge in graph.edges:
            source_vec = node_vectors[edge.source]
            role_vec = ROLE_VECTORS.get(edge.edge_type)

            if role_vec:
                bound = bind(source_vec, role_vec)
                bound_vectors.append(bound)
                nodes_with_edges.add(edge.source)

        # Step 3: Include unbound word vectors if requested
        if self.include_unbound:
            for position, vec in node_vectors.items():
                if position not in nodes_with_edges or True:  # Always include raw
                    bound_vectors.append(vec)

        # Step 4: Bundle everything
        if bound_vectors:
            sentence_vec = bundle(bound_vectors)
        else:
            # Fallback: just bundle all node vectors
            sentence_vec = bundle(list(node_vectors.values()))

        return sentence_vec

    def _get_modified_vector(self, node: "ParseNode") -> SparseVector:
        """
        Get node's semantic vector with operator modifications applied.

        Modifications:
        - Hierarchy level → permutation to intensified/attenuated subspace
        - Pending sign → binding with negation vector
        - Grammatical features → (stored as metadata, not encoded)

        Args:
            node: Parse node with lexeme and operator state

        Returns:
            Modified semantic vector
        """
        # Get base semantic vector from lexeme
        base_vec = node.lexeme.semantic_vector

        # Apply hierarchy modification (intensity scaling)
        if node.hierarchy_level != 0:
            base_vec = self._apply_hierarchy(base_vec, node.hierarchy_level)

        # Apply sign modification (negation)
        if node.pending_sign == -1:
            base_vec = self._apply_negation(base_vec)

        return base_vec

    def _apply_hierarchy(self, vec: SparseVector, level: int) -> SparseVector:
        """
        Apply intensity modification.

        Hierarchy level maps to permutation:
        +1 = shift by 100, +2 = shift by 200, etc.
        -1 = shift by -100, -2 = shift by -200, etc.

        In HDC: permutation moves to "intensified" or "attenuated" subspace.

        Args:
            vec: Input vector
            level: Hierarchy level (+/- integer)

        Returns:
            Permuted vector
        """
        if level == 0:
            return vec

        shift = level * INTENSIFY_PERMUTATION
        return permute(vec, shift)

    def _apply_negation(self, vec: SparseVector) -> SparseVector:
        """
        Apply semantic negation.

        In HDC: bind with NEGATION vector to move to "negated" subspace.

        This makes the negated vector dissimilar to both the original
        and other unrelated vectors.

        Args:
            vec: Input vector

        Returns:
            Negated vector
        """
        return bind(vec, NEGATION_VECTOR)

    def compose_phrase(
        self,
        nodes: List["ParseNode"],
        head_position: int,
    ) -> SparseVector:
        """
        Compose a phrase (subset of parse graph).

        Useful for composing noun phrases, verb phrases, etc.
        The head word is bound with modifiers bundled in.

        Args:
            nodes: List of parse nodes in the phrase
            head_position: Position of the head word

        Returns:
            Phrase-level HDC vector
        """
        vectors = []
        head_vec = None

        for node in nodes:
            vec = self._get_modified_vector(node)
            if node.position == head_position:
                head_vec = vec
            else:
                vectors.append(vec)

        if head_vec is None:
            # No head found, just bundle all
            return bundle([self._get_modified_vector(n) for n in nodes])

        if vectors:
            # Bundle modifiers with head
            modifier_bundle = bundle(vectors)
            return bundle([head_vec, modifier_bundle])
        else:
            return head_vec


def compose_sentence(
    graph: "ParseGraph",
    dimension: int = 8192,
) -> SparseVector:
    """
    Convenience function to compose a sentence.

    Args:
        graph: Parsed graph from Layer 3
        dimension: Vector dimension

    Returns:
        Sentence-level HDC vector
    """
    composer = SemanticComposer(dimension=dimension)
    return composer.compose(graph)
