"""GSE pragmatics — the Janus two-faced figure layer (irony, metaphor, the appeals…).

A figure is recognized by comparing a *deductive* symbolic read (Face A) against an
*inductive* learned read (Face B), both over the same GSE relational profile. See
``docs/JANUS_FIGURE_SYSTEM.md`` (the build) and ``docs/JANUS_MODULE_DESIGN.md`` (the
two-faced comparator).
"""

from gse.pragmatics.figures import (
    BANKS,
    BY_NAME,
    FIGURE_NAMES,
    FIGURES,
    Figure,
    appeals,
    enum_for_bank,
    figures_in_bank,
    is_gated,
    tropes,
    with_supertypes,
)

__all__ = [
    "BANKS",
    "BY_NAME",
    "FIGURE_NAMES",
    "FIGURES",
    "Figure",
    "appeals",
    "enum_for_bank",
    "figures_in_bank",
    "is_gated",
    "tropes",
    "with_supertypes",
]
