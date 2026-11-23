"""
Semantic parsing as constraint propagation over a graph.

Design principles:
- Each word is a NODE with possible roles (from lexicon)
- Grammatical rules define possible EDGES between nodes
- Parsing = constraint propagation to find valid assignment
- Operators are resolved during graph construction
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

if TYPE_CHECKING:
    from ..lexicon.word_encoding import GramRole, LexemeEntry


# ============================================================
# EDGE TYPES
# ============================================================


class EdgeType(Enum):
    """Types of syntactic relations in the parse graph."""

    # Core argument structure
    SUBJECT = auto()  # noun → verb (agent/experiencer)
    OBJECT = auto()  # verb → noun (patient/theme)
    INDIRECT_OBJECT = auto()  # verb → noun (recipient/goal)

    # Modification
    MODIFIER = auto()  # adj → noun, adv → verb
    DETERMINER = auto()  # det → noun

    # Operator relations
    AUXILIARY = auto()  # aux → verb
    NEGATION = auto()  # neg → target
    DEGREE = auto()  # degree → adj/adv

    # Prepositional
    PREP_OBJ = auto()  # prep → noun
    PREP_ATTACH = auto()  # prep phrase → verb/noun

    # Complex structures
    COORDINATION = auto()  # conj linking parallel elements
    COMPLEMENT = auto()  # complementizer → clause
    RELATIVE = auto()  # relative pronoun → verb


# ============================================================
# PARSE NODE
# ============================================================


@dataclass
class ParseNode:
    """
    A word in the parse graph.

    Each node represents a token in the sentence with:
    - Position in the sentence
    - Lexeme entry from Layer 1
    - Possible grammatical roles (narrowed during parsing)
    - Operator state (pending modifications)
    - Accumulated features from auxiliaries
    """

    position: int  # Index in sentence (0-based)
    lexeme: "LexemeEntry"  # From Layer 1 lookup

    # Constraint state (narrowed during parsing)
    possible_roles: Set["GramRole"] = field(default_factory=set)  # Initially from lexicon
    assigned_role: Optional["GramRole"] = None  # After resolution

    # Operator state (set during operator resolution)
    pending_sign: Optional[int] = None  # Sign waiting to be applied (-1 for negation)
    hierarchy_level: int = 0  # Accumulated intensity modification

    # Features accumulated from operators (TAM features from auxiliaries)
    features: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize possible_roles from lexeme if not provided."""
        if not self.possible_roles and self.lexeme:
            self.possible_roles = set(self.lexeme.possible_roles)

    @property
    def word(self) -> str:
        """The surface form of this token."""
        return self.lexeme.surface_form if self.lexeme else ""

    @property
    def lemma(self) -> str:
        """The base form of this token."""
        return self.lexeme.lemma if self.lexeme else ""

    def has_role(self, role: "GramRole") -> bool:
        """Check if this role is still possible."""
        return role in self.possible_roles

    def assign_role(self, role: "GramRole") -> None:
        """Assign a role (typically after constraint propagation)."""
        if role in self.possible_roles:
            self.assigned_role = role
        else:
            raise ValueError(f"Cannot assign role {role} - not in possible_roles")

    def prune_roles(self, keep: Set["GramRole"]) -> bool:
        """
        Prune possible_roles to intersection with keep.

        Returns True if any pruning occurred.
        """
        new_possible = self.possible_roles & keep
        changed = new_possible != self.possible_roles
        self.possible_roles = new_possible
        return changed


# ============================================================
# PARSE EDGE
# ============================================================


@dataclass
class ParseEdge:
    """
    A syntactic relation between nodes in the parse graph.

    Edges represent grammatical relationships:
    - source → target (source depends on or modifies target)
    - edge_type specifies the syntactic relation
    - weight allows for probabilistic/ambiguous parses
    """

    source: int  # Position of source node
    target: int  # Position of target node
    edge_type: EdgeType
    weight: float = 1.0  # For ambiguous parses (higher = more confident)

    @property
    def is_forward(self) -> bool:
        """Does this edge point forward in the sentence?"""
        return self.target > self.source

    @property
    def is_backward(self) -> bool:
        """Does this edge point backward in the sentence?"""
        return self.target < self.source

    @property
    def distance(self) -> int:
        """How many positions apart are source and target?"""
        return abs(self.target - self.source)


# ============================================================
# PARSE GRAPH
# ============================================================


@dataclass
class ParseGraph:
    """
    Complete parse of a sentence.

    The graph represents:
    - Nodes: One per token in the sentence
    - Edges: Syntactic relationships between tokens

    After parsing:
    - Each node has an assigned_role
    - Edges encode the dependency structure
    - Operator modifications are resolved in node fields
    """

    nodes: List[ParseNode] = field(default_factory=list)
    edges: List[ParseEdge] = field(default_factory=list)

    def __len__(self) -> int:
        """Number of nodes (tokens) in the parse."""
        return len(self.nodes)

    def get_node(self, position: int) -> ParseNode:
        """Get node at position."""
        if 0 <= position < len(self.nodes):
            return self.nodes[position]
        raise IndexError(f"Position {position} out of range")

    def get_edges_from(self, position: int) -> List[ParseEdge]:
        """Get all edges originating from a position."""
        return [e for e in self.edges if e.source == position]

    def get_edges_to(self, position: int) -> List[ParseEdge]:
        """Get all edges pointing to a position."""
        return [e for e in self.edges if e.target == position]

    def get_edge(self, source: int, target: int) -> Optional[ParseEdge]:
        """Get edge between two positions (if exists)."""
        for e in self.edges:
            if e.source == source and e.target == target:
                return e
        return None

    def add_edge(
        self,
        source: int,
        target: int,
        edge_type: EdgeType,
        weight: float = 1.0,
    ) -> ParseEdge:
        """Add an edge to the graph."""
        edge = ParseEdge(
            source=source,
            target=target,
            edge_type=edge_type,
            weight=weight,
        )
        self.edges.append(edge)
        return edge

    def get_subject(self) -> Optional[ParseNode]:
        """Get the subject node (if any)."""
        for edge in self.edges:
            if edge.edge_type == EdgeType.SUBJECT:
                return self.nodes[edge.source]
        return None

    def get_predicate(self) -> Optional[ParseNode]:
        """Get the main verb node (if any)."""
        for edge in self.edges:
            if edge.edge_type == EdgeType.SUBJECT:
                return self.nodes[edge.target]
        return None

    def get_object(self) -> Optional[ParseNode]:
        """Get the direct object node (if any)."""
        for edge in self.edges:
            if edge.edge_type == EdgeType.OBJECT:
                return self.nodes[edge.target]
        return None

    def get_modifiers(self, position: int) -> List[ParseNode]:
        """Get all modifier nodes for a position."""
        modifiers = []
        for edge in self.get_edges_to(position):
            if edge.edge_type == EdgeType.MODIFIER:
                modifiers.append(self.nodes[edge.source])
        return modifiers

    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            "nodes": [
                {
                    "position": n.position,
                    "word": n.word,
                    "lemma": n.lemma,
                    "assigned_role": n.assigned_role.name if n.assigned_role else None,
                    "pending_sign": n.pending_sign,
                    "hierarchy_level": n.hierarchy_level,
                    "features": n.features,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "edge_type": e.edge_type.name,
                    "weight": e.weight,
                }
                for e in self.edges
            ],
        }

    def pretty_print(self) -> str:
        """Human-readable representation of the parse."""
        lines = []
        lines.append("Parse Graph:")
        lines.append("  Nodes:")
        for node in self.nodes:
            role_str = node.assigned_role.name if node.assigned_role else "?"
            mod_str = ""
            if node.pending_sign == -1:
                mod_str += " [NEG]"
            if node.hierarchy_level != 0:
                mod_str += f" [HIER:{node.hierarchy_level:+d}]"
            lines.append(f"    {node.position}: {node.word!r} ({role_str}){mod_str}")

        lines.append("  Edges:")
        for edge in self.edges:
            src = self.nodes[edge.source].word
            tgt = self.nodes[edge.target].word
            lines.append(f"    {src!r} --{edge.edge_type.name}--> {tgt!r}")

        return "\n".join(lines)
