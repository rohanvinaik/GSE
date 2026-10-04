"""
GSE Merkle Tree Module

Provides:
- MerkleLexiconTree: 5-level tree for lexicon organization
- Node types: RootNode, BankNode, FamilyNode, HubNode, LexemeNode
- MerkleHashChain: SHA-256 hash chain utilities
- MembershipProof, DifferenceProof: Verification utilities
- MerkleBellmanFord: Semantic routing through tree
- HDCFuzzyDecomposer: New word decomposition
- SQLiteMerkleTranslator: Database persistence
"""

from gse.merkle.decomposer import (
    PREFIX_PATTERNS,
    SUFFIX_PATTERNS,
    DecompositionResult,
    HDCFuzzyDecomposer,
)
from gse.merkle.hash_chain import (
    DifferenceProof,
    MembershipProof,
    MerkleHashChain,
)
from gse.merkle.learning_bridge import (
    FamilyAffinityMatrix,
    KLinePattern,
    KLineStore,
    MerkleLearningBridge,
)
from gse.merkle.nodes import (
    BankNode,
    FamilyNode,
    HubNode,
    LexemeNode,
    MerkleNode,
    RootNode,
    create_bank_node,
    create_family_node,
    create_hub_node,
)
from gse.merkle.router import (
    FamilyCentroid,
    MerkleBellmanFord,
    RouteResult,
    find_semantic_path,
    semantic_distance,
)
from gse.merkle.translator import (
    SQLiteMerkleTranslator,
    migrate_legacy_lexicon,
)
from gse.merkle.tree import MerkleLexiconTree

__all__ = [
    # Nodes
    "MerkleNode",
    "RootNode",
    "BankNode",
    "FamilyNode",
    "HubNode",
    "LexemeNode",
    # Factory functions
    "create_bank_node",
    "create_family_node",
    "create_hub_node",
    # Hash utilities
    "MerkleHashChain",
    "MembershipProof",
    "DifferenceProof",
    # Tree
    "MerkleLexiconTree",
    # Router
    "MerkleBellmanFord",
    "RouteResult",
    "FamilyCentroid",
    "semantic_distance",
    "find_semantic_path",
    # Decomposer
    "HDCFuzzyDecomposer",
    "DecompositionResult",
    "PREFIX_PATTERNS",
    "SUFFIX_PATTERNS",
    # Translator
    "SQLiteMerkleTranslator",
    "migrate_legacy_lexicon",
    # Learning Bridge
    "MerkleLearningBridge",
    "FamilyAffinityMatrix",
    "KLineStore",
    "KLinePattern",
]
