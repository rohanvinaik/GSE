"""
Textual Scale Encoder

Encodes entire documents.
At this scale, we primarily look at global semantic signatures
and broad constraints (genre, style, theme).
"""

from typing import List, Dict, Any
import numpy as np
from gse.vectors import SparseVector, bundle

class TextualScale:
    """
    Encoder for the Textual Scale (Scale 4).
    """
    
    def __init__(self):
        pass
        
    def encode_document(self, paragraph_vectors: List[SparseVector]) -> SparseVector:
        """
        Encode a document by bundling its paragraph vectors.
        """
        if not paragraph_vectors:
            return SparseVector.zeros(8192)
        return bundle(paragraph_vectors)
        
    def extract_theme(self, doc_vector: SparseVector, n_banks: int = 8) -> Dict[int, float]:
        """
        Identify dominant semantic banks in the document.
        Returns {bank_index: magnitude}.
        """
        dense = doc_vector.to_dense()
        magnitudes = {}
        dims_per_bank = doc_vector.dimension // n_banks
        
        for bank in range(n_banks):
            start = bank * dims_per_bank
            end = start + dims_per_bank
            mag = float(np.sum(np.abs(dense[start:end])))
            magnitudes[bank] = mag
            
        return magnitudes
