"""Lexicon curation, and the parts of the runtime lexicon that live beside it.

The lexicon builder (``lexicon_builder``), its sources (``external_sources``) and
its command line (``cli``) build definition databases offline. The runtime lexicon's
schema, protected dictionary (``personal_dictionary``) and frequency integration live
here too, as does the older flat-lexicon builder (``lexicon_db``, ``build_clean_*``).

The names exported below load on first use (PEP 562), so importing one runtime
module, such as the protected dictionary, does not load a builder.
"""

from importlib import import_module
from typing import TYPE_CHECKING

from GSE.curation.schema import (
    ALL_PRIMITIVES,
    BIPOLAR_PAIRS,
    CERTAINTY_HIERARCHY,
    INTENSITY_HIERARCHY,
    PRIMITIVE_TO_BANK,
    QUANTITY_HIERARCHY,
    SCHEMA,
)

if TYPE_CHECKING:
    from GSE.curation.frequency_integration import FrequencyDatabase, FrequencyIntegration, WordFrequency
    from GSE.curation.lexicon_db import LexemeEntry, LexiconDatabase

_LAZY = {
    "FrequencyDatabase": "GSE.curation.frequency_integration",
    "FrequencyIntegration": "GSE.curation.frequency_integration",
    "WordFrequency": "GSE.curation.frequency_integration",
    "LexemeEntry": "GSE.curation.lexicon_db",
    "LexiconDatabase": "GSE.curation.lexicon_db",
}


def __getattr__(name: str):
    if name not in _LAZY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(_LAZY[name]), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_LAZY))


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
