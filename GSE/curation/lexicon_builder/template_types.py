"""Which chart categories a kind of word carries, read from NSM's own verified explications and templates.

Rohan (2026-11-26): the type decisions come from "NSM research itself, including entire books". A kind's carried
categories are the NSM chart categories of the primes its verified explications use, matched through the catalog's
own exponent forms. Words marked "[m]" are semantic molecules, not primes, and are skipped. The verified extracts are
copyrighted and git-ignored (data/external/references/notes/explications/*.verified.jsonl); only this code and the
derived categories are kept.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from . import word_sense_genus_differentia as gd

ROOT = Path(__file__).resolve().parents[3]
EXTRACTS = ROOT / "data/external/references/notes/explications"
MOLECULE = re.compile(r"[\w'’-]+ \[m\]")


@lru_cache(maxsize=1)
def _exponents() -> tuple[dict[str, str], tuple[str, ...]]:
    from .catalog import catalog_inventory

    units = catalog_inventory()["units"]
    signs = gd.catalog_signs(units)
    # Each exponent as written (parentheticals dropped) and its WordNet base forms of two or more letters: KINDS is
    # also "kind", WORDS "word"; AS is never the article "a" (a one-letter base made every article the prime LIKE).
    forms = {}
    for unit in units:
        if unit["unit_id"] not in signs:
            continue
        for form in unit["forms"]:
            clean = re.sub(r"\([^)]*\)", "", form).strip().lower()
            bases = () if " " in clean else tuple(b for b in _morphy(clean) if len(b) > 1)
            for key in (clean, *bases):
                forms.setdefault(key, (signs[unit["unit_id"]][0], signs[unit["unit_id"]][1], unit["unit_id"]))
    phrases = tuple(sorted((f for f in forms if " " in f), key=len, reverse=True))
    return forms, phrases


def banks_in(text: str) -> set[str]:
    """The basis coordinates whose prime exponents occur in an NSM text (molecules skipped)."""
    return set(signed_banks_in(text))


def signed_banks_in(text: str, *, skip_units: frozenset[str] = frozenset()) -> dict[str, set[int]]:
    """bank -> the signs its exponents carry in an NSM text: BAD is GOOD -1, SMALL is BIG -1, OTHER is SAME -1
    (the catalog's own signs). ``skip_units`` leaves out units a caller does not count (e.g. the deictic THIS)."""
    forms, phrases = _exponents()
    text = MOLECULE.sub(" ", text.lower())
    found: dict[str, set[int]] = {}

    def add(entry):
        bank, sign, unit = entry
        if unit not in skip_units:
            found.setdefault(bank, set()).add(sign)

    for phrase in phrases:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        if re.search(pattern, text):
            add(forms[phrase])
            text = re.sub(pattern, " ", text)
    for word in re.findall(r"[a-z'’]+", text):
        word = re.sub(r"['’]s?$", "", word)
        for base in _bases(word):
            if base in forms:
                add(forms[base])
                break
    return found


@lru_cache(maxsize=None)
def _bases(word: str) -> tuple[str, ...]:
    """The word and its base forms under WordNet's morphology (bodies -> body, living -> live, felt -> feel), so an
    inflected exponent matches its prime; the source's own morphological processor, not a hand list."""

    out = [word, *(base for base in _morphy(word) if len(base) > 1)]  # "is" -> the letter "i" is not the prime I
    return tuple(dict.fromkeys(out))


@lru_cache(maxsize=None)
def _morphy(word: str) -> tuple[str, ...]:
    from nltk.corpus import wordnet as wn

    # Every base WordNet's morphology finds, not only the first: "things" is itself a lemma, and also "thing".
    return tuple(dict.fromkeys(base for pos in ("n", "v", "a") for base in wn._morphy(word, pos)))


@lru_cache(maxsize=1)
def verified_records() -> tuple[dict, ...]:
    out = []
    for path in sorted(EXTRACTS.glob("*.verified.jsonl")):
        out.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return tuple(out)


def categories_of(records) -> set[str]:
    from .applicability import bank_categories

    categories = bank_categories()
    return {categories[bank] for record in records for bank in banks_in(record["text"]) if bank in categories}


# The explication's own referent anaphors, and the participants it distinguishes from the referent (head record, F144:
# "a participant in its content is a role, not a cell").
REFERENT = re.compile(
    r"\b(this someone|this something|something like this|someone like this|things? like this|creatures? like this|"
    r"(?:people|creatures|things|animals|birds|fish|snakes) of this kind|of this kind|they|their|them|it)\b"
)
PARTICIPANT = re.compile(r"^\W*(?:[a-z]\.\s+)?(?:other people|people|someone else|i |you |when people|if people)")


CLAUSE = re.compile(r",|;|:|\bif\b|\bbecause\b|\bwhen\b|\bat the same time\b")
PARTICIPANT_SUBJECT = re.compile(
    r"^\W*(?:[a-z]\.\s+)?(?:other people|people(?! of this kind)|someone else|i\b|you\b|other creatures"
    r"|someone(?! of this kind| like this)\b|something(?! of this kind| like this)\b)"
)


def own_lines(text: str) -> list[str]:
    """Clauses that predicate of the referent. The explication's first component is its CATEGORY (NSM's own structure:
    "people of one kind", "something living") and is the referent's own, whatever its wording; after it, a clause is
    own when it names the referent and no other participant is its subject. A clause in which another participant acts
    on the referent ("if other people don't do good things for this someone") is a role, not the referent's own
    component (head record, F144)."""
    out = []
    lines = [line.strip() for line in text.lower().split("\n") if line.strip()]
    for index, line in enumerate(lines[1:]):  # lines[0] is the explication's label and explicandum
        for clause in CLAUSE.split(line):
            body = clause.strip()
            if not body:
                continue
            if index == 0 or re.search(r"\bof one kind\b|\bof many kinds\b", body):
                out.append(body)
            elif not PARTICIPANT_SUBJECT.match(body) and REFERENT.search(body):
                out.append(body)
    return out


def own_categories(records) -> set[str]:
    from .applicability import bank_categories

    categories = bank_categories()
    return {
        categories[bank]
        for record in records
        for line in own_lines(record["text"])
        for bank in banks_in(line)
        if bank in categories
    }
