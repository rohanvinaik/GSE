"""
GSE Orchestration Module (v2)

Provides cross-scale coordination via patterns/orchestrator.py
See GSE.patterns.OrchestratorNetwork for the v2 orchestration system.
"""

# v2 orchestration is in patterns module
from GSE.patterns import OrchestratedPipeline, OrchestratorNetwork, ProcessingContext

__all__ = ["OrchestratorNetwork", "OrchestratedPipeline", "ProcessingContext"]
