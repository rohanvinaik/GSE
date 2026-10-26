"""Fill the cells a reading's rules leave open: one typed local-model decision per bank, then solve again.

The rules fix what they can. Each bank's still-open cells then go to the local model together, as
typed fields: exactly the states surviving the rules, including written 0 (F078). Every answer
becomes a restriction, the reading is solved again, and the next bank sees the result (F078, F113).
"""

from __future__ import annotations

import re
from pathlib import Path

from gse.lexicon_builder.basis import BANKS
from gse.lexicon_builder.core import CANONICAL_COORDINATES, Cell, Resolution

BANK_NAMES = ("substantives", "quantity", "evaluators", "mental", "action", "temporal", "spatial", "logical")
BANK_COORDINATES = tuple(tuple(c for c in bank if c in CANONICAL_COORDINATES) for bank in BANKS)

# What each coordinate records: NSM exponents where NSM has the prime, and primitives_v2's hierarchy
# contract for GSE's scale coordinates. A bipolar coordinate names both poles.
MEANINGS = {
    "I": "I",
    "YOU": "you",
    "SOMEONE": "someone",
    "SOMETHING": "something; a thing",
    "PEOPLE": "people",
    "BODY": "body",
    "KIND": "a kind of; the word names a category",
    "PART": "a part of",
    "SAME": "+1 the same; -1 other",
    "ONE": "one",
    "TWO": "two",
    "QUANTITY": "an amount or number applies (scale base: some, many, all)",
    "GOOD": "+1 good; -1 bad",
    "BIG": "+1 big; -1 small",
    "THINK": "think",
    "KNOW": "know",
    "WANT": "want",
    "FEEL": "feel",
    "SEE": "see",
    "HEAR": "hear",
    "INFER": "conclude from evidence",
    "SAY": "say",
    "WORDS": "words",
    "DO": "do",
    "HAPPEN": "happen",
    "MOVE": "move",
    "BE": "be (someone or something)",
    "HAVE": "have",
    "EXIST": "there is; exist",
    "ALIVE": "+1 alive; -1 dead",
    "MOMENT": "a moment",
    "WHEN": "when; a time",
    "LONG_TIME": "+1 a long time; -1 a short time",
    "BEFORE": "+1 before; -1 after",
    "THEN": "+1 then; -1 now",
    "START": "+1 start; -1 end",
    "WHERE": "where; a place",
    "HERE": "here",
    "SIDE": "side",
    "TOUCH": "touch; contact",
    "ABOVE": "+1 above; -1 below",
    "FAR": "+1 far; -1 near",
    "OUTSIDE": "+1 outside; -1 inside",
    "TOWARD": "+1 toward; -1 away",
    "WITH": "+1 with; -1 without",
    "NOT": "not",
    "MAYBE": "maybe",
    "CAN": "can",
    "MUST": "must",
    "BECAUSE": "because: a reason, or a thought that a feeling comes from",
    "CAUSE": "the word's own causing: someone or something brings about a change in another",
    "IF": "if",
    "LIKE": "like; as; the way",
    "TRUE": "+1 true; -1 false",
    "HIER_PLUS": "up a scale (more, many, very, likely) on QUANTITY, INTENSITY or CERTAINTY",
    "HIER_MINUS": "down a scale (less, few, slightly, unlikely) on QUANTITY, INTENSITY or CERTAINTY",
    "INTENSITY": "a degree applies (scale base: slightly, very, extremely)",
    "CERTAINTY": "a degree of certainty applies (scale base: possible, likely, certain)",
}
assert set(MEANINGS) == set(CANONICAL_COORDINATES)

USAS_TAGSET = Path("data/external/usas/semtags.txt")
USAS_CATEGORY = re.compile(r"[A-Z]\d+(?:\.\d+)*")


def usas_labels(path: Path = USAS_TAGSET) -> dict[str, str]:
    """UCREL's published tag list: category code to label. Absent file: no labels, codes only."""
    if not path.exists():
        return {}
    labels = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        code, _, label = line.partition("\t")
        if code and label:
            labels[code.strip()] = label.strip()
    return labels


def usas_type(tag: str, labels: dict[str, str]) -> dict:
    """A USAS tag as typed fields: its category, that category's label, and its scale side."""
    found = USAS_CATEGORY.match(tag)
    category = found.group(0) if found else tag
    plus, minus = tag.count("+"), tag.count("-")
    return {
        "tag": tag,
        "category": category,
        "label": labels.get(category),
        "scale": "+" * plus if plus else "-" * minus if minus else None,
    }


def fill_options(state: Resolution, coordinate: str) -> list[str]:
    """Offer every surviving state; rules, not the decoder, exclude zero or silence."""
    domain = state.domains[coordinate]
    if len(domain) < 2:
        return []
    return [s.value for s in (Cell.SILENT, Cell.ZERO, Cell.PLUS, Cell.MINUS) if s in domain]


def open_fields(state: Resolution, bank: int) -> dict[str, list[str]]:
    return {c: options for c in BANK_COORDINATES[bank] if (options := fill_options(state, c))}


def fill_payload(
    word: str, pos: str, scope: str, native_types: dict, state: Resolution, bank: int, fields: dict
) -> dict:
    """Typed fields only: the word, its source categories, the cells already fixed, and this bank's choices.

    The scope says what the definition covers: an emotion word's includes the thought it comes from (F129).
    """
    return {
        "schema": "GSE_BANK_FILL_V1",
        "word": word,
        "pos": pos,
        "definition_scope": scope,
        "native_types": native_types,
        "fixed": {c: v.value for c, v in state.forced().items()},
        "bank": BANK_NAMES[bank],
        "fields": {c: {"means": MEANINGS[c], "options": options} for c, options in fields.items()},
        "operation": "FILL_EACH_FIELD_FOR_THIS_READING_OWN_DEFINITION",
        "test": "+1 only if an NSM explication of this word's own meaning needs this prime; most fields are empty",
    }
