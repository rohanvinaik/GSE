"""
K-Line Pattern Storage (Minsky's Society of Mind).

A K-line records a successful primitive activation pattern. Given a partial
query pattern, matching K-lines vote on the missing primitives — enabling
pattern completion from partial activation.

This is the "agent-mind" layer of GSE: stored co-activations that complete
unknown words from their nearest known neighbours.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

import numpy as np

from gse.primitives_v2 import PrimitiveActivation

PatternPair = Tuple[str, int]  # (primitive_name, polarity)


@dataclass
class KLine:
    """
    A stored primitive activation pattern with usage statistics.

    Attributes:
        id: Unique identifier.
        pattern: Frozen set of (primitive, polarity) pairs.
        frequency: Number of corpus occurrences.
        strength: Reinforcement strength, updated on successful use.
    """

    id: str
    pattern: FrozenSet[PatternPair]
    frequency: int = 1
    strength: float = 1.0
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)

    def matches(self, query_pattern: Set[PatternPair]) -> float:
        """Jaccard overlap between this K-line and a query pattern, in [0, 1]."""
        if not self.pattern or not query_pattern:
            return 0.0
        intersection = len(self.pattern & query_pattern)
        union = len(self.pattern | query_pattern)
        return intersection / union if union > 0 else 0.0

    def get_missing(self, query_pattern: Set[PatternPair]) -> Set[PatternPair]:
        """Pattern pairs in this K-line that the query lacks."""
        return set(self.pattern - query_pattern)

    def reinforce(self, success: bool, amount: float = 0.1) -> None:
        """Reinforce on success; decay twice as fast on failure."""
        if success:
            self.strength = min(10.0, self.strength + amount)
        else:
            self.strength = max(0.01, self.strength - amount * 2)
        self.last_used = time.time()


class KLineStore:
    """
    Indexed K-line storage with pattern-completion inference.

    K-lines are indexed two ways:
    - by exact pattern hash (deduplication / reinforcement)
    - by individual primitive (candidate generation for queries)
    """

    def __init__(self, min_pattern_size: int = 2, max_patterns: int = 10_000):
        self.min_pattern_size = min_pattern_size
        self.max_patterns = max_patterns
        self._klines: Dict[str, KLine] = {}
        self._primitive_index: Dict[str, Set[str]] = defaultdict(set)
        self._pattern_hash_index: Dict[int, str] = {}

    @staticmethod
    def _pattern_hash(pattern: FrozenSet[PatternPair]) -> int:
        return hash(pattern)

    def __len__(self) -> int:
        return len(self._klines)

    def add_or_reinforce(self, pattern: Set[PatternPair]) -> Optional[KLine]:
        """Add a new K-line or reinforce an existing match. Returns the K-line."""
        if len(pattern) < self.min_pattern_size:
            return None

        frozen = frozenset(pattern)
        pattern_hash = self._pattern_hash(frozen)

        if pattern_hash in self._pattern_hash_index:
            existing = self._klines[self._pattern_hash_index[pattern_hash]]
            existing.frequency += 1
            existing.reinforce(success=True, amount=0.05)
            return existing

        kline_id = f"kl_{len(self._klines)}_{int(time.time() * 1000) % 100000}"
        kline = KLine(id=kline_id, pattern=frozen)
        self._klines[kline_id] = kline
        self._pattern_hash_index[pattern_hash] = kline_id
        for prim, _ in pattern:
            self._primitive_index[prim].add(kline_id)

        if len(self._klines) > self.max_patterns:
            self._evict_weakest()

        return kline

    def add_from_activations(
        self,
        activations: Iterable[PrimitiveActivation],
    ) -> Optional[KLine]:
        """Build a K-line pattern from a list of PrimitiveActivations."""
        pattern = {(a.primitive, int(a.polarity)) for a in activations}
        return self.add_or_reinforce(pattern)

    def _evict_weakest(self) -> None:
        """Remove the K-line minimizing strength × log1p(frequency)."""
        if not self._klines:
            return

        weakest_id = min(
            self._klines.keys(),
            key=lambda k: self._klines[k].strength * np.log1p(self._klines[k].frequency),
        )
        kline = self._klines[weakest_id]
        del self._pattern_hash_index[self._pattern_hash(kline.pattern)]
        for prim, _ in kline.pattern:
            self._primitive_index[prim].discard(weakest_id)
        del self._klines[weakest_id]

    def find_matching(
        self,
        query_pattern: Set[PatternPair],
        top_k: int = 5,
        min_overlap: float = 0.3,
    ) -> List[Tuple[KLine, float]]:
        """Return up to `top_k` K-lines with Jaccard overlap ≥ min_overlap."""
        if not query_pattern:
            return []

        candidates: Set[str] = set()
        for prim, _ in query_pattern:
            candidates.update(self._primitive_index.get(prim, set()))

        scored: List[Tuple[KLine, float]] = []
        for kline_id in candidates:
            kline = self._klines[kline_id]
            overlap = kline.matches(query_pattern)
            if overlap >= min_overlap:
                score = overlap * kline.strength * np.log1p(kline.frequency)
                scored.append((kline, score))

        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    def complete_pattern(
        self,
        partial_pattern: Set[PatternPair],
        min_confidence: float = 0.5,
        top_k: int = 10,
    ) -> List[Tuple[str, int, float]]:
        """Predict missing (primitive, polarity, confidence) pairs from partial input."""
        matches = self.find_matching(partial_pattern, top_k=top_k, min_overlap=0.3)
        if not matches:
            return []

        missing_scores: Dict[PatternPair, float] = defaultdict(float)
        for kline, score in matches:
            for prim_pol in kline.get_missing(partial_pattern):
                missing_scores[prim_pol] += score * kline.strength

        if not missing_scores:
            return []

        max_score = max(missing_scores.values())
        results = [
            (prim, pol, score / max_score)
            for (prim, pol), score in missing_scores.items()
            if score / max_score >= min_confidence
        ]
        results.sort(key=lambda x: -x[2])
        return results

    def save(self, path: str) -> None:
        """Serialize K-lines to JSON."""
        data = {
            "klines": [
                {
                    "id": kl.id,
                    "pattern": list(kl.pattern),
                    "frequency": kl.frequency,
                    "strength": kl.strength,
                }
                for kl in self._klines.values()
            ]
        }
        with open(path, "w") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, path: str) -> "KLineStore":
        """Load K-lines from JSON."""
        store = cls()
        with open(path) as f:
            data = json.load(f)

        for item in data["klines"]:
            pattern = frozenset(tuple(p) for p in item["pattern"])
            kline = KLine(
                id=item["id"],
                pattern=pattern,
                frequency=item["frequency"],
                strength=item["strength"],
            )
            store._klines[kline.id] = kline
            store._pattern_hash_index[store._pattern_hash(pattern)] = kline.id
            for prim, _ in pattern:
                store._primitive_index[prim].add(kline.id)

        return store
