"""WordNet native taxonomy records and conservative definition-specific projection.

Legacy category proposals remain available for provenance. Only explicitly
warranted definition-specific IS-A roots yield lexical primitive assignments.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional

from GSE.curation.external_sources.base_parser import BaseExternalParser

logger = logging.getLogger(__name__)


@dataclass
class WordNetHierarchyEntry:
    """Entry with hierarchy data from WordNet."""

    word: str
    pos: str
    synset_name: str
    hypernym_depth: int  # Distance to root
    hyponym_count: int  # Number of descendants
    has_meronyms: bool
    has_holonyms: bool
    lexname: Optional[str]  # Semantic domain


# Semantic domains (lexnames) to primitives mapping
LEXNAME_TO_PRIMITIVE = {
    # Noun domains
    "noun.body": {"BODY": 1, "SOMETHING": 1},
    "noun.animal": {"ALIVE": 1, "SOMETHING": 1},
    "noun.person": {"SOMEONE": 1, "ALIVE": 1},
    "noun.cognition": {"THINK": 1},
    "noun.communication": {"SAY": 1, "WORDS": 1},
    "noun.feeling": {"FEEL": 1},
    "noun.location": {"WHERE": 1},
    "noun.time": {"WHEN": 1},
    "noun.quantity": {"QUANTITY": 1},
    "noun.artifact": {"SOMETHING": 1},
    "noun.food": {"SOMETHING": 1, "BODY": 1},
    "noun.substance": {"SOMETHING": 1},
    "noun.object": {"SOMETHING": 1},
    "noun.plant": {"ALIVE": 1, "SOMETHING": 1},
    "noun.shape": {"SOMETHING": 1},
    "noun.state": {"BE": 1},
    "noun.event": {"HAPPEN": 1},
    "noun.act": {"DO": 1},
    "noun.process": {"HAPPEN": 1},
    "noun.phenomenon": {"HAPPEN": 1},
    "noun.attribute": {"BE": 1},
    "noun.relation": {"WITH": 1},
    "noun.group": {"PEOPLE": 1},
    "noun.motive": {"WANT": 1},
    "noun.possession": {"HAVE": 1},
    # Verb domains
    "verb.motion": {"MOVE": 1},
    "verb.perception": {"SEE": 1},
    "verb.cognition": {"THINK": 1},
    "verb.communication": {"SAY": 1},
    "verb.emotion": {"FEEL": 1},
    "verb.creation": {"DO": 1, "START": 1},
    "verb.change": {"HAPPEN": 1},
    "verb.possession": {"HAVE": 1},
    "verb.body": {"BODY": 1, "DO": 1},
    "verb.consumption": {"BODY": 1},
    "verb.contact": {"TOUCH": 1, "DO": 1},
    "verb.stative": {"BE": 1},
    "verb.social": {"SOMEONE": 1, "DO": 1},
    "verb.competition": {"DO": 1},
    "verb.weather": {"HAPPEN": 1},
    # Adjective domains
    "adj.all": {},  # Too general
    "adj.pert": {},  # Pertaining to
    "adj.ppl": {},  # Participial
    # Adverb domains
    "adv.all": {},
}


# Root synsets that indicate specific primitives
ROOT_CONCEPT_PRIMITIVES = {
    "entity.n.01": {"SOMETHING": 1},
    "physical_entity.n.01": {"SOMETHING": 1},
    "abstraction.n.06": {"THINK": 1},
    "psychological_feature.n.01": {"FEEL": 1, "THINK": 1},
    "living_thing.n.01": {"ALIVE": 1},
    "organism.n.01": {"ALIVE": 1},
    "person.n.01": {"SOMEONE": 1},
    "causal_agent.n.01": {"DO": 1, "CAUSE": 1},
    "act.n.02": {"DO": 1},
    "event.n.01": {"HAPPEN": 1},
    "state.n.02": {"BE": 1},
    "state.n.04": {"BE": 1},
    "location.n.01": {"WHERE": 1},
    "time.n.01": {"WHEN": 1},
    "group.n.01": {"PEOPLE": 1},
    "body_part.n.01": {"BODY": 1, "PART": 1},
    "artifact.n.01": {"SOMETHING": 1},
    "natural_object.n.01": {"SOMETHING": 1},
    "substance.n.01": {"SOMETHING": 1},
    "communication.n.02": {"SAY": 1, "WORDS": 1},
    "cognition.n.01": {"THINK": 1, "KNOW": 1},
    "emotion.n.01": {"FEEL": 1},
    "feeling.n.01": {"FEEL": 1},
    "motivation.n.01": {"WANT": 1},
    "attribute.n.02": {"BE": 1},
    "relation.n.01": {"WITH": 1},
    "measure.n.02": {"QUANTITY": 1},
    "shape.n.02": {"SOMETHING": 1},
    "change.n.03": {"HAPPEN": 1},
    # Exact verb definitions, not the union of senses sharing these lemmas.
    "think.v.03": {"THINK": 1},
    "know.v.01": {"KNOW": 1},
    "desire.v.01": {"WANT": 1},
    "see.v.01": {"SEE": 1},
    "hear.v.01": {"HEAR": 1},
    "state.v.01": {"SAY": 1},
    "perform.v.01": {"DO": 1},
    "act.v.01": {"DO": 1},
    "cause.v.01": {"CAUSE": 1},
    "happen.v.01": {"HAPPEN": 1},
    "feel.v.01": {"FEEL": 1},
    "move.v.03": {"MOVE": 1},
    # Identity roots, 2026-11-25: each synset's own gloss is the prime's meaning, or it is the
    # release's approved prime-unit binding (prime_entries). act.n.02 is already above.
    "time_period.n.01": {"WHEN": 1},
    "time_unit.n.01": {"WHEN": 1},
    "people.n.01": {"PEOPLE": 1},
    "social_group.n.01": {"PEOPLE": 1},
    "word.n.01": {"WORDS": 1},
    "kind.n.01": {"KIND": 1},
    "part.n.01": {"PART": 1},
    "body.n.01": {"BODY": 1},
    "speech_act.n.01": {"SAY": 1},
    "travel.n.01": {"MOVE": 1},
    "motion.n.03": {"MOVE": 1},
    "say.v.01": {"SAY": 1},
    "travel.v.01": {"MOVE": 1},
    "touch.v.01": {"TOUCH": 1},
    "change.v.01": {"CAUSE": 1},
    "change.v.02": {"HAPPEN": 1},
    "make.v.03": {"CAUSE": 1},
    "be.v.01": {"BE": 1},
    "get.v.01": {"HAVE": 1},
    "induce.v.02": {"CAUSE": 1},
    "equal.v.01": {"SAME": 1},
    "enter.v.01": {"MOVE": 1},
    "leave.v.01": {"MOVE": 1},
}


# Exact categories that directly warrant a closed-basis coordinate.
# Generic groups need not be people; food is not BODY; abstraction is not
# thinking. A body part warrants PART, without asserting that it is BODY.
# Emotion and feeling warrant FEEL; psychological_feature is too broad.
_WARRANTED_ROOT_PRIMITIVES = {
    "entity.n.01": frozenset({"SOMETHING"}),
    "physical_entity.n.01": frozenset({"SOMETHING"}),
    "artifact.n.01": frozenset({"SOMETHING"}),
    "person.n.01": frozenset({"SOMEONE"}),
    "living_thing.n.01": frozenset({"ALIVE"}),
    "organism.n.01": frozenset({"ALIVE"}),
    "body_part.n.01": frozenset({"PART"}),
    "emotion.n.01": frozenset({"FEEL"}),
    "feeling.n.01": frozenset({"FEEL"}),
    # Native verb IS-A ancestry carries the specified act/state, without
    # propagating it to another sense of the same lemma. For example, see.v.01
    # is visual perception, not understanding or visiting; desire.v.01 is
    # wanting, not the lack/need senses also spelled "want". move.v.03 is
    # nontranslational motion, not emotional impact or abstract transfer.
    "think.v.03": frozenset({"THINK"}),
    "know.v.01": frozenset({"KNOW"}),
    "desire.v.01": frozenset({"WANT"}),
    "see.v.01": frozenset({"SEE"}),
    "hear.v.01": frozenset({"HEAR"}),
    "state.v.01": frozenset({"SAY"}),
    "perform.v.01": frozenset({"DO"}),
    "act.v.01": frozenset({"DO"}),
    "cause.v.01": frozenset({"CAUSE"}),
    "happen.v.01": frozenset({"HAPPEN"}),
    "feel.v.01": frozenset({"FEEL"}),
    "move.v.03": frozenset({"MOVE"}),
    # Identity: what a kind of these IS. A gloss that is the prime's own meaning, or the approved
    # prime-unit binding, carries the prime to every kind below it (a dog is an animal, a minute is an
    # amount of time). Reviewed 2026-11-25 with the founder's correction: identity is positive.
    "event.n.01": frozenset({"HAPPEN"}),  # "something that happens at a given place and time"
    "act.n.02": frozenset({"DO"}),  # "something that people do or cause to happen"
    "location.n.01": frozenset({"WHERE"}),  # "a point or extent in space"
    "time_period.n.01": frozenset({"WHEN"}),  # "an amount of time"
    "time_unit.n.01": frozenset({"WHEN"}),  # "a unit for measuring time periods"
    "measure.n.02": frozenset({"QUANTITY"}),  # "how much there is or how many there are of something"
    "people.n.01": frozenset({"PEOPLE"}),  # approved binding of PEOPLE
    "social_group.n.01": frozenset({"PEOPLE"}),  # "people sharing some social relation"
    "word.n.01": frozenset({"WORDS"}),  # approved binding of WORDS
    "kind.n.01": frozenset({"KIND"}),  # approved binding of KINDS
    "part.n.01": frozenset({"PART"}),  # approved binding of PARTS, less the reviewed substance branch
    "body.n.01": frozenset({"BODY"}),  # approved binding of BODY
    "speech_act.n.01": frozenset({"SAY"}),  # "the use of language to perform some act"
    "travel.n.01": frozenset({"MOVE"}),  # "the act of going from one place to another"
    "motion.n.03": frozenset({"MOVE"}),  # "a change of position that does not entail a change of location"
    "say.v.01": frozenset({"SAY"}),  # "express in words"
    "travel.v.01": frozenset({"MOVE"}),  # "change location; move, travel, or proceed"
    "touch.v.01": frozenset({"TOUCH"}),  # "make physical contact with"
    "change.v.01": frozenset({"CAUSE"}),  # "cause to change; make different"
    "change.v.02": frozenset({"HAPPEN"}),  # "undergo a change; become different"
    # Round 2 (2026-11-25).
    "state.n.02": frozenset({"BE"}),  # "the way something is"; Rohan: own state denotation suffices for BE
    "make.v.03": frozenset({"CAUSE"}),  # "make or cause to be or to become"
    "be.v.01": frozenset({"BE"}),  # "have the quality of being" (its troponyms are stative senses)
    "get.v.01": frozenset({"HAVE"}),  # "come into the possession of something"
    "induce.v.02": frozenset({"CAUSE"}),  # "cause to do; cause to act in a specified manner"
    "equal.v.01": frozenset({"SAME"}),  # "be identical or equivalent to"
    "enter.v.01": frozenset({"MOVE"}),  # "to come or go into"
    "leave.v.01": frozenset({"MOVE"}),  # "go away from a place"
}

# A root whose WordNet subtree files a branch the prime does not describe: (root, bank) -> branch.
# WordNet places all matter under part.n.01 ("the real physical matter of which a person or thing
# consists"); matter is not a component, so whale oil and chlorophyll are not PART.
REVIEWED_BRANCH_EXCLUSIONS = {
    ("part.n.01", "PART"): "substance.n.01",
    # The nonbeing branch's BE polarity is Rohan's open decision (reserved in the explicit-state round).
    ("state.n.02", "BE"): "nonbeing.n.01",
}


REVIEWED_SAY_EXCLUSIONS = {
    "bridle.v.03": "respond to the reins, as of horses",
    "rent.v.04": "hold under a lease or rental agreement; of goods and services",
    "summarize.v.02": "be a summary of",
}


def reviewed_say_exclusion(synset_name: str, definition: str) -> tuple[str, str]:
    """Return the withdrawn ancestor projection for one exact reviewed sense."""
    expected = REVIEWED_SAY_EXCLUSIONS.get(synset_name)
    if expected is None or expected != definition:
        raise ValueError("WORDNET_PROJECTION_REVIEW_SOURCE_CHANGED:" + synset_name)
    return "state.v.01", "SAY"


# Adjective identity (founder correction 2, 2026-11-25): a head adjective whose own gloss is a prime's
# pole, and every satellite in its cluster (a satellite refines its head: "huge" is a kind of large).
ADJECTIVE_IDENTITY_HEADS = {
    "good.a.01": {"GOOD": 1},  # "having desirable or positive qualities"
    "bad.a.01": {"GOOD": -1},  # "having undesirable or negative qualities"
    "large.a.01": {"BIG": 1},  # "above average in size or number or quantity or magnitude or extent"
    "small.a.01": {"BIG": -1},  # "limited or below average in number or quantity or magnitude or extent"
    "far.a.01": {"FAR": 1},  # "located at a great distance in time or space or degree"
    "distant.a.01": {"FAR": 1},  # "separated in space or coming from or going to a distance"
    "near.a.01": {"FAR": -1},  # "not far distant in time or space or degree or circumstances"
    "close.a.01": {"FAR": -1},  # "at or within a short distance in space or time"
    "true.a.01": {"TRUE": 1},  # "consistent with fact or reality; not false"
    "false.a.01": {"TRUE": -1},  # "not in accordance with the fact or reality or actuality"
    "same.a.01": {"SAME": 1},  # "same in identity"
    "other.a.01": {"SAME": -1},  # "not the same one or ones already mentioned or implied"
    "different.a.01": {"SAME": -1},  # "unlike in nature or quality or form or degree"
    "alive.a.01": {"ALIVE": 1},  # "possessing life"
    "dead.a.01": {"ALIVE": -1},  # "no longer having or seeming to have or expecting to have life"
}


def adjective_identity(synset) -> Dict[str, int]:
    """A head's own prime pole, or a satellite's head's; nothing for any other adjective."""
    if synset.pos() == "a":
        return dict(ADJECTIVE_IDENTITY_HEADS.get(synset.name(), {}))
    heads = [head.name() for head in synset.similar_tos() if head.pos() == "a"]
    return dict(ADJECTIVE_IDENTITY_HEADS.get(heads[0], {})) if len(heads) == 1 else {}


class WordNetHierarchyParser(BaseExternalParser):
    """Parse WordNet hierarchy and map to GSE primitives."""

    def __init__(self, max_hypernym_depth: int = 10):
        super().__init__()
        self.config.name = "wordnet_hierarchy"
        self.max_depth = max_hypernym_depth
        self._synset_cache: Dict[str, Dict] = {}
        self._wn = None  # Lazy-loaded WordNet module

    def load(self) -> bool:
        """Load WordNet hierarchy data."""
        try:
            import nltk
            from nltk.corpus import wordnet as wn

            # Ensure downloaded
            try:
                wn.synsets("test")
            except LookupError:
                logger.info("Downloading WordNet...")
                nltk.download("wordnet", quiet=True)
                nltk.download("omw-1.4", quiet=True)

            self._wn = wn

            logger.info("Building WordNet hierarchy index...")
            count = 0

            for synset in wn.all_synsets():
                # Get hierarchy metrics
                hyponyms = synset.hyponyms()

                # Calculate depth (distance to root)
                depth = self._get_hypernym_depth(synset)

                # Get domain
                lexname = synset.lexname() if hasattr(synset, "lexname") else None

                for lemma in synset.lemmas():
                    word = lemma.name().lower().replace("_", " ")
                    pos = self._convert_pos(synset.pos())

                    entry = WordNetHierarchyEntry(
                        word=word,
                        pos=pos,
                        synset_name=synset.name(),
                        hypernym_depth=depth,
                        hyponym_count=len(hyponyms),
                        has_meronyms=bool(
                            synset.part_meronyms() or synset.member_meronyms() or synset.substance_meronyms()
                        ),
                        has_holonyms=bool(
                            synset.part_holonyms() or synset.member_holonyms() or synset.substance_holonyms()
                        ),
                        lexname=lexname,
                    )

                    if word not in self.entries:
                        self.entries[word] = []
                    self.entries[word].append(entry)
                    count += 1

            logger.info(f"Loaded {count} WordNet entries for {len(self.entries)} words")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load WordNet hierarchy: {e}")
            return False

    def _get_hypernym_depth(self, synset) -> int:
        """Calculate depth from root (cached)."""
        try:
            paths = synset.hypernym_paths()
            if not paths:
                return 0
            return min(len(p) for p in paths)
        except Exception:
            return 0

    def _convert_pos(self, wn_pos: str) -> str:
        """Convert WordNet POS to readable form."""
        pos_map = {"n": "noun", "v": "verb", "a": "adj", "r": "adv", "s": "adj"}
        return pos_map.get(wn_pos, "unknown")

    @lru_cache(maxsize=10000)
    def to_primitives(self, word: str) -> Dict[str, int]:
        """Project only the primary definition through the shared exact-IS-A seam.

        Dictionary construction calls ``to_primitives_for_definition`` for
        every definition. This compatibility API keeps primary-sense behavior
        without reintroducing lexname heuristics or unioning secondary senses.
        """
        if not self._loaded:
            self.load()
        if self._wn is None:
            return {}
        synsets = self._wn.synsets(word.lower().replace(" ", "_"))
        if not synsets:
            return {}
        return self.to_primitives_for_definition(synsets[0].name())

    def to_primitives_for_definition(self, synset_name: str) -> Dict[str, int]:
        """Project one loaded native definition; never load or download here.

        Unknown or unavailable definitions abstain. Lexname proposals, part
        relations and argument slots do not assert own-word coordinates. Only
        the exact approved nominal and verbal ancestor categories are admitted; callers
        still enforce source scope and canonicalize bipolar coordinates.
        """
        if not self._loaded or self._wn is None:
            return {}
        if not isinstance(synset_name, str) or not synset_name:
            raise ValueError("INVALID_DEFINITION_ID")
        from nltk.corpus.reader.wordnet import WordNetError

        try:
            synset = self._wn.synset(synset_name)
        except LookupError, WordNetError:
            return {}
        if synset.pos() in ("a", "s"):
            return adjective_identity(synset)
        if synset.pos() not in ("n", "v"):
            return {}
        primitives: Dict[str, int] = {}
        ancestors = {ancestor.name() for path in synset.hypernym_paths() for ancestor in path}
        excluded = (
            reviewed_say_exclusion(synset_name, synset.definition()) if synset_name in REVIEWED_SAY_EXCLUSIONS else None
        )
        for name in sorted(ancestors):
            for primitive in sorted(_WARRANTED_ROOT_PRIMITIVES.get(name, ())):
                if (name, primitive) == excluded:
                    continue
                if REVIEWED_BRANCH_EXCLUSIONS.get((name, primitive)) in ancestors:
                    continue
                if primitive in ROOT_CONCEPT_PRIMITIVES.get(name, {}):
                    value = ROOT_CONCEPT_PRIMITIVES[name][primitive]
                    if type(value) is not int or value not in (-1, 0, 1):
                        raise ValueError("INVALID_TAXONOMY_VALUE")
                    if primitive in primitives and primitives[primitive] != value:
                        raise ValueError("CONFLICTING_TAXONOMY_VALUES")
                    primitives[primitive] = value
        if synset.pos() == "n" and {"act.n.02", "event.n.01"} & ancestors:
            # An act or event noun derived from verbs is the act of those verbs ("departure" is a
            # departing): it takes the identity every related verb shares (DO/HAPPEN come from its own
            # ancestry). A verb with no such identity leaves nothing shared.
            verbs = {
                form.synset()
                for lemma in synset.lemmas()
                for form in getattr(lemma, "derivationally_related_forms", list)()
                if form.synset().pos() == "v"
            }
            shared = None
            for verb in sorted(verbs, key=lambda item: item.name()):
                identity = {
                    bank: value
                    for bank, value in self.to_primitives_for_definition(verb.name()).items()
                    if bank not in ("DO", "HAPPEN")
                }
                shared = identity if shared is None else {b: v for b, v in shared.items() if identity.get(b) == v}
            for bank, value in sorted((shared or {}).items()):
                if primitives.get(bank, value) != value:
                    raise ValueError("CONFLICTING_TAXONOMY_VALUES")
                primitives[bank] = value
        if synset.pos() == "v" and getattr(synset, "causes", list)():
            # WordNet states the verb causes another ("kill" causes "die"): its definition is "cause to".
            if primitives.get("CAUSE", 1) != 1:
                raise ValueError("CONFLICTING_TAXONOMY_VALUES")
            primitives["CAUSE"] = 1
        return primitives

    def _apply_ancestor_primitives(self, word: str, primitives: Dict[str, int]):
        """Compatibility helper: primary definition only, preserving known values."""
        if self._wn is None:
            return
        for primitive, value in self.to_primitives(word).items():
            primitives.setdefault(primitive, value)

    def get_all_words(self) -> List[str]:
        """Get all unique words."""
        if not self._loaded:
            self.load()
        return list(self.entries.keys())

    def get_hypernyms(self, word: str, pos: Optional[str] = None) -> List[str]:
        """Get hypernym chain for a word."""
        if not self._loaded:
            self.load()

        if self._wn is None:
            return []

        try:
            pos_char = pos[0] if pos else None
            synsets = self._wn.synsets(word, pos=pos_char)
            if not synsets:
                return []

            hypernyms = []
            for path in synsets[0].hypernym_paths():
                hypernyms.extend([s.name().split(".")[0] for s in path])

            # Remove duplicates while preserving order
            seen = set()
            result = []
            for h in hypernyms:
                if h not in seen:
                    seen.add(h)
                    result.append(h)
            return result
        except Exception:
            return []

    def get_hyponyms(self, word: str, pos: Optional[str] = None) -> List[str]:
        """Get direct hyponyms for a word."""
        if not self._loaded:
            self.load()

        if self._wn is None:
            return []

        try:
            pos_char = pos[0] if pos else None
            synsets = self._wn.synsets(word, pos=pos_char)
            if not synsets:
                return []

            hyponyms = []
            for hypo in synsets[0].hyponyms():
                for lemma in hypo.lemmas():
                    hyponyms.append(lemma.name().lower().replace("_", " "))
            return hyponyms[:20]  # Limit results
        except Exception:
            return []

    def get_meronyms(self, word: str) -> List[str]:
        """Get part-of relations for a word."""
        if not self._loaded:
            self.load()

        if self._wn is None:
            return []

        try:
            synsets = self._wn.synsets(word)
            if not synsets:
                return []

            meronyms = []
            for synset in synsets[:3]:  # Check first 3 senses
                for mero in synset.part_meronyms() + synset.member_meronyms() + synset.substance_meronyms():
                    for lemma in mero.lemmas():
                        meronyms.append(lemma.name().lower().replace("_", " "))
            return list(set(meronyms))[:20]
        except Exception:
            return []

    def get_domain(self, word: str) -> Optional[str]:
        """Get the primary semantic domain for a word."""
        if not self._loaded:
            self.load()

        entries = self.entries.get(word.lower(), [])
        if entries:
            return entries[0].lexname
        return None


def download_wordnet():
    """Download WordNet via NLTK."""
    import nltk

    nltk.download("wordnet")
    nltk.download("omw-1.4")
    print("WordNet downloaded successfully")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = WordNetHierarchyParser()
    parser.load()

    # Test some words
    test_words = ["dog", "run", "happy", "think", "person", "hand", "love", "water", "tree"]
    for word in test_words:
        domain = parser.get_domain(word)
        primitives = parser.to_primitives(word)
        hypernyms = parser.get_hypernyms(word)[:3]
        print(f"{word}: domain={domain}, primitives={primitives}, hypernyms={hypernyms}")
