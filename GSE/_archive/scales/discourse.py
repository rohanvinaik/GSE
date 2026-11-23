"""
Discourse Scale Encoder

Analyzes coherence between sentences in a paragraph.
Uses a sliding window to detect topic shifts and measure flow.
"""

from typing import List, Tuple
import numpy as np
from gse.vectors import SparseVector, bundle

class DiscourseScale:
    """
    Encoder for the Discourse Scale (Scale 3).
    """
    
    def __init__(self, window_size: int = 3):
        self.window_size = window_size
        
    def encode_paragraph(self, sentence_vectors: List[SparseVector]) -> SparseVector:
        """
        Encode a paragraph by bundling its sentence vectors.
        """
        if not sentence_vectors:
            return SparseVector.zeros(8192)
        return bundle(sentence_vectors)
    
    def measure_coherence(self, sentence_vectors: List[SparseVector]) -> float:
        """
        Measure average coherence (cosine similarity) between adjacent sentences.
        """
        if len(sentence_vectors) < 2:
            return 1.0
            
        similarities = []
        for i in range(len(sentence_vectors) - 1):
            v1 = sentence_vectors[i]
            v2 = sentence_vectors[i+1]
            sim = v1.cosine(v2)
            similarities.append(sim)
            
        return float(np.mean(similarities))
    
    def identify_topic_shifts(self, sentence_vectors: List[SparseVector], threshold: float = 0.3) -> List[int]:
        """
        Identify indices where topic shifts (low similarity) occur.
        Returns indices of the second sentence in the pair.
        """
        shifts = []
        for i in range(len(sentence_vectors) - 1):
            v1 = sentence_vectors[i]
            v2 = sentence_vectors[i+1]
            sim = v1.cosine(v2)
            
            if sim < threshold:
                shifts.append(i + 1)
                
        return shifts
