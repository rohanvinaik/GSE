"""
Semantic Graph Structure

Hierarchical graph structure for efficient traversal:
Bank (8) -> Primitive (62) -> Lexeme (100k+)

This "primitive bottleneck" allows finding semantic relations (synonyms, matches)
by traversing UP to primitives rather than comparing all vectors.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Any
import json
import heapq

class NodeType(Enum):
    BANK = auto()
    PRIMITIVE = auto()
    LEXEME = auto()

class EdgeType(Enum):
    BELONGS_TO = auto()     # Primitive -> Bank
    DECOMPOSES_TO = auto()  # Lexeme -> Primitive
    CO_OCCURS_WITH = auto() # Primitive <-> Primitive (Pattern Network)
    SYNONYM_OF = auto()     # Lexeme <-> Lexeme (rare, high similarity)
    ANTONYM_OF = auto()     # Lexeme <-> Lexeme (rare)

@dataclass
class Node:
    id: str
    type: NodeType
    data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Edge:
    source: str
    target: str
    type: EdgeType
    weight: float = 1.0

class SemanticGraph:
    """
    Graph structure optimized for Primitive Bottleneck traversal.
    """
    
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, List[Edge]] = {}  # Adjacency list: node_id -> [Edge]
        self.reverse_edges: Dict[str, List[Edge]] = {} # node_id -> [Edge incoming]
    
    def add_node(self, node_id: str, node_type: NodeType, data: Dict = None):
        """Add a node to the graph."""
        if node_id not in self.nodes:
            self.nodes[node_id] = Node(node_id, node_type, data or {})
            self.edges[node_id] = []
            self.reverse_edges[node_id] = []
    
    def add_edge(self, source: str, target: str, edge_type: EdgeType, weight: float = 1.0):
        """Add a directed edge."""
        if source not in self.nodes or target not in self.nodes:
            raise ValueError(f"Nodes must exist before adding edge: {source} -> {target}")
            
        edge = Edge(source, target, edge_type, weight)
        self.edges[source].append(edge)
        
        # Store reverse lookup for fast traversal (e.g. Primitive -> Lexeme)
        reverse_edge = Edge(target, source, edge_type, weight) # Type logic might differ for reverse?
        # Typically we just store the forward edge effectively
        self.reverse_edges[target].append(edge)

    def get_neighbors(self, node_id: str, direction: str = "out") -> List[Edge]:
        """Get outgoing or incoming edges."""
        if direction == "out":
            return self.edges.get(node_id, [])
        elif direction == "in":
            return self.reverse_edges.get(node_id, [])
        return []
    
    def get_primitives_for_lexeme(self, lexeme_id: str) -> List[Tuple[str, float]]:
        """
        Get primitives a lexeme decomposes to.
        Returns [(primitive_id, weight)].
        """
        prims = []
        for edge in self.edges.get(lexeme_id, []):
            if edge.type == EdgeType.DECOMPOSES_TO:
                prims.append((edge.target, edge.weight))
        return prims
    
    def get_lexemes_for_primitive(self, primitive_id: str) -> List[str]:
        """
        Get all lexemes that use this primitive.
        """
        lexemes = []
        for edge in self.reverse_edges.get(primitive_id, []):
            if edge.type == EdgeType.DECOMPOSES_TO:
                lexemes.append(edge.source)
        return lexemes
    
    def save(self, path: str):
        """Save graph to file."""
        data = {
            'nodes': [
                {'id': n.id, 'type': n.type.name, 'data': n.data}
                for n in self.nodes.values()
            ],
            'edges': [
                {'source': e.source, 'target': e.target, 'type': e.type.name, 'weight': e.weight}
                for src in self.edges for e in self.edges[src]
            ]
        }
        with open(path, 'w') as f:
            json.dump(data, f)
            
    @classmethod
    def load(cls, path: str) -> 'SemanticGraph':
        """Load graph from file."""
        graph = cls()
        with open(path) as f:
            data = json.load(f)
            
        for n_data in data['nodes']:
            graph.add_node(n_data['id'], getattr(NodeType, n_data['type']), n_data['data'])
            
        for e_data in data['edges']:
            graph.add_edge(
                e_data['source'], 
                e_data['target'], 
                getattr(EdgeType, e_data['type']), 
                e_data['weight']
            )
        return graph
