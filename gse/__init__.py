"""
GSE - Geometric Semantic Encoding (v2)

A hyperdimensional computing framework for semantic representation featuring:
- 8192-D sparse ternary vectors with Hadamard-OTP encoding
- 10 bipolar dimensions with exact antonym opposition (cosine = -1.0)
- Hierarchical quantity/intensity modifiers
- 5-level Merkle tree lexicon with O(42 + L/17) routing
- Scale-specific learning networks with Hebbian adaptation
- D/N sentence encoding for position recovery

Core Modules:
- primitives_v2: 8 semantic banks, ~45 primitives
- vectors_v2: Hadamard-OTP sparse vector operations
- merkle: Tree-structured lexicon with SHA-256 verification
- patterns: Scale-specific learning networks
- scales: Syntactic structure encoding
- encoders: D/N positional sentence encoding
- pipeline_v2: Complete processing pipeline

Usage:
    from gse import GSEPipeline

    pipeline = GSEPipeline()
    pipeline.add_word("happy", "ADJ", [("GOOD", "evaluation", 1), ("FEEL", "state", 1)])
    result = pipeline.encode_sentence("I feel happy")
"""

__version__ = "2.0.0"

# Core primitives and vectors
# Encoders
from gse.encoders import (
    SentenceStructureEncoder,
)

# Merkle tree lexicon
from gse.merkle import (
    BankNode,
    FamilyNode,
    HDCFuzzyDecomposer,
    HubNode,
    LexemeNode,
    MerkleBellmanFord,
    MerkleHashChain,
    MerkleLexiconTree,
    MerkleNode,
    RootNode,
    SQLiteMerkleTranslator,
)

# Learning networks
from gse.patterns import (
    LearningNetwork,
    OrchestratedPipeline,
    OrchestratorNetwork,
    ParagraphScaleNetwork,
    ScaleNetworkCollection,
    SentenceScaleNetwork,
    TextScaleNetwork,
    WordScaleNetwork,
)

# Main pipeline
from gse.pipeline_v2 import (
    DecompositionResult,
    EncodingResult,
    GSEPipeline,
    SimilarityResult,
)
from gse.primitives_v2 import (
    ALL_HIERARCHY_LEVELS,
    BIPOLAR_DIMENSIONS,
    DIMS_PER_BANK,
    HUB_PRIMITIVES,
    N_BANKS,
    PRIMITIVE_FAMILIES,
    SEMANTIC_BANK_NAMES,
    SEMANTIC_ROLES,
    D,
    SemanticBank,
    get_bank_primitives,
    get_dimension_range,
)

# Syntactic structure
from gse.scales import (
    SyntacticBank,
    SyntacticPrimitive,
    SyntacticPrimitiveEncoder,
)
from gse.vectors_v2 import (
    HadamardOTPBasis,
    SparseVector,
    bind,
    bundle,
    compose_decomposition,
    create_basis,
    permute,
)

__all__ = [
    # Version
    "__version__",
    # Dimensions
    "D",
    "N_BANKS",
    "DIMS_PER_BANK",
    # Semantic banks
    "SemanticBank",
    "SEMANTIC_BANK_NAMES",
    "BIPOLAR_DIMENSIONS",
    "HUB_PRIMITIVES",
    "SEMANTIC_ROLES",
    "ALL_HIERARCHY_LEVELS",
    "get_dimension_range",
    "get_bank_primitives",
    "PRIMITIVE_FAMILIES",
    # Vectors
    "SparseVector",
    "HadamardOTPBasis",
    "create_basis",
    "compose_decomposition",
    "bind",
    "bundle",
    "permute",
    # Merkle tree
    "MerkleLexiconTree",
    "MerkleNode",
    "RootNode",
    "BankNode",
    "FamilyNode",
    "HubNode",
    "LexemeNode",
    "MerkleHashChain",
    "MerkleBellmanFord",
    "HDCFuzzyDecomposer",
    "SQLiteMerkleTranslator",
    # Learning networks
    "LearningNetwork",
    "TextScaleNetwork",
    "ParagraphScaleNetwork",
    "SentenceScaleNetwork",
    "WordScaleNetwork",
    "ScaleNetworkCollection",
    "OrchestratorNetwork",
    "OrchestratedPipeline",
    # Syntactic
    "SyntacticPrimitive",
    "SyntacticBank",
    "SyntacticPrimitiveEncoder",
    # Encoders
    "SentenceStructureEncoder",
    # Pipeline
    "GSEPipeline",
    "EncodingResult",
    "SimilarityResult",
    "DecompositionResult",
]
