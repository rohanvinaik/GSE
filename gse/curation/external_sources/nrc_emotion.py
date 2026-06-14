"""
NRC Emotion Lexicon (EmoLex) Parser

~14,000 words with 10 emotion dimensions:
- anger, fear, anticipation, trust, surprise, sadness, joy, disgust
- positive, negative

Maps to MENTAL bank primitives (FEEL, WANT, etc.) and GOOD/BAD.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests

logger = logging.getLogger(__name__)

# NRC EmoLex download URL (academic use)
EMOLEX_URL = "https://saifmohammad.com/WebDocs/NRC-Emotion-Lexicon-Wordlevel-v0.92.txt"
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "external"


@dataclass
class EmotionEntry:
    """Entry from NRC Emotion Lexicon."""
    word: str
    emotions: Dict[str, int]  # emotion -> 0/1


# Mapping from NRC emotions to GSE primitives
EMOTION_TO_PRIMITIVE = {
    'joy': {'GOOD': 1, 'FEEL': 1},
    'sadness': {'GOOD': -1, 'FEEL': 1},
    'anger': {'GOOD': -1, 'FEEL': 1, 'WANT': 1},
    'fear': {'GOOD': -1, 'FEEL': 1},
    'trust': {'GOOD': 1, 'FEEL': 1, 'KNOW': 1},
    'disgust': {'GOOD': -1, 'FEEL': 1},
    'surprise': {'FEEL': 1, 'KNOW': -1},  # unexpected = not-know
    'anticipation': {'FEEL': 1, 'WANT': 1, 'BEFORE': 1},
    'positive': {'GOOD': 1},
    'negative': {'GOOD': -1},
}


class NRCEmotionParser:
    """
    Parse NRC Emotion Lexicon and map to GSE primitives.

    Mapping logic:
    - joy -> GOOD: +1, FEEL: +1
    - sadness -> GOOD: -1, FEEL: +1
    - anger -> GOOD: -1, FEEL: +1, WANT: +1 (frustrated want)
    - fear -> GOOD: -1, FEEL: +1
    - trust -> GOOD: +1, FEEL: +1, KNOW: +1
    - disgust -> GOOD: -1, FEEL: +1
    - surprise -> FEEL: +1, KNOW: -1 (unexpected)
    - anticipation -> FEEL: +1, WANT: +1, BEFORE: +1
    """

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = Path(data_path) if data_path else DATA_DIR / "nrc_emotion.txt"
        self.entries: Dict[str, EmotionEntry] = {}
        self._loaded = False

    def download(self) -> bool:
        """Download NRC Emotion Lexicon."""
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Downloading NRC Emotion Lexicon to {self.data_path}...")
            response = requests.get(EMOLEX_URL, timeout=60)
            response.raise_for_status()

            self.data_path.write_text(response.text)
            logger.info("Download complete")
            return True

        except Exception as e:
            logger.error(f"Failed to download NRC EmoLex: {e}")
            logger.info("You may need to download manually from: https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm")
            return False

    def load(self) -> bool:
        """Load NRC Emotion Lexicon from file."""
        if not self.data_path.exists():
            logger.info("NRC Emotion Lexicon not found, attempting download...")
            if not self.download():
                return False

        try:
            logger.info(f"Loading NRC Emotion Lexicon from {self.data_path}...")

            with open(self.data_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    parts = line.split('\t')
                    if len(parts) != 3:
                        continue

                    word, emotion, value = parts
                    word = word.lower()
                    value = int(value)

                    if word not in self.entries:
                        self.entries[word] = EmotionEntry(word=word, emotions={})

                    self.entries[word].emotions[emotion] = value

            logger.info(f"Loaded {len(self.entries)} words from NRC EmoLex")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load NRC EmoLex: {e}")
            return False

    def get_emotions(self, word: str) -> Optional[Dict[str, int]]:
        """Get emotion scores for a word."""
        if not self._loaded:
            self.load()

        word = word.lower()
        if word not in self.entries:
            return None

        return self.entries[word].emotions

    def to_primitives(self, word: str) -> Dict[str, int]:
        """
        Map emotions to GSE primitives.

        Returns:
            Dict with primitive values based on emotion profile
        """
        emotions = self.get_emotions(word)
        if emotions is None:
            return {}

        primitives: Dict[str, int] = {}

        for emotion, value in emotions.items():
            if value == 1 and emotion in EMOTION_TO_PRIMITIVE:
                for prim, prim_val in EMOTION_TO_PRIMITIVE[emotion].items():
                    # Use max absolute value for conflicts
                    if prim not in primitives:
                        primitives[prim] = prim_val
                    elif abs(prim_val) > abs(primitives[prim]):
                        primitives[prim] = prim_val
                    elif prim_val == primitives[prim]:
                        pass  # Same value, keep it
                    # For conflicts (e.g., GOOD: +1 and GOOD: -1), use the stronger signal

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

    def get_emotion_words(self, emotion: str) -> List[str]:
        """Get all words with a specific emotion."""
        if not self._loaded:
            self.load()
        return [w for w, e in self.entries.items() if e.emotions.get(emotion, 0) == 1]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = NRCEmotionParser()
    parser.load()

    # Test some words
    test_words = ['happy', 'sad', 'angry', 'love', 'hate', 'fear', 'trust', 'surprise']
    for word in test_words:
        emotions = parser.get_emotions(word)
        primitives = parser.to_primitives(word)
        active_emotions = {k: v for k, v in (emotions or {}).items() if v == 1}
        print(f"{word}: emotions={active_emotions}, primitives={primitives}")
