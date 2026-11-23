"""
Graded Antonymy for GSE.

Implements graded opposition between words, moving beyond binary antonyms:
- "hot" vs "cold" = full opposition (-1.0)
- "hot" vs "cool" = partial opposition (-0.5)
- "hot" vs "warm" = slight contrast (-0.2)
- "warm" vs "lukewarm" = near synonymy (0.8)

Uses the Hadamard-OTP bank structure to encode opposition degrees.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np

from gse.vectors import SparseVector, bind, bundle, D, DIMS_PER_BANK, SemanticBank


@dataclass
class AntonymScale:
    """A graded scale of related terms from one pole to another."""
    name: str                          # e.g., "temperature"
    positive_pole: str                 # e.g., "hot"
    negative_pole: str                 # e.g., "cold"
    terms: List[Tuple[str, float]]     # (term, position) where position is -1 to +1
    dimension_bank: SemanticBank       # Which bank encodes this scale


# Graded antonym scales
ANTONYM_SCALES = [
    AntonymScale(
        name="temperature",
        positive_pole="hot",
        negative_pole="cold",
        terms=[
            ("freezing", -1.0),
            ("cold", -0.8),
            ("cool", -0.4),
            ("lukewarm", 0.0),
            ("warm", 0.4),
            ("hot", 0.8),
            ("scalding", 1.0),
        ],
        dimension_bank=SemanticBank.EVALUATORS
    ),
    AntonymScale(
        name="size",
        positive_pole="big",
        negative_pole="small",
        terms=[
            ("tiny", -1.0),
            ("small", -0.7),
            ("little", -0.5),
            ("medium", 0.0),
            ("large", 0.5),
            ("big", 0.7),
            ("huge", 0.9),
            ("enormous", 1.0),
        ],
        dimension_bank=SemanticBank.EVALUATORS
    ),
    AntonymScale(
        name="quality",
        positive_pole="good",
        negative_pole="bad",
        terms=[
            ("terrible", -1.0),
            ("bad", -0.7),
            ("poor", -0.4),
            ("mediocre", -0.1),
            ("okay", 0.1),
            ("decent", 0.3),
            ("good", 0.6),
            ("great", 0.8),
            ("excellent", 1.0),
        ],
        dimension_bank=SemanticBank.EVALUATORS
    ),
    AntonymScale(
        name="speed",
        positive_pole="fast",
        negative_pole="slow",
        terms=[
            ("stationary", -1.0),
            ("slow", -0.7),
            ("leisurely", -0.3),
            ("moderate", 0.0),
            ("quick", 0.4),
            ("fast", 0.7),
            ("rapid", 0.9),
            ("instant", 1.0),
        ],
        dimension_bank=SemanticBank.EVALUATORS
    ),
    AntonymScale(
        name="age",
        positive_pole="old",
        negative_pole="young",
        terms=[
            ("newborn", -1.0),
            ("young", -0.7),
            ("youthful", -0.4),
            ("middle-aged", 0.0),
            ("mature", 0.3),
            ("old", 0.7),
            ("elderly", 0.9),
            ("ancient", 1.0),
        ],
        dimension_bank=SemanticBank.TEMPORAL
    ),
    AntonymScale(
        name="height",
        positive_pole="tall",
        negative_pole="short",
        terms=[
            ("tiny", -1.0),
            ("short", -0.6),
            ("average", 0.0),
            ("tall", 0.6),
            ("towering", 1.0),
        ],
        dimension_bank=SemanticBank.SPATIAL
    ),
    AntonymScale(
        name="weight",
        positive_pole="heavy",
        negative_pole="light",
        terms=[
            ("weightless", -1.0),
            ("light", -0.6),
            ("average", 0.0),
            ("heavy", 0.6),
            ("massive", 1.0),
        ],
        dimension_bank=SemanticBank.EVALUATORS
    ),
    AntonymScale(
        name="emotion",
        positive_pole="happy",
        negative_pole="sad",
        terms=[
            ("devastated", -1.0),
            ("sad", -0.7),
            ("unhappy", -0.4),
            ("neutral", 0.0),
            ("content", 0.3),
            ("happy", 0.6),
            ("joyful", 0.8),
            ("ecstatic", 1.0),
        ],
        dimension_bank=SemanticBank.MENTAL
    ),
    AntonymScale(
        name="certainty",
        positive_pole="certain",
        negative_pole="uncertain",
        terms=[
            ("impossible", -1.0),
            ("unlikely", -0.6),
            ("uncertain", -0.3),
            ("possible", 0.0),
            ("probable", 0.4),
            ("likely", 0.6),
            ("certain", 0.9),
            ("inevitable", 1.0),
        ],
        dimension_bank=SemanticBank.LOGICAL
    ),
    AntonymScale(
        name="quantity",
        positive_pole="much",
        negative_pole="little",
        terms=[
            ("none", -1.0),
            ("little", -0.6),
            ("few", -0.4),
            ("some", 0.0),
            ("several", 0.3),
            ("many", 0.6),
            ("much", 0.7),
            ("abundant", 1.0),
        ],
        dimension_bank=SemanticBank.DETERMINERS
    ),
]


class GradedAntonymyHandler:
    """
    Handle graded antonymy relationships.

    Computes expected similarity between words on antonym scales:
    - Words at opposite poles → negative similarity
    - Words near each other on scale → positive similarity
    - Words in middle → near-zero similarity with poles
    """

    def __init__(self):
        # Build lookup tables
        self.word_to_scale: Dict[str, AntonymScale] = {}
        self.word_to_position: Dict[str, float] = {}

        for scale in ANTONYM_SCALES:
            for term, position in scale.terms:
                self.word_to_scale[term] = scale
                self.word_to_position[term] = position

    def get_scale(self, word: str) -> Optional[AntonymScale]:
        """Get the antonym scale a word belongs to, if any."""
        return self.word_to_scale.get(word.lower())

    def get_position(self, word: str) -> Optional[float]:
        """Get a word's position on its antonym scale (-1 to +1)."""
        return self.word_to_position.get(word.lower())

    def compute_graded_similarity(self, word1: str, word2: str) -> Optional[float]:
        """
        Compute expected similarity based on graded antonymy.

        Returns:
            Similarity in [-1, 1] if both words are on same scale,
            None if they're on different scales or not on any scale.
        """
        word1_lower = word1.lower()
        word2_lower = word2.lower()

        scale1 = self.word_to_scale.get(word1_lower)
        scale2 = self.word_to_scale.get(word2_lower)

        if scale1 is None or scale2 is None:
            return None

        if scale1.name != scale2.name:
            return None  # Different scales, can't compare

        pos1 = self.word_to_position[word1_lower]
        pos2 = self.word_to_position[word2_lower]

        # Compute similarity based on distance on scale
        # Same position → 1.0
        # Opposite poles → -1.0
        distance = abs(pos1 - pos2)
        max_distance = 2.0  # From -1 to +1

        # Linear mapping: distance 0 → 1.0, distance 2 → -1.0
        similarity = 1.0 - distance

        return similarity

    def get_antonym_degree(self, word1: str, word2: str) -> Tuple[str, float]:
        """
        Classify the degree of antonymy between two words.

        Returns:
            (category, strength) where category is one of:
            - "full_antonym": opposite poles
            - "partial_antonym": far apart on scale
            - "contrast": moderately different
            - "similar": close on scale
            - "synonym": very close or same position
            - "unrelated": not on same scale
        """
        sim = self.compute_graded_similarity(word1, word2)

        if sim is None:
            return "unrelated", 0.0

        if sim <= -0.7:
            return "full_antonym", abs(sim)
        elif sim <= -0.3:
            return "partial_antonym", abs(sim)
        elif sim <= 0.0:
            return "contrast", abs(sim)
        elif sim <= 0.5:
            return "similar", sim
        else:
            return "synonym", sim

    def adjust_decomposition_for_position(
        self,
        base_decomposition: List[Tuple[str, str]],
        word: str
    ) -> List[Tuple[str, str]]:
        """
        Adjust a word's decomposition based on its position on an antonym scale.

        Words at extreme positions get intensity modifiers:
        - "freezing" gets (VERY, intensity) added
        - "lukewarm" might get (LITTLE, intensity) to indicate moderate

        Args:
            base_decomposition: The basic primitive-role decomposition
            word: The word being decomposed

        Returns:
            Enhanced decomposition with intensity modifiers
        """
        position = self.get_position(word)
        if position is None:
            return base_decomposition

        result = list(base_decomposition)

        # Add intensity based on distance from center
        abs_position = abs(position)

        if abs_position > 0.9:
            # Extreme: add VERY
            result.append(("VERY", "intensity"))
        elif abs_position > 0.7:
            # Strong: add MORE
            result.append(("MORE", "intensity"))
        elif abs_position < 0.2:
            # Neutral/middle: add LITTLE to indicate weak
            result.append(("LITTLE", "intensity"))

        return result

    def get_scale_terms(self, scale_name: str) -> Optional[List[Tuple[str, float]]]:
        """Get all terms on a named scale."""
        for scale in ANTONYM_SCALES:
            if scale.name == scale_name:
                return scale.terms
        return None

    def find_nearest_on_scale(
        self,
        word: str,
        target_position: float
    ) -> Optional[str]:
        """
        Find the term nearest to a target position on the same scale as word.

        Useful for generating paraphrases or finding moderate alternatives.
        """
        scale = self.get_scale(word)
        if scale is None:
            return None

        nearest = None
        nearest_dist = float('inf')

        for term, pos in scale.terms:
            dist = abs(pos - target_position)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = term

        return nearest


# Singleton instance
_handler = None


def get_antonymy_handler() -> GradedAntonymyHandler:
    """Get or create the graded antonymy handler singleton."""
    global _handler
    if _handler is None:
        _handler = GradedAntonymyHandler()
    return _handler
