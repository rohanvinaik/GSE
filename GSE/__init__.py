"""
GSE - Geometric Semantic Encoding

Functional core (deterministic, import-light):
- GSE.api      : text -> OperationTrace        (GSEEncoder)
- GSE.symbolic : OperationTrace -> typed Predicates

The v2 hyperdimensional stack (primitives_v2, vectors_v2, merkle, patterns,
scales, encoders, pipeline_v2) is auxiliary and heavier (numpy/scipy). To keep
the functional core importable without pulling that stack in, the v2 top-level
names are exposed LAZILY via PEP 562 ``__getattr__``: ``from gse import
GSEPipeline`` still works and imports on first access, but ``import GSE.api`` /
``import GSE.symbolic`` no longer eagerly drag the v2 stack (and its numpy/scipy
dependencies) into the process.

Usage:
    # functional core
    from GSE.api import GSEEncoder
    from GSE.symbolic import from_trace, resolve, evaluate_tree

    # v2 pipeline (lazy)
    from GSE import GSEPipeline
    pipeline = GSEPipeline()
    result = pipeline.encode_sentence("I feel happy")
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

__version__ = "2.0.0"

if TYPE_CHECKING:  # eager imports for static analysis / IDEs only — no runtime cost
    from GSE.encoders import SentenceStructureEncoder
    from GSE.merkle import (
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
    from GSE.patterns import (
        LearningNetwork,
        OrchestratedPipeline,
        OrchestratorNetwork,
        ParagraphScaleNetwork,
        ScaleNetworkCollection,
        SentenceScaleNetwork,
        TextScaleNetwork,
        WordScaleNetwork,
    )
    from GSE.pipeline_v2 import (
        DecompositionResult,
        EncodingResult,
        GSEPipeline,
        SimilarityResult,
    )
    from GSE.primitives_v2 import (
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
    from GSE.scales import (
        SyntacticBank,
        SyntacticPrimitive,
        SyntacticPrimitiveEncoder,
    )
    from GSE.vectors_v2 import (
        HadamardOTPBasis,
        SparseVector,
        bind,
        bundle,
        compose_decomposition,
        create_basis,
        permute,
    )

# v2 top-level name -> submodule that defines it. Exposed lazily so that
# importing the functional core (GSE.api / GSE.symbolic) does not import the
# v2 stack. Resolved on first attribute access via __getattr__ below.
_LAZY_IMPORTS = {
    # Encoders
    "SentenceStructureEncoder": "GSE.encoders",
    # Merkle tree lexicon
    "BankNode": "GSE.merkle",
    "FamilyNode": "GSE.merkle",
    "HDCFuzzyDecomposer": "GSE.merkle",
    "HubNode": "GSE.merkle",
    "LexemeNode": "GSE.merkle",
    "MerkleBellmanFord": "GSE.merkle",
    "MerkleHashChain": "GSE.merkle",
    "MerkleLexiconTree": "GSE.merkle",
    "MerkleNode": "GSE.merkle",
    "RootNode": "GSE.merkle",
    "SQLiteMerkleTranslator": "GSE.merkle",
    # Learning networks
    "LearningNetwork": "GSE.patterns",
    "OrchestratedPipeline": "GSE.patterns",
    "OrchestratorNetwork": "GSE.patterns",
    "ParagraphScaleNetwork": "GSE.patterns",
    "ScaleNetworkCollection": "GSE.patterns",
    "SentenceScaleNetwork": "GSE.patterns",
    "TextScaleNetwork": "GSE.patterns",
    "WordScaleNetwork": "GSE.patterns",
    # Main pipeline
    "DecompositionResult": "GSE.pipeline_v2",
    "EncodingResult": "GSE.pipeline_v2",
    "GSEPipeline": "GSE.pipeline_v2",
    "SimilarityResult": "GSE.pipeline_v2",
    # Primitives
    "ALL_HIERARCHY_LEVELS": "GSE.primitives_v2",
    "BIPOLAR_DIMENSIONS": "GSE.primitives_v2",
    "DIMS_PER_BANK": "GSE.primitives_v2",
    "HUB_PRIMITIVES": "GSE.primitives_v2",
    "N_BANKS": "GSE.primitives_v2",
    "PRIMITIVE_FAMILIES": "GSE.primitives_v2",
    "SEMANTIC_BANK_NAMES": "GSE.primitives_v2",
    "SEMANTIC_ROLES": "GSE.primitives_v2",
    "D": "GSE.primitives_v2",
    "SemanticBank": "GSE.primitives_v2",
    "get_bank_primitives": "GSE.primitives_v2",
    "get_dimension_range": "GSE.primitives_v2",
    # Syntactic structure
    "SyntacticBank": "GSE.scales",
    "SyntacticPrimitive": "GSE.scales",
    "SyntacticPrimitiveEncoder": "GSE.scales",
    # Vectors
    "HadamardOTPBasis": "GSE.vectors_v2",
    "SparseVector": "GSE.vectors_v2",
    "bind": "GSE.vectors_v2",
    "bundle": "GSE.vectors_v2",
    "compose_decomposition": "GSE.vectors_v2",
    "create_basis": "GSE.vectors_v2",
    "permute": "GSE.vectors_v2",
}

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


def __getattr__(name: str) -> Any:
    """PEP 562 lazy attribute access for the v2 stack (see module docstring)."""
    module = _LAZY_IMPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(module), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
