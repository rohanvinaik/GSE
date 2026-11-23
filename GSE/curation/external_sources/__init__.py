"""
External Lexical Resources Integration

Parse external lexicons and map to GSE primitives:
- SentiWordNet: GOOD/BAD valence
- NRC EmoLex: Emotion dimensions -> MENTAL primitives
- NRC VAD: Valence/Arousal/Dominance -> INTENSITY, evaluators
- VerbNet: Thematic roles -> entity/action primitives
- Concreteness: Abstract vs concrete -> THING/THINK distinction
- Lancaster Sensorimotor: Perceptual/motor -> BODY, SENSE primitives
- FrameNet: Semantic frames -> role-based primitives
- PropBank: Argument structures -> verb semantics
- WordNet Hierarchy: Taxonomic relations -> category primitives
- Wiktionary: Definitions/etymology -> multi-source primitives
- ConceptNet: Commonsense relations -> relational primitives

Cross-validation:
- ExternalSourcesComparator: Compare LLM vs external sources, flag disagreements
- ExternalSourcesIntegrator: Aggregate primitives from multiple sources
"""

# Base class
from GSE.curation.external_sources.base_parser import BaseExternalParser, ParserConfig
from GSE.curation.external_sources.comparator import ExternalSourcesComparator
from GSE.curation.external_sources.conceptnet import ConceptNetParser
from GSE.curation.external_sources.concreteness import ConcretenessParser

# New parsers
from GSE.curation.external_sources.framenet import FrameNetParser

# Aggregators
from GSE.curation.external_sources.integrator import ExternalSourcesIntegrator
from GSE.curation.external_sources.lancaster_sensorimotor import LancasterSensorimotorParser
from GSE.curation.external_sources.nrc_emotion import NRCEmotionParser
from GSE.curation.external_sources.nrc_vad import NRCVADParser
from GSE.curation.external_sources.propbank import PropBankParser

# Existing parsers
from GSE.curation.external_sources.sentiwordnet import SentiWordNetParser
from GSE.curation.external_sources.verbnet import VerbNetParser
from GSE.curation.external_sources.wiktionary import WiktionaryParser
from GSE.curation.external_sources.wordnet_hierarchy import WordNetHierarchyParser

__all__ = [
    # Base
    "BaseExternalParser",
    "ParserConfig",
    # Existing parsers
    "SentiWordNetParser",
    "NRCEmotionParser",
    "NRCVADParser",
    "VerbNetParser",
    "ConcretenessParser",
    "LancasterSensorimotorParser",
    # New parsers
    "FrameNetParser",
    "PropBankParser",
    "WordNetHierarchyParser",
    "WiktionaryParser",
    "ConceptNetParser",
    # Aggregators
    "ExternalSourcesIntegrator",
    "ExternalSourcesComparator",
]
