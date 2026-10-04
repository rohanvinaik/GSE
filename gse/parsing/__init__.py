"""
Layer 3: Semantic Graph - Parsing as constraint propagation.

Design principles:
- Each word is a NODE with possible roles (from lexicon)
- Grammatical rules define possible EDGES between nodes
- Parsing = constraint propagation to find valid assignment
- Operators are resolved during graph construction
"""

from .graph import EdgeType, ParseEdge, ParseGraph, ParseNode
from .operators import OperatorState, apply_operators_to_atomic, resolve_operator
from .parser import SentenceParser

__all__ = [
    "ParseNode",
    "ParseEdge",
    "ParseGraph",
    "EdgeType",
    "OperatorState",
    "resolve_operator",
    "apply_operators_to_atomic",
    "SentenceParser",
]
