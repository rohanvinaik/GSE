"""
GSE - Geometric Semantic Encoding

Functional core (deterministic, import-light):
- gse.api      : text -> OperationTrace        (GSEEncoder)
- gse.symbolic : OperationTrace -> typed Predicates

The v2 hyperdimensional stack (primitives_v2, vectors_v2, merkle, patterns,
scales, encoders, pipeline_v2) is auxiliary and heavier (numpy/scipy). To keep
the functional core importable without pulling that stack in, the v2 top-level
names are exposed LAZILY via PEP 562 ``__getattr__``: ``from gse import
GSEPipeline`` still works and imports on first access, but ``import gse.api`` /
``import gse.symbolic`` no longer eagerly drag the v2 stack (and its numpy/scipy
dependencies) into the process.

Usage:
    # functional core
    from gse.api import GSEEncoder
    from gse.symbolic import from_trace, resolve, evaluate_tree

    # v2 pipeline (lazy)
    from gse import GSEPipeline
    pipeline = GSEPipeline()
    result = pipeline.encode_sentence("I feel happy")
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

__version__ = "2.0.0"

if TYPE_CHECKING:  # eager imports for static analysis / IDEs only — no runtime cost
    from gse.encoders import SentenceStructureEncoder
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

# v2 top-level name -> submodule that defines it. Exposed lazily so that
# importing the functional core (gse.api / gse.symbolic) does not import the
# v2 stack. Resolved on first attribute access via __getattr__ below.
_LAZY_IMPORTS = {
    # Encoders
    "SentenceStructureEncoder": "gse.encoders",
    # Merkle tree lexicon
    "BankNode": "gse.merkle",
    "FamilyNode": "gse.merkle",
    "HDCFuzzyDecomposer": "gse.merkle",
    "HubNode": "gse.merkle",
    "LexemeNode": "gse.merkle",
    "MerkleBellmanFord": "gse.merkle",
    "MerkleHashChain": "gse.merkle",
    "MerkleLexiconTree": "gse.merkle",
    "MerkleNode": "gse.merkle",
    "RootNode": "gse.merkle",
    "SQLiteMerkleTranslator": "gse.merkle",
    # Learning networks
    "LearningNetwork": "gse.patterns",
    "OrchestratedPipeline": "gse.patterns",
    "OrchestratorNetwork": "gse.patterns",
    "ParagraphScaleNetwork": "gse.patterns",
    "ScaleNetworkCollection": "gse.patterns",
    "SentenceScaleNetwork": "gse.patterns",
    "TextScaleNetwork": "gse.patterns",
    "WordScaleNetwork": "gse.patterns",
    # Main pipeline
    "DecompositionResult": "gse.pipeline_v2",
    "EncodingResult": "gse.pipeline_v2",
    "GSEPipeline": "gse.pipeline_v2",
    "SimilarityResult": "gse.pipeline_v2",
    # Primitives
    "ALL_HIERARCHY_LEVELS": "gse.primitives_v2",
    "BIPOLAR_DIMENSIONS": "gse.primitives_v2",
    "DIMS_PER_BANK": "gse.primitives_v2",
    "HUB_PRIMITIVES": "gse.primitives_v2",
    "N_BANKS": "gse.primitives_v2",
    "PRIMITIVE_FAMILIES": "gse.primitives_v2",
    "SEMANTIC_BANK_NAMES": "gse.primitives_v2",
    "SEMANTIC_ROLES": "gse.primitives_v2",
    "D": "gse.primitives_v2",
    "SemanticBank": "gse.primitives_v2",
    "get_bank_primitives": "gse.primitives_v2",
    "get_dimension_range": "gse.primitives_v2",
    # Syntactic structure
    "SyntacticBank": "gse.scales",
    "SyntacticPrimitive": "gse.scales",
    "SyntacticPrimitiveEncoder": "gse.scales",
    # Vectors
    "HadamardOTPBasis": "gse.vectors_v2",
    "SparseVector": "gse.vectors_v2",
    "bind": "gse.vectors_v2",
    "bundle": "gse.vectors_v2",
    "compose_decomposition": "gse.vectors_v2",
    "create_basis": "gse.vectors_v2",
    "permute": "gse.vectors_v2",
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
