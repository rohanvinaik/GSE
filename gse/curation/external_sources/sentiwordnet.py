"""
SentiWordNet Parser

Maps sentiment scores to GOOD/BAD primitives.
~117,000 synsets with positive/negative/objective scores.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SentiWordEntry:
    """Entry from SentiWordNet."""
    word: str
    pos: str
    pos_score: float  # 0-1
    neg_score: float  # 0-1
    obj_score: float  # 0-1 (objectivity = 1 - pos - neg)
    synset_id: str


class SentiWordNetParser:
    """
    Parse SentiWordNet and map to GSE GOOD/BAD primitives.

    Mapping logic:
    - pos_score > 0.5 -> GOOD: +1
    - neg_score > 0.5 -> GOOD: -1 (using bipolar encoding)
    - High objectivity -> GOOD: 0, BAD: 0
    """

    def __init__(self):
        self.entries: Dict[str, List[SentiWordEntry]] = {}
        self._loaded = False

    def load(self) -> bool:
        """Load SentiWordNet via NLTK."""
        try:
            import nltk
            from nltk.corpus import sentiwordnet as swn

            # Ensure downloaded
            try:
                swn.senti_synsets('good')
            except LookupError:
                logger.info("Downloading SentiWordNet...")
                nltk.download('sentiwordnet', quiet=True)
                nltk.download('wordnet', quiet=True)

            # Load all synsets
            logger.info("Loading SentiWordNet entries...")
            count = 0
            for synset in swn.all_senti_synsets():
                for lemma in synset.synset.lemmas():
                    word = lemma.name().lower().replace('_', ' ')
                    pos = synset.synset.pos()

                    entry = SentiWordEntry(
                        word=word,
                        pos=self._convert_pos(pos),
                        pos_score=synset.pos_score(),
                        neg_score=synset.neg_score(),
                        obj_score=synset.obj_score(),
                        synset_id=synset.synset.name(),
                    )

                    if word not in self.entries:
                        self.entries[word] = []
                    self.entries[word].append(entry)
                    count += 1

            logger.info(f"Loaded {count} SentiWordNet entries for {len(self.entries)} words")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load SentiWordNet: {e}")
            return False

    def _convert_pos(self, wn_pos: str) -> str:
        """Convert WordNet POS to standard."""
        pos_map = {'n': 'noun', 'v': 'verb', 'a': 'adj', 'r': 'adv', 's': 'adj'}
        return pos_map.get(wn_pos, 'unknown')

    def get_sentiment(self, word: str, pos: Optional[str] = None) -> Optional[Dict[str, float]]:
        """
        Get aggregated sentiment for a word.

        Returns:
            Dict with 'pos', 'neg', 'obj' average scores, or None if not found
        """
        if not self._loaded:
            self.load()

        word = word.lower()
        if word not in self.entries:
            return None

        entries = self.entries[word]
        if pos:
            entries = [e for e in entries if e.pos == pos]

        if not entries:
            return None

        # Average across senses
        avg_pos = sum(e.pos_score for e in entries) / len(entries)
        avg_neg = sum(e.neg_score for e in entries) / len(entries)
        avg_obj = sum(e.obj_score for e in entries) / len(entries)

        return {'pos': avg_pos, 'neg': avg_neg, 'obj': avg_obj}

    def to_primitives(self, word: str, pos: Optional[str] = None, threshold: float = 0.25) -> Dict[str, int]:
        """
        Map sentiment to GSE primitives.

        Args:
            word: Word to look up
            pos: Optional POS filter
            threshold: Min score to trigger +1/-1 (default 0.25)

        Returns:
            Dict with GOOD primitive value (using bipolar encoding)
        """
        sentiment = self.get_sentiment(word, pos)
        if sentiment is None:
            return {}

        primitives = {}

        # Use bipolar encoding: GOOD for both positive and negative
        # (BAD is encoded as GOOD: -1)
        if sentiment['pos'] > threshold and sentiment['pos'] > sentiment['neg']:
            primitives['GOOD'] = 1
        elif sentiment['neg'] > threshold and sentiment['neg'] > sentiment['pos']:
            primitives['GOOD'] = -1

        return primitives

    def get_all_words(self) -> List[str]:
        """Get all unique words in SentiWordNet."""
        if not self._loaded:
            self.load()
        return list(self.entries.keys())

    def get_new_words(self, existing_words: set) -> List[str]:
        """Get words not in existing set."""
        if not self._loaded:
            self.load()
        return [w for w in self.entries.keys() if w not in existing_words]


def download_sentiwordnet():
    """Download SentiWordNet via NLTK."""
    import nltk
    nltk.download('sentiwordnet')
    nltk.download('wordnet')
    nltk.download('omw-1.4')  # Open Multilingual WordNet
    print("SentiWordNet downloaded successfully")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = SentiWordNetParser()
    parser.load()

    # Test some words
    test_words = ['happy', 'sad', 'good', 'bad', 'neutral', 'walk', 'love', 'hate']
    for word in test_words:
        sentiment = parser.get_sentiment(word)
        primitives = parser.to_primitives(word)
        print(f"{word}: sentiment={sentiment}, primitives={primitives}")
