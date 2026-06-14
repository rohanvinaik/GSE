"""
GSE Curation Module - Lexicon Builder

Build and curate semantic decompositions for the GSE lexicon.
Supports full 72-primitive decomposition with validation.

Usage:
    from gse.curation import LexiconDatabase, StagedBuilder

    db = LexiconDatabase("lexicon.db")
    builder = StagedBuilder(db)
    builder.build_phase_one()

CLI Usage:
    python -m gse.curation.cli.commands build --phases 1
    python -m gse.curation.cli.commands status
    python -m gse.curation.cli.commands lookup happy
"""

from gse.curation.frequency_integration import (
    FrequencyDatabase,
    FrequencyIntegration,
    WordFrequency,
)
from gse.curation.lexicon_db import LexemeEntry, LexiconDatabase
from gse.curation.schema import (
    ALL_PRIMITIVES,
    BIPOLAR_PAIRS,
    CERTAINTY_HIERARCHY,
    INTENSITY_HIERARCHY,
    PRIMITIVE_TO_BANK,
    QUANTITY_HIERARCHY,
    SCHEMA,
)

__all__ = [
    # Schema
    "SCHEMA",
    "ALL_PRIMITIVES",
    "BIPOLAR_PAIRS",
    "PRIMITIVE_TO_BANK",
    "QUANTITY_HIERARCHY",
    "INTENSITY_HIERARCHY",
    "CERTAINTY_HIERARCHY",
    # Database
    "LexiconDatabase",
    "LexemeEntry",
    # Frequency
    "FrequencyIntegration",
    "FrequencyDatabase",
    "WordFrequency",
]
