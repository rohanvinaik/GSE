"""
Hierarchical Graph Traversal

Leverages the structure: Bank -> Primitive -> Lexeme
to perform efficient semantic search and distance calculation.
"""

from typing import List, Set, Tuple, Dict, Optional
import networkx as nx  # Only if we used networkx, but we used custom graph.
# We will implement BFS/logic on our SemanticGraph.

from gse.graph.semantic_graph import SemanticGraph, NodeType, EdgeType

class HierarchicalTraversal:
    """Traversal algorithms for the Semantic Graph."""
    
    def __init__(self, graph: SemanticGraph):
        self.graph = graph
        
    def get_primitives(self, lexeme_id: str) -> Set[str]:
        """Get the set of primitives for a lexeme."""
        return {p for p, _ in self.graph.get_primitives_for_lexeme(lexeme_id)}
    
    def semantic_distance(self, lexeme1: str, lexeme2: str) -> float:
        """
        Compute semantic distance between two lexemes.
        
        Distance = 1.0 - Jaccard index of their primitive sets.
        This is the "Primitive Bottleneck" calculation.
        """
        p1 = self.get_primitives(lexeme1)
        p2 = self.get_primitives(lexeme2)
        
        if not p1 or not p2:
            return 1.0  # Max distance if either has no primitives
            
        intersection = len(p1 & p2)
        union = len(p1 | p2)
        
        jaccard = intersection / union if union > 0 else 0.0
        return 1.0 - jaccard
    
    def find_similar_lexemes(self, query_lexeme: str, limit: int = 10) -> List[Tuple[str, float]]:
        """
        Find lexemes semantically similar to the query.
        
        Algorithm:
        1. Get primitives of query.
        2. Traverse DOWN from each primitive to other lexemes.
        3. Score candidates by primitive overlap.
        """
        query_prims = self.get_primitives(query_lexeme)
        if not query_prims:
            return []
            
        candidates: Dict[str, int] = {}
        
        # Primitive Bottleneck: Only check lexemes reachable from query's primitives
        for prim in query_prims:
            linked_lexemes = self.graph.get_lexemes_for_primitive(prim)
            for lex in linked_lexemes:
                if lex == query_lexeme:
                    continue
                candidates[lex] = candidates.get(lex, 0) + 1
        
        # Score and sort
        results = []
        for lex, overlap in candidates.items():
            # Jaccard approximation: overlap / (len(query) + len(cand) - overlap)
            # Efficiently, we can just use overlap for ranking if lengths are similar
            # Or retrieve candidate primitives for full Jaccard
            cand_prims = self.get_primitives(lex)
            union = len(query_prims | cand_prims)
            score = overlap / union if union > 0 else 0.0
            
            if score > 0.0:
                 results.append((lex, score))
        
        results.sort(key=lambda x: -x[1])
        return results[:limit]
        
    def find_path(self, start_lex: str, end_lex: str) -> List[str]:
        """
        Find a semantic path between two lexemes via primitives.
        e.g., "doctor" -> (PERSON, HEAL) -> "nurse"
        """
        # Simple BFS on the graph logic
        # Lexeme <-> Primitive interactions
        
        # Just use primitives as bridge?
        p1 = self.get_primitives(start_lex)
        p2 = self.get_primitives(end_lex)
        
        intersection = p1 & p2
        if intersection:
            # Direct connection via stored primitive
            bridge = list(intersection)[0]
            return [start_lex, bridge, end_lex]
            
        return [] # TODO: Deeper search (via co-occurrence edges)
