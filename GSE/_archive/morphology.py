"""
Morphological analysis for GSE.

Handles:
- Prefix/suffix decomposition (un-, re-, -ness, -ful, etc.)
- Intensity marker detection
- Aspect inference from morphology
"""

from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import re

from gse.primitives import PREFIXES, SUFFIXES, INTENSITY_MARKERS, ASPECT_TYPES


@dataclass
class MorphologicalAnalysis:
    """Result of morphological analysis."""
    base_form: str                          # The root/stem
    prefixes: List[str]                     # Detected prefixes
    suffixes: List[str]                     # Detected suffixes
    semantic_additions: List[Tuple[str, str]]  # Additional primitive-role pairs
    intensity_level: str                    # "extreme_high", "high", "moderate", "low", "minimal"
    aspect: Optional[str]                   # "completed", "ongoing", etc.


class MorphologicalAnalyzer:
    """
    Analyze word morphology to extract semantic contributions.

    This enables compositional meaning construction from affixes:
    - "unhappy" = "happy" + NOT(state)
    - "teacher" = "teach" + SOMEONE(agent)
    - "readable" = "read" + CAN(possibility)
    """

    def __init__(self):
        # Sort prefixes by length (longest first) for greedy matching
        self.prefixes = sorted(PREFIXES.keys(), key=len, reverse=True)
        self.suffixes = sorted(SUFFIXES.keys(), key=len, reverse=True)

        # Compile intensity patterns
        self.intensity_patterns = {
            word: level for word, level in INTENSITY_MARKERS.items()
        }

    def analyze(self, word: str, pos: str = None) -> MorphologicalAnalysis:
        """
        Analyze a word's morphological structure.

        Args:
            word: The word to analyze
            pos: Part of speech (helps disambiguate)

        Returns:
            MorphologicalAnalysis with decomposed structure
        """
        word_lower = word.lower()
        detected_prefixes = []
        detected_suffixes = []
        semantic_additions = []
        base = word_lower

        # Detect prefixes (can be multiple: re-un-do)
        changed = True
        while changed:
            changed = False
            for prefix in self.prefixes:
                prefix_clean = prefix.rstrip('-')
                if base.startswith(prefix_clean) and len(base) > len(prefix_clean) + 2:
                    detected_prefixes.append(prefix)
                    base = base[len(prefix_clean):]
                    # Add semantic contribution
                    if prefix in PREFIXES:
                        for prim, role in PREFIXES[prefix]:
                            if prim in ["AGAIN"]:  # Skip non-standard primitives
                                continue
                            semantic_additions.append((prim, role))
                    changed = True
                    break

        # Detect suffixes
        changed = True
        while changed:
            changed = False
            for suffix in self.suffixes:
                suffix_clean = suffix.lstrip('-')
                if base.endswith(suffix_clean) and len(base) > len(suffix_clean) + 2:
                    detected_suffixes.append(suffix)
                    base = base[:-len(suffix_clean)]
                    # Handle suffix semantic contributions
                    suffix_type = SUFFIXES.get(suffix)
                    if suffix_type == "agent":
                        semantic_additions.append(("SOMEONE", "agent"))
                    elif suffix_type == "patient":
                        semantic_additions.append(("SOMEONE", "patient"))
                    elif suffix_type == "possibility":
                        semantic_additions.append(("CAN", "state"))
                    elif suffix_type == "having":
                        semantic_additions.append(("HAVE", "state"))
                    elif suffix_type == "lacking":
                        semantic_additions.append(("NOT", "state"))
                        semantic_additions.append(("HAVE", "state"))
                    elif suffix_type == "causative":
                        semantic_additions.append(("DO", "action"))
                        semantic_additions.append(("SOMETHING", "result"))
                    changed = True
                    break

        # Detect intensity from word itself
        intensity_level = "moderate"
        if word_lower in self.intensity_patterns:
            intensity_level = self.intensity_patterns[word_lower]

        # Infer aspect from morphology
        aspect = self._infer_aspect(word_lower, pos)

        return MorphologicalAnalysis(
            base_form=base,
            prefixes=detected_prefixes,
            suffixes=detected_suffixes,
            semantic_additions=semantic_additions,
            intensity_level=intensity_level,
            aspect=aspect
        )

    def _infer_aspect(self, word: str, pos: str = None) -> Optional[str]:
        """Infer grammatical aspect from word form."""
        # Progressive/imperfective
        if word.endswith('ing'):
            return "ongoing"

        # Past participle often indicates perfective
        if word.endswith('ed') or word.endswith('en'):
            return "completed"

        # Inchoative markers
        inchoative_patterns = ['start', 'begin', 'commence']
        if any(word.startswith(p) for p in inchoative_patterns):
            return "beginning"

        # Cessative markers
        cessative_patterns = ['stop', 'cease', 'finish', 'end']
        if any(word.startswith(p) for p in cessative_patterns):
            return "ending"

        return None

    def get_intensity_modifier(self, word: str) -> Tuple[str, float]:
        """
        Get intensity level and numeric modifier for a word.

        Returns:
            (level_name, multiplier)
        """
        from gse.primitives import INTENSITY_LEVELS

        word_lower = word.lower()
        if word_lower in self.intensity_patterns:
            level = self.intensity_patterns[word_lower]
            return level, INTENSITY_LEVELS.get(level, 1.0)
        return "moderate", 1.0

    def decompose_with_morphology(
        self,
        base_decomposition: List[Tuple[str, str]],
        word: str,
        pos: str = None
    ) -> List[Tuple[str, str]]:
        """
        Enhance a base decomposition with morphological contributions.

        Args:
            base_decomposition: Original primitive-role pairs for base word
            word: The actual word form
            pos: Part of speech

        Returns:
            Enhanced decomposition including morphological semantics
        """
        analysis = self.analyze(word, pos)

        # Start with morphological additions (prefixes first for scope)
        result = list(analysis.semantic_additions)

        # Add base decomposition
        result.extend(base_decomposition)

        # Add aspect if detected
        if analysis.aspect:
            aspect_primitives = {
                "ongoing": [("NOW", "time")],
                "completed": [("BEFORE", "time")],
                "beginning": [("NOW", "time"), ("AFTER", "aspect")],
                "ending": [("NOW", "time"), ("BEFORE", "aspect")],
                "repeated": [("MUCH", "frequency")],
            }
            if analysis.aspect in aspect_primitives:
                result.extend(aspect_primitives[analysis.aspect])

        return result


# Singleton instance
_analyzer = None

def get_morphological_analyzer() -> MorphologicalAnalyzer:
    """Get or create the morphological analyzer singleton."""
    global _analyzer
    if _analyzer is None:
        _analyzer = MorphologicalAnalyzer()
    return _analyzer
