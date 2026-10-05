"""Rohan Vinaik's personal dictionary (#60): his fields' formal terms and his own jargon, each with a dictionary
definition and a GSE word-scale decomposition.

The decompositions are written by hand, never by the old definitional decomposer, whose genus chain collapses
meaning (it built layer 2, where 25,735 words read SOMETHING alone). Two members draft each decomposition
independently; only the primes they agree on enter, and every other prime goes to the lead. The hypervector of an
entry is made by the live encoder's own word path, so a word read from this dictionary and the same word read by the
encoder are the same vector.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from gse.curation.schema import ALL_PRIMITIVES
from gse.primitives_v2 import get_canonical_pole

_PRIMES = frozenset(ALL_PRIMITIVES)
_HIERARCHY = frozenset({"HIER_PLUS", "HIER_MINUS"})  # degree is sentence-scale, never a word's identity (FA L741)
_GENERIC = frozenset({"SOMETHING", "SOMEONE", "DO", "BE", "EXIST"})
MIN_PRIMES, MAX_PRIMES = 2, 7


def check_decomposition(signed: Dict[str, int]) -> Tuple[Dict[str, int], List[str]]:
    """One drafted decomposition in canonical form, and every way it breaks GSE's word-scale rules.

    Each prime is mapped to its canonical pole (BAD +1 is GOOD -1, after gse.primitives_v2.get_canonical_pole). The
    named problems: ``UNKNOWN_PRIME:<p>``, ``HIERARCHY_MARKER:<p>``, ``NOT_TERNARY:<p>``,
    ``CONFLICTING_POLES:<pole>`` (both poles, or one pole with both signs), ``TOO_FEW``, ``TOO_MANY`` and
    ``GENERIC_ONLY`` (nothing beyond SOMETHING, SOMEONE, DO, BE, EXIST). A rejected prime stays out of the canonical
    form; an empty problem list means the decomposition may enter.
    """
    canon: Dict[str, int] = {}
    problems: List[str] = []
    for prime, value in signed.items():
        if prime in _HIERARCHY:
            problems.append(f"HIERARCHY_MARKER:{prime}")
        elif prime not in _PRIMES:
            problems.append(f"UNKNOWN_PRIME:{prime}")
        elif value not in (1, -1):
            problems.append(f"NOT_TERNARY:{prime}")
        else:
            pole, sign = get_canonical_pole(prime)
            if canon.get(pole, sign * value) != sign * value:
                problems.append(f"CONFLICTING_POLES:{pole}")
                del canon[pole]
            else:
                canon[pole] = sign * value
    if len(canon) < MIN_PRIMES:
        problems.append("TOO_FEW")
    if len(canon) > MAX_PRIMES:
        problems.append("TOO_MANY")
    if canon and set(canon) <= _GENERIC:
        problems.append("GENERIC_ONLY")
    return canon, problems


def concur(first: Dict[str, int], second: Dict[str, int]) -> Dict[str, str]:
    """How two independently drafted canonical decompositions relate, prime by prime.

    ``AGREED`` (both name it, same sign), ``SIGN_CONFLICT`` (both name it, opposite signs), ``ONLY_FIRST`` or
    ``ONLY_SECOND``. Only AGREED primes enter the dictionary; every other code goes to the lead.
    """
    out: Dict[str, str] = {}
    for prime in sorted(set(first) | set(second)):
        if prime in first and prime in second:
            out[prime] = "AGREED" if first[prime] == second[prime] else "SIGN_CONFLICT"
        else:
            out[prime] = "ONLY_FIRST" if prime in first else "ONLY_SECOND"
    return out
