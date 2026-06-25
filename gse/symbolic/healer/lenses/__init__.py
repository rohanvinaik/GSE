"""The roster — the full slate of law-grounded specialists (intelligent design, built whole).

The eight Tier-2 structural-failure laws, derived from the full-corpus defect taxonomy
(see ``docs/SPINE_SOCIETY_DESIGN.md``), in claim-priority order. Each lens is carved one-shot from
its near-miss minimal pairs and appended here as its law lands; the order matters only where two
territories could touch (more-specific law first). What no lens claims falls to the chum bucket.

  copula_predicate    — copula + predicate-adjective miscast as EVENT{adj} → TYPE_ASSERT
  matrix_collapse     — finite matrix verb lost, clause collapsed to a CONTRAST/EQUALITY stub
  participial_adjunct — secondary-predicate participle mis-segmented as a coordinate clause
  infinitival_control — infinitival complement dropped → recover CONTROL
  embedded_clause     — that/WH complement collapsed to a query stub (mostly abstain)
  attribution_say     — speech-frame residue
  vp_coord_conjunct   — VP-coordination distribution
  deictic_bind        — regulatory: unbound I/you/narrator (the ±2-line window)
"""
from __future__ import annotations

from typing import List

from ..lens import Lens
from .copula_predicate import CopulaPredicate
from .infinitival_control import InfinitivalControl
from .participial import ParticipialAdjunct
from .vp_coord import VpCoord


def default_roster() -> List[Lens]:
    """The live slate — the FORMAL audited laws: clean, accurate rules only. An empty roster is
    inert; what no lens claims = chum bucket.

    LAW KINDS (2026-06-24). TRANSFORM/FILTER laws rewrite or validate an EXISTING node (L1 copula→
    TYPE_ASSERT) — clean. RECOVER-AND-ATTACH laws reconstruct a MISSING predication and bind a subject
    (L3 participial, L7 vp_coord). Their old wall was subject-ATTACHMENT (~50%); it is **un-bucketed by
    LAYER 2**: the Society's phase-0 fold-reader resolves an entity's document-scale SIGNIFICANCE, and
    ``fold_reader.best_subject`` anchors the recovery on the recurring protagonist ("shape from the
    field") with a CONFIDENCE GATE that ABSTAINS (clean-or-hole) when no recurring agent is available —
    never falling back to the global topic (the compaction-paper §4.1 false-spine trap). Validated @
    corpus scale: participial fires resolve to real character subjects; the residual (POS-mistag/one-shot
    subjects) is low-significance → dropped by the compaction spread-cut, and is K-line TRAINING territory."""
    roster: List[Lens] = [
        CopulaPredicate(),       # L1 — predicate-adjective under a copula → TYPE_ASSERT (transform; clean)
        VpCoord(),               # L7 — VP-coordination distribution (revived; fold-reinforced subject)
        ParticipialAdjunct(),    # L3 — participial adjunct (revived; best_subject by significance) [additive, phase 2]
        InfinitivalControl(),    # L4 — dropped `to <verb>` infinitival → EVENT(controller, …) [additive, phase 2]
        # L5 embedded_clause + L6 attribution_say: NOT lenses — already handled upstream (L5: collapsed
        # queries yield 0 predicates via _collect_predicates; L6: the intake speech-split). See memory.
    ]
    return roster
