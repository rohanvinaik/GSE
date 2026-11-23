"""
Base Parser Abstract Class

Defines the common interface for all external source parsers.
All parsers must implement: load(), to_primitives(), get_all_words()
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ParserConfig:
    """Configuration for external source parsers."""

    name: str
    data_path: Optional[Path] = None
    lazy_load: bool = True  # Load on first access
    cache_size: int = 10000  # LRU cache entries
    memory_limit_mb: int = 500  # Max memory per parser


class BaseExternalParser(ABC):
    """
    Abstract base class for all external source parsers.

    Contract:
    - load() -> bool: Initialize data source
    - to_primitives(word) -> Dict[str, int]: Map word to GSE primitives
    - get_all_words() -> List[str]: Get vocabulary
    - get_metadata() -> Dict: Return source metadata
    """

    def __init__(self, config: Optional[ParserConfig] = None):
        self.config = config or ParserConfig(name=self.__class__.__name__)
        self.entries: Dict = {}
        self._loaded = False
        self._memory_usage = 0

    @abstractmethod
    def load(self) -> bool:
        """
        Load and initialize the data source.

        Returns:
            True if loading succeeded, False otherwise
        """
        pass

    @abstractmethod
    def to_primitives(self, word: str) -> Dict[str, int]:
        """
        Map a word to GSE primitive values.

        Args:
            word: The word to look up

        Returns:
            Dict mapping primitive names to values (+1, -1, or 0)
        """
        pass

    @abstractmethod
    def get_all_words(self) -> List[str]:
        """Return all words in the vocabulary."""
        pass

    def to_primitives_with_confidence(self, word: str) -> Dict[str, "tuple"]:  # noqa: F821 — runtime type, see comment
        """
        Map a word to ``{primitive: (value, confidence)}``.

        Default implementation wraps :meth:`to_primitives` with a uniform
        confidence of ``1.0`` per vote. Parsers that have per-vote
        confidence in their source data (e.g., the Wiktionary v2 DB which
        stores a confidence column per word-primitive pair) should
        override this method to return the genuine confidence rather than
        ``1.0``. The integrator's weighted-voting code prefers this
        method when present.
        """
        return {prim: (val, 1.0) for prim, val in self.to_primitives(word).items()}

    def get_metadata(self) -> Dict:
        """Return source metadata for provenance tracking."""
        return {
            "name": self.config.name,
            "loaded": self._loaded,
            "entry_count": len(self.entries),
            "memory_mb": self._memory_usage / (1024 * 1024) if self._memory_usage else 0,
        }

    def get_new_words(self, existing_words: Set[str]) -> List[str]:
        """Get words not in existing set."""
        if not self._loaded:
            self.load()
        return [w for w in self.get_all_words() if w not in existing_words]

    def has_word(self, word: str) -> bool:
        """Check if word exists in this source."""
        if not self._loaded:
            self.load()
        return word.lower() in self.entries

    def close(self):
        """Release resources."""
        self.entries.clear()
        self._loaded = False

    def __enter__(self):
        """Context manager entry."""
        self.load()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
