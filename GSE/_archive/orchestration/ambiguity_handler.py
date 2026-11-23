"""
Ambiguity Handling

Ensures graceful degradation when the system is uncertain.
Prefer returning "Ambiguous" or specific clarification questions
over making a low-confidence guess.
"""

from typing import List, Any, Dict, Optional, Tuple

class AmbiguityHandler:
    """
    Manages ambiguous states and generates resolution strategies.
    """
    
    def __init__(self, confidence_threshold: float = 0.4):
        self.confidence_threshold = confidence_threshold
        
    def check_ambiguity(self, candidates: List[Tuple[Any, float]]) -> bool:
        """
        Check if the set of candidates is ambiguous.
        
        Ambiguous if:
        1. Top candidate score < threshold
        2. Top 0 and Top 1 scores are very close (margin < 0.1)
        """
        if not candidates:
            return True
            
        top_score = candidates[0][1]
        if top_score < self.confidence_threshold:
            return True
            
        if len(candidates) >= 2:
            margin = top_score - candidates[1][1]
            if margin < 0.1:
                return True
                
        return False
        
    def resolve(self, candidates: List[Tuple[Any, float]], context: str) -> Dict[str, Any]:
        """
        Generate a resolution response for ambiguity.
        
        Returns:
            Dict with 'status': 'ambiguous', 'options': [...], 'question': ...
        """
        if not candidates:
            return {
                "status": "ambiguous",
                "reason": "no_candidates",
                "question": "I could not identify any matching concepts. Can you rephrase?"
            }
            
        top_k = candidates[:3]
        options = [str(c[0]) for c in top_k]
        
        return {
            "status": "ambiguous",
            "reason": "low_margin" if candidates[0][1] >= self.confidence_threshold else "low_confidence",
            "options": options,
            "question": f"Did you mean {options[0]} or {options[1]}?" if len(options) >= 2 else f"I am unsure, did you mean {options[0]}?"
        }
