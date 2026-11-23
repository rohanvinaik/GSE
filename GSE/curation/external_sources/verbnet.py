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


_EVENT_FORMS = {root: (root, "whole") for root in ("E", "E0", "E1")}
_EVENT_FORMS.update(
    {f"{phase}({root})": (root, phase) for root in ("E", "E0", "E1") for phase in ("start", "during", "end", "result")}
)
_UNDERGOER_EVENTS = frozenset({"motion", "transfer", "emotional_state"})


def _native_nodes(tree):
    if not isinstance(tree, dict):
        return
    yield tree
    for child in tree.get("children", []):
        yield from _native_nodes(child)


def _predicate_binding(predicate: dict) -> dict:
    """Read typed native polarity, phase and roles; never guess event syntax."""
    arguments = predicate.get("arguments")
    if not isinstance(arguments, list) or any(not isinstance(a, dict) for a in arguments):
        return {"code": "MALFORMED_NATIVE_ARGUMENTS"}
    if any(not isinstance(a.get("type"), str) or not isinstance(a.get("value"), str) for a in arguments):
        return {"code": "MALFORMED_NATIVE_ARGUMENTS"}
    negative, polarity = predicate.get("negated"), predicate.get("polarity", "")
    if not ((negative is False and polarity in ("", "+")) or (negative is True and polarity == "!")):
        return {"code": "UNSUPPORTED_NATIVE_POLARITY"}
    events = [a["value"] for a in arguments if a["type"] == "Event"]
    event_causer = predicate.get("predicate_value") == "cause" and len(events) == 2
    if (len(events) != 1 and not event_causer) or any(event not in _EVENT_FORMS for event in events):
        return {"code": "UNSUPPORTED_EVENT_FORM"}
    event, phase = _EVENT_FORMS[events[-1]]
    roles = tuple(a["value"].removeprefix("?") for a in arguments if a["type"] == "ThemRole")
    marked = tuple(
        a["value"].removeprefix("?") for a in arguments if a["type"] == "ThemRole" and a["value"].startswith("?")
    )
    constants = tuple((a["type"], a["value"]) for a in arguments if a["type"] not in {"Event", "ThemRole"})
    return {
        "code": "TYPED_NATIVE_BINDING",
        "event": event,
        "phase": phase,
        "roles": roles,
        "marked_roles": marked,
        "negative": negative,
        "event_causer": event_causer,
        "causing_event": _EVENT_FORMS[events[0]][0] if event_causer else None,
        "binding_key": (event, phase, roles, constants),
    }


def _component_status(frame: dict, name: str) -> dict:
    """Positive content survives later negation; same-phase conflicts do not."""
    predicates = frame.get("semantics", [])
    if not isinstance(predicates, list) or any(
        not isinstance(predicate, dict)
        or not isinstance(predicate.get("predicate_value"), str)
        or not predicate["predicate_value"]
        for predicate in predicates
    ):
        return {"code": "MALFORMED_NATIVE_SEMANTICS"}
    bindings = []
    signs = {}
    for index, predicate in enumerate(predicates):
        if predicate.get("predicate_value") != name:
            continue
        binding = _predicate_binding(predicate)
        if binding["code"] != "TYPED_NATIVE_BINDING":
            return binding
        signs.setdefault(binding["binding_key"], set()).add(binding["negative"])
        bindings.append({**binding, "predicate_index": index})
    if any(len(values) > 1 for values in signs.values()):
        return {"code": "CONTRADICTORY_NATIVE_BINDING"}
    positive = [binding for binding in bindings if not binding["negative"]]
    return {
        "code": "WARRANTED_LEXICAL_COMPONENT" if positive else "NO_POSITIVE_LEXICAL_COMPONENT",
        "bindings": positive,
    }


def _existence_change(frame: dict, binding: dict) -> bool:
    """Static participant existence does not supply a caused lexical change."""
    phases = {}
    for predicate in frame.get("semantics", []):
        if predicate.get("predicate_value") != "exist":
            continue
        candidate = _predicate_binding(predicate)
        if (
            candidate["code"] == "TYPED_NATIVE_BINDING"
            and candidate["event"] == binding["event"]
            and candidate["roles"] == binding["roles"]
        ):
            phases.setdefault(candidate["phase"], set()).add(candidate["negative"])
    return any(
        before != after
        for before in phases.get("start", ())
        for phase in ("end", "result")
        for after in phases.get(phase, ())
    )


def _cause_status(frame: dict, role_trees: dict[str, dict]) -> dict:
    """Require an actual lexical outcome for a confirmed other participant.

    Adapts upstream native_constraints.caused_change_status to this adapter's
    lossless frame schema. No lemma association or participant type contributes
    a bank. Only a guarded native cause supplies CAUSE and its causer component.
    """
    cause = _component_status(frame, "cause")
    if cause["code"] != "WARRANTED_LEXICAL_COMPONENT":
        return cause
    if not role_trees:
        return {"code": "PARTICIPANT_DECLARATIONS_UNAVAILABLE"}
    uncertain = {
        role
        for role, tree in role_trees.items()
        for node in _native_nodes(tree)
        if node.get("attributes", {}).get("type") == "body_part" and node.get("attributes", {}).get("Value") == "+"
    }
    for node in _native_nodes(frame.get("native", {})):
        if node.get("tag") == "NP" and any(
            child.get("attributes", {}).get("type") == "refl" and child.get("attributes", {}).get("Value") == "+"
            for child in _native_nodes(node)
        ):
            uncertain.add(node.get("attributes", {}).get("value"))
    proofs, blocked = [], set()
    for causer in cause["bindings"]:
        causer_roles = set(causer["roles"])
        if (
            (not causer_roles and not causer["event_causer"])
            or causer_roles - role_trees.keys()
            or causer_roles & uncertain
            or (causer["event_causer"] and causer["causing_event"] == causer["event"])
        ):
            blocked.add("CAUSER_IDENTITY_UNCONFIRMED")
            continue
        for index, predicate in enumerate(frame.get("semantics", [])):
            name = predicate.get("predicate_value")
            if name == "cause":
                continue
            binding = _predicate_binding(predicate)
            if binding["code"] != "TYPED_NATIVE_BINDING":
                blocked.add(binding["code"])
                continue
            if causer["event"] != "E" and binding["event"] != causer["event"]:
                continue
            affected = set(binding["roles"]) - causer_roles
            if not affected:
                continue
            if name == "Pred":
                blocked.add("CONSTRUCTION_RESULT_PLACEHOLDER")
                continue
            if name == "exist" and not _existence_change(frame, binding):
                blocked.add("PARTICIPANT_EXISTENCE_PRESUPPOSITION")
                continue
            if _component_status(frame, name)["code"] == "CONTRADICTORY_NATIVE_BINDING":
                blocked.add("CONTRADICTORY_NATIVE_BINDING")
                continue
            # A native ? marker does not remove the declared participant from
            # the predicate. Keep its binding, as upstream _roles does; this
            # is distinct from an uncertain WordNet sense-key attachment.
            bound = affected & role_trees.keys() - uncertain
            if not bound:
                blocked.add("AFFECTED_PARTICIPANT_IDENTITY_UNCONFIRMED")
                continue
            positive = not binding["negative"]
            if (
                binding["phase"] in {"end", "result"}
                or (positive and binding["phase"] == "during" and name in _UNDERGOER_EVENTS)
                or (positive and binding["phase"] == "whole" and name in {"begin", "end"})
            ):
                banks = {"CAUSE": 1}
                if "Agent" in causer_roles:
                    banks["DO"] = 1
                elif causer["event_causer"]:
                    banks["HAPPEN"] = 1
                proofs.append(
                    {
                        "cause_predicate": causer["predicate_index"],
                        "outcome_predicate": index,
                        "affected_roles": sorted(bound),
                        "primitives": banks,
                    }
                )
    return {
        "code": "BOUND_CAUSED_CHANGE" if proofs else "NO_CHANGE_TO_ANOTHER_PARTICIPANT",
        "proofs": proofs,
        "blocked_evidence": sorted(blocked),
    }


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
        """Only components warranted in every applicable native class frame.

        Positive phase-scoped components are retained; negation alone never
        fills a bank. CAUSE requires a bound lexical change in another
        participant. Raw source frames and exact sense-key links are unchanged.
        """
        return self.projection_diagnostics_for_entry(entry)["primitives"]

    def projection_diagnostics_for_entry(self, entry: VerbNetEntry) -> dict:
        """Named native decisions with the frame and predicate proof locations."""
        if not isinstance(entry, VerbNetEntry):
            raise ValueError("INVALID_VERBNET_ENTRY")
        if not isinstance(entry.class_context, list):
            raise ValueError("INVALID_VERBNET_CLASS_CONTEXT")
        roles = {}
        frames = []
        for level in entry.class_context:
            if (
                not isinstance(level, dict)
                or not isinstance(level.get("frames"), list)
                or any(not isinstance(frame, dict) for frame in level["frames"])
                or not isinstance(level.get("thematic_roles", []), list)
                or any(not isinstance(role, dict) for role in level.get("thematic_roles", []))
            ):
                raise ValueError("INVALID_VERBNET_CLASS_CONTEXT")
            for role in level.get("thematic_roles", []):
                name = role.get("attributes", {}).get("type")
                if isinstance(name, str) and name:
                    roles[name] = role
            frames.extend((level.get("class_id"), index, frame) for index, frame in enumerate(level["frames"]))
        if not frames:
            return {"code": "NO_APPLICABLE_FRAMES", "primitives": {}, "frames": []}
        diagnostics, proposals = [], []
        for class_id, frame_index, frame in frames:
            components = {
                bank: _component_status(frame, predicate)
                for predicate, bank in (("motion", "MOVE"), ("emotional_state", "FEEL"), ("desire", "WANT"))
            }
            projected = {
                bank: 1 for bank, result in components.items() if result["code"] == "WARRANTED_LEXICAL_COMPONENT"
            }
            cause = _cause_status(frame, roles)
            for proof in cause.get("proofs", []):
                projected.update(proof["primitives"])
            proposals.append(projected)
            diagnostics.append(
                {"class_id": class_id, "frame_index": frame_index, "components": components, "cause": cause}
            )
        universal = {
            bank: value
            for bank, value in proposals[0].items()
            if all(proposal.get(bank) == value for proposal in proposals[1:])
        }
        return {
            "code": "NATIVE_COMPONENTS_PROJECTED" if universal else "NO_UNIVERSAL_NATIVE_COMPONENT",
            "primitives": universal,
            "frames": diagnostics,
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
