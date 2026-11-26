"""The tail (F148): each disagreement between a word's reading and NSM's verified explication, with its cause.

Rohan (F148): "Disagreements are identified per-word, per-bank, and per-source/rule that caused the disagreement."
A disagreement is a prime the explication's own clauses use (``template_types.own_lines`` and ``banks_in``, exactly as
``scripts/lexicon_measure_vs_nsm.py`` measures) that the word's reading does not hold at +1. Its cause is computed,
never judged, in this order:

``CONVENTION_ZERO``
    The reading holds 0 because a part-of-speech convention rule of the release set it on the definitions
    (``word_senses.CONVENTION_RULES``: GOOD 0 on nouns, F057; SOMETHING 0 on adjectives and adverbs).
``SENSE_SPLIT``
    A sense of the word holds +1; the reading is what the senses agree on, and another sense does not hold it
    (Rohan, 2026-11-25: no main or default sense).
otherwise by the explication tokens that produce the bank (the same catalog exponents and WordNet morphology as
``banks_in``), each token being one of:

``frame``      inside NSM's own template structure and not a substantive: the category formula ("of one kind", the
               pattern ``own_lines`` uses), a referent anaphor (``template_types.REFERENT``), or the introducer of an
               embedded component in NSM's template records (the words before ":" that recur across them);
``deictic``    the exponent THIS, which the catalog files under SOMETHING as "a grammatical/contextual binding";
``collision``  a word that matches an exponent only after the catalog normalization drops a final "s" (the article
               "a" read as AS, so LIKE), never as itself or its WordNet base form;
``copula``     a form of "be": the catalog shares BE between BE (SOMEWHERE) and BE (SOMEONE/SOMETHING) and the
               measurement reads every "is" and "are" as the prime;
``content``    anything else.

A bank with any content token is ``LOGICAL_OPERATOR`` when its chart category is logical concepts (NOT, CAN, IF,
BECAUSE, MAYBE operate on a clause) and ``CONTENT`` otherwise; with none, it takes the class of its non-content tokens
(``COPULA_BE``, ``EXPONENT_COLLISION``, ``DEICTIC_THIS``, ``TEMPLATE_FRAME``, in that order). Each token's catalog sign is
kept: a negative-pole token (BAD, SMALL, OTHER) makes NSM's value -1, not +1. The explications are copyrighted; only
source keys, line ranges, banks, classes and counts leave this module.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache

from . import template_types as tt
from . import word_sense_genus_differentia as gd
from .word_senses import CONVENTION_RULES

CATEGORY_FORMULA = re.compile(r"\bof one kind\b|\bof many kinds\b")  # own_lines' category pattern
COMPONENT_INTRODUCER = re.compile(r"([a-z’']+ [a-z’']+):")
SUBSTANTIVES = "substantives"
LOGICAL = "logical concepts"
THIS_UNIT = "nsm:v20:this"
TOKEN_ORDER = ("copula", "collision", "deictic", "frame")
CLASS_OF_TOKEN = {
    "copula": "COPULA_BE",
    "collision": "EXPONENT_COLLISION",
    "deictic": "DEICTIC_THIS",
    "frame": "TEMPLATE_FRAME",
}


@dataclass(frozen=True)
class Token:
    bank: str
    sign: int
    kind: str


@lru_cache(maxsize=1)
def _units() -> tuple[dict[str, tuple[str, str, int]], dict[str, frozenset[str]], tuple[str, ...]]:
    """normal form -> (unit, bank, sign), built in ``template_types._exponents``' order so the same unit wins; each
    unit's own exponents (parentheticals dropped, nothing else); and the multi-word forms, longest first."""
    from .catalog import catalog_inventory

    units = catalog_inventory()["units"]
    signs = gd.catalog_signs(units)
    forms: dict[str, tuple[str, str, int]] = {}
    own: dict[str, frozenset[str]] = {}
    for unit in units:
        if unit["unit_id"] not in signs:
            continue
        bank, sign = signs[unit["unit_id"]][0], signs[unit["unit_id"]][1]
        own[unit["unit_id"]] = frozenset(re.sub(r"\([^)]*\)", "", f).strip().lower() for f in unit["forms"])
        for form in unit["forms"]:  # the same keys as template_types._exponents: as written, plus plural bases
            clean = re.sub(r"\([^)]*\)", "", form).strip().lower()
            bases = () if " " in clean else tuple(b for b in tt._morphy(clean) if len(b) > 1)
            for key in (clean, *bases):
                forms.setdefault(key, (unit["unit_id"], bank, sign))
    phrases = tuple(sorted((f for f in forms if " " in f), key=len, reverse=True))
    return forms, own, phrases


@lru_cache(maxsize=1)
def component_introducers() -> tuple[str, ...]:
    """The phrases NSM's template records put before ":" to introduce an embedded component, kept when they recur in
    at least two of the records (read from the verified templates, never typed here)."""
    found: Counter[str] = Counter()
    for record in tt.verified_records():
        if record["kind"] == "template":
            found.update(set(COMPONENT_INTRODUCER.findall(record["text"].lower())))
    return tuple(sorted(phrase for phrase, count in found.items() if count >= 2))


def _frame_spans(clause: str, introducers: Sequence[str]) -> list[tuple[int, int]]:
    spans = [m.span() for m in CATEGORY_FORMULA.finditer(clause)]
    spans += [m.span() for m in tt.REFERENT.finditer(clause)]
    for phrase in introducers:
        spans += [m.span() for m in re.finditer(r"\b" + re.escape(phrase) + r"\b", clause)]
    return spans


def tokens_in(clause: str, categories: Mapping[str, str], introducers: Sequence[str] = ()) -> list[Token]:
    """The prime tokens of one own clause, matched as ``banks_in`` matches them, each with its kind."""
    forms, own, phrases = _units()
    text = tt.MOLECULE.sub(lambda m: " " * len(m.group(0)), clause.lower())
    frames = _frame_spans(text, introducers)
    out: list[Token] = []

    def kind(unit: str, bank: str, span: tuple[int, int], surface: str, bases: Sequence[str]) -> str:
        if unit == THIS_UNIT:
            return "deictic"
        if bank == "BE" and "be" in bases:
            return "copula"
        if not (({surface} | set(bases)) & _own_forms(unit)):
            return "collision"
        inside = any(a <= span[0] and span[1] <= b for a, b in frames)
        return "frame" if inside and categories.get(bank) != SUBSTANTIVES else "content"

    for phrase in phrases:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        for match in re.finditer(pattern, text):
            unit, bank, sign = forms[phrase]
            out.append(Token(bank, sign, kind(unit, bank, match.span(), phrase, (phrase,))))
        if re.search(pattern, text):
            text = re.sub(pattern, lambda m: " " * len(m.group(0)), text)
    for match in re.finditer(r"[a-z'’]+", text):
        word = re.sub(r"['’]s?$", "", match.group(0))
        bases = tt._bases(word)
        for base in bases:
            if base in forms:
                unit, bank, sign = forms[base]
                morph = _morphy_bases(word)
                out.append(Token(bank, sign, kind(unit, bank, match.span(), word, morph)))
                break
    return out


@lru_cache(maxsize=None)
def _own_forms(unit: str) -> frozenset[str]:
    """A unit's exponents and their WordNet base forms: the chart's KINDS is also "kind"; its AS is never "a"."""
    _forms, own, _phrases = _units()
    return frozenset(base for form in own[unit] for base in _morphy_bases(form))


@lru_cache(maxsize=None)
def _morphy_bases(word: str) -> tuple[str, ...]:
    """The word itself and WordNet's base forms of it, unnormalized (so "a" is not "as")."""
    from nltk.corpus import wordnet as wn

    out = [word]
    for pos in ("n", "v", "a"):
        base = wn.morphy(word, pos)
        if base:
            out.append(base)
    return tuple(dict.fromkeys(out))


def bank_tokens(text: str, categories: Mapping[str, str]) -> dict[str, list[Token]]:
    """Every own-clause token of an explication, by bank."""
    introducers = component_introducers()
    by_bank: dict[str, list[Token]] = {}
    for clause in tt.own_lines(text):
        for token in tokens_in(clause, categories, introducers):
            by_bank.setdefault(token.bank, []).append(token)
    return by_bank


def token_class(bank: str, tokens: Sequence[Token], categories: Mapping[str, str]) -> str:
    kinds = {token.kind for token in tokens}
    if "content" in kinds:
        return "LOGICAL_OPERATOR" if categories.get(bank) == LOGICAL else "CONTENT"
    for kind in TOKEN_ORDER:
        if kind in kinds:
            return CLASS_OF_TOKEN[kind]
    return "NO_TOKEN"


def convention_set(bank: str, senses: Sequence[Mapping], traces: Mapping[str, Sequence[Mapping]]) -> bool:
    """Whether every sense holding the bank at a non-+1 value got it from a convention rule on its definitions."""
    holding = [s for s in senses if bank in s["assignments"] and s["assignments"][bank] != 1]
    if not holding:
        return False
    for sense in holding:
        entries = (sense["provenance"].get(bank) or {}).get("entries") or []
        if not entries or not all(
            any(
                step.get("kind") == "RELATION" and step.get("bank") == bank and step.get("rule_id") in CONVENTION_RULES
                for step in traces.get(entry, ())
            )
            for entry in entries
        ):
            return False
    return True


def source_state(bank: str, votes: Mapping[str, Mapping[str, int]], pos: str, dominant: bool) -> str:
    """What the word's sources say about a content bank NSM uses and no sense holds: the agreement state of the
    families that speak to this part of speech (``source_agreement``), or ``NO_VOTE`` when none votes on it."""
    from .source_agreement import agree, votes_for_pos

    row = agree(votes_for_pos(votes, pos, dominant)).get(bank)
    return row.state if row is not None else "NO_VOTE"


def synset_carry(entries: Sequence[tuple[str, int, str]], values: Mapping[int, Mapping[str, int]]) -> dict[str, dict]:
    """What a definition of a WordNet synset under a spelling outside the synset's own ``lemma_names`` ("dogs" for
    dog.n.01) would take if it carried the values the synset's native-spelling definitions hold. Measured, not built:
    the release's ``wordnet_native_lemma`` guard abstains from derived spellings on purpose (design, "Native identity
    guard for population rules"). ``entries`` are (entry_id, lexeme_id, lemma); returns entry -> {"gained": {bank:
    value}, "clash": {bank: [own, native]}, "native": [entry ids]}, for derived-spelling entries with a native sibling."""
    from nltk.corpus import wordnet as wn

    by_synset: dict[str, list[tuple[str, int, str]]] = {}
    for entry in entries:
        by_synset.setdefault(entry[0].rsplit(":", 1)[-1], []).append(entry)
    out: dict[str, dict] = {}
    for synset, rows in by_synset.items():
        try:
            names = {name.casefold().replace("_", " ") for name in wn.synset(synset).lemma_names()}
        except Exception:  # noqa: BLE001 - a synset name WordNet does not know carries nothing
            continue
        native = [row for row in rows if row[2].casefold().replace("_", " ") in names]
        derived = [row for row in rows if row not in native]
        if not native or not derived:
            continue
        held: dict[str, set[int]] = {}
        for _entry, lexeme, _lemma in native:
            for bank, value in values.get(lexeme, {}).items():
                held.setdefault(bank, set()).add(value)
        for entry, lexeme, _lemma in derived:
            own = values.get(lexeme, {})
            gained, clash = {}, {}
            for bank, found in sorted(held.items()):
                if len(found) != 1:
                    clash[bank] = sorted(found)
                elif bank not in own:
                    gained[bank] = next(iter(found))
                elif own[bank] not in found:
                    clash[bank] = [own[bank], next(iter(found))]
            out[entry] = {"gained": gained, "clash": clash, "native": sorted(row[0] for row in native)}
    return out


def classify(
    bank: str,
    held: Mapping[str, int],
    senses: Sequence[Mapping],
    tokens: Sequence[Token],
    categories: Mapping[str, str],
    traces: Mapping[str, Sequence[Mapping]],
) -> str:
    """The cause of one disagreement (a bank NSM's own clauses use that the reading does not hold at +1)."""
    if bank in held and held[bank] != 1 and convention_set(bank, senses, traces):
        return "CONVENTION_ZERO"
    if any(s["assignments"].get(bank) == 1 for s in senses):
        return "SENSE_SPLIT"
    return token_class(bank, tokens, categories)
