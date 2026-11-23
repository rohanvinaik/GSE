"""Reviewed own-word bank relevance, independent of source assertion competence.

An annotation says which banks a native observation may inform; it never
assigns a value. Unclassified observations conservatively remain relevant to
every bank, so their presence cannot license an absence default. Native source
scope ceilings and English descriptions do not classify individual records.

Callers apply this set to exact definition links and unresolved candidate links.
They can retain the compact set without copying the native observation payload.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .foundation import BANKS

if TYPE_CHECKING:
    from .evidence import Observation


_ALL_BANKS = frozenset(BANKS)


def validate_bank_relevance(annotation: object) -> frozenset[str]:
    """Validate an explicit classification; an empty bank list needs provenance.

    The reserved annotation is a JSON object with exactly ``code``, ``banks``,
    and ``provenance``. Coordinate names must already be canonical, so aliases
    and negative-pole spellings cannot silently change the declared scope.
    """
    if not isinstance(annotation, dict) or set(annotation) != {"code", "banks", "provenance"}:
        raise ValueError("INVALID_BANK_RELEVANCE_FIELDS")
    if annotation["code"] != "CLASSIFIED":
        raise ValueError("INVALID_BANK_RELEVANCE_CODE")
    banks = annotation["banks"]
    if (
        not isinstance(banks, list)
        or any(not isinstance(bank, str) or bank not in _ALL_BANKS for bank in banks)
        or len(set(banks)) != len(banks)
    ):
        raise ValueError("INVALID_BANK_RELEVANCE_BANKS")
    provenance = annotation["provenance"]
    if (
        not isinstance(provenance, list)
        or not provenance
        or any(not isinstance(item, str) or not item.strip() for item in provenance)
    ):
        raise ValueError("INVALID_BANK_RELEVANCE_PROVENANCE")
    return frozenset(banks)


def observation_relevance(observation: Observation) -> frozenset[str]:
    """Return potentially relevant banks, without inferring any lexical sign.

    Missing classification means UNCLASSIFIED, not irrelevant. An explicitly
    reviewed empty classification is the only annotation that returns no banks.
    A present null or malformed classification fails instead of becoming silence.
    """
    if "bank_relevance" not in observation.features:
        return _ALL_BANKS
    return validate_bank_relevance(observation.features["bank_relevance"])
