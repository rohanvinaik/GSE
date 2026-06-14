"""
GSE Verification Suite.

Provides comprehensive tests proving the GSE system works:
- Reproducibility (deterministic encoding)
- Similarity preservation (similar meanings -> similar vectors)
- Antonym relationships (bipolar vs semantic antonyms)
- Entity recovery (extract subjects/objects from vectors)
- Attribute extraction (GOOD/BAD/BIG/SMALL)
- Operator antisymmetry (argument order matters)
"""

from gse.verification.proof_suite import GSEProofSuite

__all__ = ["GSEProofSuite"]
