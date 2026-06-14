"""
Main parsing algorithm: constraint propagation over token sequence.

Architecture:
1. Initialize graph with all possible roles per token (from lexicon)
2. Apply grammatical constraints to prune impossible edges
3. Resolve operators left-to-right
4. Output: ParseGraph with assigned roles and resolved operators
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Protocol, Set, Tuple

from ..lexicon.word_encoding import (
    ComponentType,
    GramRole,
    OperatorType,
)
from .graph import EdgeType, ParseEdge, ParseGraph, ParseNode
from .operators import OperatorState, apply_operators_to_atomic, resolve_operator

if TYPE_CHECKING:
    from ..lexicon.word_encoding import LexemeEntry


# ============================================================
# GRAMMATICAL CONSTRAINTS
# ============================================================

# What roles can precede what roles? (bigram constraints)
ROLE_TRANSITIONS: Dict[GramRole, Set[GramRole]] = {
    GramRole.DET: {GramRole.NOUN, GramRole.ADJ},
    GramRole.ADJ: {GramRole.NOUN, GramRole.ADJ},
    GramRole.NOUN: {GramRole.VERB, GramRole.PREP, GramRole.CONJ, GramRole.NOUN},
    GramRole.PRON: {GramRole.VERB, GramRole.PREP, GramRole.CONJ, GramRole.AUX},
    GramRole.AUX: {GramRole.VERB, GramRole.ADV, GramRole.PARTICLE, GramRole.AUX},
    GramRole.ADV: {GramRole.VERB, GramRole.ADJ, GramRole.ADV},
    GramRole.VERB: {
        GramRole.NOUN,
        GramRole.ADV,
        GramRole.PREP,
        GramRole.DET,
        GramRole.PRON,
        GramRole.ADJ,
    },
    GramRole.PREP: {GramRole.NOUN, GramRole.DET, GramRole.PRON, GramRole.ADJ},
    GramRole.CONJ: {
        GramRole.NOUN,
        GramRole.VERB,
        GramRole.ADJ,
        GramRole.ADV,
        GramRole.DET,
        GramRole.PRON,
    },
    GramRole.PARTICLE: {GramRole.VERB, GramRole.ADV, GramRole.ADJ},
}

# What edge types connect what roles?
EDGE_TEMPLATES: List[Tuple[GramRole, GramRole, EdgeType]] = [
    # Subject/predicate
    (GramRole.NOUN, GramRole.VERB, EdgeType.SUBJECT),
    (GramRole.PRON, GramRole.VERB, EdgeType.SUBJECT),
    # Object
    (GramRole.VERB, GramRole.NOUN, EdgeType.OBJECT),
    (GramRole.VERB, GramRole.PRON, EdgeType.OBJECT),
    # Modification
    (GramRole.DET, GramRole.NOUN, EdgeType.DETERMINER),
    (GramRole.ADJ, GramRole.NOUN, EdgeType.MODIFIER),
    (GramRole.ADV, GramRole.VERB, EdgeType.MODIFIER),
    (GramRole.ADV, GramRole.ADJ, EdgeType.MODIFIER),
    # Auxiliary
    (GramRole.AUX, GramRole.VERB, EdgeType.AUXILIARY),
    # Prepositional
    (GramRole.PREP, GramRole.NOUN, EdgeType.PREP_OBJ),
    (GramRole.PREP, GramRole.PRON, EdgeType.PREP_OBJ),
]


# ============================================================
# LEXICON PROTOCOL
# ============================================================


class LexiconProtocol(Protocol):
    """Protocol for lexicon lookup."""

    def lookup(self, token: str) -> "LexemeEntry":
        """Look up a token in the lexicon."""
        ...


# ============================================================
# SENTENCE PARSER
# ============================================================


class SentenceParser:
    """
    Parses token sequence into semantic graph.

    Algorithm:
    1. Lexicon lookup for each token
    2. Initialize nodes with possible roles
    3. Constraint propagation to prune roles
    4. Operator resolution (left-to-right)
    5. Edge construction based on final roles
    """

    def __init__(
        self,
        lexicon: Optional[LexiconProtocol] = None,
        lookup_func: Optional[Callable[[str], "LexemeEntry"]] = None,
    ):
        """
        Initialize parser with a lexicon.

        Args:
            lexicon: Object with .lookup(token) method
            lookup_func: Alternative: a lookup function
        """
        self.lexicon = lexicon
        self.lookup_func = lookup_func

    def _lookup(self, token: str) -> "LexemeEntry":
        """Look up a token using configured lexicon."""
        if self.lookup_func:
            return self.lookup_func(token)
        elif self.lexicon:
            return self.lexicon.lookup(token)
        else:
            raise ValueError("No lexicon configured - provide lexicon or lookup_func")

    def parse(self, tokens: List[str]) -> ParseGraph:
        """
        Main entry point.

        Algorithm:
        1. Lexicon lookup for each token
        2. Initialize nodes with possible roles
        3. Constraint propagation to prune roles
        4. Operator resolution (left-to-right)
        5. Edge construction based on final roles

        Args:
            tokens: List of tokens (words) in the sentence

        Returns:
            ParseGraph with nodes and edges
        """
        # Step 1: Lexicon lookup
        lexemes = [self._lookup(t) for t in tokens]

        # Step 2: Initialize nodes
        nodes = [
            ParseNode(
                position=i,
                lexeme=lex,
                possible_roles=set(lex.possible_roles),
            )
            for i, lex in enumerate(lexemes)
        ]

        # Step 3: Constraint propagation
        nodes = self._propagate_constraints(nodes)

        # Step 4: Assign roles and resolve operators
        nodes = self._assign_roles(nodes)
        nodes = self._resolve_operators(nodes)

        # Step 5: Edge construction
        edges = self._construct_edges(nodes)

        return ParseGraph(nodes=nodes, edges=edges)

    def parse_with_lexemes(self, lexemes: List["LexemeEntry"]) -> ParseGraph:
        """
        Parse directly from lexeme entries (skips lookup).

        Useful when lexemes are already loaded or for testing.

        Args:
            lexemes: List of LexemeEntry objects

        Returns:
            ParseGraph with nodes and edges
        """
        # Initialize nodes
        nodes = [
            ParseNode(
                position=i,
                lexeme=lex,
                possible_roles=set(lex.possible_roles),
            )
            for i, lex in enumerate(lexemes)
        ]

        # Constraint propagation
        nodes = self._propagate_constraints(nodes)

        # Assign roles and resolve operators
        nodes = self._assign_roles(nodes)
        nodes = self._resolve_operators(nodes)

        # Edge construction
        edges = self._construct_edges(nodes)

        return ParseGraph(nodes=nodes, edges=edges)

    def _propagate_constraints(self, nodes: List[ParseNode]) -> List[ParseNode]:
        """
        Iteratively prune impossible role assignments.

        Uses bigram constraints: if role R1 at position i,
        then position i+1 must have a role in ROLE_TRANSITIONS[R1].

        Forward and backward passes until convergence.
        """
        if len(nodes) <= 1:
            return nodes

        max_iterations = 10
        for _ in range(max_iterations):
            changed = False

            # Forward pass: prune next based on current
            for i in range(len(nodes) - 1):
                current = nodes[i]
                next_node = nodes[i + 1]

                # What roles are possible for next given current?
                valid_next: Set[GramRole] = set()
                for role in current.possible_roles:
                    if role in ROLE_TRANSITIONS:
                        valid_next.update(ROLE_TRANSITIONS[role])

                # If current has no valid transitions, allow all
                if not valid_next:
                    continue

                # Prune next's roles
                if next_node.prune_roles(valid_next):
                    changed = True

            # Backward pass: prune prev based on current
            for i in range(len(nodes) - 1, 0, -1):
                current = nodes[i]
                prev_node = nodes[i - 1]

                # What roles could precede current's roles?
                valid_prev: Set[GramRole] = set()
                for role in current.possible_roles:
                    for prev_role, next_roles in ROLE_TRANSITIONS.items():
                        if role in next_roles:
                            valid_prev.add(prev_role)

                # If no valid predecessors found, allow all
                if not valid_prev:
                    continue

                if prev_node.prune_roles(valid_prev):
                    changed = True

            if not changed:
                break

        return nodes

    def _assign_roles(self, nodes: List[ParseNode]) -> List[ParseNode]:
        """
        Assign final role to each node.

        Uses priority-based selection when multiple roles possible.
        """
        for node in nodes:
            if node.possible_roles:
                node.assigned_role = self._select_role(node)

        return nodes

    def _select_role(self, node: ParseNode) -> GramRole:
        """
        Select final role from possibilities.

        Priority order based on component type and frequency.
        """
        roles = node.possible_roles
        lex = node.lexeme

        # Operators prefer their operator role
        if lex.component_type == ComponentType.OPERATOR:
            if lex.operator_spec:
                op_type = lex.operator_spec.op_type
                if op_type == OperatorType.AUXILIARY:
                    if GramRole.AUX in roles:
                        return GramRole.AUX
                elif op_type == OperatorType.DETERMINER:
                    if GramRole.DET in roles:
                        return GramRole.DET

        # For hybrids, prefer atomic roles
        if lex.component_type == ComponentType.HYBRID:
            # Prefer verb/noun over aux
            if GramRole.VERB in roles:
                return GramRole.VERB
            if GramRole.NOUN in roles:
                return GramRole.NOUN

        # Default priority order
        priority = [
            GramRole.NOUN,
            GramRole.VERB,
            GramRole.ADJ,
            GramRole.ADV,
            GramRole.DET,
            GramRole.PREP,
            GramRole.AUX,
            GramRole.PRON,
            GramRole.CONJ,
            GramRole.PARTICLE,
        ]

        for role in priority:
            if role in roles:
                return role

        # Fallback: return any available role
        return list(roles)[0] if roles else GramRole.NOUN

    def _resolve_operators(self, nodes: List[ParseNode]) -> List[ParseNode]:
        """
        Left-to-right operator resolution.

        Implements the state machine:
        - SIGN sets pending_sign
        - HIERARCHY consumes sign, waits for atomic
        - AUXILIARY lazy-binds to verb
        - ATOMIC receives all pending operations
        """
        state = OperatorState()

        for node in nodes:
            lex = node.lexeme

            if lex.component_type == ComponentType.OPERATOR:
                state = resolve_operator(lex, state)

            elif lex.component_type == ComponentType.ATOMIC:
                node = apply_operators_to_atomic(node, state)
                # Clear state after applying to atomic
                state = state.reset()

            elif lex.component_type == ComponentType.HYBRID:
                # Context determines behavior
                if node.assigned_role == GramRole.AUX:
                    state = resolve_operator(lex, state)
                else:
                    node = apply_operators_to_atomic(node, state)
                    state = state.reset()

        return nodes

    def _construct_edges(self, nodes: List[ParseNode]) -> List[ParseEdge]:
        """
        Build edges based on assigned roles and templates.
        """
        edges = []

        for i, source in enumerate(nodes):
            for j, target in enumerate(nodes):
                if i == j:
                    continue

                # Check if this pair matches any template
                for src_role, tgt_role, edge_type in EDGE_TEMPLATES:
                    if (
                        source.assigned_role == src_role
                        and target.assigned_role == tgt_role
                    ):
                        # Check positional and structural constraints
                        if self._valid_edge(i, j, edge_type, nodes):
                            edges.append(
                                ParseEdge(
                                    source=i,
                                    target=j,
                                    edge_type=edge_type,
                                )
                            )

        return edges

    def _valid_edge(
        self,
        i: int,
        j: int,
        edge_type: EdgeType,
        nodes: List[ParseNode],
    ) -> bool:
        """Check if edge satisfies positional constraints."""

        # Subject precedes verb
        if edge_type == EdgeType.SUBJECT:
            return i < j

        # Object follows verb
        if edge_type == EdgeType.OBJECT:
            return i < j

        # Determiner immediately precedes noun (within window)
        if edge_type == EdgeType.DETERMINER:
            return i < j and j - i <= 3

        # Adjective precedes noun (within window)
        if edge_type == EdgeType.MODIFIER:
            if nodes[i].assigned_role == GramRole.ADJ:
                return i < j and j - i <= 4
            else:  # Adverb can follow verb
                return abs(i - j) <= 3

        # Auxiliary precedes main verb
        if edge_type == EdgeType.AUXILIARY:
            return i < j

        # Preposition precedes its object
        if edge_type == EdgeType.PREP_OBJ:
            return i < j and j - i <= 3

        return True
