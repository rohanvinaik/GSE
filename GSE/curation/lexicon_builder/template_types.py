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
    forms = {gd._normal(f): signs[u["unit_id"]][0] for u in units if u["unit_id"] in signs for f in u["forms"]}
    phrases = tuple(sorted((f for f in forms if " " in f), key=len, reverse=True))
    return forms, phrases


def banks_in(text: str) -> set[str]:
    """The basis coordinates whose prime exponents occur in an NSM text (molecules skipped)."""
    forms, phrases = _exponents()
    text = MOLECULE.sub(" ", text.lower())
    found = set()
    for phrase in phrases:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        if re.search(pattern, text):
            found.add(forms[phrase])
            text = re.sub(pattern, " ", text)
    for word in re.findall(r"[a-z'’]+", text):
        if gd._normal(word) in forms:
            found.add(forms[gd._normal(word)])
    return found


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
PARTICIPANT_SUBJECT = re.compile(r"^\W*(?:[a-z]\.\s+)?(?:other people|people|someone else|i\b|you\b|other creatures)")


def own_lines(text: str) -> list[str]:
    """Clauses that predicate of the referent: the referent is named and no other participant is the clause's subject.
    A clause in which another participant acts on the referent ("if other people don't do good things for this
    someone") is a role, not the referent's own component (head record, F144)."""
    out = []
    for line in text.lower().split("\n"):
        for clause in CLAUSE.split(line):
            body = clause.strip()
            if not body or PARTICIPANT_SUBJECT.match(body):
                continue
            if REFERENT.search(body) or re.search(r"\bof one kind\b|\bof many kinds\b", body):
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
