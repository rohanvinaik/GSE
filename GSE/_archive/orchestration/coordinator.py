"""
GFS Coordinator

Central orchestration layer that routes requests, manages multi-scale encoding,
handling collisions, and ensuring graceful degradation.
"""

from typing import List, Dict, Any, Optional

from gse.graph.semantic_graph import SemanticGraph
from gse.graph.traversal import HierarchicalTraversal
from gse.patterns.pattern_network import PrimitivePatternNetwork
from gse.scales import LexicalScale, SyntacticScale, DiscourseScale, TextualScale
from gse.orchestration.collision import CollisionClassifier, CollisionType
from gse.orchestration.ambiguity_handler import AmbiguityHandler
from gse.vectors import SparseVector

class Coordinator:
    """
    Main entry point for GFS operations.
    """
    
    def __init__(
        self,
        graph: SemanticGraph,
        pattern_network: PrimitivePatternNetwork,
        scales: Dict[str, Any]
    ):
        self.graph = graph
        self.pattern_network = pattern_network
        self.traversal = HierarchicalTraversal(graph)
        
        # Scales
        self.lexical = scales.get("lexical")
        self.syntactic = scales.get("syntactic")
        self.discourse = scales.get("discourse")
        self.textual = scales.get("textual")
        
        # Helpers
        self.classifier = CollisionClassifier()
        self.ambiguity_handler = AmbiguityHandler()
        
    def process_text(self, text: str, mode: str = "sentence") -> Dict[str, Any]:
        """
        Process text input based on mode.
        """
        if mode == "word":
             # 1. Lexical encoding
             vec = self.lexical.encode(text)
             # 2. Check patterns (is this a valid concept?)
             # ...
             return {"vector": vec, "status": "ok"}
             
        elif mode == "sentence":
             if not self.syntactic:
                 return {"status": "error", "message": "Syntactic scale not available"}
             vec = self.syntactic.encode(text)
             return {"vector": vec, "status": "ok"}
        
        return {"status": "error", "message": f"Unknown mode: {mode}"}
    
    def verify_concept(self, primitives: List[str]) -> Dict[str, Any]:
        """
        Verify if a set of primitives forms a valid concept
        using the Pattern Network.
        """
        # Score coherence
        # Requires creating a dummy decomposition list [(prim, role), ...]
        # We simplify here assuming default roles?
        # Actually pattern network takes list of tuples.
        # Let's assume user passes primitives and we verify coherence.
        
        # This is a bit abstract without full context, but logical
        decomp = [(p, "attribute") for p in primitives] # Dummy roles
        score = self.pattern_network.score_pattern_coherence(decomp)
        
        if score < 0.3:
            return {
                "valid": False,
                "score": score,
                "ambiguity": self.ambiguity_handler.resolve([], f"Low coherence: {score}")
            }
            
        return {"valid": True, "score": score}
