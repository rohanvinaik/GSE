"""
GSE Teaching System - Hebbian Learning from Corpus

Provides components for teaching the learning networks from text corpora:
- FeatureExtractor: Extract scale-appropriate features from GSE traces
- NetworkTeacher: Epoch-based teaching with behavior tracking
- ConversationProcessor: Handle large Claude/GPT conversation JSON files
"""

from GSE.teaching.conversation_processor import ConversationProcessor
from GSE.teaching.feature_extractor import FeatureExtractor
from GSE.teaching.teacher import NetworkTeacher, TeachingEpoch, TeachingSession

__all__ = [
    "FeatureExtractor",
    "NetworkTeacher",
    "TeachingEpoch",
    "TeachingSession",
    "ConversationProcessor",
]
