"""
Brysbaert Concreteness Ratings Parser

40,000 words rated on 1-5 scale:
- 1 = highly abstract (e.g., "freedom", "idea")
- 5 = highly concrete (e.g., "table", "apple")

Maps to SOMETHING/BODY (concrete) vs THINK/abstract primitives.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests

logger = logging.getLogger(__name__)

# Brysbaert concreteness data
CONCRETENESS_URL = "https://raw.githubusercontent.com/ArtsEngine/concreteness/master/Concreteness_ratings.csv"
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "external"


@dataclass
class ConcretenessEntry:
    """Entry from concreteness ratings."""

    word: str
    concreteness: float  # 1-5 scale
    known_percent: float  # % of raters who knew the word
    n_ratings: int


class ConcretenessParser:
    """
    Parse Brysbaert Concreteness Ratings and map to GSE primitives.

    Mapping logic:
    - Concreteness >= 4.0 -> SOMETHING: +1, BODY: +1 (physical objects)
    - Concreteness <= 2.0 -> THINK: +1 (abstract concepts)
    - Mid-range -> no strong signal
    """

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = Path(data_path) if data_path else DATA_DIR / "concreteness.csv"
        self.entries: Dict[str, ConcretenessEntry] = {}
        self._loaded = False

    def download(self) -> bool:
        """Download concreteness ratings."""
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Downloading Concreteness Ratings to {self.data_path}...")
            response = requests.get(CONCRETENESS_URL, timeout=60)
            response.raise_for_status()

            self.data_path.write_text(response.text)
            logger.info("Download complete")
            return True

        except Exception as e:
            logger.error(f"Failed to download concreteness ratings: {e}")
            return False

    def load(self) -> bool:
        """Load concreteness ratings from file."""
        if not self.data_path.exists():
            logger.info("Concreteness ratings not found, attempting download...")
            if not self.download():
                return False

        try:
            logger.info(f"Loading Concreteness Ratings from {self.data_path}...")

            with open(self.data_path, "r", encoding="utf-8") as f:
                f.readline()  # skip the header row

                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # CSV format: Word,Bigram,Conc.M,Conc.SD,Unknown,%known,SUBTLEX,Dom_Pos
                    parts = line.split(",")
                    if len(parts) < 6:
                        continue

                    try:
                        word = parts[0].lower().strip('"')
                        concreteness = float(parts[2])
                        known_pct = float(parts[5]) if parts[5] else 100.0
                        # n_ratings not in this format, estimate
                        n_ratings = 30

                        self.entries[word] = ConcretenessEntry(
                            word=word,
                            concreteness=concreteness,
                            known_percent=known_pct,
                            n_ratings=n_ratings,
                        )
                    except ValueError, IndexError:
                        continue

            logger.info(f"Loaded {len(self.entries)} words from Concreteness Ratings")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load concreteness ratings: {e}")
            return False

    def get_concreteness(self, word: str) -> Optional[float]:
        """Get concreteness rating for a word (1-5 scale)."""
        if not self._loaded:
            self.load()

        word = word.lower()
        entry = self.entries.get(word)
        return entry.concreteness if entry else None

    def to_primitives(
        self,
        word: str,
        concrete_threshold: float = 4.0,
        abstract_threshold: float = 2.5,
    ) -> Dict[str, int]:
        """
        Map concreteness to GSE primitives.

        Args:
            word: Word to look up
            concrete_threshold: Above this = concrete (SOMETHING, BODY)
            abstract_threshold: Below this = abstract (THINK)

        Returns:
            Dict with primitive values
        """
        rating = self.get_concreteness(word)
        if rating is None:
            return {}

        primitives: Dict[str, int] = {}

        if rating >= concrete_threshold:
            # Highly concrete - physical objects
            primitives["SOMETHING"] = 1
            if rating >= 4.5:
                primitives["BODY"] = 1  # Very concrete, likely physical/bodily
        elif rating <= abstract_threshold:
            # Abstract concept
            primitives["THINK"] = 1
            if rating <= 1.8:
                # Extremely abstract
                primitives["SOMETHING"] = -1  # Not a thing

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

    def get_concrete_words(self, threshold: float = 4.5) -> List[str]:
        """Get highly concrete words."""
        if not self._loaded:
            self.load()
        return [w for w, e in self.entries.items() if e.concreteness >= threshold]

    def get_abstract_words(self, threshold: float = 2.0) -> List[str]:
        """Get highly abstract words."""
        if not self._loaded:
            self.load()
        return [w for w, e in self.entries.items() if e.concreteness <= threshold]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = ConcretenessParser()
    parser.load()

    # Test some words
    test_words = ["table", "chair", "apple", "freedom", "idea", "love", "rock", "abstract", "democracy"]
    for word in test_words:
        rating = parser.get_concreteness(word)
        primitives = parser.to_primitives(word)
        if rating:
            print(f"{word}: concreteness={rating:.2f} -> {primitives}")
        else:
            print(f"{word}: not found")
