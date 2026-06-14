"""
Collision Classification

Handles disagreements between different encoding/retrieval mechanisms.
e.g., when Pattern Network predicts a primitive that Graph says shouldn't be there.
"""

from enum import Enum, auto
from typing import Dict, Any, List

class CollisionType(Enum):
    FALSE_POSITIVE = auto()   # Mechanism predicted X, but verification failed
    NOVEL_SENSE = auto()      # New usage not in lexicon (potential learning opportunity)
    CONTEXTUAL_SHIFT = auto() # Valid usage but specific to context
    ERROR = auto()            # System error or flat contradiction

class CollisionClassifier:
    """
    Classifies collisions (disagreements) to guide resolution.
    """
    
    def classify(
        self, 
        mechanism_a: str, 
        prediction_a: Any, 
        mechanism_b: str, 
        prediction_b: Any,
        context: Dict[str, Any] = None
    ) -> CollisionType:
        """
        Classify the collision between two mechanisms.
        
        Args:
            mechanism_a: Name of first mechanism (e.g., "pattern_network")
            prediction_a: Prediction from A
            mechanism_b: Name of second mechanism (e.g., "lexicon")
            prediction_b: Prediction from B
            context: Additional context
            
        Returns:
            CollisionType classification
        """
        # Heuristic rules based on mechanism trust levels
        
        # Rule 1: Lexicon (Ground Truth) vs Pattern Network (Probabilistic)
        if mechanism_b == "lexicon" and mechanism_a == "pattern_network":
            # If pattern network predicts something NOT in lexicon
            # And prediction is strong (> 0.8 conf), it might be a novel sense.
            score = context.get("score_a", 0.5) if context else 0.5
            if score > 0.8:
                return CollisionType.NOVEL_SENSE
            else:
                return CollisionType.FALSE_POSITIVE
                
        # Rule 2: Syntactic (Structure) vs Lexical (Meaning)
        if mechanism_a == "syntactic" and mechanism_b == "lexical":
             # Syntactic parser is usually robust for structure
             return CollisionType.CONTEXTUAL_SHIFT
             
        # Default
        return CollisionType.ERROR
