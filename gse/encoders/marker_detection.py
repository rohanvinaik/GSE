"""
Marker detection strategies for the text and paragraph encoders.

The encoders historically embedded their keyword and regex tables as module-
or class-level constants. This module factors those out so the detection
strategy is swappable: a future spaCy- or K-line-driven detector only needs
to provide a ``detect(text) -> Dict[category, float]`` method.

Two detectors are provided:

* :class:`KeywordDetector` — substring matching with optional "avoid" lists
  that penalize the category when present. Reproduces the legacy text-encoder
  behavior for genre/register/domain and the paragraph-encoder behavior for
  coherence relations.
* :class:`RegexPatternDetector` — compiled regex matching, used for the
  Gestalt trigger patterns where prefix/anchor semantics matter.
"""

import re
from typing import Dict, Generic, Hashable, List, Optional, TypeVar

T = TypeVar("T", bound=Hashable)


class KeywordDetector(Generic[T]):
    """Substring-match detector with optional per-category avoid penalties."""

    def __init__(
        self,
        markers: Dict[T, List[str]],
        avoid: Optional[Dict[T, List[str]]] = None,
        avoid_penalty: float = 0.5,
    ):
        self.markers = markers
        self.avoid = avoid or {}
        self.avoid_penalty = avoid_penalty

    def detect(self, text: str) -> Dict[T, float]:
        """Return raw per-category scores. Caller is responsible for normalization."""
        lower = text.lower()
        scores: Dict[T, float] = {}
        for category, keywords in self.markers.items():
            score = 0.0
            for keyword in keywords:
                if keyword in lower:
                    score += 1.0
            for avoid_keyword in self.avoid.get(category, []):
                if avoid_keyword in lower:
                    score -= self.avoid_penalty
            scores[category] = max(0.0, score)
        return scores


class RegexPatternDetector(Generic[T]):
    """Regex-pattern detector that returns per-category match counts."""

    def __init__(self, patterns: Dict[T, List[str]]):
        self._compiled: Dict[T, List[re.Pattern]] = {
            category: [re.compile(p) for p in pats] for category, pats in patterns.items()
        }

    def detect(self, text: str) -> Dict[T, float]:
        """Return per-category match counts against the precompiled patterns."""
        lower = text.lower()
        scores: Dict[T, float] = {}
        for category, compiled in self._compiled.items():
            scores[category] = float(sum(1 for p in compiled if p.search(lower)))
        return scores

    def patterns_for(self, category: T) -> List[re.Pattern]:
        """Expose compiled patterns for a category (used by Gestalt detection)."""
        return self._compiled.get(category, [])
