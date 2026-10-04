"""
VerbNet Parser

6,000+ verbs in 270+ semantic classes with thematic roles:
- Agent, Patient, Theme, Experiencer, etc.

Maps verb classes to action/mental primitives.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class VerbNetEntry:
    """Entry from VerbNet."""

    word: str
    verb_class: str
    thematic_roles: List[str]


# Mapping from VerbNet thematic roles to GSE primitives
ROLE_TO_PRIMITIVE = {
    "Agent": {"SOMEONE": 1, "DO": 1},
    "Patient": {"SOMETHING": 1},
    "Theme": {"SOMETHING": 1},
    "Experiencer": {"SOMEONE": 1, "FEEL": 1},
    "Stimulus": {"CAUSE": 1},
    "Instrument": {"SOMETHING": 1, "WITH": 1},
    "Location": {"WHERE": 1},
    "Source": {"AWAY": 1},
    "Goal": {"TOWARD": 1},
    "Recipient": {"SOMEONE": 1},
    "Beneficiary": {"SOMEONE": 1, "GOOD": 1},
    "Time": {"WHEN": 1},
    "Manner": {"LIKE": 1},
}

# Mapping from VerbNet class names to primitives
CLASS_TO_PRIMITIVE = {
    # Motion verbs
    "run": {"MOVE": 1, "DO": 1, "BODY": 1},
    "walk": {"MOVE": 1, "DO": 1, "BODY": 1},
    "roll": {"MOVE": 1},
    "slide": {"MOVE": 1},
    "fly": {"MOVE": 1, "ABOVE": 1},
    "swim": {"MOVE": 1, "BODY": 1},
    # Communication verbs
    "say": {"SAY": 1, "WORDS": 1},
    "talk": {"SAY": 1, "WORDS": 1},
    "tell": {"SAY": 1, "WORDS": 1},
    "speak": {"SAY": 1, "WORDS": 1},
    "whisper": {"SAY": 1, "WORDS": 1, "INTENSITY": -1},
    "shout": {"SAY": 1, "WORDS": 1, "INTENSITY": 1},
    # Perception verbs
    "see": {"SEE": 1},
    "look": {"SEE": 1, "WANT": 1},
    "hear": {"HEAR": 1},
    "listen": {"HEAR": 1, "WANT": 1},
    "smell": {"FEEL": 1, "BODY": 1},
    "taste": {"FEEL": 1, "BODY": 1},
    "touch": {"TOUCH": 1, "BODY": 1},
    # Cognition verbs
    "think": {"THINK": 1},
    "know": {"KNOW": 1},
    "believe": {"THINK": 1, "MAYBE": 1},
    "understand": {"KNOW": 1, "THINK": 1},
    "remember": {"KNOW": 1, "BEFORE": 1},
    "forget": {"KNOW": -1, "BEFORE": 1},
    "learn": {"KNOW": 1, "START": 1},
    # Emotion verbs
    "love": {"FEEL": 1, "GOOD": 1, "WANT": 1},
    "hate": {"FEEL": 1, "GOOD": -1},
    "fear": {"FEEL": 1, "GOOD": -1},
    "enjoy": {"FEEL": 1, "GOOD": 1},
    "suffer": {"FEEL": 1, "GOOD": -1},
    # Possession verbs
    "have": {"HAVE": 1},
    "get": {"HAVE": 1, "START": 1},
    "give": {"HAVE": -1},  # Transfer away
    "take": {"HAVE": 1},
    "own": {"HAVE": 1},
    # Existence verbs
    "be": {"BE": 1},
    "exist": {"EXIST": 1},
    "live": {"ALIVE": 1, "EXIST": 1},
    "die": {"ALIVE": -1, "END": 1},
    # Creation/destruction
    "make": {"DO": 1, "CAUSE": 1, "START": 1},
    "create": {"DO": 1, "CAUSE": 1, "START": 1},
    "build": {"DO": 1, "START": 1},
    "destroy": {"DO": 1, "END": 1},
    "break": {"DO": 1, "END": 1},
    # Change verbs
    "change": {"HAPPEN": 1},
    "become": {"BE": 1, "START": 1},
    "grow": {"BIG": 1, "HAPPEN": 1},
    "shrink": {"BIG": -1, "HAPPEN": 1},
}


class VerbNetParser:
    """
    Parse VerbNet and map to GSE primitives.

    Uses NLTK's VerbNet corpus.
    """

    def __init__(self):
        self.entries: Dict[str, List[VerbNetEntry]] = {}
        self._loaded = False

    def load(self) -> bool:
        """Load VerbNet via NLTK."""
        try:
            import nltk
            from nltk.corpus import verbnet as vn

            # Ensure downloaded
            try:
                vn.classids()
            except LookupError:
                logger.info("Downloading VerbNet...")
                nltk.download("verbnet", quiet=True)

            logger.info("Loading VerbNet entries...")
            count = 0

            for classid in vn.classids():
                try:
                    # Get lemmas for this class
                    lemmas = vn.lemmas(classid)

                    # Get thematic roles
                    try:
                        roles = [r.attrib.get("type", "") for r in vn.vnclass(classid).findall(".//THEMROLE")]
                    except:
                        roles = []

                    for lemma in lemmas:
                        word = lemma.lower()

                        entry = VerbNetEntry(
                            word=word,
                            verb_class=classid,
                            thematic_roles=roles,
                        )

                        if word not in self.entries:
                            self.entries[word] = []
                        self.entries[word].append(entry)
                        count += 1

                except Exception as e:
                    logger.debug(f"Error processing class {classid}: {e}")

            logger.info(f"Loaded {count} VerbNet entries for {len(self.entries)} verbs")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load VerbNet: {e}")
            return False

    def get_verb_info(self, word: str) -> Optional[List[VerbNetEntry]]:
        """Get VerbNet info for a verb."""
        if not self._loaded:
            self.load()

        word = word.lower()
        return self.entries.get(word)

    def to_primitives(self, word: str) -> Dict[str, int]:
        """
        Map verb to GSE primitives based on class and roles.

        Returns:
            Dict with primitive values
        """
        entries = self.get_verb_info(word)
        if entries is None:
            return {}

        primitives: Dict[str, int] = {}

        # Check class-based mappings first
        word_lower = word.lower()
        for class_prefix, prims in CLASS_TO_PRIMITIVE.items():
            if word_lower == class_prefix or any(class_prefix in e.verb_class for e in entries):
                for prim, val in prims.items():
                    if prim not in primitives:
                        primitives[prim] = val

        # Add role-based primitives
        all_roles = set()
        for entry in entries:
            all_roles.update(entry.thematic_roles)

        for role in all_roles:
            if role in ROLE_TO_PRIMITIVE:
                for prim, val in ROLE_TO_PRIMITIVE[role].items():
                    if prim not in primitives:
                        primitives[prim] = val

        # Default: all verbs involve DO
        if not primitives:
            primitives["DO"] = 1

        return primitives

    def get_all_words(self) -> List[str]:
        """Get all unique verbs."""
        if not self._loaded:
            self.load()
        return list(self.entries.keys())

    def get_new_words(self, existing_words: Set[str]) -> List[str]:
        """Get verbs not in existing set."""
        if not self._loaded:
            self.load()
        return [w for w in self.entries.keys() if w not in existing_words]


def download_verbnet():
    """Download VerbNet via NLTK."""
    import nltk

    nltk.download("verbnet")
    nltk.download("verbnet3")
    print("VerbNet downloaded successfully")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = VerbNetParser()
    parser.load()

    # Test some verbs
    test_words = ["run", "walk", "say", "think", "love", "give", "make", "see", "hear"]
    for word in test_words:
        info = parser.get_verb_info(word)
        primitives = parser.to_primitives(word)
        classes = [e.verb_class for e in (info or [])][:3]
        print(f"{word}: classes={classes}, primitives={primitives}")
