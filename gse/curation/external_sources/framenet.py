"""
FrameNet Parser

1,221 semantic frames with frame elements (FEs):
- Core FEs: Required participants (Agent, Patient, Theme, etc.)
- Non-core FEs: Optional modifiers (Time, Place, Manner, etc.)

Maps frame semantics to GSE primitives based on:
- Frame type (action, state, perception, cognition, etc.)
- Core frame element roles
- Lexical unit (LU) participation
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional

from gse.curation.external_sources.base_parser import BaseExternalParser

logger = logging.getLogger(__name__)


@dataclass
class FrameNetEntry:
    """Entry from FrameNet."""

    word: str
    pos: str  # n, v, a, etc.
    frame_name: str
    frame_id: int
    core_fes: List[str]
    is_core_lu: bool  # Is this word a core lexical unit?


# Mapping from frame semantic types to GSE primitives
FRAME_TO_PRIMITIVE = {
    # Cognitive frames
    "Awareness": {"THINK": 1, "KNOW": 1},
    "Cognition": {"THINK": 1},
    "Coming_to_believe": {"KNOW": 1, "START": 1},
    "Remembering_experience": {"KNOW": 1, "BEFORE": 1},
    "Categorization": {"THINK": 1, "KNOW": 1},
    "Judgment": {"THINK": 1, "GOOD": 1},
    "Opinion": {"THINK": 1, "MAYBE": 1},
    "Certainty": {"KNOW": 1, "CERTAINTY": 1},
    "Deciding": {"THINK": 1, "WANT": 1},
    "Purpose": {"WANT": 1, "THINK": 1},
    # Perception frames
    "Perception": {"SEE": 1},
    "Perception_experience": {"FEEL": 1},
    "Perception_active": {"SEE": 1, "DO": 1},
    "Hear": {"HEAR": 1},
    "Seeking": {"SEE": 1, "WANT": 1},
    # Communication frames
    "Statement": {"SAY": 1, "WORDS": 1},
    "Communication": {"SAY": 1},
    "Request": {"SAY": 1, "WANT": 1},
    "Telling": {"SAY": 1, "WORDS": 1, "KNOW": 1},
    "Questioning": {"SAY": 1, "WANT": 1, "KNOW": 1},
    "Text_creation": {"SAY": 1, "WORDS": 1, "DO": 1},
    "Conversation": {"SAY": 1, "WORDS": 1},
    # Motion frames
    "Motion": {"MOVE": 1},
    "Self_motion": {"MOVE": 1, "BODY": 1, "DO": 1},
    "Cause_motion": {"MOVE": 1, "CAUSE": 1},
    "Motion_directional": {"MOVE": 1, "TOWARD": 1},
    "Departing": {"MOVE": 1, "AWAY": 1},
    "Arriving": {"MOVE": 1, "TOWARD": 1},
    "Traversing": {"MOVE": 1},
    "Bringing": {"MOVE": 1, "DO": 1},
    # Commercial frames
    "Commerce_buy": {"HAVE": 1, "START": 1},
    "Commerce_sell": {"HAVE": -1},
    "Commerce_pay": {"HAVE": -1},
    "Commerce_goods-transfer": {"HAVE": 1, "MOVE": 1},
    # Emotion frames
    "Emotions": {"FEEL": 1},
    "Experiencer_focus": {"FEEL": 1},
    "Stimulus_focus": {"CAUSE": 1, "FEEL": 1},
    "Emotions_by_stimulus": {"FEEL": 1, "CAUSE": 1},
    "Desiring": {"WANT": 1, "FEEL": 1},
    "Experiencer_obj": {"FEEL": 1, "CAUSE": 1},
    # Existence/state frames
    "Existence": {"EXIST": 1},
    "Being_located": {"WHERE": 1, "BE": 1},
    "Locative_relation": {"WHERE": 1},
    "Possession": {"HAVE": 1},
    "State": {"BE": 1},
    "Being_obligated": {"MUST": 1},
    "Capability": {"CAN": 1},
    # Causation frames
    "Causation": {"CAUSE": 1},
    "Cause_change": {"CAUSE": 1, "HAPPEN": 1},
    "Intentionally_affect": {"DO": 1, "CAUSE": 1},
    "Cause_harm": {"DO": 1, "GOOD": -1},
    "Killing": {"ALIVE": -1, "CAUSE": 1},
    # Creation/destruction
    "Creating": {"DO": 1, "START": 1, "CAUSE": 1},
    "Intentionally_create": {"DO": 1, "START": 1},
    "Building": {"DO": 1, "START": 1},
    "Destroying": {"DO": 1, "END": 1},
    # Body/physical
    "Body_movement": {"BODY": 1, "MOVE": 1},
    "Body_parts": {"BODY": 1, "PART": 1},
    "Ingestion": {"BODY": 1, "INSIDE": 1},
    "Breathing": {"BODY": 1, "ALIVE": 1},
    # Temporal
    "Duration_description": {"LONG_TIME": 1},
    "Temporal_collocation": {"WHEN": 1},
    "Time_period": {"WHEN": 1, "MOMENT": 1},
    "Frequency": {"WHEN": 1},
    # Social
    "Social_interaction_evaluation": {"SOMEONE": 1, "FEEL": 1},
    "Personal_relationship": {"SOMEONE": 1},
    "People_by_vocation": {"SOMEONE": 1, "DO": 1},
}


# Mapping from frame element names to primitives
FE_TO_PRIMITIVE = {
    # Agent/Actor roles
    "Agent": {"SOMEONE": 1, "DO": 1},
    "Actor": {"SOMEONE": 1, "DO": 1},
    "Protagonist": {"SOMEONE": 1},
    # Experiencer roles
    "Experiencer": {"SOMEONE": 1, "FEEL": 1},
    "Perceiver": {"SOMEONE": 1, "SEE": 1},
    "Perceiver_passive": {"SOMEONE": 1, "SEE": 1},
    "Cognizer": {"SOMEONE": 1, "THINK": 1},
    # Communication roles
    "Speaker": {"SOMEONE": 1, "SAY": 1},
    "Communicator": {"SOMEONE": 1, "SAY": 1},
    "Addressee": {"SOMEONE": 1},
    "Message": {"WORDS": 1, "SOMETHING": 1},
    "Topic": {"SOMETHING": 1},
    # Patient/Theme roles
    "Theme": {"SOMETHING": 1},
    "Patient": {"SOMETHING": 1},
    "Entity": {"SOMETHING": 1},
    "Item": {"SOMETHING": 1},
    # Spatial roles
    "Goal": {"TOWARD": 1},
    "Source": {"AWAY": 1},
    "Path": {"MOVE": 1},
    "Location": {"WHERE": 1},
    "Place": {"WHERE": 1},
    "Ground": {"WHERE": 1},
    "Area": {"WHERE": 1},
    "Direction": {"TOWARD": 1},
    # Temporal roles
    "Time": {"WHEN": 1},
    "Duration": {"LONG_TIME": 1},
    "Frequency": {"WHEN": 1},
    # Causal roles
    "Cause": {"CAUSE": 1},
    "Reason": {"BECAUSE": 1},
    "Purpose": {"WANT": 1, "BECAUSE": 1},
    "Explanation": {"BECAUSE": 1},
    # Manner/degree
    "Manner": {"LIKE": 1},
    "Degree": {"INTENSITY": 1},
    "Means": {"WITH": 1},
    "Instrument": {"SOMETHING": 1, "WITH": 1},
    # Self_mover specific
    "Self_mover": {"SOMEONE": 1, "MOVE": 1, "DO": 1},
}


class FrameNetParser(BaseExternalParser):
    """Parse FrameNet and map to GSE primitives."""

    def __init__(self):
        super().__init__()
        self.config.name = "framenet"
        self._frame_cache: Dict[str, Dict] = {}

    def load(self) -> bool:
        """Load FrameNet via NLTK."""
        try:
            import nltk
            from nltk.corpus import framenet as fn

            # Ensure downloaded
            try:
                fn.frames()
            except LookupError:
                logger.info("Downloading FrameNet...")
                nltk.download("framenet_v17", quiet=True)

            logger.info("Loading FrameNet entries...")
            count = 0

            for frame in fn.frames():
                frame_name = frame.name
                core_fes = [fe.name for fe in frame.FE.values() if hasattr(fe, "coreType") and fe.coreType == "Core"]

                # Cache frame metadata for quick lookup
                self._frame_cache[frame_name] = {
                    "id": frame.ID,
                    "core_fes": core_fes,
                    "definition": frame.definition[:200] if frame.definition else "",
                }

                # Extract lexical units
                for lu_name, lu in frame.lexUnit.items():
                    # Parse LU name: "buy.v" -> word="buy", pos="v"
                    parts = lu_name.rsplit(".", 1)
                    if len(parts) == 2:
                        word, pos = parts
                        word = word.lower().replace("_", " ")

                        entry = FrameNetEntry(
                            word=word,
                            pos=pos,
                            frame_name=frame_name,
                            frame_id=frame.ID,
                            core_fes=core_fes,
                            is_core_lu=True,
                        )

                        if word not in self.entries:
                            self.entries[word] = []
                        self.entries[word].append(entry)
                        count += 1

            logger.info(f"Loaded {count} FrameNet entries for {len(self.entries)} words")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load FrameNet: {e}")
            return False

    @lru_cache(maxsize=10000)
    def to_primitives(self, word: str) -> Dict[str, int]:
        """Map word to GSE primitives based on frame semantics."""
        if not self._loaded:
            self.load()

        word = word.lower()
        entries = self.entries.get(word, [])
        if not entries:
            return {}

        primitives: Dict[str, int] = {}

        for entry in entries:
            # Apply frame-type mappings
            if entry.frame_name in FRAME_TO_PRIMITIVE:
                for prim, val in FRAME_TO_PRIMITIVE[entry.frame_name].items():
                    if prim not in primitives:
                        primitives[prim] = val

            # Apply frame element mappings
            for fe in entry.core_fes:
                if fe in FE_TO_PRIMITIVE:
                    for prim, val in FE_TO_PRIMITIVE[fe].items():
                        if prim not in primitives:
                            primitives[prim] = val

        return primitives

    def get_all_words(self) -> List[str]:
        """Get all unique words."""
        if not self._loaded:
            self.load()
        return list(self.entries.keys())

    def get_frames_for_word(self, word: str) -> List[str]:
        """Get all frames a word participates in."""
        if not self._loaded:
            self.load()
        entries = self.entries.get(word.lower(), [])
        return list(set(e.frame_name for e in entries))

    def get_frame_info(self, frame_name: str) -> Optional[Dict]:
        """Get cached frame metadata."""
        if not self._loaded:
            self.load()
        return self._frame_cache.get(frame_name)


def download_framenet():
    """Download FrameNet via NLTK."""
    import nltk

    nltk.download("framenet_v17")
    print("FrameNet downloaded successfully")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = FrameNetParser()
    parser.load()

    # Test some words
    test_words = ["run", "walk", "say", "think", "love", "give", "make", "see", "buy"]
    for word in test_words:
        frames = parser.get_frames_for_word(word)
        primitives = parser.to_primitives(word)
        print(f"{word}: frames={frames[:3]}, primitives={primitives}")
