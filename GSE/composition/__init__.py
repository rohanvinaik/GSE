"""
Layer 2: Composition - HDC operations on resolved structures.

Design principles:
- Takes parsed graph from Layer 3 as input
- Applies operator modifications to atomic vectors
- Binds each node to its syntactic role
- Bundles into sentence-level HDC vector
"""

from .composer import SemanticComposer

__all__ = ["SemanticComposer"]
