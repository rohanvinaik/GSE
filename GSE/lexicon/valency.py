"""The predicates whose bearer must be a person or creature, read from the reviewed prime profiles (runtime side).

The October-reviewed prime profiles (``GSE/curation/lexicon_builder/prime_profiles.json``, read here as data so the
runtime imports no construction code) type each prime's arguments (``REQUIRES_ARGUMENT``). A lexical-predicate prime
whose first, bearer slot is typed exactly ``person`` can be predicated only of someone; Goddard (2018) widens that to
creatures. A prime is kept out when NSM's own texts give it a thing as subject: HAVE ("it has two parts" of a bird's
beak, G18 line 255; the snake's body, line 358). Used by the construction layer (``valency_absence``) and the runtime's
sentence selection (``GSE.symbolic.clause_selection``).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PROFILES = Path(__file__).resolve().parents[1] / "curation" / "lexicon_builder" / "prime_profiles.json"
THING_SUBJECT_ATTESTED = {"HAVE": ("G18 birds line 255", "G18 snakes line 358")}


@lru_cache(maxsize=1)
def person_bearer_primes() -> tuple[str, ...]:
    """Lexical-predicate primes whose reviewed bearer slot is ``person``, less those NSM attests with a thing subject.
    These primes are positive-pole and are their own bank."""
    out = set()
    for profile in json.loads(PROFILES.read_text())["profiles"]:
        heads = {c.get("value") for c in profile["claims"] if c["kind"] == "CLASSIFIES_HEAD"}
        slots = next((c.get("slots") for c in profile["claims"] if c["kind"] == "REQUIRES_ARGUMENT"), None) or []
        if "lexical_predicate" in heads and slots and slots[0].split(":", 1)[1] == "person":
            if profile["prime"] not in THING_SUBJECT_ATTESTED:
                out.add(profile["prime"])
    return tuple(sorted(out))
