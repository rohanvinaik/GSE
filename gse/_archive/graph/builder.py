"""
Graph Builder

Constructs the SemanticGraph from:
1. Primitives definitions (Banks)
2. Lexicon (Lexemes -> Primitives)
3. Pattern Network (Primitive <-> Primitive)
"""

from typing import List, Dict, Optional
import sqlite3
import json

from gse.graph.semantic_graph import SemanticGraph, NodeType, EdgeType
from gse.primitives import PRIMITIVES, canonicalize_decomposition
from gse.vectors import SemanticBank, PRIMITIVE_BANKS

class GraphBuilder:
    """Builder for the Semantic Graph."""
    
    def __init__(self, primitives: List[str] = PRIMITIVES):
        self.primitives = primitives
        self.graph = SemanticGraph()
        
    def build(self, lexicon_path: str, pattern_network = None) -> SemanticGraph:
        """
        Build the full graph.
        
        Args:
            lexicon_path: Path to lexicon.db
            pattern_network: Optional PrimitivePatternNetwork instance for co-occurrence edges
        """
        print("Building Semantic Graph...")
        
        # 1. Add Bank Nodes
        for bank in SemanticBank:
            self.graph.add_node(
                f"BANK_{bank.name}", 
                NodeType.BANK, 
                {"index": bank.value}
            )
            
        # 2. Add Primitive Nodes and connect to Banks
        # Need to map primitives to banks. reusing PRIMITIVE_BANKS from vectors.py logic?
        # gse.vectors.PRIMITIVE_BANKS maps str -> SemanticBank
        from gse.vectors import PRIMITIVE_BANKS
        
        for prim in self.primitives:
             self.graph.add_node(prim, NodeType.PRIMITIVE)
             
             if prim in PRIMITIVE_BANKS:
                 bank_enum = PRIMITIVE_BANKS[prim]
                 bank_node = f"BANK_{bank_enum.name}"
                 self.graph.add_edge(prim, bank_node, EdgeType.BELONGS_TO)
        
        # 3. Add Lexeme Nodes from Lexicon
        self._add_lexemes_from_db(lexicon_path)
        
        # 4. Add Co-occurrence Edges (Optional)
        if pattern_network:
            self._add_pattern_edges(pattern_network)
            
        return self.graph
    
    def _add_lexemes_from_db(self, db_path: str):
        """Add all lexemes and their decomposition edges."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT lemma, pos, decomposition, frequency FROM lexicon WHERE decomposition IS NOT NULL")
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            print("Warning: lexicon table not found")
            rows = []
        
        count = 0
        for lemma, pos, decomp_json, freq in rows:
            if not decomp_json:
                continue
                
            lexeme_id = f"{lemma}.{pos}"
            self.graph.add_node(lexeme_id, NodeType.LEXEME, {"frequency": freq})
            
            try:
                decomp = json.loads(decomp_json)
                canonical = canonicalize_decomposition(decomp)
                
                for activation in canonical:
                    # Edge: Lexeme -> Primitive (DECOMPOSES_TO)
                    if activation.primitive in self.graph.nodes:
                        self.graph.add_edge(
                            lexeme_id, 
                            activation.primitive, 
                            EdgeType.DECOMPOSES_TO,
                            weight=1.0  # Could be weighted by polarity or role importance?
                        )
                count += 1
            except Exception:
                continue
                
        conn.close()
        print(f"Added {count} lexemes to graph")
        
    def _add_pattern_edges(self, network):
        """Add strong co-occurrence edges between primitives."""
        # Check matrix for strong connections
        matrix = network.matrix
        threshold = 0.15
        
        count = 0
        for i in range(matrix.n):
            for j in range(i+1, matrix.n):
                prob = (matrix.probs[i, j] + matrix.probs[j, i]) / 2
                if prob > threshold:
                    p1 = matrix.idx_to_prim[i]
                    p2 = matrix.idx_to_prim[j]
                    
                    self.graph.add_edge(p1, p2, EdgeType.CO_OCCURS_WITH, prob)
                    self.graph.add_edge(p2, p1, EdgeType.CO_OCCURS_WITH, prob)
                    count += 1
        print(f"Added {count} co-occurrence edges")
