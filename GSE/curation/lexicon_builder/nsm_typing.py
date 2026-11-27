"""Which readings an NSM explication describes: a typed alignment proof from its head line (rebuild tasks 4-5).

Design E2: "Join by exact native identifiers, declared mappings, or a typed alignment proof." An explication says
which sense it describes through its head line: a word explicated as "creatures [m] of one kind" claims a kind of
creature. The lead's ruling of 2026-11-26 refines rule 1 with that claim:

1. The head category is the head line's molecule, or the substantive heading its head referent, as a noun lemma
   (`nsm.head_category`).
2. The category's hub readings are the cohort's readings of that exact lemma; their synsets are the hub. No table
   maps a category to a synset.
3. A reading of the explicated word is eligible when its WordNet kind-of ancestry (hypernyms and instance hypernyms,
   transitively) contains a hub synset. This is set logic, with no threshold. The ancestry includes the reading's
   own synset: where WordNet makes the word and its category one synset (animal and creature are both
   animal.n.01), the exact native identity is the strongest join there is.
   SOMETHING~THING gives no typing (ruling of 2026-11-26): NSM's most general substantive says only that the
   referent is some kind of thing, which every noun reading is, so the English word's WordNet senses (thing.n.12,
   matter.n.01) would select arbitrary readings. Its bindings are `UNTYPED`, `MOST_GENERAL_CATEGORY`.
4. One eligible reading takes the content as a restriction, several take the obligation, and none leaves the
   obligation over every reading, `UNTYPED`.
5. Readings outside WordNet (Wiktionary) have no ancestry yet. They stay out of a typed row set and are counted.
"""

from __future__ import annotations

from dataclasses import dataclass

from nltk.corpus import wordnet as wn
from nltk.corpus.reader.wordnet import WordNetError

from . import inheritance

NO_HEAD_CATEGORY = "NO_HEAD_CATEGORY"  # a predicate's head line names participants, not a category
NO_HUB_SYNSET = "NO_HUB_SYNSET"  # the category lemma has no WordNet reading in the cohort
NONE_ELIGIBLE = "NONE_ELIGIBLE"  # no WordNet reading of the word descends from the hub
MOST_GENERAL_CATEGORY = "MOST_GENERAL_CATEGORY"  # SOMETHING~THING: every noun reading is some kind of thing


@dataclass(frozen=True)
class Typed:
    """The typed rows of one binding, or the reason there are none."""

    category: str
    hub: tuple[str, ...]
    rows: tuple[int, ...]
    wordnet: int
    outside: int
    reason: str = ""

    def receipt(self) -> dict:
        out = {"category": self.category, "hub_synsets": len(self.hub), "wordnet_readings": self.wordnet}
        out |= {"outside_wordnet": self.outside, "eligible": len(self.rows)}
        return out | ({"reason": self.reason} if self.reason else {})


class Aligner:
    """The cohort's WordNet synsets by row, the hub of a category lemma, and kind-of ancestry."""

    def __init__(self, readings, index: dict[tuple[str, str], list[int]], most_general=frozenset()):
        self.synset = {row: name for name, rows in inheritance.wordnet_groups(readings).items() for row in rows}
        self.index = index
        self.most_general = frozenset(most_general)
        self._ancestry: dict[str, frozenset[str]] = {}
        self.unresolved: set[str] = set()

    def ancestry(self, name: str) -> frozenset[str]:
        if name not in self._ancestry:
            try:
                synset = wn.synset(name)
            except WordNetError, ValueError:
                self.unresolved.add(name)
                self._ancestry[name] = frozenset()
            else:
                up = synset.closure(lambda s: s.hypernyms() + s.instance_hypernyms())
                self._ancestry[name] = frozenset(a.name() for a in up)
        return self._ancestry[name]

    def hub(self, category: str) -> frozenset[str]:
        return frozenset(self.synset[r] for r in self.index.get((category, "noun"), ()) if r in self.synset)

    def type(self, category: str | None, rows) -> Typed:
        wordnet_rows = [r for r in rows if r in self.synset]
        outside = len(rows) - len(wordnet_rows)
        if not category:
            return Typed("", (), (), len(wordnet_rows), outside, NO_HEAD_CATEGORY)
        if category in self.most_general:
            return Typed(category, (), (), len(wordnet_rows), outside, MOST_GENERAL_CATEGORY)
        hub = self.hub(category)
        if not hub:
            return Typed(category, (), (), len(wordnet_rows), outside, NO_HUB_SYNSET)
        eligible = tuple(r for r in wordnet_rows if self.synset[r] in hub or self.ancestry(self.synset[r]) & hub)
        reason = "" if eligible else NONE_ELIGIBLE
        return Typed(category, tuple(sorted(hub)), eligible, len(wordnet_rows), outside, reason)
