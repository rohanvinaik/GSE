"""
A word's E/P/A coordinates: its prime signature projected through one per-pole table (#157).

Register, the second meaning channel (M5, NARRATIVE_MEANING.md), reads where a sentence's projection lifts above its
document's baseline. The projection was kept as copies, in SparseWiki (``src/wiki_grounding/epa.py``) and
personal-wiki (``gse_layer.py``), with weights per prime as stored. A bipolar pair stored on either pole then read
differently: DEAD +1 gave A -1, while the same meaning stored as ALIVE -1 gave A -0.3. This is the one law. Its
weights are keyed by POLE (the canonical prime and its sign), with today's values exactly, so a row's storage form,
and canonical form (#55) rewriting it, move no coordinate.

E is the one valence law (:func:`gse.primitives_v2.literal_valence`) alone. The copies also gave FEEL +0.2 on E, but a
bare FEEL encodes no evaluation, so under the literal-valence ruling that share is dropped and FEEL projects onto A only
(Rohan, 2026-10-05 00:21 UTC). P and A come from the hand weights the copies carried (Rohan, 2026-10-04 22:55 UTC: "Add
in A and P"). The projection is a function of the 72
primes, inside the basis; it is not the NRC-VAD potency and arousal held under #12. How a measure aggregates it (a
mean over projecting words, a sum, a baseline and lift) is the measure's definition, not this module's.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from gse.primitives_v2 import get_canonical_pole, literal_valence

# (canonical prime, sign) -> axis weights. The evaluation dimension (GOOD/BAD) is not here: E is literal_valence.
EPA_POLES: Dict[Tuple[str, int], Dict[str, float]] = {
    ("BIG", 1): {"P": 1.0},
    ("BIG", -1): {"P": -1.0},
    ("ALIVE", 1): {"A": 0.3},
    ("ALIVE", -1): {"A": -1.0},  # DEAD
    ("CAN", 1): {"P": 0.5},
    ("CAN", -1): {"P": -0.5},
    ("MUST", 1): {"P": -0.3},
    ("MUST", -1): {"P": 0.3},
    ("DO", 1): {"A": 1.0},
    ("DO", -1): {"A": -1.0},
    ("MOVE", 1): {"A": 0.8},
    ("MOVE", -1): {"A": -0.8},
    ("HAPPEN", 1): {"A": 0.5},
    ("HAPPEN", -1): {"A": -0.5},
    ("WANT", 1): {"A": 0.3, "P": 0.2},
    ("WANT", -1): {"A": -0.3, "P": -0.2},
    ("THINK", 1): {"A": 0.2},
    ("THINK", -1): {"A": -0.2},
    ("FEEL", 1): {"A": 0.2},
    ("FEEL", -1): {"A": -0.2},
}


def epa_projection(signature: Dict[str, int]) -> Optional[Dict[str, float]]:
    """A word's ``{"E", "P", "A"}`` coordinates, or None when no prime of its signature projects.

    None is an abstention, distinct from a word that projects to zero: a measure counts only the words that project.
    """
    totals = {"E": float(literal_valence(signature)), "P": 0.0, "A": 0.0}
    projects = False
    for primitive, value in signature.items():
        canonical, pole = get_canonical_pole(primitive)
        if not value:
            continue
        if canonical == "GOOD":
            projects = True  # carries the evaluation dimension, even where its poles net to zero
            continue
        weights = EPA_POLES.get((canonical, pole if value > 0 else -pole))
        if weights:
            projects = True
            for axis, weight in weights.items():
                totals[axis] += weight
    return totals if projects else None
