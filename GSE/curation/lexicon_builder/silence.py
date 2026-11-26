"""Reading the lexicon under the four-state contract (Rohan, F118: "0 is explicit absence; empty is silence").

Two things a build needs before any cell can be silent:

- **Starting domains** (F040: "Use only 0/+1 for unpaired primes"). A bipolar bank starts at {EMPTY, -1, 0, +1}; an
  unpaired bank at {EMPTY, 0, +1}. WANT is signed: the release's founder ``want_polarity`` convention gives it
  NOT_WANT / ORTHOGONAL_TO_WANTING / WANT.
- **Relations written before silence existed**, read by F088's own definition of a relation: "presence of any
  non-zero and non-empty input in <bank A> forces <bank b> to be [typed 0/empty/also filled/etc]". A relation is
  triggered by presence and forces a typed state. So in a row, a 0 the relation does not force (some nonzero value is
  also allowed there, the rest of the row unchanged) is "not present", and silence reads the same way; a 0 the
  relation forces is its typed consequence, explicit absence, and stays 0. A relation that already names EMPTY is
  taken as written.
"""

from __future__ import annotations

from dataclasses import replace

from GSE.curation.schema import BIPOLAR_PAIRS

from .engine import EMPTY, STATES, Relation
from .foundation import BANKS

SIGNED_BY_CONVENTION = frozenset({"WANT"})  # foundation.WANT_POLARITY (founder want_polarity)
BIPOLAR_BANKS = frozenset(positive for positive, _negative in BIPOLAR_PAIRS) | SIGNED_BY_CONVENTION
UNPAIRED_STATES = frozenset((EMPTY, 0, 1))


def starting_domains(banks: tuple[str, ...] = BANKS) -> dict[str, frozenset]:
    """F040 starting domains for every bank, with silence possible until something excludes it."""
    return {bank: STATES if bank in BIPOLAR_BANKS else UNPAIRED_STATES for bank in banks}


def _free_zero(rows: frozenset, row: tuple, index: int) -> bool:
    """The 0 at ``index`` is not a typed consequence. Under F088 a relation is triggered by presence, so a 0 is forced
    only when another bank in its row is present and no nonzero value is allowed there instead."""
    if not any(value for k, value in enumerate(row) if k != index):
        return True  # nothing in the row is present: every 0 here is "not present"
    return any(row[:index] + (value,) + row[index + 1 :] in rows for value in (-1, 1))


def read_with_silence(relation: Relation) -> Relation:
    """A pre-silence relation under F088: a free 0 also admits EMPTY; a forced 0 stays explicit absence."""
    original = frozenset(relation.allowed_rows)
    if any(value is EMPTY for row in original for value in row):
        return relation
    rows = set(original)
    frontier = list(original)
    while frontier:
        row = frontier.pop()
        for index, value in enumerate(row):
            if value != 0:
                continue
            base = tuple(0 if v is EMPTY else v for v in row)  # forcedness is judged on the relation as written
            if _free_zero(original, base, index):
                lifted = row[:index] + (EMPTY,) + row[index + 1 :]
                if lifted not in rows:
                    rows.add(lifted)
                    frontier.append(lifted)
    ordered = tuple(sorted(rows, key=lambda r: tuple(-2 if v is EMPTY else v for v in r)))
    return replace(relation, allowed_rows=ordered)
