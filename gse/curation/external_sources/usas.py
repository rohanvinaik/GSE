"""
USAS Semantic Tagger Parser

Parses the UCREL Semantic Analysis System (USAS) lexicon for:
- 21 major semantic fields (A-Z categories)
- 232 fine-grained semantic tags
- Maps to GSE primitives via category mappings

Data source: https://github.com/UCREL/Multilingual-USAS
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from gse.curation.external_sources.base_parser import BaseExternalParser

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "external" / "usas"


@dataclass
class USASEntry:
    """Entry from USAS lexicon."""

    lemma: str
    pos: str
    semantic_tags: List[str]  # e.g., ["M1", "A1.1.1"]


# USAS category to GSE primitive mappings
# Based on USAS tagset: https://ucrel.lancs.ac.uk/usas/USASSemanticTagset.pdf
USAS_TO_GSE = {
    # A: General and abstract terms
    "A1": {"BE": 1},  # Being, existing
    "A2": {"DO": 1},  # Affect (cause/effect)
    "A3": {},  # Comparing
    "A4": {},  # Classification
    "A5": {"CAUSE": 1},  # Evaluation
    "A6": {"SAME": 1},  # Comparing: Similar/different
    "A7": {"MAYBE": 1},  # Probability
    "A8": {},  # Seem/appear
    "A9": {"INTENSITY": 1},  # Getting/losing
    "A10": {"CAN": 1, "MUST": 1},  # Open/closed
    "A11": {},  # Importance
    "A12": {},  # Easy/difficult
    "A13": {"SAME": 1, "OTHER": 1},  # Degree
    "A14": {},  # Exclusivizers
    "A15": {},  # Safety/danger
    # B: The body and the individual
    "B1": {"BODY": 1},  # Anatomy and physiology
    "B2": {"BODY": 1, "ALIVE": 1},  # Health and disease
    "B3": {"BODY": 1},  # Medicines
    "B4": {"BODY": 1},  # Cleaning
    "B5": {"BODY": 1},  # Clothes
    # C: Arts and crafts
    "C1": {"DO": 1},  # Arts and crafts
    # E: Emotion
    "E1": {"FEEL": 1},  # General emotions
    "E2": {"FEEL": 1, "GOOD": 1},  # Liking
    "E3": {"FEEL": 1},  # Calm/violent/angry
    "E4": {"FEEL": 1},  # Happy/sad
    "E5": {"FEEL": 1},  # Fear/bravery
    "E6": {"FEEL": 1, "THINK": 1},  # Worry/concern/confident
    # F: Food and farming
    "F1": {"BODY": 1},  # Food
    "F2": {"BODY": 1},  # Drinks
    "F3": {"BODY": 1},  # Cigarettes and drugs
    "F4": {"ALIVE": 1},  # Farming
    # G: Government and public
    "G1": {"SOMEONE": 1, "PEOPLE": 1},  # Government
    "G2": {"SOMEONE": 1},  # Crime/law
    "G3": {"DO": 1},  # Warfare/defense
    # H: Architecture, housing, home
    "H1": {"WHERE": 1},  # Architecture/buildings
    "H2": {"WHERE": 1, "INSIDE": 1},  # Parts of buildings
    "H3": {"WHERE": 1},  # Areas around buildings
    "H4": {"WHERE": 1},  # Residence
    "H5": {"SOMETHING": 1},  # Furniture
    # I: Money and commerce
    "I1": {"HAVE": 1},  # Money/finance
    "I2": {"DO": 1},  # Business
    "I3": {"DO": 1},  # Work
    "I4": {"DO": 1},  # Industry
    # K: Entertainment, sports, games
    "K1": {"DO": 1},  # Entertainment
    "K2": {"DO": 1, "BODY": 1},  # Music/dancing
    "K3": {"DO": 1},  # Recorded sound
    "K4": {"DO": 1, "MOVE": 1},  # Drama/cinema
    "K5": {"DO": 1, "MOVE": 1, "BODY": 1},  # Sports
    "K6": {"DO": 1},  # Games
    # L: Life and living things
    "L1": {"ALIVE": 1},  # Life and living things
    "L2": {"ALIVE": 1, "BODY": 1},  # Living creatures
    "L3": {"ALIVE": 1},  # Plants
    # M: Movement, location, travel
    "M1": {"MOVE": 1},  # Moving/coming/going
    "M2": {"MOVE": 1},  # Putting/pulling/pushing
    "M3": {"MOVE": 1},  # Vehicles
    "M4": {"MOVE": 1},  # Swimming/diving
    "M5": {"MOVE": 1},  # Flying/landing
    "M6": {"WHERE": 1},  # Location
    "M7": {"WHERE": 1},  # Places
    "M8": {"MOVE": 1},  # Staying
    # N: Numbers and measurement
    "N1": {"ONE": 1},  # Numbers (QUANTITY primitives)
    "N2": {"QUANTITY": 1},  # Mathematics
    "N3": {"QUANTITY": 1},  # Measurement
    "N4": {"QUANTITY": 1},  # Linear order
    "N5": {"SOME": 1, "ALL": 1},  # Quantities
    "N6": {"MUCH": 1, "LITTLE": 1},  # Frequency
    # O: Substances, materials, objects
    "O1": {"SOMETHING": 1},  # Substances/materials
    "O2": {"SOMETHING": 1},  # Objects generally
    "O3": {"SOMETHING": 1},  # Electricity
    "O4": {"SOMETHING": 1, "BODY": 1},  # Physical attributes
    # P: Education
    "P1": {"KNOW": 1, "THINK": 1},  # Education
    # Q: Language and communication
    "Q1": {"SAY": 1, "WORDS": 1},  # Communication
    "Q2": {"SAY": 1, "WORDS": 1},  # Speech acts
    "Q3": {"SAY": 1},  # Telecommunications
    "Q4": {"WORDS": 1},  # Media
    # S: Social actions, states, processes
    "S1": {"SOMEONE": 1, "PEOPLE": 1},  # Social actions
    "S2": {"SOMEONE": 1, "PEOPLE": 1},  # People
    "S3": {"SOMEONE": 1, "PEOPLE": 1},  # Relationships
    "S4": {"ALIVE": 1},  # Kin
    "S5": {"PEOPLE": 1},  # Groups/affiliations
    "S6": {"MUST": 1},  # Obligations
    "S7": {"CAN": 1, "MUST": 1},  # Power/organizing
    "S8": {"FEEL": 1},  # Helping/hindering
    "S9": {"SOMEONE": 1},  # Religion
    # T: Time
    "T1": {"WHEN": 1},  # Time
    "T2": {"WHEN": 1, "START": 1},  # Beginning/ending
    "T3": {"WHEN": 1, "LONG_TIME": 1},  # Long time
    "T4": {"WHEN": 1, "SHORT_TIME": 1},  # Short time
    # W: World and environment
    "W1": {"WHERE": 1},  # World/universe
    "W2": {"WHERE": 1},  # Light
    "W3": {"WHERE": 1},  # Weather
    "W4": {"WHERE": 1, "SOMETHING": 1},  # Substances
    "W5": {"WHERE": 1},  # Green issues
    # X: Psychological actions, states, processes
    "X1": {"THINK": 1},  # Psychological actions/states
    "X2": {"THINK": 1},  # Mental actions
    "X3": {"FEEL": 1},  # Sensory
    "X4": {"THINK": 1},  # Mental object
    "X5": {"THINK": 1},  # Attention
    "X6": {"THINK": 1},  # Deciding
    "X7": {"WANT": 1},  # Wanting/needing
    "X8": {"THINK": 1},  # Trying
    "X9": {"CAN": 1},  # Ability
    # Y: Science and technology
    "Y1": {"THINK": 1, "KNOW": 1},  # Science/technology
    "Y2": {"THINK": 1, "KNOW": 1},  # IT and computing
    # Z: Names and grammatical words
    "Z0": {},  # Unmatched
    "Z1": {"SOMEONE": 1},  # Personal names
    "Z2": {"WHERE": 1},  # Place names
    "Z3": {},  # Other proper names
    "Z4": {},  # Discourse markers
    "Z5": {},  # Grammatical words
    "Z6": {},  # Negative
    "Z7": {"I": 1},  # If (conditional)
    "Z8": {"I": 1, "YOU": 1},  # Pronouns
    "Z9": {},  # Trash can
    "Z99": {},  # Unmatched
}

# Add +/- modifiers for evaluative tags
USAS_MODIFIERS = {
    "+": {"GOOD": 1},  # Positive evaluation
    "-": {"GOOD": -1},  # Negative evaluation
    "++": {"GOOD": 1, "INTENSITY": 1},
    "--": {"GOOD": -1, "INTENSITY": 1},
}


class USASParser(BaseExternalParser):
    """
    Parse USAS lexicon and map to GSE primitives.

    The USAS system provides semantic field tags for English words,
    which we map to GSE primitives for constraint aggregation.
    """

    def __init__(self, lexicon_path: Optional[Path] = None):
        super().__init__()
        self.config.name = "usas"
        self.lexicon_path = lexicon_path or DATA_DIR / "semantic_lexicon_en.tsv"
        self.entries: Dict[str, List[USASEntry]] = {}
        self._mwe_entries: Dict[str, List[USASEntry]] = {}

    def download(self) -> bool:
        """Download USAS lexicon from GitHub."""
        try:
            import requests
        except ImportError:
            logger.error("requests library required for download")
            return False

        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Download semantic lexicon
        single_url = "https://raw.githubusercontent.com/UCREL/Multilingual-USAS/master/English/semantic_lexicon_en.tsv"
        logger.info(f"Downloading USAS semantic lexicon from {single_url}...")

        try:
            response = requests.get(single_url, timeout=60)
            response.raise_for_status()

            single_path = DATA_DIR / "semantic_lexicon_en.tsv"
            with open(single_path, "wb") as f:
                f.write(response.content)

            logger.info(f"Downloaded {len(response.content):,} bytes to {single_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to download USAS lexicon: {e}")
            return False

    def load(self) -> bool:
        """Load USAS lexicon from TSV file."""
        if not self.lexicon_path.exists():
            logger.info(f"USAS lexicon not found at {self.lexicon_path}")
            logger.info("Attempting to download...")
            if not self.download():
                return False

        try:
            count = 0
            with open(self.lexicon_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    parts = line.split("\t")
                    if len(parts) < 2:
                        continue

                    # Format: lemma \t POS \t semantic_tags
                    # or: lemma \t semantic_tags
                    if len(parts) >= 3:
                        lemma, pos, tags_str = parts[0], parts[1], parts[2]
                    else:
                        lemma, tags_str = parts[0], parts[1]
                        pos = None

                    # Parse semantic tags (space-separated)
                    tags = tags_str.split()

                    entry = USASEntry(lemma=lemma.lower(), pos=pos, semantic_tags=tags)

                    self.entries.setdefault(lemma.lower(), []).append(entry)
                    count += 1

            logger.info(f"Loaded {count:,} USAS entries for {len(self.entries):,} unique words")
            self._loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load USAS lexicon: {e}")
            return False

    def _parse_tag(self, tag: str) -> Dict[str, int]:
        """
        Parse a USAS semantic tag and return GSE primitives.

        Tag format: <letter><number>[.<subcategory>][mfc][+-]*
        Examples: "M1" (movement), "E4.2+" (happy, positive), "S2mfc" (people, gender marked)
        """
        primitives = {}

        # Remove gender/number markers (m, f, c, n at end if followed by nothing or +-)
        clean_tag = tag.rstrip("+-")
        while clean_tag and clean_tag[-1] in "mfcn":
            clean_tag = clean_tag[:-1]

        # Extract modifiers (+ and - at end)
        modifier = ""
        for i in range(len(tag) - 1, -1, -1):
            if tag[i] in "+-":
                modifier = tag[i] + modifier
            else:
                break

        # Extract base category (letter + number, optionally with subcategory)
        # E.g., "M1", "E4", "A5.1", "X2.1"
        base_parts = clean_tag.split("/")  # Handle compound tags like "M1/N3.3"

        for part in base_parts:
            # Try progressively shorter matches
            # E4.2 → E4 → E
            test_cats = []
            if "." in part:
                main, sub = part.split(".", 1)
                test_cats = [part, main, main[0] if main else ""]
            else:
                # Remove trailing digits for letter+number categories
                main = part.rstrip("0123456789")
                if main != part:
                    test_cats = [part[: len(main) + 1], main[0] if main else ""]
                else:
                    test_cats = [part, part[0] if part else ""]

            for cat in test_cats:
                if cat in USAS_TO_GSE and USAS_TO_GSE[cat]:
                    primitives.update(USAS_TO_GSE[cat])
                    break

        # Apply modifiers
        if modifier:
            plus_count = modifier.count("+")
            minus_count = modifier.count("-")

            if plus_count > minus_count:
                primitives["GOOD"] = 1
                if plus_count > 1:
                    primitives["INTENSITY"] = 1
            elif minus_count > plus_count:
                primitives["GOOD"] = -1
                if minus_count > 1:
                    primitives["INTENSITY"] = 1

        return primitives

    def to_primitives(self, word: str) -> Dict[str, int]:
        """
        Map word to GSE primitives based on USAS semantic tags.

        Returns aggregated primitives from all matching entries.
        """
        if not self._loaded:
            if not self.load():
                return {}

        word = word.lower()

        if word not in self.entries:
            return {}

        # Aggregate primitives from all entries
        primitives: Dict[str, int] = {}
        tag_counts: Dict[str, int] = {}  # For majority voting

        for entry in self.entries[word]:
            for tag in entry.semantic_tags:
                tag_prims = self._parse_tag(tag)

                for prim, val in tag_prims.items():
                    key = f"{prim}:{val}"
                    tag_counts[key] = tag_counts.get(key, 0) + 1

        # Use majority voting for conflicts
        prim_votes: Dict[str, Dict[int, int]] = {}
        for key, count in tag_counts.items():
            prim, val = key.rsplit(":", 1)
            val = int(val)
            prim_votes.setdefault(prim, {})[val] = prim_votes.get(prim, {}).get(val, 0) + count

        for prim, votes in prim_votes.items():
            # Pick the value with most votes
            best_val = max(votes.items(), key=lambda x: x[1])[0]
            primitives[prim] = best_val

        return primitives

    def get_semantic_tags(self, word: str) -> List[str]:
        """Get raw USAS semantic tags for a word."""
        if not self._loaded:
            if not self.load():
                return []

        word = word.lower()
        if word not in self.entries:
            return []

        tags = []
        for entry in self.entries[word]:
            tags.extend(entry.semantic_tags)
        return list(set(tags))

    def get_category_name(self, tag: str) -> str:
        """Get human-readable name for a USAS category."""
        category_names = {
            "A": "General/Abstract",
            "B": "Body",
            "C": "Arts/Crafts",
            "E": "Emotion",
            "F": "Food/Farming",
            "G": "Government",
            "H": "Housing/Architecture",
            "I": "Money/Commerce",
            "K": "Entertainment/Sports",
            "L": "Life/Living",
            "M": "Movement/Location",
            "N": "Numbers/Measurement",
            "O": "Substances/Objects",
            "P": "Education",
            "Q": "Communication",
            "S": "Social",
            "T": "Time",
            "W": "World/Environment",
            "X": "Psychological",
            "Y": "Science/Technology",
            "Z": "Names/Grammar",
        }
        if tag and tag[0] in category_names:
            return category_names[tag[0]]
        return "Unknown"

    def get_all_words(self) -> List[str]:
        """Get all words in the lexicon."""
        if not self._loaded:
            if not self.load():
                return []
        return list(self.entries.keys())


# Convenience function
def download_usas():
    """Download USAS lexicon."""
    parser = USASParser()
    if parser.download():
        print("USAS lexicon downloaded successfully")
        if parser.load():
            print(f"Loaded {len(parser.entries):,} unique words")
    else:
        print("Failed to download USAS lexicon")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = USASParser()
    if parser.load():
        # Test some words
        test_words = ["run", "happy", "person", "building", "think", "money", "time"]
        for word in test_words:
            tags = parser.get_semantic_tags(word)
            prims = parser.to_primitives(word)
            print(f"\n{word}:")
            print(f"  Tags: {tags}")
            print(f"  Primitives: {prims}")
    else:
        print("USAS not available - attempting download...")
        download_usas()
