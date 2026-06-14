"""
Merkle Navigator (Cache)

Provides content-addressable storage for GFS states.
Used to cache partial results (vectors, graphs) and detect state changes.
"""

import hashlib
import json
import pickle
from typing import Any, Dict, Optional

class MerkleNavigator:
    """
    Cache system using Merkle hashes for state tracking.
    """
    
    def __init__(self):
        self._store: Dict[str, Any] = {}
        
    def compute_hash(self, obj: Any) -> str:
        """Compute SHA-256 hash of a Python object."""
        if isinstance(obj, (dict, list, tuple, str, int, float, bool, type(None))):
             # JSON serializable
             try:
                 encoded = json.dumps(obj, sort_keys=True).encode('utf-8')
             except TypeError:
                 # Fallback to pickle
                 encoded = pickle.dumps(obj)
        else:
             encoded = pickle.dumps(obj)
             
        return hashlib.sha256(encoded).hexdigest()
        
    def put(self, obj: Any) -> str:
        """Store object and return its hash."""
        h = self.compute_hash(obj)
        self._store[h] = obj
        return h
        
    def get(self, h: str) -> Optional[Any]:
        """Retrieve object by hash."""
        return self._store.get(h)
        
    def exists(self, h: str) -> bool:
        return h in self._store
