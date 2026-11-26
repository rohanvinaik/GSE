"""Which banks a word's own type can carry (Rohan, 2026-11-25 17:56: "classifies all the dimensions that are plausibly
sane and potentially valid encodings, and which are definitionally not valid ... For the ones that are completely
orthogonal to a valid definition of the word" the cell is decided; "Others should NOT be automatically filled").

The form is TrialLedger's: a type owns coordinates, and a case's type comes from a source-bound identity, never from a
guess at the word. Here a bank's owner is its NSM chart category (computed from the chart text through the catalog, as
round 2's identity banks are); a noun's type is WordNet's lexicographer category, stated per synset. The table below
says which chart categories a noun type's own head carries, following the chart's combinatorics (F067: substantives and
quantifiers combine, "a 'flock' is 'many' of the object 'bird'"; evaluators and descriptors exclude each other;
descriptors "require objective-ness"). A bank in a category the type does not carry is orthogonal: silent (F118).

Evaluation is not decided here: F057's own-evaluation 0 for nouns is explicit absence, already a release relation.
Every proposed silence is checked against stored content before it may write (NEGATIVE_SPECIFICATION Prop. 5.5).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from . import word_sense_genus_differentia as gd

ROOT = Path(__file__).resolve().parents[3]

SUBSTANTIVE = ("substantives", "relational substantives", "quantifiers", "determiners")
OBJECT = SUBSTANTIVE + ("descriptors", "space")  # descriptors require objectness (F067); objects are located
LIVING = OBJECT + ("life and death",)
# Noun type -> the chart categories its own head carries. "evaluators" is absent everywhere: F057 writes explicit 0.
NOUN_TYPE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "noun.Tops": SUBSTANTIVE + ("life and death",),
    "noun.person": LIVING + ("mental predicates", "speech", "actions, events, movement, contact"),
    "noun.animal": LIVING,
    "noun.plant": LIVING,
    "noun.body": LIVING,
    "noun.artifact": OBJECT,
    "noun.object": OBJECT,
    "noun.substance": OBJECT,
    "noun.food": OBJECT,
    "noun.shape": OBJECT,
    "noun.location": OBJECT + ("location, existence, possession, specification",),
    "noun.group": SUBSTANTIVE + ("life and death",),
    "noun.quantity": SUBSTANTIVE + ("descriptors", "time", "space", "intensifier, augmentor"),
    "noun.time": SUBSTANTIVE + ("time",),
    "noun.act": SUBSTANTIVE + ("actions, events, movement, contact", "time", "mental predicates", "speech"),
    "noun.event": SUBSTANTIVE + ("actions, events, movement, contact", "time", "space"),
    "noun.process": SUBSTANTIVE + ("actions, events, movement, contact", "time", "life and death"),
    "noun.phenomenon": SUBSTANTIVE + ("actions, events, movement, contact", "time", "space"),
    "noun.feeling": SUBSTANTIVE + ("mental predicates", "intensifier, augmentor"),
    "noun.cognition": SUBSTANTIVE + ("mental predicates", "logical concepts", "speech"),
    "noun.motive": SUBSTANTIVE + ("mental predicates", "logical concepts"),
    "noun.communication": SUBSTANTIVE + ("speech", "mental predicates", "actions, events, movement, contact"),
    "noun.state": SUBSTANTIVE
    + (
        "location, existence, possession, specification",
        "life and death",
        "mental predicates",
        "intensifier, augmentor",
    ),
    "noun.attribute": SUBSTANTIVE + ("descriptors", "intensifier, augmentor", "similarity"),
    "noun.possession": SUBSTANTIVE + ("location, existence, possession, specification",),
    "noun.relation": SUBSTANTIVE + ("similarity", "logical concepts", "space", "time"),
}


@lru_cache(maxsize=1)
def bank_categories() -> dict[str, str]:
    """bank -> its NSM chart category, read from the chart text through the catalog (never typed here)."""
    from .catalog import catalog_inventory

    table = gd.category_table((ROOT / gd.CATEGORY_TABLE).read_text(encoding="utf-8"))
    units = catalog_inventory()["units"]
    signs = gd.catalog_signs(units)
    out: dict[str, str] = {}
    for category, exponents in table.items():
        for exponent in exponents:
            wanted = {gd._normal(a) for a in exponent.split("~")}
            for unit in units:
                if {gd._normal(f) for f in unit["forms"]} & wanted and unit["unit_id"] in signs:
                    out.setdefault(signs[unit["unit_id"]][0], category)
    return out


def silent_banks(noun_type: str) -> tuple[str, ...]:
    """Banks the type's own head cannot carry: their chart category is outside the type's row (evaluators excepted)."""
    carried = NOUN_TYPE_CATEGORIES.get(noun_type)
    if carried is None:
        return ()
    return tuple(
        sorted(
            bank for bank, category in bank_categories().items() if category not in carried and category != "evaluators"
        )
    )


# A verb's own head is a predicate. Its substantive cells are explicit 0 by the head law (F144, VERB_HEADS_NO_SUBSTANTIVE),
# so every verb row carries the substantive categories and silence never contests that law. Evaluators are carried
# where a verb can be the act of evaluating (F057: "'I hate you' carries implicit value judgement").
_VERB_BASE = SUBSTANTIVE + ("actions, events, movement, contact", "time")
VERB_TYPE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "verb.motion": _VERB_BASE + ("space", "descriptors"),
    "verb.contact": _VERB_BASE + ("space",),
    "verb.change": _VERB_BASE
    + ("descriptors", "life and death", "location, existence, possession, specification", "space"),
    "verb.creation": _VERB_BASE + ("location, existence, possession, specification",),
    "verb.consumption": _VERB_BASE + ("life and death",),
    "verb.body": _VERB_BASE + ("life and death", "mental predicates"),
    "verb.possession": _VERB_BASE + ("location, existence, possession, specification",),
    "verb.stative": _VERB_BASE
    + ("location, existence, possession, specification", "space", "similarity", "descriptors"),
    "verb.weather": _VERB_BASE + ("space",),
    "verb.perception": _VERB_BASE + ("mental predicates",),
    "verb.cognition": _VERB_BASE + ("mental predicates", "logical concepts", "speech", "similarity"),
    "verb.communication": _VERB_BASE + ("speech", "mental predicates", "evaluators", "logical concepts"),
    "verb.emotion": _VERB_BASE + ("mental predicates", "evaluators", "intensifier, augmentor"),
    "verb.social": _VERB_BASE + ("speech", "evaluators", "location, existence, possession, specification"),
    "verb.competition": _VERB_BASE + ("space",),
}


def verb_silent_banks(verb_type: str) -> tuple[str, ...]:
    carried = VERB_TYPE_CATEGORIES.get(verb_type)
    if carried is None:
        return ()
    return tuple(sorted(bank for bank, category in bank_categories().items() if category not in carried))
