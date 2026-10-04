"""
PropBank Parser

4,659 verb rolesets with semantic argument structures:
- ARG0: Proto-Agent (doer)
- ARG1: Proto-Patient (affected entity)
- ARG2-5: Various roles (beneficiary, instrument, etc.)
- ARGM-*: Modifiers (time, location, manner, etc.)

Maps argument structure patterns to GSE primitives.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional

from gse.curation.external_sources.base_parser import BaseExternalParser

logger = logging.getLogger(__name__)


@dataclass
class PropBankEntry:
    """Entry from PropBank."""

    lemma: str
    roleset_id: str  # e.g., "run.01"
    name: str  # e.g., "operate, proceed"
    roles: Dict[str, str]  # ARG0 -> "operator", ARG1 -> "machine"


# Mapping from PropBank argument types to GSE primitives
ARG_TO_PRIMITIVE = {
    "ARG0": {"SOMEONE": 1, "DO": 1},  # Agent/Causer
    "ARG1": {"SOMETHING": 1},  # Patient/Theme
    "ARG2": {},  # Varies by verb (beneficiary, instrument, attribute)
    "ARG3": {},  # Varies
    "ARG4": {},  # Varies
    "ARGM-TMP": {"WHEN": 1},  # Temporal
    "ARGM-LOC": {"WHERE": 1},  # Locative
    "ARGM-MNR": {"LIKE": 1},  # Manner
    "ARGM-CAU": {"BECAUSE": 1, "CAUSE": 1},  # Cause
    "ARGM-PRP": {"WANT": 1},  # Purpose
    "ARGM-DIR": {"TOWARD": 1},  # Direction
    "ARGM-EXT": {"INTENSITY": 1},  # Extent
    "ARGM-NEG": {"NOT": 1},  # Negation
    "ARGM-MOD": {"MAYBE": 1},  # Modal
    "ARGM-ADV": {},  # Adverbial (too general)
    "ARGM-DIS": {},  # Discourse marker
    "ARGM-GOL": {"TOWARD": 1},  # Goal
    "ARGM-PRD": {},  # Secondary predication
    "ARGM-REC": {},  # Reciprocal
}


# Mapping from roleset semantic classes/names
ROLESET_CLASS_TO_PRIMITIVE = {
    # Motion verbs
    "run": {"MOVE": 1, "BODY": 1},
    "walk": {"MOVE": 1, "BODY": 1},
    "move": {"MOVE": 1},
    "go": {"MOVE": 1},
    "come": {"MOVE": 1, "TOWARD": 1},
    "fly": {"MOVE": 1, "ABOVE": 1},
    "swim": {"MOVE": 1, "BODY": 1},
    "jump": {"MOVE": 1, "BODY": 1},
    "fall": {"MOVE": 1, "BELOW": 1},
    "rise": {"MOVE": 1, "ABOVE": 1},
    # Communication
    "say": {"SAY": 1, "WORDS": 1},
    "tell": {"SAY": 1, "WORDS": 1},
    "speak": {"SAY": 1, "WORDS": 1},
    "talk": {"SAY": 1, "WORDS": 1},
    "ask": {"SAY": 1, "WANT": 1},
    "answer": {"SAY": 1, "WORDS": 1},
    "call": {"SAY": 1},
    "write": {"SAY": 1, "WORDS": 1},
    "read": {"SEE": 1, "WORDS": 1},
    # Cognition
    "think": {"THINK": 1},
    "know": {"KNOW": 1},
    "believe": {"THINK": 1, "MAYBE": 1},
    "understand": {"KNOW": 1, "THINK": 1},
    "remember": {"KNOW": 1, "BEFORE": 1},
    "forget": {"KNOW": -1},
    "learn": {"KNOW": 1, "START": 1},
    "decide": {"THINK": 1, "WANT": 1},
    "expect": {"THINK": 1, "AFTER": 1},
    "hope": {"WANT": 1, "GOOD": 1},
    # Perception
    "see": {"SEE": 1},
    "look": {"SEE": 1, "WANT": 1},
    "watch": {"SEE": 1, "WANT": 1},
    "hear": {"HEAR": 1},
    "listen": {"HEAR": 1, "WANT": 1},
    "feel": {"FEEL": 1},
    "smell": {"FEEL": 1, "BODY": 1},
    "taste": {"FEEL": 1, "BODY": 1},
    "touch": {"TOUCH": 1},
    # Emotion
    "love": {"FEEL": 1, "GOOD": 1, "WANT": 1},
    "like": {"FEEL": 1, "GOOD": 1},
    "hate": {"FEEL": 1, "GOOD": -1},
    "fear": {"FEEL": 1, "GOOD": -1},
    "want": {"WANT": 1},
    "need": {"WANT": 1, "MUST": 1},
    "enjoy": {"FEEL": 1, "GOOD": 1},
    "suffer": {"FEEL": 1, "GOOD": -1},
    # Possession
    "have": {"HAVE": 1},
    "get": {"HAVE": 1, "START": 1},
    "give": {"HAVE": -1},
    "take": {"HAVE": 1, "DO": 1},
    "receive": {"HAVE": 1},
    "keep": {"HAVE": 1},
    "lose": {"HAVE": -1},
    "own": {"HAVE": 1},
    # Change of state
    "become": {"HAPPEN": 1, "START": 1},
    "change": {"HAPPEN": 1},
    "grow": {"BIG": 1, "HAPPEN": 1},
    "develop": {"HAPPEN": 1, "START": 1},
    "turn": {"HAPPEN": 1},
    # Creation/destruction
    "make": {"DO": 1, "CAUSE": 1, "START": 1},
    "create": {"DO": 1, "START": 1},
    "build": {"DO": 1, "START": 1},
    "produce": {"DO": 1, "CAUSE": 1},
    "destroy": {"DO": 1, "END": 1},
    "break": {"DO": 1, "END": 1},
    "kill": {"ALIVE": -1, "CAUSE": 1},
    "die": {"ALIVE": -1, "END": 1},
    # Existence
    "be": {"BE": 1},
    "exist": {"EXIST": 1},
    "live": {"ALIVE": 1, "EXIST": 1},
    "stay": {"BE": 1, "LONG_TIME": 1},
    "remain": {"BE": 1},
    # Action/doing
    "do": {"DO": 1},
    "try": {"DO": 1, "WANT": 1},
    "use": {"DO": 1, "WITH": 1},
    "work": {"DO": 1},
    "play": {"DO": 1, "GOOD": 1},
    "help": {"DO": 1, "GOOD": 1},
    "start": {"START": 1},
    "begin": {"START": 1},
    "stop": {"END": 1},
    "end": {"END": 1},
    "finish": {"END": 1},
    "continue": {"LONG_TIME": 1},
}


class PropBankParser(BaseExternalParser):
    """Parse PropBank and map to GSE primitives."""

    def __init__(self):
        super().__init__()
        self.config.name = "propbank"

    def load(self) -> bool:
        """Load PropBank via NLTK."""
        try:
            import nltk
            from nltk.corpus import propbank

            # Ensure downloaded
            try:
                propbank.rolesets()
            except LookupError:
                logger.info("Downloading PropBank...")
                nltk.download("propbank", quiet=True)

            logger.info("Loading PropBank entries...")
            count = 0

            for roleset in propbank.rolesets():
                roleset_id = roleset.attrib["id"]
                lemma = roleset_id.split(".")[0].lower()
                name = roleset.attrib.get("name", "")

                # Extract roles
                roles = {}
                for role in roleset.findall("roles/role"):
                    arg_num = role.attrib.get("n", "")
                    descr = role.attrib.get("descr", "")
                    roles[f"ARG{arg_num}"] = descr

                entry = PropBankEntry(
                    lemma=lemma,
                    roleset_id=roleset_id,
                    name=name,
                    roles=roles,
                )

                if lemma not in self.entries:
                    self.entries[lemma] = []
                self.entries[lemma].append(entry)
                count += 1

            logger.info(f"Loaded {count} PropBank rolesets for {len(self.entries)} verbs")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load PropBank: {e}")
            return False

    @lru_cache(maxsize=5000)
    def to_primitives(self, word: str) -> Dict[str, int]:
        """Map verb to GSE primitives based on argument structure."""
        if not self._loaded:
            self.load()

        word = word.lower()
        entries = self.entries.get(word, [])
        if not entries:
            return {}

        primitives: Dict[str, int] = {}

        # Check semantic class mappings first
        if word in ROLESET_CLASS_TO_PRIMITIVE:
            for prim, val in ROLESET_CLASS_TO_PRIMITIVE[word].items():
                primitives[prim] = val

        # Apply argument-based primitives
        for entry in entries:
            for arg_type in entry.roles.keys():
                if arg_type in ARG_TO_PRIMITIVE:
                    for prim, val in ARG_TO_PRIMITIVE[arg_type].items():
                        if prim not in primitives:
                            primitives[prim] = val

        # All verbs default to DO if no other mappings found
        if not primitives:
            primitives["DO"] = 1

        return primitives

    def get_all_words(self) -> List[str]:
        """Get all unique verbs."""
        if not self._loaded:
            self.load()
        return list(self.entries.keys())

    def get_rolesets(self, word: str) -> List[PropBankEntry]:
        """Get all rolesets for a verb."""
        if not self._loaded:
            self.load()
        return self.entries.get(word.lower(), [])

    def get_roleset_info(self, roleset_id: str) -> Optional[PropBankEntry]:
        """Get a specific roleset by ID."""
        if not self._loaded:
            self.load()

        lemma = roleset_id.split(".")[0].lower()
        entries = self.entries.get(lemma, [])
        for entry in entries:
            if entry.roleset_id == roleset_id:
                return entry
        return None


def download_propbank():
    """Download PropBank via NLTK."""
    import nltk

    nltk.download("propbank")
    print("PropBank downloaded successfully")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = PropBankParser()
    parser.load()

    # Test some verbs
    test_words = ["run", "walk", "say", "think", "love", "give", "make", "see", "buy"]
    for word in test_words:
        rolesets = parser.get_rolesets(word)
        primitives = parser.to_primitives(word)
        rs_ids = [rs.roleset_id for rs in rolesets[:3]]
        print(f"{word}: rolesets={rs_ids}, primitives={primitives}")
