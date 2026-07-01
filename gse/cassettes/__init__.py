"""Cassettes — domain-portable experts that resolve an in-frame uncertainty using OUT-OF-FRAME,
multi-scale context. GSE is the player; a cassette is the tape.

A cassette reads the LITERAL RAW TEXT through GSE's existing multi-scale grounding (a
``MultiScaleDoc``) and answers ONE focused question under the SymbolicSpellCheck discipline: trigger
only on a genuine gap, propose from higher scales, ground every candidate, score by orthogonal
strands, commit on a decisive margin or abstain — never destroying a correct value. Loaded cassettes'
committed resolutions compose into the cheat-sheet, which with the literal pipeline produces clean
Innerese. Domain-portable: swap the deck per domain.

See ``~/Genesis/docs/CASSETTE_ARCHITECTURE_DESIGN_BRIEF.md``.
"""
from __future__ import annotations

from .base import Cassette, Resolution, Scored
from .deck import CassetteDeck, CheatEntry, DeckResult
from .entity_identity import EntityIdentity, IdentityGap
from .cheatsheet import (CheatSheet, build_cheatsheet, build_relabel_map,
                         correct_contracts, make_merge_repair)
from .multiscale import Mention, MultiScaleDoc
from .person_validation import PersonGap, PersonValidation
from .relational_identity import RelationalIdentity

__all__ = [
    "MultiScaleDoc", "Mention",
    "Cassette", "Resolution", "Scored",
    "EntityIdentity", "IdentityGap",
    "PersonValidation", "PersonGap",
    "RelationalIdentity",
    "CassetteDeck", "CheatEntry", "DeckResult",
    "CheatSheet", "build_cheatsheet", "correct_contracts",
    "build_relabel_map", "make_merge_repair",
]
