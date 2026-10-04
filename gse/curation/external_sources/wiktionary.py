"""
Wiktionary Local Dump Parser

Parses pre-processed Wiktionary dump for:
- Definitions (gloss text analysis)
- Etymology (derivation patterns)
- Part of speech
- Semantic relationships (synonyms, antonyms)

Uses SQLite for memory-efficient storage and querying.
Data source: kaikki.org pre-processed JSON dumps.
"""

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from gse.curation.external_sources.base_parser import BaseExternalParser

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "external"
WIKTIONARY_DIR = DATA_DIR / "wiktionary"
WIKTIONARY_DB = WIKTIONARY_DIR / "wiktionary-en.sqlite"


@dataclass
class WiktionaryEntry:
    """Entry from Wiktionary."""

    word: str
    pos: str
    definition: str
    etymology: Optional[str]
    synonyms: List[str]
    antonyms: List[str]


# Definition keywords to primitives mapping
# These patterns extract semantic primitives from definition text
DEFINITION_PATTERNS = {
    # Action/movement words
    r"\bto move\b|\bmoving\b|\bmotion\b": {"MOVE": 1},
    r"\bto run\b|\brunning\b": {"MOVE": 1, "BODY": 1},
    r"\bto walk\b|\bwalking\b": {"MOVE": 1, "BODY": 1},
    # Communication words
    r"\bto say\b|\bsaying\b|\bsaid\b": {"SAY": 1, "WORDS": 1},
    r"\bto tell\b|\btelling\b|\btold\b": {"SAY": 1, "WORDS": 1},
    r"\bto speak\b|\bspeaking\b|\bspoken\b": {"SAY": 1, "WORDS": 1},
    r"\bto write\b|\bwriting\b|\bwritten\b": {"SAY": 1, "WORDS": 1},
    r"\bcommunicat": {"SAY": 1},
    # Cognition words
    r"\bto think\b|\bthinking\b|\bthought\b": {"THINK": 1},
    r"\bto know\b|\bknowing\b|\bknowledge\b": {"KNOW": 1},
    r"\bto understand\b|\bunderstanding\b": {"KNOW": 1, "THINK": 1},
    r"\bto believe\b|\bbelief\b": {"THINK": 1, "MAYBE": 1},
    r"\bto remember\b|\bmemory\b": {"KNOW": 1, "BEFORE": 1},
    r"\bto learn\b|\blearning\b": {"KNOW": 1, "START": 1},
    r"\bmental\b|\bcognitive\b": {"THINK": 1},
    # Emotion/feeling words
    r"\bto feel\b|\bfeeling\b|\bfelt\b": {"FEEL": 1},
    r"\bemotion\b|\bemotional\b": {"FEEL": 1},
    r"\bhappy\b|\bhappiness\b|\bjoy\b": {"FEEL": 1, "GOOD": 1},
    r"\bsad\b|\bsadness\b|\bunhappy\b": {"FEEL": 1, "GOOD": -1},
    r"\banger\b|\bangry\b": {"FEEL": 1, "GOOD": -1},
    r"\bfear\b|\bafraid\b|\bscared\b": {"FEEL": 1, "GOOD": -1},
    r"\blove\b|\bloving\b": {"FEEL": 1, "GOOD": 1, "WANT": 1},
    r"\bhate\b|\bhatred\b": {"FEEL": 1, "GOOD": -1},
    # Perception words
    r"\bto see\b|\bseeing\b|\bsight\b|\bvisual\b": {"SEE": 1},
    r"\bto look\b|\blooking\b": {"SEE": 1, "WANT": 1},
    r"\bto hear\b|\bhearing\b|\bsound\b|\bauditory\b": {"HEAR": 1},
    r"\bto listen\b|\blistening\b": {"HEAR": 1, "WANT": 1},
    r"\bto touch\b|\btouching\b|\btactile\b": {"TOUCH": 1},
    r"\bto smell\b|\bsmelling\b|\bolfactory\b": {"FEEL": 1, "BODY": 1},
    r"\bto taste\b|\btasting\b|\bgustatory\b": {"FEEL": 1, "BODY": 1},
    # Desire/want
    r"\bto want\b|\bwanting\b|\bwish\b|\bdesire\b": {"WANT": 1},
    r"\bto need\b|\bneeding\b|\bnecessity\b": {"WANT": 1, "MUST": 1},
    # Action/doing
    r"\bto do\b|\bdoing\b|\baction\b": {"DO": 1},
    r"\bto make\b|\bmaking\b|\bcreate\b": {"DO": 1, "CAUSE": 1},
    r"\bto use\b|\busing\b": {"DO": 1, "WITH": 1},
    r"\bto work\b|\bworking\b": {"DO": 1},
    # Existence/state
    r"\bto be\b|\bbeing\b|\bstate of\b": {"BE": 1},
    r"\bto exist\b|\bexistence\b": {"EXIST": 1},
    r"\bto live\b|\bliving\b|\blife\b": {"ALIVE": 1, "EXIST": 1},
    r"\bto die\b|\bdying\b|\bdeath\b": {"ALIVE": -1, "END": 1},
    # Possession
    r"\bto have\b|\bhaving\b|\bpossess\b": {"HAVE": 1},
    r"\bto own\b|\bowning\b|\bproperty\b": {"HAVE": 1},
    r"\bto get\b|\bgetting\b|\bobtain\b": {"HAVE": 1, "START": 1},
    r"\bto give\b|\bgiving\b": {"HAVE": -1},
    r"\bto lose\b|\blosing\b|\bloss\b": {"HAVE": -1},
    # Change/happening
    r"\bto happen\b|\bhappening\b|\boccur\b": {"HAPPEN": 1},
    r"\bto change\b|\bchanging\b": {"HAPPEN": 1},
    r"\bto become\b|\bbecoming\b": {"HAPPEN": 1, "START": 1},
    # Evaluative
    r"\bgood\b|\bpositive\b|\bbeneficial\b|\bexcellent\b": {"GOOD": 1},
    r"\bbad\b|\bnegative\b|\bharmful\b|\bterrible\b": {"GOOD": -1},
    r"\bbig\b|\blarge\b|\bgreat\b|\bhuge\b": {"BIG": 1},
    r"\bsmall\b|\blittle\b|\btiny\b|\bminute\b": {"BIG": -1},
    # Spatial/temporal
    r"\babove\b|\bupper\b|\bhigh\b|\btop\b": {"ABOVE": 1},
    r"\bbelow\b|\blower\b|\bunder\b|\bbottom\b": {"BELOW": 1},
    r"\bbefore\b|\bprior\b|\bearlier\b|\bpreceding\b": {"BEFORE": 1},
    r"\bafter\b|\blater\b|\bsubsequent\b|\bfollowing\b": {"AFTER": 1},
    r"\binside\b|\bwithin\b|\binternal\b|\binner\b": {"INSIDE": 1},
    r"\boutside\b|\bexternal\b|\bouter\b": {"OUTSIDE": 1},
    r"\bnear\b|\bclose\b|\badjacent\b": {"NEAR": 1},
    r"\bfar\b|\bdistant\b|\bremote\b": {"FAR": 1},
    # Entity types
    r"\bperson\b|\bhuman\b|\bindividual\b|\bpeople\b": {"SOMEONE": 1},
    r"\bbody\b|\bphysical\b|\bcorporeal\b|\bbodily\b": {"BODY": 1},
    r"\bthing\b|\bobject\b|\bitem\b": {"SOMETHING": 1},
    r"\bplace\b|\blocation\b|\bsite\b": {"WHERE": 1},
    r"\btime\b|\bperiod\b|\bmoment\b": {"WHEN": 1},
    r"\babstract\b|\bconcept\b|\bidea\b": {"THINK": 1},
    # Causation
    r"\bcause\b|\bcausing\b|\bcaused by\b": {"CAUSE": 1},
    r"\bresult\b|\beffect\b|\bconsequence\b": {"CAUSE": 1},
    r"\bbecause\b|\breason\b|\bdue to\b": {"BECAUSE": 1},
    # Modality
    r"\bcan\b|\bable\b|\bcapable\b|\bability\b": {"CAN": 1},
    r"\bmust\b|\bshould\b|\bobligation\b|\brequired\b": {"MUST": 1},
    r"\bmaybe\b|\bperhaps\b|\bpossibly\b|\bmight\b": {"MAYBE": 1},
}

# Etymology patterns to primitives
ETYMOLOGY_PATTERNS = {
    r"negative prefix|un-|in-|dis-|non-": {"NOT": 1},
    r"causative": {"CAUSE": 1},
    r"diminutive": {"BIG": -1},
    r"augmentative": {"BIG": 1},
    r"frequentative": {"INTENSITY": 1},
    r"intensive": {"INTENSITY": 1},
}


class WiktionaryParser(BaseExternalParser):
    """Parse Wiktionary local dump and map to GSE primitives."""

    def __init__(self, db_path: Optional[Path] = None):
        super().__init__()
        self.config.name = "wiktionary"
        self.db_path = db_path or WIKTIONARY_DB
        self.conn: Optional[sqlite3.Connection] = None
        # Precompile regex patterns for performance
        self._compiled_def_patterns = {
            re.compile(pattern, re.IGNORECASE): prims for pattern, prims in DEFINITION_PATTERNS.items()
        }
        self._compiled_etym_patterns = {
            re.compile(pattern, re.IGNORECASE): prims for pattern, prims in ETYMOLOGY_PATTERNS.items()
        }

    def download_and_process(self) -> bool:
        """
        Download and process Wiktionary dump.

        Uses kaikki.org pre-processed JSON for efficiency.
        """
        try:
            import requests
        except ImportError:
            logger.error("requests library required for download")
            return False

        try:
            # Create directory
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Download pre-processed English dump
            url = "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.json"
            logger.info(f"Downloading Wiktionary data from {url}...")
            logger.info("This may take 10-15 minutes...")

            # Stream download to avoid memory issues
            response = requests.get(url, stream=True, timeout=600)
            response.raise_for_status()

            # Process into SQLite
            self._create_database()

            count = 0
            batch = []

            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    word = entry.get("word", "").lower()
                    if not word:
                        continue

                    pos = entry.get("pos", "")

                    # Get first definition
                    senses = entry.get("senses", [])
                    definition = ""
                    if senses and "glosses" in senses[0]:
                        definition = senses[0]["glosses"][0] if senses[0]["glosses"] else ""

                    # Get etymology
                    etymology = entry.get("etymology_text", "")

                    # Get related words
                    synonyms = []
                    antonyms = []
                    for sense in senses:
                        synonyms.extend([s.get("word", "") for s in sense.get("synonyms", []) if s.get("word")])
                        antonyms.extend([a.get("word", "") for a in sense.get("antonyms", []) if a.get("word")])

                    batch.append(
                        (
                            word,
                            pos,
                            definition,
                            etymology,
                            json.dumps(synonyms[:10]),  # Limit stored synonyms
                            json.dumps(antonyms[:10]),
                        )
                    )

                    if len(batch) >= 5000:
                        self._insert_batch(batch)
                        count += len(batch)
                        batch = []
                        if count % 50000 == 0:
                            logger.info(f"Processed {count:,} entries...")

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.debug(f"Error processing entry: {e}")
                    continue

            if batch:
                self._insert_batch(batch)
                count += len(batch)

            logger.info(f"Processed {count:,} Wiktionary entries")
            return True

        except Exception as e:
            logger.error(f"Failed to process Wiktionary: {e}")
            return False

    def _create_database(self):
        """Create SQLite database for Wiktionary data."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY,
                word TEXT NOT NULL,
                pos TEXT,
                definition TEXT,
                etymology TEXT,
                synonyms TEXT,
                antonyms TEXT
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_word ON entries(word)")
        self.conn.commit()

    def _insert_batch(self, batch: List):
        """Insert batch of entries."""
        self.conn.executemany(
            """
            INSERT INTO entries (word, pos, definition, etymology, synonyms, antonyms)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            batch,
        )
        self.conn.commit()

    def load(self) -> bool:
        """Load Wiktionary database."""
        if not self.db_path.exists():
            logger.info("Wiktionary database not found.")
            logger.info("Run download_and_process() to download from kaikki.org")
            logger.info("Or download manually and place at: {self.db_path}")
            return False

        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row

            cursor = self.conn.execute("SELECT COUNT(*) FROM entries")
            count = cursor.fetchone()[0]

            logger.info(f"Loaded Wiktionary database with {count:,} entries")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load Wiktionary: {e}")
            return False

    @lru_cache(maxsize=20000)
    def to_primitives(self, word: str) -> Dict[str, int]:
        """Map word to GSE primitives based on definition analysis."""
        if not self._loaded:
            if not self.load():
                return {}

        word = word.lower()

        cursor = self.conn.execute("SELECT * FROM entries WHERE word = ? LIMIT 5", (word,))
        rows = cursor.fetchall()

        if not rows:
            return {}

        primitives: Dict[str, int] = {}

        for row in rows:
            definition = row["definition"] or ""
            etymology = row["etymology"] or ""

            # Analyze definition text
            for pattern, prims in self._compiled_def_patterns.items():
                if pattern.search(definition):
                    for prim, val in prims.items():
                        if prim not in primitives:
                            primitives[prim] = val

            # Analyze etymology
            for pattern, prims in self._compiled_etym_patterns.items():
                if pattern.search(etymology):
                    for prim, val in prims.items():
                        if prim not in primitives:
                            primitives[prim] = val

        return primitives

    def get_all_words(self) -> List[str]:
        """Get all unique words (limited for memory)."""
        if not self._loaded:
            if not self.load():
                return []

        cursor = self.conn.execute("SELECT DISTINCT word FROM entries LIMIT 50000")
        return [row[0] for row in cursor.fetchall()]

    def get_definition(self, word: str) -> Optional[str]:
        """Get the primary definition for a word."""
        if not self._loaded:
            if not self.load():
                return None

        cursor = self.conn.execute("SELECT definition FROM entries WHERE word = ? LIMIT 1", (word.lower(),))
        row = cursor.fetchone()
        return row["definition"] if row else None

    def get_synonyms(self, word: str) -> List[str]:
        """Get synonyms for a word."""
        if not self._loaded:
            if not self.load():
                return []

        cursor = self.conn.execute("SELECT synonyms FROM entries WHERE word = ? LIMIT 1", (word.lower(),))
        row = cursor.fetchone()
        if row and row["synonyms"]:
            try:
                return json.loads(row["synonyms"])
            except:
                return []
        return []

    def get_antonyms(self, word: str) -> List[str]:
        """Get antonyms for a word."""
        if not self._loaded:
            if not self.load():
                return []

        cursor = self.conn.execute("SELECT antonyms FROM entries WHERE word = ? LIMIT 1", (word.lower(),))
        row = cursor.fetchone()
        if row and row["antonyms"]:
            try:
                return json.loads(row["antonyms"])
            except:
                return []
        return []

    def get_etymology(self, word: str) -> Optional[str]:
        """Get etymology for a word."""
        if not self._loaded:
            if not self.load():
                return None

        cursor = self.conn.execute(
            "SELECT etymology FROM entries WHERE word = ? AND etymology != '' LIMIT 1", (word.lower(),)
        )
        row = cursor.fetchone()
        return row["etymology"] if row else None

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
        super().close()


def download_wiktionary():
    """Download and process Wiktionary dump."""
    parser = WiktionaryParser()
    if parser.download_and_process():
        print("Wiktionary downloaded and processed successfully")
    else:
        print("Failed to download Wiktionary")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = WiktionaryParser()
    if parser.load():
        # Test some words
        test_words = ["dog", "run", "happy", "think", "person", "love", "water"]
        for word in test_words:
            definition = parser.get_definition(word)
            primitives = parser.to_primitives(word)
            print(f"{word}: primitives={primitives}")
            if definition:
                print(f"  def: {definition[:80]}...")
    else:
        print("Wiktionary not available - run download_wiktionary() to fetch data")
