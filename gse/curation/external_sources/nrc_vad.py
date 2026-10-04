"""
NRC VAD (Valence-Arousal-Dominance) Lexicon Parser

20,000 words with continuous scores (0-1):
- Valence: negative to positive (maps to GOOD/BAD)
- Arousal: calm to excited (maps to INTENSITY)
- Dominance: submissive to dominant (maps to CAN/MUST)
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests

logger = logging.getLogger(__name__)

# NRC VAD download URL
VAD_URL = "https://saifmohammad.com/WebDocs/VAD/NRC-VAD-Lexicon.txt"
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "external"


@dataclass
class VADEntry:
    """Entry from NRC VAD Lexicon."""

    word: str
    valence: float  # 0-1 (0=negative, 1=positive)
    arousal: float  # 0-1 (0=calm, 1=excited)
    dominance: float  # 0-1 (0=submissive, 1=dominant)


class NRCVADParser:
    """
    Parse NRC VAD Lexicon and map to GSE primitives.

    Mapping logic:
    - Valence > 0.6 -> GOOD: +1
    - Valence < 0.4 -> GOOD: -1
    - Arousal > 0.6 -> INTENSITY: +1
    - Arousal < 0.4 -> INTENSITY: -1
    - Dominance > 0.7 -> CAN: +1 (able/powerful)
    - Dominance < 0.3 -> MUST: +1 (constrained/submissive)
    """

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = Path(data_path) if data_path else DATA_DIR / "nrc_vad.txt"
        self.entries: Dict[str, VADEntry] = {}
        self._loaded = False

    def download(self) -> bool:
        """Download NRC VAD Lexicon."""
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Downloading NRC VAD Lexicon to {self.data_path}...")
            response = requests.get(VAD_URL, timeout=60)
            response.raise_for_status()

            self.data_path.write_text(response.text)
            logger.info("Download complete")
            return True

        except Exception as e:
            logger.error(f"Failed to download NRC VAD: {e}")
            logger.info("You may need to download manually from: https://saifmohammad.com/WebPages/nrc-vad.html")
            return False

    def load(self) -> bool:
        """Load NRC VAD Lexicon from file."""
        if not self.data_path.exists():
            logger.info("NRC VAD Lexicon not found, attempting download...")
            if not self.download():
                return False

        try:
            logger.info(f"Loading NRC VAD Lexicon from {self.data_path}...")

            with open(self.data_path, "r", encoding="utf-8") as f:
                f.readline()  # skip the header row

                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split("\t")
                    if len(parts) != 4:
                        continue

                    word, valence, arousal, dominance = parts
                    word = word.lower()

                    self.entries[word] = VADEntry(
                        word=word,
                        valence=float(valence),
                        arousal=float(arousal),
                        dominance=float(dominance),
                    )

            logger.info(f"Loaded {len(self.entries)} words from NRC VAD")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load NRC VAD: {e}")
            return False

    def get_vad(self, word: str) -> Optional[VADEntry]:
        """Get VAD scores for a word."""
        if not self._loaded:
            self.load()

        word = word.lower()
        return self.entries.get(word)

    def to_primitives(
        self,
        word: str,
        valence_threshold: float = 0.15,  # Distance from 0.5
        arousal_threshold: float = 0.15,
        dominance_threshold: float = 0.2,
    ) -> Dict[str, int]:
        """
        Map VAD to GSE primitives.

        Current scope: valence only (GOOD/BAD). Arousal and dominance no
        longer contribute. The previous mappings (Arousal → INTENSITY,
        Dominance → CAN/MUST) were category errors — INTENSITY is the
        GSE hierarchy anchor for BARELY/SLIGHTLY/.../EXTREMELY, not a
        generic intensity tag; CAN/MUST are logical-modal primitives,
        not affective. NRC VAD votes on those primitives produced
        systematic cross-bank pollution (May 2026 antonym investigation).

        Arousal and dominance are still affective signals worth keeping
        ``arousal_threshold`` and ``dominance_threshold`` parameters for
        backwards compat, but they do not influence the output until a
        principled mapping to MENTAL primitives (FEEL/WANT) is added.
        """
        del arousal_threshold, dominance_threshold  # parameters retained for compat

        vad = self.get_vad(word)
        if vad is None:
            return {}

        primitives: Dict[str, int] = {}

        # Valence -> GOOD (bipolar). The reliable signal NRC VAD provides.
        if vad.valence > 0.5 + valence_threshold:
            primitives["GOOD"] = 1
        elif vad.valence < 0.5 - valence_threshold:
            primitives["GOOD"] = -1

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

    def get_high_valence_words(self, threshold: float = 0.8) -> List[str]:
        """Get words with high positive valence."""
        if not self._loaded:
            self.load()
        return [w for w, e in self.entries.items() if e.valence >= threshold]

    def get_low_valence_words(self, threshold: float = 0.2) -> List[str]:
        """Get words with low (negative) valence."""
        if not self._loaded:
            self.load()
        return [w for w, e in self.entries.items() if e.valence <= threshold]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = NRCVADParser()
    parser.load()

    # Test some words
    test_words = ["happy", "sad", "angry", "calm", "excited", "powerful", "weak", "love", "hate"]
    for word in test_words:
        vad = parser.get_vad(word)
        primitives = parser.to_primitives(word)
        if vad:
            print(f"{word}: V={vad.valence:.2f} A={vad.arousal:.2f} D={vad.dominance:.2f} -> {primitives}")
        else:
            print(f"{word}: not found")
