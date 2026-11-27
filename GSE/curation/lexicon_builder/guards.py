"""Typed facts about readings that select a law's scope (design E2).

A guard is a fact about the reading itself, established by a source and a warrant, never by the law it selects.
Only guards with a warrant are computed here; a guard without one selects no reading, so its law stays idle rather
than firing on a guess.

- `own_role=lexical_predicate`: the reading is a verb (its native part of speech). A verb's head is a predicate,
  not a substantive (F144: the approved head priors).
- `own_role=modifier_property_only`: the reading is an adjective. F088: "adjectives can't be 'things' because they
  are inherently modifiers, they lack independent objectness".
- `own_role=substantive` with `lexical_unit_kind=PRIME`: the reading is an authored substantive prime.

The source lenses (`projection.py`) establish the rest, each from a bound source observation. These are
`own_predicate=physical_change_of_place` from a VerbNet motion predicate on an exact sense key, and the reading
facts of a USAS and FrameNet source rule. The latter hold only where the lemma and part of speech have one reading.
`scopes` takes them as `facts` and adds them to the guards computed here.
"""

from __future__ import annotations

import numpy as np

VERB = {"verb", "v"}
ADJECTIVE = {"adj", "adjective", "a", "s"}
SUBSTANTIVE_PRIMES = {"i", "you", "someone", "something", "people", "body", "kinds", "parts"}


def _role(readings) -> dict[str, np.ndarray]:
    pos = np.array([r.pos.lower() for r in readings])
    return {
        "own_role=lexical_predicate": np.isin(pos, list(VERB)),
        "own_role=modifier_property_only": np.isin(pos, list(ADJECTIVE)),
    }


def _prime_substantives(readings) -> np.ndarray:
    return np.array(
        [r.source in {"nsm_chart", "gse_closed_class"} and r.lemma.lower() in SUBSTANTIVE_PRIMES for r in readings]
    )


def scopes(readings, wanted, facts=None) -> dict[str, np.ndarray]:
    """A boolean mask over readings for every scope name in `wanted`; unwarranted guards select nothing.

    `facts` maps a guard name to the readings a source lens established it for (`LensOutput.facts`). A reading is
    in a scope when this module or a lens establishes the guard for it.
    """
    known = _role(readings)
    known["lexical_unit_kind=PRIME&own_role=substantive"] = _prime_substantives(readings)
    for name, mask in (facts or {}).items():
        known[name] = known[name] | mask if name in known else mask.copy()
    n = len(readings)
    return {name: known.get(name, np.zeros(n, dtype=bool)) for name in wanted}
