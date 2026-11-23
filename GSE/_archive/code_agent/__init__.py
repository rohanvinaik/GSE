#!/usr/bin/env python3
"""
GSE Code Agent Module

Geometric Semantic Encoding for LLM Coding Agent Prompting.
Provides intent detection, semantic matching, and action routing
for coding agent "voice mode" interactions.
"""

from gse.code_agent.primitives import (
    CodeIntent,
    CodeDomain,
    CodeAction,
    CODE_INTENT_PRIMITIVES,
    CODE_DOMAIN_PRIMITIVES,
    CODE_ACTION_PRIMITIVES,
    ALL_CODE_PRIMITIVES,
)
from gse.code_agent.networks import (
    CodeAgentNetwork,
    IntentNetwork,
    DomainNetwork,
    ActionNetwork,
)
from gse.code_agent.trainer import CodeAgentTrainer
from gse.code_agent.detector import IntentDetector

__all__ = [
    # Primitives
    "CodeIntent",
    "CodeDomain",
    "CodeAction",
    "CODE_INTENT_PRIMITIVES",
    "CODE_DOMAIN_PRIMITIVES",
    "CODE_ACTION_PRIMITIVES",
    "ALL_CODE_PRIMITIVES",
    # Networks
    "CodeAgentNetwork",
    "IntentNetwork",
    "DomainNetwork",
    "ActionNetwork",
    # Training
    "CodeAgentTrainer",
    # Detection
    "IntentDetector",
]
