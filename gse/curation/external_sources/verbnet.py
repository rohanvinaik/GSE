"""
VerbNet Parser

6,000+ verbs in 270+ semantic classes with thematic roles:
- Agent, Patient, Theme, Experiencer, etc.

Maps verb classes to action/mental primitives.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class VerbNetEntry:
    """Entry from VerbNet."""

    word: str
    verb_class: str
    thematic_roles: List[str]
    wordnet_sense_keys: List[str] = field(default_factory=list)
    member_attributes: Dict[str, str] = field(default_factory=dict)
    class_context: List[dict] = field(default_factory=list)


def _native_xml(node) -> dict:
    """Lossless XML content tree, excluding only formatting between elements."""
    return {
        "tag": node.tag,
        "attributes": dict(node.attrib),
        "text": node.text or "",
        "tail": node.tail or "",
        "children": [_native_xml(child) for child in node],
    }


def _native_frame(frame) -> dict:
    return {
        "native": _native_xml(frame),
        "semantics": [
            {
                "predicate_value": predicate.get("value"),
                "negated": predicate.get("bool") == "!",
                "polarity": predicate.get("bool", ""),
                "arguments": [dict(argument.attrib) for argument in predicate.findall("ARGS/ARG")],
            }
            for predicate in frame.findall("SEMANTICS/PRED")
        ],
    }


def _explicit_event_predicate(frame: dict, name: str) -> bool:
    """Positive Event predicate only; negation or malformed polarity abstains."""
    predicates = [p for p in frame.get("semantics", []) if p.get("predicate_value") == name]
    if any(p.get("negated") is not False or p.get("polarity", "") not in ("", "+") for p in predicates):
        return False
    return any(
        any(
            argument.get("type") == "Event" and isinstance(argument.get("value"), str) and argument["value"]
            for argument in predicate.get("arguments", [])
        )
        for predicate in predicates
    )


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
        """Load native memberships, exact sense links and inherited frame context."""
        try:
            import nltk
            from nltk.corpus import verbnet as vn

            try:
                class_ids = vn.classids()
            except LookupError:
                logger.info("Downloading VerbNet...")
                nltk.download("verbnet", quiet=True)
                class_ids = vn.classids()

            nodes = {class_id: vn.vnclass(class_id) for class_id in class_ids}
            parents = {
                child.get("ID"): class_id
                for class_id, node in nodes.items()
                for child in node.findall("SUBCLASSES/VNSUBCLASS")
            }
            contexts = {}
            for class_id in class_ids:
                chain = []
                current = class_id
                seen = set()
                while current is not None:
                    if current in seen or current not in nodes:
                        raise ValueError("INVALID_VERBNET_CLASS_HIERARCHY")
                    seen.add(current)
                    node = nodes[current]
                    chain.append(
                        {
                            "class_id": current,
                            "thematic_roles": [_native_xml(role) for role in node.findall("THEMROLES/THEMROLE")],
                            "frames": [_native_frame(frame) for frame in node.findall("FRAMES/FRAME")],
                        }
                    )
                    current = parents.get(current)
                contexts[class_id] = list(reversed(chain))

            entries = {}
            count = 0
            for class_id, node in nodes.items():
                context = contexts[class_id]
                roles = sorted(
                    {
                        role["attributes"]["type"]
                        for level in context
                        for role in level["thematic_roles"]
                        if "type" in role["attributes"]
                    }
                )
                for member in node.findall("MEMBERS/MEMBER"):
                    word = member.get("name", "").lower().replace("_", " ")
                    if not word:
                        raise ValueError("MISSING_VERBNET_MEMBER_NAME")
                    entry = VerbNetEntry(
                        word=word,
                        verb_class=class_id,
                        thematic_roles=roles,
                        wordnet_sense_keys=member.get("wn", "").split(),
                        member_attributes=dict(member.attrib),
                        class_context=context,
                    )
                    entries.setdefault(word, []).append(entry)
                    count += 1
            self.entries = entries
            self._loaded = True
            logger.info("Loaded %s VerbNet memberships for %s verbs", count, len(entries))
            return True
        except Exception as error:
            logger.error("Failed to load VerbNet: %s", error)
            return False

    def definition_links(self, entry: VerbNetEntry, wordnet) -> List[dict]:
        """Resolve only explicitly attached, unmarked native WordNet sense keys.

        VerbNet omits the empty head-word/head-ID suffix on verb keys. Append
        its conventional ``::`` before exact WordNet lookup; no fuzzy match,
        key-prefix stripping or lemma-based sense guessing is performed.
        """
        from nltk.corpus.reader.wordnet import WordNetError

        if not entry.wordnet_sense_keys:
            return [{"code": "MISSING_SENSE_KEY"}]
        links = []
        for key in entry.wordnet_sense_keys:
            link = {"sense_key": key}
            if not isinstance(key, str) or not key:
                links.append(dict(link, code="INVALID_SENSE_KEY"))
                continue
            if key.startswith("?") or entry.member_attributes.get("name", entry.word).startswith("?"):
                links.append(dict(link, code="UNCERTAIN_SENSE_KEY"))
                continue
            if wordnet is None:
                links.append(dict(link, code="WORDNET_UNAVAILABLE"))
                continue
            normalized = key + "::" if key.count(":") == 2 else key
            link["normalized_sense_key"] = normalized
            try:
                lemma = wordnet.lemma_from_key(normalized)
            except LookupError, WordNetError, ValueError, KeyError:
                links.append(dict(link, code="INVALID_SENSE_KEY"))
                continue
            synset = lemma.synset()
            if lemma.name().lower().replace("_", " ") != entry.word or synset.pos() != "v":
                links.append(dict(link, code="SENSE_KEY_MISMATCH"))
                continue
            links.append(dict(link, code="LINKED", synset_name=synset.name()))
        return links

    def to_primitives_for_entry(self, entry: VerbNetEntry) -> Dict[str, int]:
        """Project only universal positive motion/causation event predicates.

        All native frames in the actual class/ancestor chain must warrant the
        predicate. A construction-specific cause cannot label every sense of
        a motion verb. Roles, class-name substrings and missing frames confer
        no assignments. Original nested arguments remain in class_context.
        """
        frames = [frame for level in entry.class_context for frame in level["frames"]]
        if not frames:
            return {}
        return {
            bank: 1
            for predicate, bank in (("motion", "MOVE"), ("cause", "CAUSE"))
            if all(_explicit_event_predicate(frame, predicate) for frame in frames)
        }

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
