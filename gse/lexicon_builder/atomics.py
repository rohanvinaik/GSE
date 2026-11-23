"""Compatibility entry point for sourced prime reconstruction (F148).

The old one-cell-plus-57-silences declaration proof is retired. This route and
batch builds use the same profiles, guarded laws and reading constructor.
"""

from gse.lexicon_builder.foundation import reconstruction
from gse.lexicon_builder.registry import load_rulebook


def atomic_proof(rulebook: dict | None = None, foundation: dict | None = None) -> dict:
    return reconstruction(load_rulebook() if rulebook is None else rulebook, foundation)
