"""
Primitive Pattern Network

Integrates Cooccurrence Matrix and K-Lines to provide:
1. Pattern Completion (predicting missing primitives)
2. Coherence Scoring (how "normal" is this decomposition?)
3. Anomaly Detection (surprising combinations)
"""

from typing import List, Set, Tuple, Dict, Optional
import os
import numpy as np

from gse.patterns.cooccurrence import CooccurrenceMatrix
from gse.patterns.klines import KLineStore
from gse.primitives import canonicalize_decomposition, Polarity, PrimitiveActivation


class PrimitivePatternNetwork:
    """
    Orchestrates pattern-based reasoning over primitives.
    """
    
    def __init__(self, primitives: List[str]):
        self.primitives = primitives
        self.matrix = CooccurrenceMatrix(primitives)
        self.klines = KLineStore()
        self.is_learned = False
    
    def learn(self, lexicon_path: str):
        """Learn patterns from the lexicon."""
        print("Learning Cooccurrence Matrix...")
        self.matrix.learn_from_lexicon(lexicon_path)
        
        print("Learning K-Lines...")
        self.klines.learn_from_lexicon(lexicon_path, self.primitives)
        
        self.is_learned = True
    
    def predict_primitives(
        self, 
        active_primitives: Set[str], 
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Suggest primitives to add to the current set.
        Combines signals from Cooccurrence Matrix and K-Lines.
        """
        # Signal 1: Cooccurrence Matrix (pairwise stats)
        matrix_preds = dict(self.matrix.get_likely_companions(active_primitives, top_k=10))
        
        # Signal 2: K-Line Completion (structural patterns)
        # Convert simple set to (prim, polarity) for K-Lines, assuming positive for input
        pattern_query = {(p, 1) for p in active_primitives}
        kline_completion = self.klines.complete_pattern(pattern_query, min_confidence=0.3)
        kline_preds = {prim: score for prim, pol, score in kline_completion}
        
        # Combine signals
        combined_scores = {}
        all_candidates = set(matrix_preds.keys()) | set(kline_preds.keys())
        
        for prim in all_candidates:
            s1 = matrix_preds.get(prim, 0.0)
            s2 = kline_preds.get(prim, 0.0)
            
            # Hybrid score: MAX(s1, s2) + 0.5 * MIN(s1, s2)
            # This rewards confirmation from both sources
            score = max(s1, s2) + 0.5 * min(s1, s2)
            combined_scores[prim] = score
        
        # Sort and trim
        results = sorted(combined_scores.items(), key=lambda x: -x[1])
        return results[:top_k]
    
    def score_pattern_coherence(self, decomposition: List[Tuple]) -> float:
        """
        How coherent/typical is this decomposition?
        
        Returns score [0, 1]:
        1.0 = Highly typical (matches strong K-lines or high co-occurrence)
        0.0 = Highly anomalous (unseen combinations)
        """
        # Canonicalize
        canonical = canonicalize_decomposition(decomposition)
        if not canonical:
            return 0.0
            
        prims = {a.primitive for a in canonical}
        pattern = {(a.primitive, int(a.polarity)) for a in canonical}
        
        # 1. K-Line Match Score (Exact or strong partial match)
        # Find best matching K-line
        matches = self.klines.find_matching(pattern, top_k=1, min_overlap=0.7)
        if matches:
            kline, score = matches[0]
            # Perfect match of a strong K-line is ideal
            kline_score = min(1.0, score * 1.2)
        else:
            kline_score = 0.0
            
        # 2. Pairwise Coherence Score (Cooccurrence Matrix)
        pairwise_score = 0.0
        n_pairs = 0
        prim_list = list(prims)
        
        if len(prim_list) < 2:
             # Single primitive is coherent by definition if it exists
             return 1.0 if prim_list[0] in self.matrix.prim_to_idx else 0.0
             
        for i in range(len(prim_list)):
            for j in range(i+1, len(prim_list)):
                p1, p2 = prim_list[i], prim_list[j]
                prob = self.matrix.get_probability(p1, p2)
                pairwise_score += prob
                n_pairs += 1
                
        avg_pairwise = pairwise_score / n_pairs if n_pairs > 0 else 0.0
        
        # Weighted average: K-lines are structure (stronger signal), Pairwise is glue
        final_score = 0.6 * kline_score + 0.4 * avg_pairwise
        
        # Boost for exact matches in K-lines
        if any(kl.pattern == pattern for kl in self.klines._klines.values()):
            final_score = max(final_score, 0.95)
            
        return min(1.0, final_score)

    def save(self, dir_path: str):
        """Save components to directory."""
        os.makedirs(dir_path, exist_ok=True)
        self.matrix.save(os.path.join(dir_path, "cooccurrence.npz"))
        self.klines.save(os.path.join(dir_path, "klines.json"))
        
    def load(self, dir_path: str) -> 'PrimitivePatternNetwork':
        """Load components from directory."""
        self.matrix = CooccurrenceMatrix.load(os.path.join(dir_path, "cooccurrence.npz"))
        self.klines = KLineStore.load(os.path.join(dir_path, "klines.json"))
        self.is_learned = True
        return self
