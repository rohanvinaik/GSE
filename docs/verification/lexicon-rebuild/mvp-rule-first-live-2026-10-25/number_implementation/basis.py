"""Versioned 72-name lexical basis and its 58 signed coordinates.

This inventory is explicitly copied into the new build contract so the
constructor does not execute or inherit the old curation pipeline. A label is
not yet a reviewed lexical-unit/combinatorial profile. NUMBER is intentionally
absent: it is a scale operation over this basis, never a lexical prime.
"""

from __future__ import annotations

BASIS_ID = "GSE_LEXICAL_72_SIGNED_58_V1"

BANKS: tuple[tuple[str, ...], ...] = (
    ("I", "YOU", "SOMEONE", "SOMETHING", "PEOPLE", "BODY", "KIND", "PART", "SAME", "OTHER"),
    ("ONE", "TWO", "QUANTITY"),
    ("GOOD", "BAD", "BIG", "SMALL"),
    ("THINK", "KNOW", "WANT", "FEEL", "SEE", "HEAR", "INFER"),
    ("SAY", "WORDS", "DO", "HAPPEN", "MOVE", "BE", "HAVE", "EXIST", "ALIVE", "DEAD"),
    ("MOMENT", "WHEN", "LONG_TIME", "SHORT_TIME", "BEFORE", "AFTER", "THEN", "NOW", "START", "END"),
    (
        "WHERE",
        "HERE",
        "SIDE",
        "TOUCH",
        "ABOVE",
        "BELOW",
        "FAR",
        "NEAR",
        "OUTSIDE",
        "INSIDE",
        "TOWARD",
        "AWAY",
        "WITH",
        "WITHOUT",
    ),
    (
        "NOT",
        "MAYBE",
        "CAN",
        "MUST",
        "BECAUSE",
        "CAUSE",
        "IF",
        "LIKE",
        "TRUE",
        "FALSE",
        "HIER_PLUS",
        "HIER_MINUS",
        "INTENSITY",
        "CERTAINTY",
    ),
)

PRIMES = tuple(prime for bank in BANKS for prime in bank)
PRIME_TO_BANK = {prime: bank_id for bank_id, bank in enumerate(BANKS) for prime in bank}

OPPOSITE_POLES: tuple[tuple[str, str], ...] = (
    ("SAME", "OTHER"),
    ("GOOD", "BAD"),
    ("BIG", "SMALL"),
    ("ALIVE", "DEAD"),
    ("LONG_TIME", "SHORT_TIME"),
    ("BEFORE", "AFTER"),
    ("THEN", "NOW"),
    ("START", "END"),
    ("ABOVE", "BELOW"),
    ("FAR", "NEAR"),
    ("OUTSIDE", "INSIDE"),
    ("TOWARD", "AWAY"),
    ("WITH", "WITHOUT"),
    ("TRUE", "FALSE"),
)

assert len(BANKS) == 8
assert len(PRIMES) == len(set(PRIMES)) == 72
assert len(OPPOSITE_POLES) == 14
assert "NUMBER" not in PRIMES
assert all(positive in PRIMES and negative in PRIMES for positive, negative in OPPOSITE_POLES)
