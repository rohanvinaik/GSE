"""
Syntactic Scale Encoder

Encodes sentences by:
1. Parsing dependency structure (via spaCy).
2. Mapping dependencies to semantic roles.
3. Encoding each word via Lexical Scale.
4. Permuting word vectors based on syntactic role.
5. Bundling into a single sentence vector.
"""

from typing import List, Dict, Optional
import numpy as np

try:
    import spacy
except ImportError:
    spacy = None

from gse.scales.lexical import LexicalScale
from gse.vectors import SparseVector, bundle, permute, SYNTACTIC_SHIFTS

class SyntacticScale:
    """
    Encoder for the Syntactic Scale (Scale 2).
    """
    
    def __init__(self, lexical_scale: LexicalScale, model: str = "en_core_web_sm"):
        self.lexical_scale = lexical_scale
        if spacy:
            try:
                self.nlp = spacy.load(model)
            except OSError:
                print(f"Warning: spaCy model '{model}' not found. Downloading...")
                from spacy.cli import download
                download(model)
                self.nlp = spacy.load(model)
        else:
            self.nlp = None
            print("Warning: spaCy not installed. Syntactic encoding will be limited.")
            
    def map_dependency_to_role(self, dep: str) -> str:
        """Map spaCy dependency label to GFS syntactic role."""
        # Simple mapping heuristic
        mapping = {
            "nsubj": "agent",
            "nsubjpass": "patient",
            "dobj": "patient",
            "iobj": "recipient",
            "pobj": "location", # approximate
            "amod": "attribute",
            "advmod": "manner",
            "aux": "auxiliary",
            "det": "determiner",
            "prep": "preposition",
            "cc": "conjunction",
            "conj": "conjunction",
            "mark": "subordinate",
            "ROOT": "root"
        }
        return mapping.get(dep, "default")
    
    def encode(self, sentence: str) -> SparseVector:
        """
        Encode a sentence into a single vector.
        """
        if not self.nlp:
            return SparseVector.zeros(8192) # or basis dimension
            
        doc = self.nlp(sentence)
        vectors = []
        
        for token in doc:
            # 1. Get lexical vector
            # Convert spaCy POS to GFS POS (optional, or just use lemma)
            # using 'noun', 'verb' etc.
            pos_map = {"NOUN": "noun", "VERB": "verb", "ADJ": "adj", "ADV": "adv"}
            gfs_pos = pos_map.get(token.pos_, "noun")
            
            word_vec = self.lexical_scale.encode(token.lemma_, gfs_pos)
            
            if not word_vec:
                continue
                
            # 2. Determine syntactic role and shift
            role = self.map_dependency_to_role(token.dep_)
            shift_amount = SYNTACTIC_SHIFTS.get(role, 0)
            
            # 3. Permute
            permuted_vec = permute(word_vec, shift_amount)
            vectors.append(permuted_vec)
            
        if not vectors:
            return SparseVector.zeros(8192)
            
        # 4. Bundle
        return bundle(vectors)
