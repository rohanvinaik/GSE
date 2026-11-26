"""NSM molecule inheritance: a category explication's own positive components hold for every kind of that category.

NSM defines a subkind through a molecule: "dogs: creatures [m] of one kind". The [m] marks a molecule, which carries
its own explication into every explication that uses it, so what the category's explication positively asserts of its
referent is part of the meaning of every kind of it (Rohan, 2026-11-26: the books' work "should be extended in ways
that are relevant and useful"). WordNet's IS-A says which words are kinds of what. Everything is computed from the
verified extracts and WordNet; no word or value is written here:

* binding: a category explication whose subkinds NSM explicates ("X [m] of one kind" on their category line) binds to
  the lowest common WordNet hypernym of those subkinds that have exactly one organism sense;
* components: the category explication's lines whose subject explicitly names the referent ("something like this",
  "creatures of this kind", ...; never a bare pronoun, which NSM's sections also use for people), outside quoted
  folk-model text, unquantified ("some", "many", "often" ...), unnegated, and in a predicate or descriptor category of
  the chart (substantives, frame words and operators are the head rules' and are left out);
* refutation: a component is dropped when any subkind explication denies it in an unconditioned line (no if, when,
  like, because, before, after). Non-mention is not denial.

The extracts are copyrighted and git-ignored; only source keys, line ranges, banks and synset names leave here.
"""

from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache

from . import template_types as tt

NEGATION = re.compile(r"\b(not|can't|cannot|can’t|don't|don’t|doesn't|doesn’t|no)\b")
QUANTIFIED = re.compile(r"\b(some|many|often|sometimes|usually|most|few|at many times)\b")
CONDITIONED = re.compile(r"\b(if|when|like|because|before|after)\b")
REFERENT_SUBJECT = re.compile(
    r"^\W*(?:[a-z]\.\s+)?(?:something like this|someone like this|this something|this someone"
    r"|(?:creatures|things|people|birds|fish|snakes|animals)(?: \[m\])? of (?:this|all these) kinds?)\b"
)
CATEGORY_LINE = re.compile(r"([a-z’'-]+) \[m\] of (?:one|many) kinds?")
FRAME_AND_OPERATORS = frozenset({"KIND", "ONE", "LIKE", "BE", "CAN", "NOT"})
PREDICATE_CATEGORIES = frozenset(
    {
        "mental predicates",
        "actions, events, movement, contact",
        "life and death",
        "speech",
        "descriptors",
        "space",
        "time",
    }
)
THIS = frozenset({"nsm:v20:this"})


def _lemma(explicandum: str) -> str | None:
    words = re.sub(r"\(.*?\)|\[.*?\]", " ", explicandum.lower()).split()
    return words[0] if len(words) == 1 else None


def _organism_senses(word: str) -> list[str]:
    from nltk.corpus import wordnet as wn

    base = wn.morphy(word, "n") or word
    return [s.name() for s in wn.synsets(base, "n") if "organism.n.01" in _ancestors(s.name())]


@lru_cache(maxsize=None)
def _ancestors(synset_name: str) -> frozenset[str]:
    from nltk.corpus import wordnet as wn

    try:
        synset = wn.synset(synset_name)
    except Exception:
        return frozenset()
    return frozenset(a.name() for path in synset.hypernym_paths() for a in path) | {synset_name}


@lru_cache(maxsize=1)
def bindings() -> dict[str, dict]:
    """category -> {"synset", "record": source key and lines, "subkinds": [(source, lemma, lines)]}."""
    from nltk.corpus import wordnet as wn

    records = [r for r in tt.verified_records() if r["kind"] == "explication"]
    by_lemma = {_lemma(r["explicates"]): r for r in records if _lemma(r["explicates"])}
    subkinds = defaultdict(list)
    for record in records:
        lines = tt.own_lines(record["text"])
        match = CATEGORY_LINE.search(lines[0]) if lines else None
        if match and _lemma(record["explicates"]):
            subkinds[match.group(1)].append(record)
    out = {}
    for category, kids in subkinds.items():
        if category not in by_lemma:
            continue
        unique = [s[0] for s in (_organism_senses(_lemma(k["explicates"])) for k in kids) if len(s) == 1]
        if len(unique) < 2:
            continue
        common = wn.synset(unique[0])
        for name in unique[1:]:
            common = common.lowest_common_hypernyms(wn.synset(name))[0]
        record = by_lemma[category]
        out[category] = {
            "synset": common.name(),
            "record": [record["source"], record["start_line"], record["end_line"]],
            "subkinds": [[k["source"], _lemma(k["explicates"]), k["start_line"], k["end_line"]] for k in kids],
        }
    return out


def _signed(text: str, *, denials: bool) -> dict[str, set[int]]:
    """The explication's referent-subject components (or, with ``denials``, its unconditioned denials)."""
    from .applicability import bank_categories

    categories = bank_categories()
    text = re.sub(r"“[^”]*”?", " ", text, flags=re.S).lower()
    found: dict[str, set[int]] = defaultdict(set)
    for line in text.split("\n")[1:]:
        if QUANTIFIED.search(line) or (denials and CONDITIONED.search(line)):
            continue
        for clause in tt.CLAUSE.split(line):
            clause = clause.strip()
            if not REFERENT_SUBJECT.match(clause) or bool(NEGATION.search(clause)) != denials:
                continue
            for bank, signs in tt.signed_banks_in(clause, skip_units=THIS).items():
                if bank not in FRAME_AND_OPERATORS and categories.get(bank) in PREDICATE_CATEGORIES:
                    found[bank] |= signs
    return found


@lru_cache(maxsize=1)
def components() -> dict[str, dict[str, int]]:
    """category -> bank -> value: its components that no subkind denies."""
    by_key = {(r["source"], r["start_line"], r["end_line"]): r for r in tt.verified_records()}
    out = {}
    for category, binding in bindings().items():
        record = by_key[tuple(binding["record"])]
        positive = _signed(record["text"], denials=False)
        denied = set()
        for source, _lemma_, start, end in binding["subkinds"]:
            denied |= set(_signed(by_key[(source, start, end)]["text"], denials=True))
        out[category] = {b: next(iter(s)) for b, s in positive.items() if len(s) == 1 and b not in denied}
    return out


def inherited(synset_name: str) -> dict[str, tuple[int, dict]]:
    """bank -> (value, warrant) a WordNet synset inherits from every category explication bound above it."""
    out: dict[str, tuple[int, dict]] = {}
    for category, binding in bindings().items():
        if binding["synset"] in _ancestors(synset_name):
            for bank, value in components().get(category, {}).items():
                warrant = {"category": category, "record": binding["record"], "binding": binding["synset"]}
                if bank in out and out[bank][0] != value:
                    out[bank] = (None, warrant)  # two categories disagree: neither holds
                else:
                    out.setdefault(bank, (value, warrant))
    return {b: v for b, v in out.items() if v[0] is not None}


def sense_inheritance(member_ids) -> dict[str, tuple[int, dict]]:
    """What a sense inherits: values every one of its WordNet members inherits alike (needs at least one)."""
    synsets = [e.rsplit(":", 1)[1] for e in member_ids if e.startswith("wordnet:") and ".n." in e]
    if not synsets:
        return {}
    first = inherited(synsets[0])
    shared = {}
    for bank, (value, warrant) in first.items():
        if all(inherited(s).get(bank, (None,))[0] == value for s in synsets[1:]):
            shared[bank] = (value, {**warrant, "entries": sorted(member_ids)})
    return shared
