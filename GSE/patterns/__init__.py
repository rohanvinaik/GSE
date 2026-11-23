"""
GSE Patterns Module (v2)

Provides scale-specific learning networks:
- TextScaleNetwork: Genre, register, domain patterns
- ParagraphScaleNetwork: RST discourse relations
- SentenceScaleNetwork: Syntactic structure patterns
- WordScaleNetwork: Semantic primitive co-occurrence
- ScaleNetworkCollection: Unified interface for all scales
- OrchestratorNetwork: Cross-scale coordination
- OrchestratedPipeline: Complete processing pipeline
"""

from .klines import KLine, KLineStore
from .networks_v2 import (
    PARAGRAPH_PRIMITIVES,
    SENTENCE_PRIMITIVES,
    TEXT_PRIMITIVES,
    WORD_PRIMITIVES,
    LearningNetwork,
    ParagraphScaleNetwork,
    ScaleNetworkCollection,
    SentenceScaleNetwork,
    TextScaleNetwork,
    WordScaleNetwork,
)
from .orchestrator import (
    COMB_NODES,
    CONF_NODES,
    CTX_NODES,
    ERR_NODES,
    SCALE_NODES,
    TASK_NODES,
    OrchestratedPipeline,
    OrchestratorNetwork,
    OrchestratorNode,
    ProcessingContext,
)

__all__ = [
    # Networks
    "LearningNetwork",
    "TextScaleNetwork",
    "ParagraphScaleNetwork",
    "SentenceScaleNetwork",
    "WordScaleNetwork",
    "ScaleNetworkCollection",
    # Primitives
    "TEXT_PRIMITIVES",
    "PARAGRAPH_PRIMITIVES",
    "SENTENCE_PRIMITIVES",
    "WORD_PRIMITIVES",
    # Orchestrator
    "OrchestratorNetwork",
    "OrchestratorNode",
    "OrchestratedPipeline",
    "ProcessingContext",
    "SCALE_NODES",
    "TASK_NODES",
    "CONF_NODES",
    "COMB_NODES",
    "ERR_NODES",
    "CTX_NODES",
    # K-lines
    "KLine",
    "KLineStore",
]
