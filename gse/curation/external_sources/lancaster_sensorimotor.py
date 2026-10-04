"""
Lancaster Sensorimotor Norms Parser

~40,000 words rated on 11 perceptual and motor dimensions:

Perceptual (0-5 scale):
- Auditory: how much is the concept experienced through hearing
- Gustatory: how much is the concept experienced through taste
- Haptic: how much is the concept experienced through touch
- Interoceptive: how much is the concept experienced through internal sensations
- Olfactory: how much is the concept experienced through smell
- Visual: how much is the concept experienced through vision

Action (0-5 scale):
- Foot/Leg: how much does interacting with the concept involve the foot/leg
- Hand/Arm: how much does interacting with the concept involve the hand/arm
- Head: how much does interacting with the concept involve the head (excluding mouth)
- Mouth: how much does interacting with the concept involve the mouth
- Torso: how much does interacting with the concept involve the torso

Maps to BODY, FEEL, SEE, HEAR, TOUCH, MOVE primitives.

Reference:
Lynott, D., Connell, L., Brysbaert, M., Brand, J., & Carney, J. (2020).
The Lancaster Sensorimotor Norms. Behavior Research Methods, 52, 1271-1291.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests

logger = logging.getLogger(__name__)

# Download URL from OSF
LANCASTER_URL = "https://osf.io/download/7emr6/"  # Direct download link
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "external"


@dataclass
class SensorimotorEntry:
    """Entry from Lancaster Sensorimotor Norms."""

    word: str
    # Perceptual modalities (0-5)
    auditory: float
    gustatory: float
    haptic: float
    interoceptive: float
    olfactory: float
    visual: float
    # Action effectors (0-5)
    foot_leg: float
    hand_arm: float
    head: float
    mouth: float
    torso: float
    # Composite scores
    max_perceptual: float = 0.0
    max_action: float = 0.0
    dominant_perceptual: str = ""
    dominant_action: str = ""

    def __post_init__(self):
        perceptual = {
            "auditory": self.auditory,
            "gustatory": self.gustatory,
            "haptic": self.haptic,
            "interoceptive": self.interoceptive,
            "olfactory": self.olfactory,
            "visual": self.visual,
        }
        action = {
            "foot_leg": self.foot_leg,
            "hand_arm": self.hand_arm,
            "head": self.head,
            "mouth": self.mouth,
            "torso": self.torso,
        }

        if perceptual:
            self.max_perceptual = max(perceptual.values())
            self.dominant_perceptual = max(perceptual, key=perceptual.get)
        if action:
            self.max_action = max(action.values())
            self.dominant_action = max(action, key=action.get)


# Mapping from sensorimotor dimensions to GSE primitives
DIMENSION_TO_PRIMITIVE = {
    # Perceptual modalities
    "auditory": {"HEAR": 1},
    "visual": {"SEE": 1},
    "haptic": {"TOUCH": 1, "BODY": 1},
    "gustatory": {"BODY": 1, "FEEL": 1},  # Taste is bodily feeling
    "olfactory": {"BODY": 1, "FEEL": 1},  # Smell is bodily feeling
    "interoceptive": {"BODY": 1, "FEEL": 1, "INSIDE": 1},  # Internal feelings
    # Action effectors - all involve BODY, MOVE, DO
    "foot_leg": {"BODY": 1, "MOVE": 1, "DO": 1},
    "hand_arm": {"BODY": 1, "DO": 1, "TOUCH": 1},
    "head": {"BODY": 1},
    "mouth": {"BODY": 1, "SAY": 1},  # Mouth often for speech
    "torso": {"BODY": 1},
}


class LancasterSensorimotorParser:
    """
    Parse Lancaster Sensorimotor Norms and map to GSE primitives.

    Mapping logic:
    - High auditory (>3.0) -> HEAR: +1
    - High visual (>3.0) -> SEE: +1
    - High haptic (>3.0) -> TOUCH: +1, BODY: +1
    - High interoceptive (>2.5) -> BODY: +1, FEEL: +1, INSIDE: +1
    - High action scores (>3.0) -> BODY: +1, MOVE: +1, DO: +1
    - Low sensorimotor overall (<1.5 max) -> Possibly abstract (THINK: +1)
    """

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = Path(data_path) if data_path else DATA_DIR / "lancaster_sensorimotor.csv"
        self.entries: Dict[str, SensorimotorEntry] = {}
        self._loaded = False

    def download(self) -> bool:
        """Download Lancaster Sensorimotor Norms."""
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Downloading Lancaster Sensorimotor Norms to {self.data_path}...")
            logger.info("This file is ~3MB, please wait...")

            response = requests.get(LANCASTER_URL, timeout=120, allow_redirects=True)
            response.raise_for_status()

            self.data_path.write_bytes(response.content)
            logger.info("Download complete")
            return True

        except Exception as e:
            logger.error(f"Failed to download Lancaster norms: {e}")
            logger.info("You may need to download manually from: https://osf.io/7emr6/")
            return False

    def load(self) -> bool:
        """Load Lancaster Sensorimotor Norms from file."""
        if not self.data_path.exists():
            logger.info("Lancaster norms not found, attempting download...")
            if not self.download():
                return False

        try:
            import csv

            logger.info(f"Loading Lancaster Sensorimotor Norms from {self.data_path}...")

            with open(self.data_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        # Get word (handle quoted values)
                        word = row.get("Word", "").strip('"').lower()
                        if not word:
                            continue

                        def get_float(key_variants):
                            for key in key_variants:
                                if key in row:
                                    val = row[key].strip()
                                    return float(val) if val else 0.0
                            return 0.0

                        entry = SensorimotorEntry(
                            word=word,
                            auditory=get_float(["Auditory.mean", "auditory.mean", "Auditory_mean"]),
                            gustatory=get_float(["Gustatory.mean", "gustatory.mean", "Gustatory_mean"]),
                            haptic=get_float(["Haptic.mean", "haptic.mean", "Haptic_mean"]),
                            interoceptive=get_float(["Interoceptive.mean", "interoceptive.mean", "Interoceptive_mean"]),
                            olfactory=get_float(["Olfactory.mean", "olfactory.mean", "Olfactory_mean"]),
                            visual=get_float(["Visual.mean", "visual.mean", "Visual_mean"]),
                            foot_leg=get_float(["Foot_leg.mean", "foot_leg.mean", "Foot/leg.mean"]),
                            hand_arm=get_float(["Hand_arm.mean", "hand_arm.mean", "Hand/arm.mean"]),
                            head=get_float(["Head.mean", "head.mean", "Head_mean"]),
                            mouth=get_float(["Mouth.mean", "mouth.mean", "Mouth_mean"]),
                            torso=get_float(["Torso.mean", "torso.mean", "Torso_mean"]),
                        )

                        self.entries[word] = entry

                    except ValueError, KeyError:
                        continue

            logger.info(f"Loaded {len(self.entries)} words from Lancaster norms")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load Lancaster norms: {e}")
            return False

    def get_sensorimotor(self, word: str) -> Optional[SensorimotorEntry]:
        """Get sensorimotor data for a word."""
        if not self._loaded:
            self.load()

        word = word.lower()
        return self.entries.get(word)

    def to_primitives(
        self,
        word: str,
        high_threshold: float = 3.0,  # 0-5 scale
        abstract_threshold: float = 1.5,  # Below this = abstract
    ) -> Dict[str, int]:
        """
        Map sensorimotor dimensions to GSE primitives.

        Args:
            word: Word to look up
            high_threshold: Above this value = strong modality (0-5 scale)
            abstract_threshold: If max is below this, word is likely abstract

        Returns:
            Dict with primitive values
        """
        entry = self.get_sensorimotor(word)
        if entry is None:
            return {}

        primitives: Dict[str, int] = {}

        # Check perceptual modalities
        if entry.auditory >= high_threshold:
            primitives["HEAR"] = 1
        if entry.visual >= high_threshold:
            primitives["SEE"] = 1
        if entry.haptic >= high_threshold:
            primitives["TOUCH"] = 1
            primitives["BODY"] = 1
        if entry.gustatory >= high_threshold - 0.5:  # Slightly lower threshold for taste
            primitives["BODY"] = 1
            primitives["FEEL"] = 1
        if entry.olfactory >= high_threshold - 0.5:  # Slightly lower for smell
            primitives["BODY"] = 1
        if entry.interoceptive >= high_threshold - 0.5:
            primitives["BODY"] = 1
            primitives["FEEL"] = 1
            primitives["INSIDE"] = 1

        # Check action modalities
        action_score = max(entry.foot_leg, entry.hand_arm, entry.head, entry.mouth, entry.torso)

        if action_score >= high_threshold:
            primitives["BODY"] = 1
            primitives["DO"] = 1

            if entry.foot_leg >= high_threshold:
                primitives["MOVE"] = 1
            if entry.hand_arm >= high_threshold:
                primitives["TOUCH"] = 1
            if entry.mouth >= high_threshold:
                primitives["SAY"] = 1

        # Check for abstract concepts (low sensorimotor scores)
        max_score = max(entry.max_perceptual, entry.max_action)
        if max_score < abstract_threshold:
            primitives["THINK"] = 1
            primitives["SOMETHING"] = -1  # Not a physical thing

        return primitives

    def get_all_words(self) -> List[str]:
        """Get all unique words."""
        if not self._loaded:
            self.load()
        return list(self.entries.keys())

    def get_new_words(self, existing_words: Set[str]) -> List[str]:
        """Get words not in existing set."""
        if not self._loaded:
            self.load()
        return [w for w in self.entries.keys() if w not in existing_words]

    def get_highly_embodied_words(self, threshold: float = 4.0) -> List[str]:
        """Get words with high bodily/action involvement."""
        if not self._loaded:
            self.load()
        return [
            w
            for w, e in self.entries.items()
            if e.max_action >= threshold or e.haptic >= threshold or e.interoceptive >= threshold
        ]

    def get_perceptual_words(self, modality: str, threshold: float = 4.0) -> List[str]:
        """Get words high on a specific perceptual modality."""
        if not self._loaded:
            self.load()

        modality = modality.lower()
        results = []

        for word, entry in self.entries.items():
            score = getattr(entry, modality, 0)
            if score >= threshold:
                results.append(word)

        return results

    def get_statistics(self) -> Dict[str, any]:
        """Get statistics about the loaded data."""
        if not self._loaded:
            self.load()

        if not self.entries:
            return {}

        # Calculate averages
        avgs = {
            "auditory": 0.0,
            "visual": 0.0,
            "haptic": 0.0,
            "gustatory": 0.0,
            "olfactory": 0.0,
            "interoceptive": 0.0,
            "foot_leg": 0.0,
            "hand_arm": 0.0,
            "head": 0.0,
            "mouth": 0.0,
            "torso": 0.0,
        }

        for entry in self.entries.values():
            avgs["auditory"] += entry.auditory
            avgs["visual"] += entry.visual
            avgs["haptic"] += entry.haptic
            avgs["gustatory"] += entry.gustatory
            avgs["olfactory"] += entry.olfactory
            avgs["interoceptive"] += entry.interoceptive
            avgs["foot_leg"] += entry.foot_leg
            avgs["hand_arm"] += entry.hand_arm
            avgs["head"] += entry.head
            avgs["mouth"] += entry.mouth
            avgs["torso"] += entry.torso

        n = len(self.entries)
        for key in avgs:
            avgs[key] /= n

        return {
            "total_words": n,
            "averages": avgs,
            "highly_visual": len(self.get_perceptual_words("visual", 4.0)),
            "highly_auditory": len(self.get_perceptual_words("auditory", 4.0)),
            "highly_embodied": len(self.get_highly_embodied_words(4.0)),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = LancasterSensorimotorParser()
    parser.load()

    # Print statistics
    stats = parser.get_statistics()
    print(f"\nLoaded {stats.get('total_words', 0)} words")
    print("\nAverage scores by dimension:")
    for dim, avg in stats.get("averages", {}).items():
        print(f"  {dim}: {avg:.2f}")

    # Test some words
    test_words = ["table", "music", "running", "love", "freedom", "pain", "red", "loud"]
    print("\nTest words:")
    for word in test_words:
        entry = parser.get_sensorimotor(word)
        primitives = parser.to_primitives(word)
        if entry:
            print(f"\n{word}:")
            print(f"  Visual: {entry.visual:.2f}, Auditory: {entry.auditory:.2f}")
            print(f"  Haptic: {entry.haptic:.2f}, Intero: {entry.interoceptive:.2f}")
            print(f"  Max Action: {entry.max_action:.2f} ({entry.dominant_action})")
            print(f"  -> Primitives: {primitives}")
        else:
            print(f"{word}: not found")
