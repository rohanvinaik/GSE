"""
Primitive Co-occurrence Matrix

Learned from the decomposition corpus (lexicon.db).
NOT trained with gradient descent — just counting and normalizing.

This captures: "When primitive X is active, how likely is primitive Y?"
"""

import numpy as np
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import sqlite3
import json


class CooccurrenceMatrix:
    """
    62×62 matrix of primitive co-occurrence probabilities.
    
    Learning process:
    1. Load all decompositions from lexicon
    2. For each decomposition, count co-occurring primitive pairs
    3. Normalize to get P(prim_j | prim_i)
    
    This is NOT gradient descent. It's frequency counting.
    """
    
    def __init__(self, primitives: List[str]):
        self.primitives = primitives
        self.n = len(primitives)
        self.prim_to_idx = {p: i for i, p in enumerate(primitives)}
        self.idx_to_prim = {i: p for i, p in enumerate(primitives)}
        
        # Co-occurrence counts
        self.counts = np.zeros((self.n, self.n), dtype=np.float32)
        # Marginal counts (how often each primitive appears)
        self.marginals = np.zeros(self.n, dtype=np.float32)
        # Conditional probability matrix
        self.probs = np.zeros((self.n, self.n), dtype=np.float32)
        # Learning statistics
        self.n_words_learned = 0
    
    def learn_from_lexicon(self, lexicon_path: str) -> 'CooccurrenceMatrix':
        """
        Learn co-occurrence from lexicon decompositions.
        
        This is the "learning" — counting, not gradient descent.
        """
        conn = sqlite3.connect(lexicon_path)
        cursor = conn.cursor()
        
        # Check if table exists (for safety in partial installs)
        try:
            cursor.execute("SELECT decomposition FROM lexicon WHERE decomposition IS NOT NULL")
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            print("Warning: lexicon table not found or empty")
            rows = []
        
        for (decomp_json,) in rows:
            if not decomp_json:
                continue
            
            try:
                decomp = json.loads(decomp_json)
            except json.JSONDecodeError:
                continue
            
            # Extract primitives from this decomposition
            prims_in_word = set()
            for item in decomp:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    prim = item[0]
                    if prim in self.prim_to_idx:
                        prims_in_word.add(prim)
            
            if not prims_in_word:
                continue
            
            # Count co-occurrences
            prim_list = list(prims_in_word)
            for i, p1 in enumerate(prim_list):
                idx1 = self.prim_to_idx[p1]
                self.marginals[idx1] += 1
                
                for p2 in prim_list[i+1:]:
                    idx2 = self.prim_to_idx[p2]
                    self.counts[idx1, idx2] += 1
                    self.counts[idx2, idx1] += 1  # Symmetric
            
            self.n_words_learned += 1
        
        conn.close()
        
        # Compute conditional probabilities: P(j | i) = count(i,j) / count(i)
        for i in range(self.n):
            if self.marginals[i] > 0:
                self.probs[i, :] = self.counts[i, :] / self.marginals[i]
        
        print(f"Learned co-occurrence from {self.n_words_learned} decompositions")
        return self
    
    def get_probability(self, prim_given: str, prim_query: str) -> float:
        """P(prim_query | prim_given)"""
        if prim_given not in self.prim_to_idx or prim_query not in self.prim_to_idx:
            return 0.0
        i = self.prim_to_idx[prim_given]
        j = self.prim_to_idx[prim_query]
        return float(self.probs[i, j])
    
    def get_likely_companions(self, active_prims: Set[str], top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Given a set of active primitives, predict likely additional primitives.
        
        Uses product of conditional probabilities (naive Bayes assumption).
        """
        if not active_prims:
            return []
        
        # Score each primitive by product of P(prim | active_i)
        scores = np.ones(self.n)
        
        for prim in active_prims:
            if prim in self.prim_to_idx:
                idx = self.prim_to_idx[prim]
                # Multiply by P(other | this) for each active primitive
                scores *= (self.probs[idx, :] + 0.01)  # Smoothing
        
        # Zero out already-active primitives
        for prim in active_prims:
            if prim in self.prim_to_idx:
                scores[self.prim_to_idx[prim]] = 0.0
        
        # Get top k
        top_indices = np.argsort(scores)[-top_k:][::-1]
        return [(self.idx_to_prim[i], float(scores[i])) for i in top_indices if scores[i] > 0.01]
    
    def get_cross_bank_connections(
        self, 
        bank_assignments: Dict[str, int], 
        threshold: float = 0.1
    ) -> List[Tuple[str, str, float]]:
        """
        Find significant cross-bank primitive connections.
        
        These are informationally dense: primitives that often co-occur
        despite being in different (supposedly orthogonal) banks.
        """
        connections = []
        
        for i in range(self.n):
            for j in range(i+1, self.n):
                p1, p2 = self.idx_to_prim[i], self.idx_to_prim[j]
                
                # Check if different banks
                bank1 = bank_assignments.get(p1, -1)
                bank2 = bank_assignments.get(p2, -1)
                
                if bank1 != bank2 and bank1 >= 0 and bank2 >= 0:
                    prob = (self.probs[i, j] + self.probs[j, i]) / 2
                    if prob > threshold:
                        connections.append((p1, p2, prob))
        
        connections.sort(key=lambda x: -x[2])
        return connections
    
    def save(self, path: str):
        """Save matrix to file."""
        np.savez(path, 
                 counts=self.counts, 
                 marginals=self.marginals, 
                 probs=self.probs,
                 primitives=np.array(self.primitives),
                 n_words_learned=self.n_words_learned)
    
    @classmethod
    def load(cls, path: str) -> 'CooccurrenceMatrix':
        """Load matrix from file."""
        data = np.load(path, allow_pickle=True)
        matrix = cls(list(data['primitives']))
        matrix.counts = data['counts']
        matrix.marginals = data['marginals']
        matrix.probs = data['probs']
        matrix.n_words_learned = int(data['n_words_learned'])
        return matrix
